# -*- coding: utf-8 -*-
"""
Database layer — SQLite (zero-config, Docker-friendly).

Replaces the original SQL Server / pyodbc setup. The schema is identical
to the original `OCR_Grade` database:

    danh_muc_mon(ten_mon TEXT PRIMARY KEY, tin_chi INTEGER)

Set DB_PATH (default: ./grade.db) to point at your database file.
Seed data lives in data/danh_muc_mon.csv — extend it with your own
subject list and run `python seed_db.py` to rebuild.
"""
import csv
import os
import sqlite3

DB_PATH = os.environ.get('DB_PATH', os.path.join(os.path.dirname(os.path.abspath(__file__)), 'grade.db'))
SEED_CSV = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data', 'danh_muc_mon.csv')


def _ensure_db_dir():
    """Create the parent directory of DB_PATH if missing (e.g. /app/data in Docker)."""
    d = os.path.dirname(DB_PATH)
    if d:
        os.makedirs(d, exist_ok=True)


def get_db():
    """Open a connection to the SQLite database (mirrors original get_db_connection())."""
    _ensure_db_dir()
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Create the danh_muc_mon table if it does not exist yet."""
    conn = get_db()
    try:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS danh_muc_mon (
                ten_mon  TEXT PRIMARY KEY,
                tin_chi  INTEGER NOT NULL DEFAULT 3
            )
        """)
        conn.commit()
    finally:
        conn.close()


def seed_from_csv(csv_path=SEED_CSV):
    """Load subjects from CSV (ten_mon,tin_chi) — INSERT OR REPLACE so it is idempotent."""
    if not os.path.exists(csv_path):
        print(f"[db] Không tìm thấy {csv_path} — bỏ qua seed.")
        return 0
    conn = get_db()
    count = 0
    try:
        with open(csv_path, 'r', encoding='utf-8-sig') as f:
            reader = csv.reader(f)
            header = next(reader, None)  # skip header if present
            if header and header[0].strip().lower() not in ('ten_mon', 'subject', 'ten'):
                # no header -> rewind
                f.seek(0)
                reader = csv.reader(f)
                header = None
            for row in reader:
                if not row or not row[0].strip():
                    continue
                try:
                    credit = int(float(row[1])) if len(row) > 1 and row[1].strip() else 3
                except ValueError:
                    credit = 3
                conn.execute("INSERT OR REPLACE INTO danh_muc_mon (ten_mon, tin_chi) VALUES (?, ?)",
                             (row[0].strip(), credit))
                count += 1
        conn.commit()
    finally:
        conn.close()
    print(f"[db] Đã seed {count} môn học vào {DB_PATH}")
    return count


def all_subjects():
    """(ten_mon, tin_chi) for every subject — used by auto_correct_universal."""
    conn = get_db()
    try:
        cur = conn.execute("SELECT ten_mon, tin_chi FROM danh_muc_mon")
        return cur.fetchall()
    finally:
        conn.close()


def search_subjects(query, limit=20):
    """Accent-insensitive LIKE search (mirrors the original SQL Server CI/AI collation)."""
    from utils import no_accent_vietnamese
    q = query.strip().lower()
    if not q:
        return []
    q_norm = no_accent_vietnamese(q)
    conn = get_db()
    try:
        rows = conn.execute("SELECT ten_mon, tin_chi FROM danh_muc_mon").fetchall()
    finally:
        conn.close()
    out = []
    for r in rows:
        name = r['ten_mon']
        if q in name.lower() or q_norm in no_accent_vietnamese(name).lower():
            out.append({'ten_mon': name, 'tin_chi': r['tin_chi']})
            if len(out) >= limit:
                break
    return out
