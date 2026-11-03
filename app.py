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
from rapidfuzz import fuzz, process

from flask import Flask, render_template, request, jsonify
from werkzeug.utils import secure_filename

import db
from ocr import engines
from utils import no_accent_vietnamese, normalize

app = Flask(__name__)

# --- CẤU HÌNH (từ biến môi trường, không còn đường dẫn Windows cứng) ---
UPLOAD_FOLDER = os.environ.get('UPLOAD_FOLDER', '/tmp/uploads' if os.environ.get('VERCEL') else 'uploads')
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


def reconstruct_lines_anchor(word_list):
    """Handwriting rows: anchor each row on its left-most text (subject name) and
    attach every other token (credits / grade columns) to the anchor with the
    nearest skew-corrected Y. Robust to tilted photos where the right columns
    drift up/down relative to the names."""
    if not word_list:
        return []
    xs = sorted(w['x'] for w in word_list)
    x_min, x_max = xs[0], xs[-1]
    split = x_min + 0.35 * (x_max - x_min)
    anchors = sorted([w for w in word_list if w['x'] <= split and re.search(r'[^\W\d_]{2,}', w['text'])],
                     key=lambda w: w['y'])
    if len(anchors) < 2:
        return None
    # estimate skew: median slope between each right token and its naive-nearest anchor
    import statistics
    slopes = []
    for w in word_list:
        if w['x'] > split:
            a = min(anchors, key=lambda a: abs(a['y'] - w['y']))
            if w['x'] - a['x'] > 50:
                slopes.append((w['y'] - a['y']) / (w['x'] - a['x']))
    slope = statistics.median(slopes) if slopes else 0.0
    if abs(slope) > 0.15:
        slope = 0.0
    rows = {id(a): [a] for a in anchors}
    for w in word_list:
        if any(w is a for a in anchors):
            continue
        a = min(anchors, key=lambda a: abs(w['y'] - (a['y'] + slope * (w['x'] - a['x']))))
        rows[id(a)].append(w)
    lines = []
    for a in anchors:
        row = sorted(rows[id(a)], key=lambda k: k['x'])
        lines.append(" ".join(item['text'] for item in row))
    return lines


def reconstruct_lines(word_list, mode):
    if mode == 'handwriting':
        anchored = reconstruct_lines_anchor(list(word_list))
        if anchored:
            return anchored
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


_ABBR = {
    'vn': 'viet nam', 'hcm': 'ho chi minh', 'ml': 'mac lenin', 'cnxh': 'chu nghia xa hoi',
    'gd': 'giao duc', 'gdtc': 'giao duc the chat', 'gdqp': 'giao duc quoc phong', 'pp': 'phuong phap',
    'ppdh': 'phuong phap day hoc', 'nckh': 'nghien cuu khoa hoc', 'csdl': 'co so du lieu',
    'ctdl': 'cau truc du lieu', 'cntt': 'cong nghe thong tin', 'th': 'tieu hoc', 'mn': 'mam non',
    'tv': 'tieng viet', 'ta': 'tieng anh', 'dc': 'dai cuong', 'ktdg': 'kiem tra danh gia',
}


def expand_abbr(q):
    return ' '.join(_ABBR.get(t, t) for t in q.split())


def auto_correct_universal(raw_name, mode, code=None, credit=None):
    """Fuzzy-match an OCR'd subject name against the all-faculty UED database.

    1. 8-digit UED course code found in the line -> exact lookup (100%).
    2. Diacritic-insensitive normalisation (utils.normalize).
    3. rapidfuzz: combined score = max(token_set_ratio, WRatio, ratio) with a
       length-penalty so short noise does not match long names.
    Returns (ten_mon, "NN%", tin_chi).
    """
    try:
        if code:
            hit = db.by_code(code)
            if hit:
                return hit['ten_mon'], "100%", hit['tin_chi']
        q = expand_abbr(normalize(raw_name))
        q = re.sub(r'^\d+\s+', '', q)
        subjects = db.all_subjects()
        if not q or not subjects:
            return raw_name, "0%", 3
        choices = [s['norm'] for s in subjects]
        idxs = []
        for scorer in (fuzz.WRatio, fuzz.ratio, fuzz.token_sort_ratio):
            idxs += [i for _, _, i in process.extract(q, choices, scorer=scorer, limit=15)]
        best, best_score = None, -1.0
        for idx in dict.fromkeys(idxs):
            n = choices[idx]
            sc = 0.6 * fuzz.ratio(q, n) + 0.4 * max(fuzz.partial_ratio(q, n), fuzz.token_set_ratio(q, n))
            # exact numeric suffix matters ("Giải tích 1" vs "Giải tích 2")
            dq, dn = re.findall(r'\d+', q), re.findall(r'\d+', n)
            if dq and dn and dq[-1] != dn[-1]:
                sc -= 15
            elif bool(dq) != bool(dn):
                sc -= 6
            if credit is not None and subjects[idx]['tin_chi'] == credit:
                sc += 4  # OCR'd credit agrees with the DB -> tie-breaker
            if sc > best_score:
                best, best_score = subjects[idx], sc
        pct = f"{int(round(min(max(best_score, 0), 100)))}%"
        threshold = 75 if mode == 'computer' else 65
        if best_score >= threshold:
            return best['ten_mon'], pct, best['tin_chi']
        return raw_name, pct, best['tin_chi'] if best_score >= 45 else 3
    except Exception as e:
        print("Lỗi matching:", e)
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

            code_m = re.search(r'\b(\d{8})\b', line)
            ten_mon_chuan, similarity_pct, db_credit = auto_correct_universal(
                raw_name, 'computer', code_m.group(1) if code_m else None)
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
def _split_handwriting_line(line):
    """Token-based split: <name> [credit] <score10> [letter...].
    The score is the LAST decimal token (7.5 / 7,5); if the decimal point was
    lost by OCR ("95"), a 2-digit 11..99 token is read as 9.5. Names may end
    in digits ("Giải tích 1", "Tiếng Anh B1.1") so we anchor from the score."""
    toks = line.split()
    score_i = None
    for i in range(len(toks) - 1, 0, -1):
        if re.fullmatch(r"\d{1,2}[\.,]\d{1,2}", toks[i]) and float(toks[i].replace(',', '.')) <= 10:
            score_i = i
            break
    fixed = None
    if score_i is None:
        for i in range(len(toks) - 1, 0, -1):
            t = toks[i]
            if re.fullmatch(r"\d{2}", t) and 11 <= int(t) <= 99:
                score_i, fixed = i, f"{t[0]}.{t[1]}"
                break
            if re.fullmatch(r"\d{1,2}", t) and int(t) <= 10 and i >= 2:
                score_i = i
                break
    if score_i is None:
        return None
    credit = None
    name_end = score_i
    if score_i >= 2 and re.fullmatch(r"[1-9]", toks[score_i - 1]):
        credit = toks[score_i - 1]
        name_end = score_i - 1
    name = " ".join(toks[:name_end]).strip()
    if not re.search(r"[^\W\d_]{2,}", name):
        return None
    return name, credit, fixed or toks[score_i], " ".join(toks[score_i + 1:])


def parse_handwriting(lines):
    results = []

    for line in lines:
        line = line.strip()
        parts = _split_handwriting_line(line)
        if parts:
            raw_name_ocr, tin_chi_ocr, diem_10_str, phan_duoi = parts

            diem_chu_ocr = None
            match_chu = re.search(r"([A-DF])\s*([\+\-tTyY\*%\d]?)", phan_duoi, re.IGNORECASE)
            if match_chu:
                chu_cai = match_chu.group(1).upper()
                dau_kem_theo = match_chu.group(2).upper()
                # 't/y/*' AND digits are almost always a misread '+' in handwriting (e.g. C4 = C+)
                if dau_kem_theo in ['T', 'Y', '*', '%'] or dau_kem_theo.isdigit():
                    dau_kem_theo = '+'
                diem_chu_ocr = chu_cai + dau_kem_theo

            ten_mon_chuan, similarity_pct, db_credit = auto_correct_universal(
                raw_name_ocr, 'handwriting', credit=int(tin_chi_ocr) if tin_chi_ocr else None)

            final_tin_chi = int(tin_chi_ocr) if tin_chi_ocr is not None else db_credit

            try:
                diem_10 = float(diem_10_str.replace(',', '.'))
            except Exception:
                diem_10 = -1.0
            decimal_seen = bool(re.search(r'[\.,]', diem_10_str or '')) and diem_10_str in line
            if diem_chu_ocr and not decimal_seen:
                # decimal point was lost/reconstructed -> the written letter is more reliable
                final_diem_he_4 = diem_chu_ocr
            elif 0.0 <= diem_10 <= 10.0 and decimal_seen:
                # the 10-point score is the source of truth; handwritten letters
                # (B+ vs B4 vs B%) are the most error-prone part of OCR
                final_diem_he_4 = quy_doi_chuan(diem_10)
            elif diem_chu_ocr:
                final_diem_he_4 = diem_chu_ocr
            else:
                final_diem_he_4 = quy_doi_chuan(max(diem_10, 0.0))

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
    return jsonify({"success": True, "status": "ok", "ocr": engines.engine_status()})


@app.route('/api/stats')
def api_stats():
    return jsonify(db.stats())


@app.route('/api/faculties')
def api_faculties():
    return jsonify([f['khoa'] for f in db.stats()['faculties']])


@app.route('/api/match', methods=['GET'])
def api_match():
    """Debug/demo: fuzzy-match a free-text subject name."""
    q = request.args.get('q', '')
    mode = request.args.get('mode', 'handwriting')
    name, pct, tc = auto_correct_universal(q, mode)
    return jsonify({"query": q, "ten_mon": name, "percentage": pct, "tin_chi": tc})


@app.route('/api/search_subject', methods=['GET'])
def search_subject():
    query = request.args.get('q', '')
    if not query:
        return jsonify([])
    return jsonify(db.search_subjects(query, khoa=request.args.get('khoa') or None))


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
                engine = 'rapidocr-onnx' if engines.OCR_HANDWRITING_ENGINE == 'rapid' else ('tesseract' if engines._tesseract_is_available() else 'paddle-det+vietocr')

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


db.init_db()
if not db.all_subjects():
    db.seed_from_csv()

if os.environ.get('WARMUP', '0') == '1':
    import threading
    threading.Thread(target=lambda: engines._get_rapid() if engines.OCR_HANDWRITING_ENGINE == 'rapid' else (engines._vietocr_is_available() and engines._get_hybrid()), daemon=True).start()

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
