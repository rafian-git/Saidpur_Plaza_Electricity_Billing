import sqlite3
import os
import sys

DB_NAME = 'database.db'
SQL_FILE = 'database.db.sql'


def main():
    if not os.path.exists(SQL_FILE):
        print(f"FATAL: SQL file '{SQL_FILE}' not found", file=sys.stderr)
        sys.exit(1)

    if os.path.exists(DB_NAME):
        os.remove(DB_NAME)

    conn = sqlite3.connect(DB_NAME)
    with open(SQL_FILE, 'r', encoding='utf-8') as f:
        conn.executescript(f.read())
    conn.commit()
    conn.close()
    print("SQL imported successfully ->", DB_NAME)


if __name__ == '__main__':
    main()
