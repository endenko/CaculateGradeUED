# -*- coding: utf-8 -*-
"""
🌸 UED Calculate Grade — Docker-ready Flask server
====================================================
Ported from LocalOCR.py (original repo) with these changes:
  * No hardcoded Windows paths (tesseract path, Google key.json) — all env-driven
  * Database: SQL Server/pyodbc -> SQLite (db.py), same danh_muc_mon schema
  * Handwriting OCR: Google Cloud Vision -> Vietnamese OCR (PaddleOCR lang='vi'),
    with Tesseract (vie+eng) kept for computer-screenshot mode
  * Google Vision remains available as an OPTIONAL engine (OCR_HANDWRITING_ENGINE=google
    + GOOGLE_APPLICATION_CREDENTIALS + requirements-google.txt)

Original parsing logic (regex, fuzzy matching, grade conversion) is unchanged.
"""
import os
import re
from difflib import SequenceMatcher

from flask import Flask, render_template, request, jsonify
from werkzeug.utils import secure_filename

import db
from ocr import engines
from utils import no_accent_vietnamese

app = Flask(__name__)

# --- CẤU HÌNH (từ biến môi trường, không còn đường dẫn Windows cứng) ---
UPLOAD_FOLDER = os.environ.get('UPLOAD_FOLDER', 'uploads')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 32 * 1024 * 1024  # 32MB


# ========================================================
# 👁️ LÕI THỊ GIÁC HYBRID (Tesseract + Vietnamese OCR)
# ========================================================
def _x_overlap(group_a, group_b):
    """True if two word-groups share any horizontal extent (same table columns)."""
    a1 = min(w['x'] for w in group_a)
    a2 = max(w['x'] for w in group_a)
    b1 = min(w['x'] for w in group_b)
    b2 = max(w['x'] for w in group_b)
    return not (a2 < b1 or b2 < a1)


def _x_separated(group, word, min_gap=150):
    """True if `word` sits clearly to the left/right of the group (different
    table columns) — used to merge same-row column splits without merging
    stacked rows (which share x positions)."""
    g_min = min(w['x'] for w in group)
    g_max = max(w['x'] for w in group)
    if word['x'] < g_min:
        return (g_min - word['x']) >= min_gap
    if word['x'] > g_max:
        return (word['x'] - g_max) >= min_gap
    return False


def reconstruct_lines(word_list, mode):
    """Group words into lines by Y. Handwriting OCR boxes within one row can be
    vertically offset (subject column vs grade column), so side-by-side groups
    (clearly separated X positions) within a moderate Y gap are merged back."""
    if not word_list:
        return []
    word_list.sort(key=lambda k: k['y'])
    y_tolerance = 15 if mode == 'computer' else 40
    merge_gap = y_tolerance * 3
    lines = []
    current_line = []
    current_y = -100
    last_y = -100
    for w in word_list:
        if abs(w['y'] - current_y) > y_tolerance:
            if (current_line and abs(w['y'] - last_y) <= merge_gap
                    and _x_separated(current_line, w)):
                # same visual row, side-by-side columns with vertical offset -> merge
                current_line.append(w)
                last_y = w['y']
                continue
            if current_line:
                current_line.sort(key=lambda k: k['x'])
                lines.append(" ".join([item['text'] for item in current_line]))
            current_line = [w]
            current_y = w['y']
            last_y = w['y']
        else:
            current_line.append(w)
            last_y = w['y']
    if current_line:
        current_line.sort(key=lambda k: k['x'])
        lines.append(" ".join([item['text'] for item in current_line]))
    return lines


# ========================================================
# 🛡️ TRUNG TÂM SỬA TÊN & LẤY TÍN CHỈ CỨU HỘ
# ========================================================
def quy_doi_chuan(diem_so):
    try:
        clean = re.sub(r"[^\d,\.]", "", str(diem_so))
        d = float(clean.replace(',', '.'))
        if d >= 9.0: return 'A+'
        if d >= 8.5: return 'A'
        if d >= 8.0: return 'B+'
        if d >= 7.0: return 'B'
        if d >= 6.5: return 'C+'
        if d >= 5.5: return 'C'
        if d >= 5.0: return 'D+'
        if d >= 4.0: return 'D'
        return 'F'
    except Exception:
        return 'F'


def auto_correct_universal(raw_name, mode):
    """Fuzzy-match the OCR'd subject name against danh_muc_mon (SQLite now)."""
    try:
        db_subjects = db.all_subjects()
        best_match = raw_name
        highest_ratio = 0.0
        best_credit = 3

        raw_lower = raw_name.lower()
        if 'c++' in raw_lower or 'cet' in raw_lower or 'ctt' in raw_lower or 'c t' in raw_lower:
            return "Lập trình C++", "100%", 3

        raw_no_accent = no_accent_vietnamese(raw_name).lower()
        clean_raw = re.sub(r'www\.\S+', '', raw_no_accent)
        clean_raw = re.sub(r'[^\w\s\+#]', '', clean_raw).strip()

        for row in db_subjects:
            subject = row['ten_mon']
            db_credit = row['tin_chi']

            sub_no_accent = no_accent_vietnamese(subject).lower()
            clean_sub = re.sub(r'[^\w\s\+#]', '', sub_no_accent)

            ratio = SequenceMatcher(None, clean_raw, clean_sub).ratio()
            if ratio > highest_ratio:
                highest_ratio = ratio
                best_match = subject
                best_credit = db_credit

        similarity_string = f"{int(highest_ratio * 100)}%"

        threshold = 0.60 if mode == 'computer' else 0.20
        if highest_ratio >= threshold:
            return best_match, similarity_string, best_credit
        else:
            return raw_name, similarity_string, best_credit
    except Exception as e:
        print("Lỗi SQL:", e)
        return raw_name, "0%", 3


# ========================================================
# 💻 PARSER MÁY TÍNH
# ========================================================
def parse_computer(lines):
    results = []
    pat_A = re.compile(r"(.+?)\s+(\d{2}[-.\s]\d{4})\s*(\d)\b")
    pat_B = re.compile(r"(.+?)\s+(\d)\s+(\d+[\.,]\d+)")

    for line in lines:
        match = None
        mode = "A"
        match = pat_A.search(line)
        if not match:
            mode = "B"
            match = pat_B.search(line)

        if match:
            raw_name = match.group(1).strip()
            tin_chi_ocr = match.group(3) if mode == "A" else match.group(2)
            end_pos = match.end()

            raw_name = re.sub(r'^\d+\s+\d{5,10}\s+', '', raw_name)
            raw_name = re.sub(r'^\d{5,10}\s+', '', raw_name)
            raw_name = re.sub(r'^\d+\s+', '', raw_name).strip()

            name_check = no_accent_vietnamese(raw_name).lower()
            blacklist = ["trung binh", "tich luy", "ren luyen", "tong so", "he 10", "he 4",
                         "giao duc the chat", "quoc phong"]
            if any(kw in name_check for kw in blacklist):
                continue

            phan_duoi = line[end_pos:]
            diem_10_float = -1.0
            match_diem_so = re.findall(r"(\d+[\.,]\d+)", phan_duoi)
            if match_diem_so:
                try:
                    diem_10_float = float(match_diem_so[-1].replace(',', '.'))
                except Exception:
                    pass

            match_diem_chu = re.search(r"([A-DF]\s*\+?|F)(?=\s|$|\*|\d)", phan_duoi, re.IGNORECASE)
            diem_chu_ocr = match_diem_chu.group(1).upper().replace(" ", "") if match_diem_chu else 'F'

            if diem_10_float != -1.0:
                diem_chuan = quy_doi_chuan(diem_10_float)
                if diem_chuan[0] != diem_chu_ocr[0]:
                    diem_chu = diem_chuan
                elif len(diem_chuan) > len(diem_chu_ocr):
                    diem_chu = diem_chuan
                else:
                    diem_chu = diem_chu_ocr
            else:
                diem_chu = diem_chu_ocr

            ten_mon_chuan, similarity_pct, db_credit = auto_correct_universal(raw_name, 'computer')
            if len(ten_mon_chuan) < 2:
                continue

            results.append({
                "raw_name": raw_name,
                "ten_mon": ten_mon_chuan,
                "percentage": similarity_pct,
                "tin_chi": int(tin_chi_ocr),
                "diem_he_4": diem_chu
            })
    return results


# ========================================================
# ✍️ PARSER VIẾT TAY (CHỐNG LƯỜI V38)
# ========================================================
def parse_handwriting(lines):
    results = []
    pattern = re.compile(r"(.+?)\s+(?:(\d)\s+)?(\d{1,2}(?:[\.,]\d+)?)(.*)")

    for line in lines:
        line = line.strip()
        match = pattern.search(line)
        if match:
            raw_name_ocr = match.group(1).strip()
            tin_chi_ocr = match.group(2)
            diem_10_str = match.group(3)
            phan_duoi = match.group(4) or ""

            diem_chu_ocr = None
            match_chu = re.search(r"([A-DF])\s*([\+\-tTyY\*\d]?)", phan_duoi, re.IGNORECASE)
            if match_chu:
                chu_cai = match_chu.group(1).upper()
                dau_kem_theo = match_chu.group(2).upper()
                # 't/y/*' AND digits are almost always a misread '+' in handwriting (e.g. C4 = C+)
                if dau_kem_theo in ['T', 'Y', '*'] or dau_kem_theo.isdigit():
                    dau_kem_theo = '+'
                diem_chu_ocr = chu_cai + dau_kem_theo

            ten_mon_chuan, similarity_pct, db_credit = auto_correct_universal(raw_name_ocr, 'handwriting')

            final_tin_chi = int(tin_chi_ocr) if tin_chi_ocr is not None else db_credit

            if diem_chu_ocr:
                final_diem_he_4 = diem_chu_ocr
            else:
                try:
                    diem_10 = float(diem_10_str.replace(',', '.'))
                except Exception:
                    diem_10 = 0.0
                final_diem_he_4 = quy_doi_chuan(diem_10)

            if len(ten_mon_chuan) < 2:
                continue

            results.append({
                "raw_name": raw_name_ocr,
                "ten_mon": ten_mon_chuan,
                "percentage": similarity_pct,
                "tin_chi": final_tin_chi,
                "diem_he_4": final_diem_he_4
            })
    return results


# ========================================================
# 🚀 API ENDPOINTS
# ========================================================
@app.route('/')
def home():
    return render_template('index.html')


@app.route('/health')
def health():
    return jsonify({"success": True, "status": "ok"})


@app.route('/api/search_subject', methods=['GET'])
def search_subject():
    query = request.args.get('q', '')
    if not query:
        return jsonify([])
    return jsonify(db.search_subjects(query))


@app.route('/api/process_ocr', methods=['POST'])
def process_ocr():
    if 'file_anh' not in request.files:
        return jsonify({"success": False, "error": "Chưa chọn file"})
    file = request.files['file_anh']
    mode = request.form.get('mode', 'computer')

    if file:
        filename = secure_filename(file.filename)
        path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(path)
        try:
            if mode == 'handwriting':
                word_list, engine = engines.handwriting_words(path)
                lines = reconstruct_lines(word_list, mode)
                extracted_data = parse_handwriting(lines)
            else:
                word_list = engines.computer_words(path)
                lines = reconstruct_lines(word_list, mode)
                extracted_data = parse_computer(lines)
                engine = 'tesseract'

            return jsonify({"success": True, "data": extracted_data, "engine": engine})
        except Exception as e:
            return jsonify({"success": False, "error": str(e)})
    return jsonify({"success": False, "error": "File không hợp lệ"})


@app.route('/api/scan_detail_score', methods=['POST'])
def scan_detail_score():
    if 'file_anh' not in request.files:
        return jsonify({"success": False, "error": "Chưa chọn file"})
    file = request.files['file_anh']
    if file:
        filename = secure_filename(file.filename)
        path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(path)
        try:
            text = engines.tesseract_full_text(path)

            bp_match = re.search(r'bộ phận[^\d]*(\d+[\.,]\d+)', text, re.IGNORECASE)
            gk_match = re.search(r'giữa kỳ[^\d]*(\d+[\.,]\d+)', text, re.IGNORECASE)

            bp = float(bp_match.group(1).replace(',', '.')) if bp_match else None
            gk = float(gk_match.group(1).replace(',', '.')) if gk_match else None

            if bp is None and gk is None:
                return jsonify({"success": False, "error": "Không tìm thấy Điểm Bộ Phận hay Giữa Kỳ!"})

            return jsonify({"success": True, "bp": bp, "gk": gk})
        except Exception as e:
            return jsonify({"success": False, "error": str(e)})
    return jsonify({"success": False, "error": "File không hợp lệ"})


if __name__ == '__main__':
    db.init_db()
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
