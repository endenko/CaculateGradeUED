# -*- coding: utf-8 -*-
"""Build the SQLite database from data/danh_muc_mon.csv (idempotent)."""
from db import init_db, seed_from_csv

if __name__ == '__main__':
    init_db()
    seed_from_csv()
