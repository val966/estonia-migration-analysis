"""Preview loaded SQLite tables and learn exact field names."""
import sqlite3
from pathlib import Path

DB = Path(__file__).resolve().parents[1] / 'data' / 'estonia_migration.sqlite'
with sqlite3.connect(DB) as conn:
    for (table,) in conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"):
        print('\n' + table)
        print('Columns:', [r[1] for r in conn.execute(f'PRAGMA table_info("{table}")')])
        print('Rows:', conn.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0])
        for row in conn.execute(f'SELECT * FROM "{table}" LIMIT 2'):
            print(row)
