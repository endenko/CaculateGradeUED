# -*- coding: utf-8 -*-
"""Build data/hoc_phan_ued.csv from the official UED CTĐT khóa 2025 PDFs.

Pipeline (all free/offline):
  1. download PDFs listed on https://ued.udn.vn/2025/11/09/chuong-trinh-dao-tao-ke-hoach-dao-tao-ap-dung-cho-khoa-ts-2025/
  2. pdftoppm -r 150 -> PNG pages (PDFs are scans, no text layer)
  3. PaddleOCR PP-OCRv6_medium_det + VietOCR vgg_transformer -> /tmp/ctdt/ocr2.json (tools/ocr_pages.py)
  4. this script: table-row reconstruction (8-digit course code anchors) -> CSV
Names are then normalised by "voting": the same course code across programs is
OCR'd several times; the most frequent spelling wins.
"""
import csv, json, re, sys, os, unicodedata
from collections import Counter, defaultdict

SRC = 'https://ued.udn.vn/wp-content/uploads/{path}'
KHOA = {
 'Toán – Tin': ['Su-pham-Toan-hoc', 'Su-pham-Tin-hoc', 'Cong-nghe-thong-tin', 'Khoa-hoc-du-lieu'],
 'Lý – Hoá': ['Su-pham-Vat-ly', 'Su-pham-Hoa-hoc', 'Su-pham-Khoa-hoc-Tu-nhien', 'Vat-ly-ky-thuat', 'Hoa-duoc', 'Hoa-phan-tich-Ung-dung'],
 'Sinh – Nông nghiệp – Môi trường': ['Su-pham-Sinh-hoc', 'Quan-ly-Tai-nguyen-Moi-truong', 'Cong-nghe-sinh-hoc'],
 'Ngữ văn – Truyền thông': ['Su-pham-Ngu-van', 'Bao-chi', 'Quan-he-cong-chung', 'Van-hoa-hoc', 'Van-hoc'],
 'Sử – Địa – Chính trị': ['Su-pham-Lich-su-1', 'Su-pham-Dia-ly', 'Giao-duc-Cong-dan', 'Giao-duc-chinh-tri', 'Giao-duc-Phap-luat',
                          'Su-pham-Lich-su-Dia-ly', 'Viet-Nam-hoc', 'Dia-ly-hoc', 'Quan-he-quoc-te'],
 'Tâm lý – Giáo dục – Công tác xã hội': ['Cong-tac-xa-hoi', 'Tam-ly-hoc'],
 'Giáo dục Tiểu học – Mầm non': ['Giao-duc-Tieu-hoc', 'Giao-duc-Mam-non', 'Su-pham-Tin-va-Cong-nghe-tieu-hoc'],
 'Giáo dục Nghệ thuật – Thể chất': ['Su-pham-Am-nhac', 'Su-pham-My-thuat', 'Giao-duc-The-chat'],
}
NGANH = {
 'Su-pham-Toan-hoc': 'Sư phạm Toán học', 'Su-pham-Tin-hoc': 'Sư phạm Tin học', 'Cong-nghe-thong-tin': 'Công nghệ thông tin',
 'Khoa-hoc-du-lieu': 'Khoa học dữ liệu', 'Su-pham-Vat-ly': 'Sư phạm Vật lý', 'Su-pham-Hoa-hoc': 'Sư phạm Hoá học',
 'Su-pham-Khoa-hoc-Tu-nhien': 'Sư phạm Khoa học tự nhiên', 'Vat-ly-ky-thuat': 'Vật lý kỹ thuật', 'Hoa-duoc': 'Hóa dược',
 'Hoa-phan-tich-Ung-dung': 'Hóa phân tích – Ứng dụng', 'Su-pham-Sinh-hoc': 'Sư phạm Sinh học',
 'Quan-ly-Tai-nguyen-Moi-truong': 'Quản lý Tài nguyên và Môi trường', 'Cong-nghe-sinh-hoc': 'Công nghệ sinh học',
 'Su-pham-Ngu-van': 'Sư phạm Ngữ văn', 'Bao-chi': 'Báo chí', 'Quan-he-cong-chung': 'Quan hệ công chúng', 'Van-hoa-hoc': 'Văn hóa học',
 'Van-hoc': 'Văn học', 'Su-pham-Lich-su-1': 'Sư phạm Lịch sử', 'Su-pham-Dia-ly': 'Sư phạm Địa lý', 'Giao-duc-Cong-dan': 'Giáo dục Công dân',
 'Giao-duc-chinh-tri': 'Giáo dục Chính trị', 'Giao-duc-Phap-luat': 'Giáo dục Pháp luật', 'Su-pham-Lich-su-Dia-ly': 'Sư phạm Lịch sử – Địa lý',
 'Viet-Nam-hoc': 'Việt Nam học (Văn hoá – Du lịch)', 'Dia-ly-hoc': 'Địa lý học (Địa lý du lịch)', 'Quan-he-quoc-te': 'Lịch sử (Quan hệ Quốc tế)',
 'Cong-tac-xa-hoi': 'Công tác xã hội', 'Tam-ly-hoc': 'Tâm lý học', 'Giao-duc-Tieu-hoc': 'Giáo dục Tiểu học', 'Giao-duc-Mam-non': 'Giáo dục Mầm non',
 'Su-pham-Tin-va-Cong-nghe-tieu-hoc': 'Sư phạm Tin học và Công nghệ tiểu học', 'Su-pham-Am-nhac': 'Sư phạm Âm nhạc',
 'Su-pham-My-thuat': 'Sư phạm Mỹ thuật', 'Giao-duc-The-chat': 'Giáo dục Thể chất',
}
PROG2KHOA = {p: k for k, ps in KHOA.items() for p in ps}

# ---- Khóa 2024 (pre-merge structure, https://daotao.ued.udn.vn/chuong-trinh-dao-tao-ke-hoach-dao-tao-ap-dung-cho-khoa-ts-2024/)
# file prefix = old faculty number used by UED (311 Toán ... 324 GD Nghệ thuật)
KHOA_CU = {'311': 'Toán', '312': 'Tin học', '313': 'Vật lý', '314': 'Hóa học', '315': 'Sinh – Môi trường',
           '316': 'Giáo dục Chính trị', '317': 'Ngữ văn', '318': 'Lịch sử', '319': 'Địa lý', '320': 'Tâm lý – Giáo dục',
           '322': 'Giáo dục Tiểu học', '323': 'Giáo dục Mầm non', '324': 'Giáo dục Nghệ thuật'}
KHOA_CU2MOI = {'Toán': 'Toán – Tin', 'Tin học': 'Toán – Tin', 'Vật lý': 'Lý – Hoá', 'Hóa học': 'Lý – Hoá',
               'Sinh – Môi trường': 'Sinh – Nông nghiệp – Môi trường', 'Giáo dục Chính trị': 'Sử – Địa – Chính trị',
               'Ngữ văn': 'Ngữ văn – Truyền thông', 'Lịch sử': 'Sử – Địa – Chính trị', 'Địa lý': 'Sử – Địa – Chính trị',
               'Tâm lý – Giáo dục': 'Tâm lý – Giáo dục – Công tác xã hội', 'Giáo dục Tiểu học': 'Giáo dục Tiểu học – Mầm non',
               'Giáo dục Mầm non': 'Giáo dục Tiểu học – Mầm non', 'Giáo dục Nghệ thuật': 'Giáo dục Nghệ thuật – Thể chất'}
NGANH24 = {'311-CKDL': 'Khoa học dữ liệu', '311-ST': 'Sư phạm Toán học', '312-CNTT': 'Công nghệ thông tin', '312-SPT': 'Sư phạm Tin học',
           '313-CVK': 'Vật lý kỹ thuật', '313-SVL': 'Sư phạm Vật lý', '314-CHD': 'Hóa học (CN Hóa dược)', '314-SHH': 'Sư phạm Hóa học',
           '314-SKT': 'Sư phạm Khoa học tự nhiên', '315-CNSH': 'Công nghệ sinh học', '315-CTM': 'Quản lý tài nguyên môi trường',
           '315-SS': 'Sư phạm Sinh học', '316-SGC': 'Giáo dục Chính trị', '316SCD': 'Giáo dục Công dân', '317-CBC': 'Báo chí',
           '317-CVH': 'Văn học', '317-CVHH': 'Văn hóa học', '317-QHCC': 'Quan hệ công chúng', '317-SNV': 'Sư phạm Ngữ văn',
           '318-LS': 'Lịch sử', '318-SLD': 'Sư phạm Lịch sử và Địa lý', '318-SLS': 'Sư phạm Lịch sử', '318VNH': 'Việt Nam học',
           '319-CDDL': 'Địa lý học (Địa lý du lịch)', '319-SDL': 'Sư phạm Địa lý', '320-CTL': 'Tâm lý học', '320-CTXH': 'Công tác xã hội',
           '322-GDTH': 'Giáo dục Tiểu học', '322-STC': 'Sư phạm Tin học và Công nghệ Tiểu học', '323-GMN': 'Giáo dục Mầm non',
           '324-SAN': 'Sư phạm Âm nhạc', '324-SGT': 'Giáo dục Thể chất', '324-SMT': 'Sư phạm Mỹ thuật'}
for _p, _n in NGANH24.items():
    _old = KHOA_CU[_p[:3]]
    NGANH[_p] = _n + ' (khóa 2024)'
    PROG2KHOA[_p] = KHOA_CU2MOI[_old]
PROG2KHOA_CU = {p: KHOA_CU[p[:3]] for p in NGANH24}
# 2025 programs -> pre-merge faculty (from the 2024 list)
for _p, _old in {'Su-pham-Toan-hoc': 'Toán', 'Khoa-hoc-du-lieu': 'Toán', 'Su-pham-Tin-hoc': 'Tin học', 'Cong-nghe-thong-tin': 'Tin học',
                 'Su-pham-Vat-ly': 'Vật lý', 'Vat-ly-ky-thuat': 'Vật lý', 'Su-pham-Hoa-hoc': 'Hóa học', 'Su-pham-Khoa-hoc-Tu-nhien': 'Hóa học',
                 'Hoa-duoc': 'Hóa học', 'Su-pham-Sinh-hoc': 'Sinh – Môi trường', 'Quan-ly-Tai-nguyen-Moi-truong': 'Sinh – Môi trường',
                 'Cong-nghe-sinh-hoc': 'Sinh – Môi trường', 'Giao-duc-chinh-tri': 'Giáo dục Chính trị', 'Giao-duc-Cong-dan': 'Giáo dục Chính trị',
                 'Su-pham-Ngu-van': 'Ngữ văn', 'Bao-chi': 'Ngữ văn', 'Van-hoc': 'Ngữ văn', 'Van-hoa-hoc': 'Ngữ văn', 'Quan-he-cong-chung': 'Ngữ văn',
                 'Su-pham-Lich-su-1': 'Lịch sử', 'Su-pham-Lich-su-Dia-ly': 'Lịch sử', 'Viet-Nam-hoc': 'Lịch sử', 'Quan-he-quoc-te': 'Lịch sử',
                 'Su-pham-Dia-ly': 'Địa lý', 'Dia-ly-hoc': 'Địa lý', 'Tam-ly-hoc': 'Tâm lý – Giáo dục', 'Cong-tac-xa-hoi': 'Tâm lý – Giáo dục',
                 'Giao-duc-Tieu-hoc': 'Giáo dục Tiểu học', 'Su-pham-Tin-va-Cong-nghe-tieu-hoc': 'Giáo dục Tiểu học',
                 'Giao-duc-Mam-non': 'Giáo dục Mầm non', 'Su-pham-Am-nhac': 'Giáo dục Nghệ thuật', 'Su-pham-My-thuat': 'Giáo dục Nghệ thuật',
                 'Giao-duc-The-chat': 'Giáo dục Nghệ thuật'}.items():
    PROG2KHOA_CU[_p] = _old
# 'Hoa-phan-tich-Ung-dung' and 'Giao-duc-Phap-luat' are new in 2025 (no pre-merge faculty) -> left blank


def strip(s):
    s = unicodedata.normalize('NFD', s)
    return ''.join(c for c in s if unicodedata.category(c) != 'Mn').replace('đ', 'd').replace('Đ', 'D').lower()


def parse_page(words, credit_x=None):
    for w in words:
        b = w['b']; w['x1'], w['y1'], w['x2'], w['y2'] = b
        w['xc'] = (b[0] + b[2]) / 2; w['yc'] = (b[1] + b[3]) / 2
    W = max(w['x2'] for w in words) if words else 1
    # header: "Số tín chỉ" column
    hdr = None
    for w in words:
        if re.search(r'tin chi', strip(w['t'])) and w['xc'] > 0.4 * W:
            hdr = w['xc']
    # 2024 layout: "Số tín chỉ" spans TC | LT | TH ... -> use the "TC" sub-header when present
    tc = [w for w in words if w['t'].strip().upper() in ('TC', 'STC') and w['xc'] > 0.4 * W]
    if tc:
        credit_x = min(tc, key=lambda w: w['xc'])['xc']
    elif hdr is not None:
        credit_x = hdr
    codes = [w for w in words if re.fullmatch(r'\*?\d{8}\*?', w['t'].strip()) and w['xc'] < 0.35 * W]
    codes.sort(key=lambda w: w['yc'])
    if not codes or credit_x is None:
        return [], credit_x
    code_right = max(c['x2'] for c in codes)
    rows = []
    for i, c in enumerate(codes):
        gap_dn = (codes[i + 1]['yc'] - c['yc']) / 2 if i + 1 < len(codes) else None
        gap_up = (c['yc'] - codes[i - 1]['yc']) / 2 if i else None
        top = c['yc'] - (gap_up if gap_up is not None else max(30, gap_dn or 30))
        bot = c['yc'] + (gap_dn if gap_dn is not None else max(30, gap_up or 30))
        band = [w for w in words if top <= w['yc'] < bot]
        name_parts = [w for w in band if w['x1'] >= code_right - 5 and w['x2'] < credit_x - 25]
        name_parts.sort(key=lambda w: (round(w['yc'] / 12), w['x1']))
        name = ' '.join(w['t'] for w in name_parts).strip()
        cr = [w for w in band if abs(w['xc'] - credit_x) < 45 and re.fullmatch(r'\(?\d{1,2}\)?', w['t'].strip())]
        cr.sort(key=lambda w: abs(w['yc'] - c['yc']))
        credit = int(re.sub(r'\D', '', cr[0]['t'])) if cr else None
        rows.append({'ma_hp': c['t'].strip('*'), 'ten_mon': name, 'tin_chi': credit,
                     'bracket': bool(cr and '(' in cr[0]['t'])})
    return rows, credit_x


def clean_name(n):
    n = re.sub(r'\s+', ' ', n).strip(' .,*-')
    n = re.sub(r'\s*\*$', '', n)
    n = re.sub(r'(?i)\b(học phần|hoc phan) (tự chọ\w*|bắt buộc)( tối thiểu)?\b', ' ', n)
    n = re.sub(r'(?i)số tín ch\w*( trong k\w*)?', ' ', n)
    n = re.sub(r'\s(19[89]\d)$', '', n)
    n = n.replace('C/C%4', 'C/C++').replace('C/C%', 'C/C++').replace('C%', 'C++')
    n = re.sub(r'(?i)\bkhối kiến thức[^A-Z]*$', ' ', n)
    n = re.sub(r'\s+', ' ', n).strip(' .,*-:')
    n = re.sub(r'\bmác\b', 'Mác', n).replace('việt nam', 'Việt Nam')
    return n[:1].upper() + n[1:] if n else n


def main(ocr_json, out_csv, urls_file):
    data, urls = {}, {}
    for oj, uf in zip(ocr_json.split(','), urls_file.split(',')):
        if os.path.exists(oj):
            data.update(json.load(open(oj)))
            urls.update({os.path.basename(u.strip())[:-4]: u.strip() for u in open(uf) if u.strip()})
    by_prog = defaultdict(list)
    for k in sorted(data, key=lambda k: (k.rsplit('-', 1)[0], int(k.rsplit('-', 1)[1][:-4]))):
        by_prog[k.rsplit('-', 1)[0]].append(k)
    raw = []
    for prog, pages in by_prog.items():
        cx = None
        for pg in pages:
            rows, cx = parse_page(data[pg], cx)
            for r in rows:
                r.update(prog=prog, page=pg)
                raw.append(r)
    # voting: best spelling / credit per course code
    names = defaultdict(Counter); credits = defaultdict(Counter)
    for r in raw:
        n = clean_name(r['ten_mon'])
        if len(n) >= 3:
            names[r['ma_hp']][n] += 1
        if r['tin_chi'] is not None and 0 <= r['tin_chi'] <= 15:
            credits[r['ma_hp']][r['tin_chi']] += 1
    out, seen = [], set()
    for r in raw:
        code = r['ma_hp']
        if not names[code]:
            continue
        key = (code, r['prog'])
        cands = names[code]
        def _score(n):
            sc = cands[n] * 10 + min(len(n.split()), 12) - (6 if len(n.split()) <= 1 and cands[n] < 2 else 0)
            base = re.sub(r'\s\d$', '', n)
            if base != n and base in cands:
                sc -= 25  # trailing semester digit leaked from the 2024 plan columns
            return sc
        best_name = max(cands, key=_score)
        if key in seen:
            continue
        seen.add(key)
        tc = credits[code].most_common(1)[0][0] if credits[code] else ''
        out.append({'ma_hp': code, 'ten_mon': best_name, 'tin_chi': tc,
                    'khoa': PROG2KHOA.get(r['prog'], ''), 'khoa_cu': PROG2KHOA_CU.get(r['prog'], ''), 'nganh': NGANH.get(r['prog'], r['prog']),
                    'nguon': urls.get(r['prog'], '') + ('' if tc != '' else ' [tín chỉ: không đọc được]')})
    with open(out_csv, 'w', encoding='utf-8', newline='') as f:
        w = csv.DictWriter(f, fieldnames=['ma_hp', 'ten_mon', 'tin_chi', 'khoa', 'khoa_cu', 'nganh', 'nguon'])
        w.writeheader(); w.writerows(out)
    print(f"raw rows={len(raw)} out rows={len(out)} codes={len({o['ma_hp'] for o in out})} "
          f"names={len({o['ten_mon'] for o in out})} programs={len({o['nganh'] for o in out})} "
          f"missing_credit={sum(1 for o in out if o['tin_chi']=='')}")


if __name__ == '__main__':
    main(*(sys.argv[1:] or ['/tmp/ctdt/ocr2.json,/tmp/ctdt24/ocr2.json', 'data/hoc_phan_ued.csv', '/tmp/ctdt/urls.txt,/tmp/ctdt24/u.txt']))
