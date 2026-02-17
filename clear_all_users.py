#!/usr/bin/env python3
"""Jednorazowe usunięcie wszystkich użytkowników (przed wdrożeniem). Użycie: python clear_all_users.py"""
from __future__ import annotations

import os
import sys

# Upewnij się, że katalog projektu jest na ścieżce
BASE = os.path.dirname(os.path.abspath(__file__))
if BASE not in sys.path:
    sys.path.insert(0, BASE)

from core.config import DATA_DIR
from core.persistence import init_persistence, ensure_kv_table, clear_all_users

def main():
    database_url = os.environ.get("DATABASE_URL")
    psycopg2_module = None
    if database_url:
        try:
            import psycopg2
            psycopg2_module = psycopg2
        except ImportError:
            pass
    init_persistence(data_dir=DATA_DIR, database_url=database_url, psycopg2_module=psycopg2_module)
    try:
        ensure_kv_table()
    except Exception:
        pass
    n = clear_all_users()
    print(f"Usunięto użytkowników: {n}")

if __name__ == "__main__":
    main()
