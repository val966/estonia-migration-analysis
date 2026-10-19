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
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from metadata_store import ensure_metadata, upsert_source, log_import

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
        ensure_metadata(conn)
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
        upsert_source(conn, code, entry['provider'], table, args.csv_file.resolve().as_uri(),
                      entry.get('ui_url', ''), count, count, digest, 1, now)
        log_import(conn, code, entry['provider'], table, 'csv', 'success', count,
                   args.csv_file.resolve().as_uri(),
                   {'csv_sha256': digest, 'file_name': args.csv_file.name,
                    'encoding': encoding, 'delimiter': delimiter,
                    'completeness': 'unverified'}, now)
        conn.commit()
        print(f'Imported {count} rows into {table} ({args.db})')
        print(f'CSV SHA-256: {digest}')
        print('Completeness: NOT VERIFIED (source_registry.partial_years=1).')
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


if __name__ == '__main__':
    main()
