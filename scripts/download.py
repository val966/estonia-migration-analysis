"""Download Estonian migration PxWeb tables into reproducible SQLite snapshots.

Usage: python scripts/download.py --tables RVR03 RVR05 RVR08 RVR051
For quick smoke test: python scripts/download.py --tables RVR03 --latest-years 2
"""
import argparse
import io
import json
import math
import re
import sqlite3
import time
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import requests

BASE = 'https://andmed.stat.ee/api/v1/en/stat'
ROOT = Path(__file__).resolve().parents[1]
DB = ROOT / 'data' / 'estonia_migration.sqlite'
META = ROOT / 'data' / 'metadata'
TABLES = ('RVR03', 'RVR05', 'RVR08', 'RVR051')
MAX_CELLS = 15000  # Conservative chunk size; API has request limits.


def fetch(session, method, url, **kwargs):
    for attempt in range(5):
        try:
            response = session.request(method, url, timeout=90, **kwargs)
            if response.status_code in (429, 500, 502, 503, 504):
                raise requests.HTTPError(f'{response.status_code}: {response.text[:200]}')
            response.raise_for_status()
            return response
        except (requests.RequestException, requests.HTTPError):
            if attempt == 4:
                raise
            time.sleep(min(2 ** attempt * 3, 30))


def chunks(variables, limit=MAX_CELLS):
    """Partition a Cartesian product so requests fit under a conservative cell limit."""
    batches = [{v['code']: list(v['values']) for v in variables}]
    while batches:
        b = batches.pop()
        total = math.prod(len(items) for items in b.values())
        if total <= limit:
            yield b
            continue
        candidates = [(len(items), code) for code, items in b.items() if len(items) > 1]
        if not candidates:
            raise ValueError('Unable to split oversized query')
        _, code = max(candidates)
        values = b[code]
        midpoint = len(values) // 2
        for subset in (values[:midpoint], values[midpoint:]):
            copy = dict(b)
            copy[code] = subset
            batches.append(copy)


def csv_frame(response):
    # PxWeb csv2 contains a header row and localized labels; pandas detects delimiter.
    data = response.content.decode('utf-8-sig')
    if not data.strip():
        return pd.DataFrame()
    try:
        result = pd.read_csv(io.StringIO(data), sep=None, engine='python', dtype=str,
                             keep_default_na=False)
    except Exception as exc:
        raise ValueError(f'CSV parsing failed: {data[:200]!r}') from exc
    if len(result.columns) < 2:
        raise ValueError(f'Unexpected CSV structure: {data[:200]!r}')
    return result


def sql_table(table):
    if table not in TABLES:
        raise ValueError('Unexpected table name')
    return table.lower()


def load_table(session, connection, table, latest_years=None):
    url = f'{BASE}/{table}'
    meta = fetch(session, 'GET', url).json()
    if not meta.get('variables'):
        raise ValueError(f'{table}: no variables found')
    META.mkdir(parents=True, exist_ok=True)
    (META / f'{table}.json').write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding='utf-8')
    variables = []
    for v in meta['variables']:
        v = dict(v)
        if latest_years is not None and v.get('time'):
            v['values'] = v['values'][-latest_years:]
        variables.append(v)
    print(f'{table}: {math.prod(len(v["values"]) for v in variables):,} possible cells')

    # Build replacement table in a transaction; no partial published tables.
    staging = f'_new_{sql_table(table)}'
    connection.execute(f'DROP TABLE IF EXISTS "{staging}"')
    rows = 0
    try:
        for part, selection in enumerate(chunks(variables), start=1):
            query = {
                'query': [{'code': v['code'], 'selection': {'filter': 'item', 'values': selection[v['code']]}}
                          for v in variables],
                'response': {'format': 'csv2'}
            }
            response = fetch(session, 'POST', url, json=query)
            frame = csv_frame(response)
            if frame.empty:
                continue
            frame.columns = [str(c).strip() for c in frame.columns]
            if len(set(frame.columns)) != len(frame.columns):
                raise ValueError(f'{table}: duplicate column names')
            frame['source_table'] = table
            frame['retrieved_at_utc'] = datetime.now(timezone.utc).isoformat()
            frame.to_sql(staging, connection, if_exists='append', index=False)
            rows += len(frame)
            print(f'  batch {part}: +{len(frame)} records')
        if not rows:
            raise ValueError(f'{table}: no rows obtained')
        connection.execute(f'DROP TABLE IF EXISTS "{sql_table(table)}"')
        connection.execute(f'ALTER TABLE "{staging}" RENAME TO "{sql_table(table)}"')
        connection.execute('''INSERT INTO source_registry (table_code, records, retrieved_at_utc, source_url)
            VALUES (?, ?, ?, ?) ON CONFLICT(table_code) DO UPDATE SET
            records=excluded.records, retrieved_at_utc=excluded.retrieved_at_utc,
            source_url=excluded.source_url''',
            (table, rows, datetime.now(timezone.utc).isoformat(), url))
        connection.commit()
    except Exception:
        connection.rollback()
        connection.execute(f'DROP TABLE IF EXISTS "{staging}"')
        connection.commit()
        raise
    print(f'Finished {table}: {rows:,} rows')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--tables', nargs='+', choices=TABLES, default=list(TABLES))
    parser.add_argument('--latest-years', type=int, default=None,
                        help='Only N latest years; omit for full available history')
    args = parser.parse_args()
    if args.latest_years is not None and args.latest_years < 1:
        parser.error('--latest-years must be positive')
    DB.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(DB) as con, requests.Session() as session:
        session.headers.update({'User-Agent': 'EstoniaMigrationStudentResearch/0.1'})
        con.execute('''CREATE TABLE IF NOT EXISTS source_registry (
            table_code TEXT PRIMARY KEY, records INTEGER NOT NULL,
            retrieved_at_utc TEXT NOT NULL, source_url TEXT NOT NULL)''')
        for table in args.tables:
            try:
                load_table(session, con, table, args.latest_years)
            except Exception as exc:
                print(f'FAILED {table}: {exc}')
                raise
    print('Database:', DB)


if __name__ == '__main__':
    main()
