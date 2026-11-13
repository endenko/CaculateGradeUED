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
os.environ.setdefault("MALLOC_ARENA_MAX", "2")
os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("RAPID_LIMIT_SIDE", "960")

import re
from rapidfuzz import fuzz, process

from flask import Flask, Response, render_template, request, jsonify, send_from_directory
from werkzeug.utils import secure_filename

import db
import export_xlsx
import newsfeed
import ocr_queue
import regulations
import roadmap
import solver
import advising
import calendar_feed
import schedule_ocr
from ocr import engines
from utils import no_accent_vietnamese, normalize
from flask_limiter import Limiter
from flask_limiter.errors import RateLimitExceeded
from flask_limiter.util import get_remote_address

app = Flask(__name__)
limiter = Limiter(key_func=get_remote_address, app=app, default_limits=[], storage_uri="memory://")
# One bucket for both OCR entry points so /api/process_ocr cannot dodge the cap.
ocr_limit = limiter.shared_limit("5 per minute; 30 per hour", scope="ocr")

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


def _phone_row_cut(gaps):
    """Ngưỡng tách dòng cho ảnh điện thoại: khe trong một dòng nhỏ, khe giữa hai dòng lớn."""
    import statistics
    positive = sorted(gap for gap in gaps if gap >= 0.6)
    if len(positive) < 4:
        return 14.0
    median = statistics.median(positive)
    intra = [gap for gap in positive if gap <= max(median, 3.0) * 1.8]
    typical = statistics.median(intra) if intra else median
    big = [gap for gap in positive if gap >= max(8.0, typical * 2.8)]
    if big:
        return max(typical * 2.2, min(big) * 0.72)
    return max(10.0, typical * 3.0)


def reconstruct_lines_phone(word_list):
    """Nhóm từ theo khoảng cách dọc. Không gộp cột lệch sang dòng kế bên như ảnh chụp màn hình."""
    if not word_list:
        return []
    words = sorted(word_list, key=lambda item: item['y'])
    gaps = [words[index + 1]['y'] - words[index]['y'] for index in range(len(words) - 1)]
    cut = _phone_row_cut(gaps)
    lines = []
    current = [words[0]]
    for word, gap in zip(words[1:], gaps):
        if gap > cut:
            current.sort(key=lambda item: item['x'])
            lines.append(" ".join(item['text'] for item in current))
            current = [word]
        else:
            current.append(word)
    if current:
        current.sort(key=lambda item: item['x'])
        lines.append(" ".join(item['text'] for item in current))
    return lines


def reconstruct_lines(word_list, mode):
    if mode == 'phone':
        return reconstruct_lines_phone(word_list)
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
    """Thang A/B/C/D/F của Thông tư 08/2021 Điều 9 và QĐ 1473 Điều 20. Không có A+/B+."""
    try:
        clean = re.sub(r"[^\d,\.]", "", str(diem_so))
        d = float(clean.replace(',', '.'))
        letter, _pts = regulations.letter_from_score10(d)
        return letter
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
            elif dq and dn and dq[-1] == dn[-1] and set(q.split()) <= set(n.split()):
                # "giai tich 1" should beat "giai tich so" when the DB name contains those tokens.
                sc += 22
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
# 💻 PARSER MÁY TÍNH + DÒNG HỌC KỲ TRÊN PORTAL
# ========================================================
_SKIP_FOLDED = (
    "trung binh", "tich luy", "ren luyen", "tong so", "so tin chi",
    "diem hp", "ten hoc phan", "phuc khao", "chi tiet", "dvht",
)


def _fold_line(line):
    return no_accent_vietnamese(line).lower()


def extract_term(lines):
    """Đọc 'Học kỳ: 2 - Năm học: 2024 - 2025'. Thiếu kỳ hoặc thiếu năm thì không đoán."""
    folded = _fold_line("\n".join(lines or []))
    hk = re.search(r"h\w{0,3}c\s*k[yi]\w*\s*[:\-]?\s*(he|\d)", folded)
    nam = re.search(r"n\w{0,3}m\s*h\w{0,3}c\s*[:\-]?\s*(20\d{2})\s*-\s*(20\d{2})", folded)
    if not hk or not nam:
        return None
    ky = hk.group(1)
    if ky == "he":
        hoc_ky = "he"
    elif ky in ("1", "2"):
        hoc_ky = ky
    else:
        return None
    y1, y2 = int(nam.group(1)), int(nam.group(2))
    if y2 != y1 + 1:
        return None
    return {"hoc_ky": hoc_ky, "nam_hoc": f"{y1}-{y2}"}


def term_label(term):
    if not term:
        return "Không xác định được kỳ/năm"
    ky = {"1": "1", "2": "2", "he": "hè"}.get(term.get("hoc_ky"), term.get("hoc_ky"))
    return f"Học kỳ {ky} · {term.get('nam_hoc')}"


def _grades_from_tail(tail):
    """Điểm ở đuôi dòng portal: hệ 10 lần 1 [lần 2] rồi hệ 4 lần 1 [lần 2].

    Có lần 2 thì lấy lần 2 (học lại). Không có điểm thập phân và không có chữ
    thì là môn đang học, không gán F.
    """
    decimals = []
    for raw in re.findall(r"\d+[\.,]\d+", tail or ""):
        val = float(raw.replace(",", "."))
        if 0 <= val <= 10:
            decimals.append(val)
    letters = [(m.group(1) + (m.group(2) or "")).upper()
               for m in re.finditer(r"(?<![A-Z])([A-DF])(\+)?(?![A-Z])", tail or "", re.I)]
    lan = 1
    if len(decimals) >= 2:
        score, lan = decimals[1], 2
    elif len(decimals) == 1:
        score = decimals[0]
    else:
        score = None
    if len(letters) >= 2:
        letter, lan = letters[-1], 2
        if score is not None and quy_doi_chuan(score)[0] != letter[0]:
            letter = quy_doi_chuan(score)
    elif len(letters) == 1:
        letter = letters[0]
        if score is not None:
            derived = quy_doi_chuan(score)
            if derived[0] != letter[0] or len(derived) > len(letter):
                letter = derived
    elif score is not None:
        letter = quy_doi_chuan(score)
    else:
        letter = None
    return {
        "diem_10": score,
        "diem_he_4": letter,
        "lan": lan if letter or score is not None else 1,
        "in_progress": letter is None and score is None,
    }


def _skip_ocr_line(line):
    folded = _fold_line(line)
    if any(bit in folded for bit in _SKIP_FOLDED):
        return True
    if (re.search(r"h\w{0,3}c\s*k[yi]", folded) and re.search(r"20\d{2}\s*-\s*20\d{2}", folded)
            and not re.search(r"\b\d{8}\b", line)):
        return True
    return False


def _clean_raw_name(raw_name):
    raw_name = re.sub(r'^\d+\s+\d{5,10}\s+', '', raw_name)
    raw_name = re.sub(r'^\d{5,10}\s+', '', raw_name)
    raw_name = re.sub(r'^\d+\s+', '', raw_name).strip()
    return raw_name


def _row_from_parts(raw_name, tin_chi, grades, line):
    raw_name = _clean_raw_name(raw_name)
    folded = _fold_line(raw_name)
    if any(bit in folded for bit in ("trung binh", "tich luy", "ren luyen", "tong so")):
        return None
    if len(raw_name) < 2:
        return None
    code_m = re.search(r'\b(\d{8})\b', line)
    credit = int(tin_chi) if str(tin_chi).isdigit() else None
    ten_mon, pct, _db_credit = auto_correct_universal(
        raw_name, 'computer', code_m.group(1) if code_m else None, credit=credit)
    if len(ten_mon) < 2:
        return None
    return {
        "raw_name": raw_name,
        "ten_mon": ten_mon,
        "percentage": pct,
        "tin_chi": credit if credit else 3,
        "diem_he_4": grades["diem_he_4"],
        "diem_10": grades["diem_10"],
        "lan": grades["lan"],
        "in_progress": grades["in_progress"],
        "ma_hp": code_m.group(1) if code_m else None,
    }


def parse_computer(lines):
    results = []
    pat_A = re.compile(r"(.+?)\s+(\d{2}[-.\s]\d{4})\s*(\d)\b")
    pat_B = re.compile(r"(.+?)\s+(\d)\s+(\d+[\.,]\d+)")
    pat_score = re.compile(r"^(.+?)\s+([1-9])\s+(\d+[\.,]\d+)\s*([A-DF]\+?)?\s*$", re.I)
    pat_letter = re.compile(r"^(.+?)\s+([1-9])\s+([A-DF]\+?|F)\s*$", re.I)

    for line in lines:
        line = line.strip()
        if not line or _skip_ocr_line(line):
            continue
        match = pat_A.search(line)
        mode = "A"
        if not match:
            mode = "B"
            match = pat_B.search(line)
        if match:
            raw_name = match.group(1).strip()
            tin_chi = match.group(3) if mode == "A" else match.group(2)
            tail = line[match.end():]
            if mode == "B":
                tail = f"{match.group(3)} {tail}"
            row = _row_from_parts(raw_name, tin_chi, _grades_from_tail(tail), line)
            if row:
                results.append(row)
            continue
        # Dòng ngắn kiểu "Giải tích 1  3  A" hoặc "Toán  3  8.5  A" — chỉ khi không phải dòng portal.
        simple = pat_score.match(line) or pat_letter.match(line)
        if not simple or re.search(r"\b\d{8}\b", line) or re.search(r"\d{2}-\d{4}", line):
            continue
        if simple.re is pat_score:
            tail = simple.group(3) + " " + (simple.group(4) or "")
        else:
            tail = simple.group(3)
        row = _row_from_parts(simple.group(1), simple.group(2), _grades_from_tail(tail), line)
        if row:
            results.append(row)
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

    pat_score = re.compile(r"^(.+?)\s+([1-9])\s+(\d+[\.,]\d+)\s*([A-DF]\+?)?\s*$", re.I)
    pat_letter = re.compile(r"^(.+?)\s+([1-9])\s+([A-DF]\+?|F)\s*$", re.I)

    for line in lines:
        line = line.strip()
        simple = pat_letter.match(line)
        if simple and not re.search(r"\d+[\.,]\d+", line):
            raw_name, tin_chi, letter = simple.group(1), simple.group(2), simple.group(3).upper()
            ten_mon, pct, db_credit = auto_correct_universal(raw_name, 'handwriting', credit=int(tin_chi))
            results.append({
                "raw_name": raw_name.strip(),
                "ten_mon": ten_mon,
                "percentage": pct,
                "tin_chi": int(tin_chi) if tin_chi else db_credit,
                "diem_he_4": letter,
                "diem_10": None,
                "lan": 1,
                "in_progress": False,
            })
            continue
        scored = pat_score.match(line)
        if scored:
            line = f"{scored.group(1)} {scored.group(3)} {scored.group(4) or ''}".strip()
            # giữ tín chỉ bằng cách nhét lại sau khi tách theo điểm
            credit_hint = scored.group(2)
        else:
            credit_hint = None
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

            final_tin_chi = int(credit_hint) if credit_hint else (int(tin_chi_ocr) if tin_chi_ocr is not None else db_credit)

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
                "diem_he_4": final_diem_he_4,
                "diem_10": diem_10 if 0 <= diem_10 <= 10 else None,
                "lan": 1,
                "in_progress": False,
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
    try:
        ocr_queue.queue.ensure()
        worker_alive = ocr_queue.queue.worker_alive()
    except Exception:
        app.logger.exception("OCR queue health check failed")
        worker_alive = False
    if not worker_alive:
        app.logger.error("OCR queue consumer is not alive in pid %s", os.getpid())
    return jsonify({
        "success": True,
        "status": "ok",
        "ocr": engines.engine_status(),
        "queue_worker": worker_alive,
        "queue_pid": os.getpid(),
    })


@app.route('/api/stats')
def api_stats():
    return jsonify(db.stats())


@app.route('/api/programs')
def api_programs():
    return jsonify(roadmap.list_programs())


@app.route('/api/roadmap', methods=['POST'])
def api_roadmap():
    data = request.get_json(silent=True) or {}
    return jsonify(roadmap.build_roadmap(data.get('nganh') or '', data.get('courses') or []))


@app.route('/api/gpa_series', methods=['POST'])
def api_gpa_series():
    data = request.get_json(silent=True) or {}
    try:
        out = regulations.summarize({
            "courses": data.get("courses") or [],
            "program_credits": data.get("program_credits") or 130,
            "rule": data.get("rule") or "qd1586",
        })
    except ValueError as exc:
        return jsonify({"success": False, "error": str(exc)}), 400
    return jsonify({"success": True, "semesters": out["semesters"], "cumulative": out["cumulative"]})


@app.route('/api/export.xlsx', methods=['POST'])
def api_export_xlsx():
    data = request.get_json(silent=True) or {}
    body = export_xlsx.build_xlsx(export_xlsx.grade_sheets(data))
    return Response(
        body,
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        headers={'Content-Disposition': 'attachment; filename="bang-diem-ued.xlsx"'},
    )


@app.route('/sw.js')
def service_worker():
    resp = send_from_directory(app.static_folder, 'sw.js')
    resp.headers['Content-Type'] = 'application/javascript; charset=utf-8'
    resp.headers['Service-Worker-Allowed'] = '/'
    resp.headers['Cache-Control'] = 'no-cache'
    return resp


@app.route('/manifest.webmanifest')
def web_manifest():
    resp = send_from_directory(app.static_folder, 'manifest.webmanifest')
    resp.headers['Content-Type'] = 'application/manifest+json; charset=utf-8'
    return resp


@app.route('/offline.html')
def offline_page():
    return send_from_directory(app.static_folder, 'offline.html')


@app.route('/api/lookup')
@limiter.limit("40 per minute", override_defaults=False)
def api_lookup():
    query = request.args.get('q', '')
    try:
        limit = int(request.args.get('limit') or 12)
    except ValueError:
        limit = 12
    payload = db.lookup_courses(query, limit=limit)
    response = jsonify(payload)
    response.headers['Cache-Control'] = 'public, max-age=120'
    return response


@app.route('/api/advise', methods=['POST'])
def api_advise():
    data = request.get_json(silent=True) or {}
    courses = data.get('courses') or []
    program = data.get('program_credits') or 130
    try:
        return jsonify({
            "success": True,
            "retake": advising.retake_suggestions(courses, target=data.get('target') or 'A', top_n=int(data.get('top_n') or 5)),
            "scholarship": advising.scholarship_report(courses, drl=data.get('drl'), discipline=bool(data.get('discipline')), program_credits=program),
            "warning": advising.warning_report(courses, program_credits=program, rule=data.get('rule') or 'qd1586'),
        })
    except ValueError as exc:
        return jsonify({"success": False, "error": str(exc)}), 400


@app.route('/api/calendar/feed', methods=['POST'])
def calendar_feed_create():
    data = request.get_json(silent=True) or {}
    token = calendar_feed.save_feed(data.get("schedule") or {}, data.get("previous") or "")
    base = request.host_url.rstrip("/")
    return jsonify({
        "success": True,
        "token": token,
        "https": f"{base}/cal/{token}.ics",
        "webcal": f"webcal://{request.host}/cal/{token}.ics",
    })


@app.route('/api/calendar/feed/revoke', methods=['POST'])
def calendar_feed_revoke():
    calendar_feed.revoke_feed((request.get_json(silent=True) or {}).get("token") or "")
    return jsonify({"success": True})


@app.route('/cal/<token>.ics')
def calendar_ics(token):
    schedule = calendar_feed.load_feed(token)
    if schedule is None:
        return Response("Không thấy lịch này.", status=404, mimetype="text/plain")
    return Response(calendar_feed.build_ics(schedule), mimetype="text/calendar; charset=utf-8")


@app.route('/api/calendar/google/status')
def google_calendar_status():
    return jsonify({"enabled": calendar_feed.oauth_enabled()})


@app.route('/api/calendar/google/start')
def google_calendar_start():
    if not calendar_feed.oauth_enabled():
        return jsonify({"success": False, "error": "Chưa cấu hình Google OAuth"}), 404
    import secrets
    state = secrets.token_urlsafe(16)
    sid = request.cookies.get("ued_gcal") or secrets.token_urlsafe(18)
    redirect_uri = request.host_url.rstrip("/") + "/api/calendar/google/callback"
    response = app.redirect(calendar_feed.auth_url(redirect_uri, state))
    response.set_cookie("ued_gcal", sid, httponly=True, samesite="Lax", max_age=180 * 24 * 3600)
    response.set_cookie("ued_gcal_state", state, httponly=True, samesite="Lax", max_age=600)
    return response


@app.route('/api/calendar/google/callback')
def google_calendar_callback():
    if not calendar_feed.oauth_enabled():
        return jsonify({"success": False, "error": "Chưa cấu hình Google OAuth"}), 404
    if request.args.get("state") != request.cookies.get("ued_gcal_state"):
        return Response("Phiên OAuth không khớp.", status=400)
    import secrets
    redirect_uri = request.host_url.rstrip("/") + "/api/calendar/google/callback"
    token = calendar_feed.exchange_code(request.args.get("code") or "", redirect_uri)
    sid = request.cookies.get("ued_gcal") or secrets.token_urlsafe(18)
    calendar_feed.save_google(sid, token.get("refresh_token") or "")
    response = app.redirect("/#lich")
    response.set_cookie("ued_gcal", sid, httponly=True, samesite="Lax", max_age=180 * 24 * 3600)
    return response


@app.route('/api/calendar/google/sync', methods=['POST'])
def google_calendar_sync():
    if not calendar_feed.oauth_enabled():
        return jsonify({"success": False, "error": "Chưa cấu hình Google OAuth"}), 404
    data = request.get_json(silent=True) or {}
    try:
        count = calendar_feed.sync_events(request.cookies.get("ued_gcal") or "", data.get("schedule") or {})
    except PermissionError as exc:
        return jsonify({"success": False, "error": str(exc), "auth": "/api/calendar/google/start"}), 401
    except Exception as exc:
        return jsonify({"success": False, "error": str(exc)}), 502
    return jsonify({"success": True, "events": count})


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


def _run_ocr_file(path, mode):
    prepared = None
    try:
        if mode in ("exam", "timetable"):
            words = engines.computer_words(path)
            parsed = schedule_ocr.parse_exam(words) if mode == "exam" else schedule_ocr.parse_timetable(words)
            parsed["rows"] = schedule_ocr.attach_catalog(parsed.get("rows") or [])
            return {
                "success": True,
                "mode": mode,
                "rows": parsed["rows"],
                "meta": {k: v for k, v in parsed.items() if k != "rows"},
                "engine": "rapidocr-onnx",
                "data": [],
            }
        from ocr.prepare import PhotoPrepareError, looks_like_phone_capture, prepare_exif_image, prepare_phone_image
        use_phone = mode == 'phone' or (mode == 'computer' and looks_like_phone_capture(path))
        if use_phone:
            prepared = prepare_phone_image(path)
            ocr_path = prepared
        elif mode != 'handwriting':
            prepared = prepare_exif_image(path)
            ocr_path = prepared or path
        else:
            ocr_path = path
        if mode == 'handwriting' and not use_phone:
            word_list, engine = engines.handwriting_words(ocr_path)
            lines = reconstruct_lines(word_list, mode)
            extracted_data = parse_handwriting(lines)
        else:
            word_list = engines.computer_words(ocr_path)
            lines = reconstruct_lines(word_list, 'phone' if use_phone else 'computer')
            extracted_data = parse_computer(lines)
            engine = 'rapidocr-onnx' if engines.OCR_HANDWRITING_ENGINE == 'rapid' else ('tesseract' if engines._tesseract_is_available() else 'paddle-det+vietocr')
            if use_phone:
                engine = engine + '+phone'
        term = extract_term(lines)
        for row in extracted_data:
            row["hoc_ky"] = term["hoc_ky"] if term else None
            row["nam_hoc"] = term["nam_hoc"] if term else None
            row["term_unknown"] = term is None
        return {
            "success": True,
            "data": extracted_data,
            "engine": engine,
            "term": term,
            "term_label": term_label(term),
        }
    except PhotoPrepareError as exc:
        return {"success": False, "error": str(exc)}
    except Exception as exc:
        return {"success": False, "error": str(exc)}
    finally:
        for leftover in (path, prepared):
            if not leftover:
                continue
            try:
                os.remove(leftover)
            except OSError:
                pass


ocr_queue.queue.set_runner(_run_ocr_file)


@app.errorhandler(RateLimitExceeded)
def _rate_limited(_exc):
    if request.path.startswith('/api/lookup'):
        message = "Bạn tra cứu môn quá nhanh. Đợi một lát rồi gõ tiếp."
    else:
        message = "Bạn gửi ảnh OCR quá nhanh. Mỗi máy chỉ được 5 ảnh mỗi phút và 30 ảnh mỗi giờ. Đợi một lát rồi thử lại nhé."
    return jsonify({"success": False, "accepted": False, "error": message}), 429


def _save_upload():
    if 'file_anh' not in request.files:
        return None, (jsonify({"success": False, "error": "Chưa chọn file"}), 400)
    file = request.files['file_anh']
    if not file:
        return None, (jsonify({"success": False, "error": "File không hợp lệ"}), 400)
    filename = secure_filename(file.filename) or "scan.jpg"
    path = os.path.join(app.config['UPLOAD_FOLDER'], f"{os.urandom(4).hex()}_{filename}")
    file.save(path)
    return path, None


@app.route('/api/ocr/jobs', methods=['POST'])
@ocr_limit
def ocr_job_submit():
    path, err = _save_upload()
    if err:
        return err
    mode = request.form.get('mode', 'computer')
    ticket = ocr_queue.queue.submit(path, mode)
    if not ticket.get("accepted", True):
        try:
            os.remove(path)
        except OSError:
            pass
        return jsonify(ticket), 429
    return jsonify(ticket)


@app.route('/api/ocr/jobs/<job_id>')
def ocr_job_status(job_id):
    info = ocr_queue.queue.status(job_id)
    if not info.get("found"):
        return jsonify(info), 404
    return jsonify(info)


@app.route('/api/process_ocr', methods=['POST'])
@ocr_limit
def process_ocr():
    """Synchronous OCR. Same queue and rate limit as /api/ocr/jobs."""
    path, err = _save_upload()
    if err:
        return err
    mode = request.form.get('mode', 'computer')
    ticket = ocr_queue.queue.submit(path, mode)
    if not ticket.get("accepted", True):
        try:
            os.remove(path)
        except OSError:
            pass
        return jsonify({"success": False, "error": ticket.get("error") or "Hàng đợi OCR đang đầy"}), 429
    info = ocr_queue.queue.wait(ticket["id"], timeout=110)
    if info.get("status") == "done":
        return jsonify(info.get("result") or {"success": False, "error": "OCR không trả kết quả"})
    if info.get("status") == "error":
        return jsonify(info.get("result") or {"success": False, "error": info.get("error") or "OCR lỗi"})
    return jsonify({"success": False, "error": "OCR quá thời gian chờ hàng đợi"}), 504


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


@app.route('/api/academics', methods=['POST'])
def api_academics():
    try:
        return jsonify(regulations.summarize(request.get_json(force=True) or {}))
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400


@app.route('/api/semester_options', methods=['POST'])
def api_semester_options():
    data = request.get_json(force=True) or {}
    try:
        weights = tuple(data.get("weights") or (0.2, 0.3, 0.5))
        options = solver.semester_options(
            data.get("table2") or [],
            float(data.get("target") or 3.2),
            weights,
            limit=5,
        )
    except (TypeError, ValueError) as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify({"options": options})


@app.route('/api/components', methods=['POST'])
def api_components():
    data = request.get_json(force=True) or {}
    try:
        return jsonify(regulations.component_result(data.get("parts") or []))
    except (ValueError, KeyError, TypeError) as exc:
        return jsonify({"error": str(exc)}), 400


@app.route('/api/drl', methods=['POST'])
def api_drl():
    data = request.get_json(force=True) or {}
    try:
        return jsonify(regulations.drl_result(data.get("scores") or {}, data.get("discipline") or "none"))
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400


@app.route('/api/news')
def api_news():
    board = newsfeed.get_board()
    return jsonify({
        "posts": board.get("posts") or [],
        "calendar": board.get("calendar") or [],
        "source": board.get("source"),
        "facebook": board.get("facebook"),
        "cache": board.get("cache"),
        "stale": bool(board.get("stale")),
        "error": board.get("error"),
        "fetched_at": board.get("fetched_at_epoch"),
    })


db.init_db()
if not db.all_subjects():
    db.seed_from_csv()

if os.environ.get('WARMUP', '0') == '1':
    import threading
    threading.Thread(target=lambda: engines._get_rapid() if engines.OCR_HANDWRITING_ENGINE == 'rapid' else (engines._vietocr_is_available() and engines._get_hybrid()), daemon=True).start()

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
