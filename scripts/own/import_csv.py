"""Import an official CSV export into the project's existing SQLite database.

Example:
  python scripts/import_csv.py data/downloads/NH01.csv --dataset NH01

Preserves CSV values as TEXT; does not silently clean statistical markers.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import re
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / '..' / 'config' / 'datasets.json'
DEFAULT_DB = ROOT / '..' / 'data' / 'estonia_migration.sqlite'


def identifier(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


def read_csv(path: Path, delimiter: str | None):
    raw = path.read_bytes()
    if not raw:
        raise ValueError('CSV is empty')
    decoded = None
    encoding = None
    for encoding_candidate in ('utf-8-sig', 'cp1257', 'cp1252'):
        try:
            decoded = raw.decode(encoding_candidate)
            encoding = encoding_candidate
            break
        except UnicodeDecodeError:
            continue
    if decoded is None:
        raise ValueError('Cannot decode CSV; convert it to UTF-8 first')
    sample = decoded[:32768]
    if delimiter is None:
        try:
            delimiter = csv.Sniffer().sniff(sample, delimiters=',;\t|').delimiter
        except csv.Error:
            delimiter = ';' if sample.splitlines()[0].count(';') > sample.splitlines()[0].count(',') else ','
    # Skip optional PxWeb title rows before the actual CSV header.
    reader = csv.reader(io.StringIO(decoded, newline=''), delimiter=delimiter)
    header = None
    records = []
    for row in reader:
        if not row or all(not x.strip() for x in row):
            continue
        if header is None:
            if len(row) == 1 and re.match(r'^[A-Za-z][A-Za-z0-9_]*:', row[0].strip()):
                continue
            if len(row) < 2:
                raise ValueError('Expected CSV header with at least two columns')
            header = row
            if any(not h.strip() for h in header):
                raise ValueError('CSV contains an empty column name')
            if len(set(header)) != len(header):
                raise ValueError('CSV contains duplicate column names')
            continue
        if len(row) != len(header):
            raise ValueError(f'CSV line {reader.line_num}: {len(row)} values, expected {len(header)}')
        records.append(tuple(row))
    if header is None:
        raise ValueError('CSV has no header')
    if not records:
        raise ValueError('CSV contains no data rows')
    return header, records, raw, encoding, delimiter


def main():
    parser = argparse.ArgumentParser(description='Import CSV into the current project SQLite database')
    parser.add_argument('csv_file', type=Path)
    parser.add_argument('--dataset', default='NH01', help='Dataset key from config/datasets.json (default: NH01)')
    parser.add_argument('--db', type=Path, default=DEFAULT_DB)
    parser.add_argument('--delimiter', choices=[',', ';', '\t', '|'])
    parser.add_argument('--replace', action='store_true', help='Allow replacing an already loaded table')
    args = parser.parse_args()
    config = json.loads(CONFIG.read_text(encoding='utf-8'))
    code = args.dataset.upper()
    if code not in config['tables']:
        parser.error(f'Unknown dataset {code} in {CONFIG}')
    entry = config['tables'][code]
    table = entry['sqlite_table']
    cols, records, raw, encoding, delimiter = read_csv(args.csv_file, args.delimiter)
    args.db.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(args.db)
    try:
        conn.execute('PRAGMA busy_timeout = 5000')
        existing = conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)).fetchone()
        if existing and not args.replace:
            raise RuntimeError(f'{table} already exists. Use --replace explicitly to overwrite it.')
        conn.execute('BEGIN IMMEDIATE')
        conn.execute('''CREATE TABLE IF NOT EXISTS dataset_registry (
            table_code TEXT PRIMARY KEY, sqlite_table TEXT NOT NULL UNIQUE,
            provider TEXT NOT NULL, source_url TEXT NOT NULL, ui_url TEXT NOT NULL,
            records INTEGER NOT NULL, possible_cells INTEGER NOT NULL,
            retrieved_at_utc TEXT NOT NULL, metadata_sha256 TEXT NOT NULL,
            partial_years INTEGER NOT NULL)''')
        conn.execute('''CREATE TABLE IF NOT EXISTS csv_import_log (
            id INTEGER PRIMARY KEY, table_code TEXT NOT NULL, imported_at_utc TEXT NOT NULL,
            csv_sha256 TEXT NOT NULL, file_name TEXT NOT NULL, row_count INTEGER NOT NULL,
            encoding TEXT NOT NULL, delimiter TEXT NOT NULL)''')
        staging = '__csv_stage_' + re.sub(r'[^a-z0-9_]', '_', table.lower())
        conn.execute(f'DROP TABLE IF EXISTS {identifier(staging)}')
        conn.execute(f'CREATE TABLE {identifier(staging)} (' + ', '.join(f'{identifier(c)} TEXT' for c in cols) + ')')
        placeholders = ','.join('?' for _ in cols)
        conn.executemany(f'INSERT INTO {identifier(staging)} VALUES ({placeholders})', records)
        count = conn.execute(f'SELECT COUNT(*) FROM {identifier(staging)}').fetchone()[0]
        assert count == len(records)
        if existing:
            conn.execute(f'DROP TABLE {identifier(table)}')
        conn.execute(f'ALTER TABLE {identifier(staging)} RENAME TO {identifier(table)}')
        now = datetime.now(timezone.utc).isoformat()
        digest = hashlib.sha256(raw).hexdigest()
        conn.execute('''INSERT INTO dataset_registry
            (table_code, sqlite_table, provider, source_url, ui_url, records,
             possible_cells, retrieved_at_utc, metadata_sha256, partial_years)
            VALUES (?,?,?,?,?,?,?,?,?,?)
            ON CONFLICT(table_code) DO UPDATE SET
            sqlite_table=excluded.sqlite_table, provider=excluded.provider,
            source_url=excluded.source_url, ui_url=excluded.ui_url,
            records=excluded.records, possible_cells=excluded.possible_cells,
            retrieved_at_utc=excluded.retrieved_at_utc,
            metadata_sha256=excluded.metadata_sha256,
            partial_years=excluded.partial_years''',
            (code, table, entry['provider'], args.csv_file.resolve().as_uri(),
             entry.get('ui_url', ''), count, count, now, digest, 1))
        conn.execute('''INSERT INTO csv_import_log
            (table_code, imported_at_utc, csv_sha256, file_name, row_count, encoding, delimiter)
            VALUES (?,?,?,?,?,?,?)''',
            (code, now, digest, args.csv_file.name, count, encoding, delimiter))
        conn.commit()
        print(f'Imported {count} rows into {table} ({args.db})')
        print(f'CSV SHA-256: {digest}')
        print('Completeness: NOT VERIFIED (dataset_registry.partial_years=1).')
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


if __name__ == '__main__':
    main()
