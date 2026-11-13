# -*- coding: utf-8 -*-
"""
Database layer — SQLite (zero-config).

Tables
  danh_muc_mon(ten_mon PK, tin_chi, ma_hp, khoa, so_nganh)   -- one row per unique subject name
                                                              (same schema as original + extra cols)
  hoc_phan(ma_hp, ten_mon, tin_chi, khoa, nganh, nguon)       -- every course of every UED program

Seed files
  data/danh_muc_mon.csv      original IT-faculty list (ten_mon,tin_chi)
  data/hoc_phan_ued.csv      all faculties, extracted from official UED CTĐT khóa 2025 PDFs
"""
import csv
import os
import re
import sqlite3
from collections import Counter, defaultdict

from utils import no_accent_vietnamese

BASE = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.environ.get('DB_PATH', '/tmp/grade.db' if os.environ.get('VERCEL') else os.path.join(BASE, 'grade.db'))
SEED_CSV = os.path.join(BASE, 'data', 'danh_muc_mon.csv')
UED_CSV = os.path.join(BASE, 'data', 'hoc_phan_ued.csv')

_cache = None  # in-memory subject list for fuzzy matching


def _ensure_db_dir():
    d = os.path.dirname(DB_PATH)
    if d:
        os.makedirs(d, exist_ok=True)


def get_db():
    _ensure_db_dir()
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db()
    try:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS danh_muc_mon (
                ten_mon  TEXT PRIMARY KEY,
                tin_chi  INTEGER NOT NULL DEFAULT 3
            );
            CREATE TABLE IF NOT EXISTS hoc_phan (
                ma_hp   TEXT,
                ten_mon TEXT NOT NULL,
                tin_chi INTEGER,
                khoa    TEXT,
                khoa_cu TEXT,
                nganh   TEXT,
                nguon   TEXT,
                PRIMARY KEY (ma_hp, nganh, ten_mon)
            );
            CREATE INDEX IF NOT EXISTS ix_hp_ten ON hoc_phan(ten_mon);
        """)
        hp_cols = {r[1] for r in conn.execute("PRAGMA table_info(hoc_phan)")}
        if 'khoa_cu' not in hp_cols:
            conn.execute("ALTER TABLE hoc_phan ADD COLUMN khoa_cu TEXT")
        cols = {r[1] for r in conn.execute("PRAGMA table_info(danh_muc_mon)")}
        for col in ('ma_hp', 'khoa', 'so_nganh', 'khoa_cu'):
            if col not in cols:
                conn.execute(f"ALTER TABLE danh_muc_mon ADD COLUMN {col} TEXT")
        conn.commit()
    finally:
        conn.close()


# Headings glued on by the CTĐT scan ("Kiến thức Nghiệp vụ sư phạm ...").
_NAME_HEADINGS = (
    "kiến thức thực tập và khóa luận tốt nghiệp",
    "kiến thức thực tập và đồ án tốt nghiệp",
    "kiến thức nghiệp vụ sư phạm",
    "kiến thức cơ sở ngành",
    "kiến thức chuyên ngành",
    "kiến thức cơ sở",
    "kiến thức đại cương",
    "kiến thức thực tập",
    "nghiệp vụ sư phạm",
    "cơ sở ngành",
    "chuyên ngành",
)


def clean_course_name(name: str) -> str:
    """Drop a curriculum-block heading stuck to the front of a subject name."""
    text = " ".join((name or "").split())
    if not text:
        return text
    heads = sorted((no_accent_vietnamese(h).lower() for h in _NAME_HEADINGS), key=len, reverse=True)
    changed = True
    while changed and text:
        changed = False
        folded = no_accent_vietnamese(text).lower()
        for head in heads:
            if folded.startswith(head + " ") or folded == head:
                text = text[len(head):].strip()
                text = re.sub(r"^\d+\s+", "", text)
                changed = True
                break
    return text or " ".join((name or "").split())


def _read_csv(path):
    if not os.path.exists(path):
        return []
    with open(path, 'r', encoding='utf-8-sig') as f:
        return list(csv.DictReader(f))


def seed_from_csv(csv_path=SEED_CSV, ued_csv=UED_CSV):
    global _cache
    init_db()
    conn = get_db()
    try:
        conn.execute("DELETE FROM hoc_phan")
        conn.execute("DELETE FROM danh_muc_mon")
        n_hp = 0
        for r in _read_csv(ued_csv):
            conn.execute("INSERT OR IGNORE INTO hoc_phan (ma_hp,ten_mon,tin_chi,khoa,khoa_cu,nganh,nguon) VALUES (?,?,?,?,?,?,?)",
                         (r['ma_hp'] or None, clean_course_name(r['ten_mon']),
                          int(r['tin_chi']) if r['tin_chi'] else None,
                          r['khoa'], r.get('khoa_cu', ''), r['nganh'], r['nguon']))
            n_hp += 1
        # original list (khoa Tin) kept as-is
        for r in _read_csv(csv_path):
            try:
                tc = int(float(r.get('tin_chi') or 3))
            except ValueError:
                tc = 3
            conn.execute("INSERT OR IGNORE INTO hoc_phan (ma_hp,ten_mon,tin_chi,khoa,khoa_cu,nganh,nguon) VALUES (?,?,?,?,?,?,?)",
                         (None, clean_course_name(r['ten_mon']), tc, 'Toán – Tin', 'Tin học', 'Danh sách gốc (repo)', 'repo gốc'))
        # unique-name view used by fuzzy matching
        groups = defaultdict(list)
        for row in conn.execute("SELECT * FROM hoc_phan"):
            groups[row['ten_mon']].append(row)
        for name, rows in groups.items():
            credits = Counter(r['tin_chi'] for r in rows if r['tin_chi'] is not None)
            tc = credits.most_common(1)[0][0] if credits else 3
            codes = Counter(r['ma_hp'] for r in rows if r['ma_hp'])
            khoa = Counter(r['khoa'] for r in rows if r['khoa'])
            kcu = Counter(r['khoa_cu'] for r in rows if r['khoa_cu'])
            conn.execute("INSERT OR REPLACE INTO danh_muc_mon (ten_mon,tin_chi,ma_hp,khoa,so_nganh,khoa_cu) VALUES (?,?,?,?,?,?)",
                         (name, tc, codes.most_common(1)[0][0] if codes else None,
                          khoa.most_common(1)[0][0] if khoa else None,
                          str(len({r['nganh'] for r in rows})),
                          kcu.most_common(1)[0][0] if kcu else None))
        conn.commit()
        total = conn.execute("SELECT COUNT(*) FROM danh_muc_mon").fetchone()[0]
    finally:
        conn.close()
    _cache = None
    clear_lookup_cache()
    print(f"[db] Seed: {n_hp} dòng học phần UED, {total} môn (tên duy nhất) vào {DB_PATH}")
    return total


def all_subjects():
    """Cached list of dicts with precomputed normalized names for fuzzy matching."""
    global _cache
    if _cache is None:
        from utils import normalize
        conn = get_db()
        try:
            rows = conn.execute("SELECT ten_mon, tin_chi, ma_hp, khoa, khoa_cu FROM danh_muc_mon").fetchall()
        finally:
            conn.close()
        cleaned = []
        seen = set()
        for r in rows:
            name = clean_course_name(r['ten_mon'])
            if name in seen:
                continue
            seen.add(name)
            cleaned.append(dict(ten_mon=name, tin_chi=r['tin_chi'], ma_hp=r['ma_hp'], khoa=r['khoa'], khoa_cu=r['khoa_cu'],
                                norm=normalize(name)))
        _cache = cleaned
    return _cache


def by_code(code):
    conn = get_db()
    try:
        r = conn.execute("SELECT ten_mon, tin_chi FROM hoc_phan WHERE ma_hp=? LIMIT 1", (code,)).fetchone()
        if not r:
            return None
        hit = dict(r)
        hit['ten_mon'] = clean_course_name(hit['ten_mon'])
        return hit
    finally:
        conn.close()


def stats():
    conn = get_db()
    try:
        return {
            'subjects': conn.execute("SELECT COUNT(*) FROM danh_muc_mon").fetchone()[0],
            'rows': conn.execute("SELECT COUNT(*) FROM hoc_phan").fetchone()[0],
            'codes': conn.execute("SELECT COUNT(DISTINCT ma_hp) FROM hoc_phan WHERE ma_hp IS NOT NULL").fetchone()[0],
            'faculties': [dict(khoa=r[0], nganh=r[1], so_mon=r[2]) for r in conn.execute(
                "SELECT khoa, COUNT(DISTINCT nganh), COUNT(DISTINCT ten_mon) FROM hoc_phan GROUP BY khoa ORDER BY khoa")],
            'faculties_old': [dict(khoa=r[0], nganh=r[1], so_mon=r[2]) for r in conn.execute(
                "SELECT khoa_cu, COUNT(DISTINCT nganh), COUNT(DISTINCT ten_mon) FROM hoc_phan WHERE khoa_cu<>'' GROUP BY khoa_cu ORDER BY khoa_cu")],
        }
    finally:
        conn.close()


_lookup_cache = {}
_course_index = None


def _build_course_index():
    from utils import normalize
    conn = get_db()
    try:
        rows = conn.execute(
            """SELECT ma_hp, ten_mon, tin_chi, khoa, nganh FROM hoc_phan
               WHERE nganh IS NOT NULL AND nganh != '' AND nganh != 'Danh sách gốc (repo)'"""
        ).fetchall()
    finally:
        conn.close()
    grouped = {}
    for row in rows:
        name = clean_course_name(row["ten_mon"])
        item = grouped.get(name)
        if item is None:
            item = {
                "ten_mon": name,
                "ma_hp": row["ma_hp"] or "",
                "tin_chi": row["tin_chi"],
                "khoa": row["khoa"] or "",
                "programs": [],
                "norm": normalize(name),
                "code": str(row["ma_hp"] or "").lower(),
            }
            grouped[name] = item
        if row["ma_hp"] and not item["ma_hp"]:
            item["ma_hp"] = row["ma_hp"]
            item["code"] = str(row["ma_hp"]).lower()
        program = row["nganh"]
        if program and program not in item["programs"]:
            item["programs"].append(program)
    return list(grouped.values())


def course_index():
    global _course_index
    if _course_index is None:
        _course_index = _build_course_index()
    return _course_index


def lookup_courses(query, limit=12):
    """Accent-insensitive lookup. Results are cached in this process."""
    from utils import normalize
    q = normalize(query)
    if len(q) < 2:
        return []
    limit = max(1, min(int(limit or 12), 20))
    key = (q, limit)
    cached = _lookup_cache.get(key)
    if cached is not None:
        return cached
    rows = course_index()
    found = [row for row in rows if q in row["norm"] or (row["code"] and q in row["code"])]
    found.sort(key=lambda row: (not row["norm"].startswith(q), len(row["norm"]), row["ten_mon"]))
    if len(found) < limit:
        try:
            from rapidfuzz import fuzz, process
            seen = {row["ten_mon"] for row in found}
            for _match, score, idx in process.extract(q, [row["norm"] for row in rows], scorer=fuzz.WRatio, limit=limit * 2):
                row = rows[idx]
                if score >= 86 and row["ten_mon"] not in seen:
                    found.append(row)
                    seen.add(row["ten_mon"])
        except ImportError:
            pass
    out = [{
        "ten_mon": row["ten_mon"],
        "ma_hp": row["ma_hp"],
        "tin_chi": row["tin_chi"],
        "khoa": row["khoa"],
        "programs": row["programs"][:6],
        "program_count": len(row["programs"]),
    } for row in found[:limit]]
    if len(_lookup_cache) > 64:
        _lookup_cache.clear()
    _lookup_cache[key] = out
    return out


def clear_lookup_cache():
    global _course_index
    _lookup_cache.clear()
    _course_index = None


def search_subjects(query, limit=20, khoa=None):
    """Accent-insensitive substring + fuzzy search (rapidfuzz)."""
    from utils import normalize
    q = normalize(query)
    if not q:
        return []
    subs = all_subjects()
    if khoa:
        subs = [s for s in subs if khoa in (s['khoa'], s['khoa_cu'])]
    out = [s for s in subs if q in s['norm']]
    out.sort(key=lambda s: (not s['norm'].startswith(q), len(s['norm'])))
    if len(out) < limit:
        try:
            from rapidfuzz import process, fuzz
            seen = {s['ten_mon'] for s in out}
            for _, score, idx in process.extract(q, [s['norm'] for s in subs], scorer=fuzz.WRatio, limit=limit * 2):
                if score >= 86 and subs[idx]['ten_mon'] not in seen:
                    out.append(subs[idx]); seen.add(subs[idx]['ten_mon'])
        except ImportError:
            pass
    return [{'ten_mon': s['ten_mon'], 'tin_chi': s['tin_chi'], 'ma_hp': s['ma_hp'],
             'khoa': s['khoa'] + (f" (cũ: {s['khoa_cu']})" if s['khoa_cu'] else '') if s['khoa'] else s['khoa']}
            for s in out[:limit]]
