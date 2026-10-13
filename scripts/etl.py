"""Unified PxWeb ETL for Statistics Estonia migration, extra tables and TAI.
Uses config/datasets.json. Original migration names are retained.
"""
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import re
import sqlite3
from datetime import datetime, timezone

import pandas as pd
import requests

import io
import time

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


MAX_CELLS = 15000

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




ROOT = Path(__file__).resolve().parents[1]
CONFIG = json.loads((ROOT / 'config' / 'datasets.json').read_text(encoding='utf-8'))
DEFAULT_DB = ROOT / 'data' / 'estonia_migration.sqlite'
STAT_BASE = 'https://andmed.stat.ee/api/v1/en/stat'


def candidates(code, entry):
    if entry['provider'] == 'statistics_estonia':
        return [f'{STAT_BASE}/{code}']
    overridden = os.getenv('TAI_NH01_API_URL')
    return ([overridden] if overridden else []) + entry['api_candidates']


def discover(session, code, entry):
    errors = []
    for url in candidates(code, entry):
        try:
            response = fetch(session, 'GET', url)
            meta = response.json()
            if not isinstance(meta, dict) or not meta.get('variables'):
                raise ValueError('Metadata without variables')
            for v in meta['variables']:
                if not v.get('code') or not v.get('values'):
                    raise ValueError('Variable without code/values')
                if len(v['values']) != len(v.get('valueTexts', [])):
                    raise ValueError('Metadata value codes/labels misaligned')
            return url, meta
        except (requests.RequestException, ValueError) as exc:
            errors.append(f'{url}: {str(exc)[:140]}')
    raise RuntimeError(f'{code}: no working API endpoint. Set TAI_NH01_API_URL if needed.\n' + '\n'.join(errors))


def year_limit(v, n):
    if n is None:
        return v
    # Quarterly EH045 periods usually are not marked time:true, so use value labels as well.
    values = v['values']
    labels = v['valueTexts']
    if v.get('time') or (len(labels) > 2 and sum(bool(re.search(r'\b(?:19|20)\d{2}\b', str(s))) for s in labels) >= len(labels) * .7):
        years = []
        for code, label in zip(values, labels):
            match = re.search(r'\b(?:19|20)\d{2}\b', str(label)) or re.search(r'\b(?:19|20)\d{2}\b', str(code))
            years.append(int(match.group()) if match else None)
        distinct = sorted({y for y in years if y is not None})
        if distinct:
            allowed = set(distinct[-n:])
            v = dict(v)
            v['values'] = [code for code, y in zip(values, years) if y in allowed]
            v['valueTexts'] = [label for label, y in zip(labels, years) if y in allowed]
    return v


def initialise(con):
    con.execute('''CREATE TABLE IF NOT EXISTS extra_source_registry (
      table_code TEXT PRIMARY KEY, provider TEXT NOT NULL, source_url TEXT NOT NULL,
      ui_url TEXT NOT NULL, row_count INTEGER NOT NULL, possible_cells INTEGER NOT NULL,
      batches INTEGER NOT NULL, retrieved_at_utc TEXT NOT NULL, metadata_sha256 TEXT NOT NULL,
      partial_years INTEGER NOT NULL DEFAULT 0)''')
    con.execute('''CREATE TABLE IF NOT EXISTS extra_load_log (
      id INTEGER PRIMARY KEY, table_code TEXT NOT NULL, loaded_at_utc TEXT NOT NULL,
      success INTEGER NOT NULL, message TEXT NOT NULL)''')
    con.execute('''CREATE TABLE IF NOT EXISTS source_registry (
      table_code TEXT PRIMARY KEY, records INTEGER NOT NULL,
      retrieved_at_utc TEXT NOT NULL, source_url TEXT NOT NULL)''')
    con.execute('''CREATE TABLE IF NOT EXISTS dataset_registry (
      table_code TEXT PRIMARY KEY, sqlite_table TEXT NOT NULL UNIQUE,
      provider TEXT NOT NULL, source_url TEXT NOT NULL, ui_url TEXT NOT NULL,
      records INTEGER NOT NULL, possible_cells INTEGER NOT NULL,
      retrieved_at_utc TEXT NOT NULL, metadata_sha256 TEXT NOT NULL,
      partial_years INTEGER NOT NULL)''')
    con.commit()


def replace_table(con, code, entry, url, meta, session, latest, limit):
    full_meta = json.dumps(meta, sort_keys=True, ensure_ascii=False).encode('utf-8')
    sha = hashlib.sha256(full_meta).hexdigest()
    metadata_dir = ROOT / 'data' / 'metadata'
    metadata_dir.mkdir(parents=True, exist_ok=True)
    (metadata_dir / f'{code}.json').write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding='utf-8')
    variables = [year_limit(dict(v), latest) for v in meta['variables']]
    if any(not v['values'] for v in variables):
        raise ValueError(f'{code}: no selected values')
    count = math.prod(len(v['values']) for v in variables)
    print(f'{code}: {count:,} requested possible cells ({url})', flush=True)
    name = entry['sqlite_table']
    staging = f'_staging_{name}'
    con.execute(f'DROP TABLE IF EXISTS "{staging}"')
    con.commit()
    rows, batches, column_signature = 0, 0, None
    retrieved_at = datetime.now(timezone.utc).isoformat()
    try:
        for selection in chunks(variables, limit=limit):
            query = {'query': [{'code': v['code'], 'selection': {'filter': 'item', 'values': selection[v['code']]}} for v in variables], 'response': {'format': 'csv2'}}
            response = fetch(session, 'POST', url, json=query)
            frame = csv_frame(response)
            batches += 1
            if frame.empty:
                continue
            columns = [str(c).strip() for c in frame.columns]
            if len(columns) != len(set(columns)) or any(not c for c in columns):
                raise ValueError(f'{code}: duplicate/empty columns')
            if column_signature is None:
                column_signature = columns
            if columns != column_signature:
                raise ValueError(f'{code}: schema changed during chunked download')
            # Preserve original labelled values and missing-value markers.
            frame.columns = columns
            if entry.get('add_provenance'):
                frame['source_table'] = code
                frame['retrieved_at_utc'] = retrieved_at
            frame.to_sql(staging, con, if_exists='append', index=False, chunksize=1000)
            rows += len(frame)
            print(f'  batch {batches}: {len(frame):,} rows; total {rows:,}', flush=True)
        if rows > count:
            raise ValueError(f'{code}: returned rows {rows} exceed requested cells {count}')
        if rows == 0:
            raise ValueError(f'{code}: no data returned; original table retained')
        now = datetime.now(timezone.utc).isoformat()
        con.execute('BEGIN IMMEDIATE')
        con.execute(f'DROP TABLE IF EXISTS "{name}"')
        con.execute(f'ALTER TABLE "{staging}" RENAME TO "{name}"')
        con.execute('''INSERT INTO extra_source_registry
          (table_code, provider, source_url, ui_url, row_count, possible_cells, batches, retrieved_at_utc, metadata_sha256, partial_years)
          VALUES (?,?,?,?,?,?,?,?,?,?)
          ON CONFLICT(table_code) DO UPDATE SET
          provider=excluded.provider, source_url=excluded.source_url, ui_url=excluded.ui_url,
          row_count=excluded.row_count, possible_cells=excluded.possible_cells,
          batches=excluded.batches, retrieved_at_utc=excluded.retrieved_at_utc,
          metadata_sha256=excluded.metadata_sha256, partial_years=excluded.partial_years''',
          (code, entry['provider'], url, entry['ui_url'], rows, count, batches, now, sha, int(latest is not None)))
        # Maintain legacy migration registry for existing consumers.
        if entry.get('add_provenance'):
            con.execute('''INSERT INTO source_registry(table_code,records,retrieved_at_utc,source_url)
                VALUES(?,?,?,?) ON CONFLICT(table_code) DO UPDATE SET
                records=excluded.records,retrieved_at_utc=excluded.retrieved_at_utc,
                source_url=excluded.source_url''', (code, rows, now, url))
        con.execute('''INSERT INTO dataset_registry
          (table_code,sqlite_table,provider,source_url,ui_url,records,possible_cells,
           retrieved_at_utc,metadata_sha256,partial_years)
          VALUES(?,?,?,?,?,?,?,?,?,?) ON CONFLICT(table_code) DO UPDATE SET
          sqlite_table=excluded.sqlite_table,provider=excluded.provider,
          source_url=excluded.source_url,ui_url=excluded.ui_url,
          records=excluded.records,possible_cells=excluded.possible_cells,
          retrieved_at_utc=excluded.retrieved_at_utc,
          metadata_sha256=excluded.metadata_sha256,partial_years=excluded.partial_years''',
          (code,name,entry['provider'],url,entry['ui_url'],rows,count,now,sha,int(latest is not None)))
        con.commit()
        return rows
    except Exception:
        con.rollback()
        con.execute(f'DROP TABLE IF EXISTS "{staging}"')
        con.commit()
        raise


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--tables', nargs='+', choices=list(CONFIG['tables']), default=list(CONFIG['tables']))
    p.add_argument('--latest-years', type=int, help='Smoke test only: N most recent years (quarters included for EH045)')
    p.add_argument('--max-cells', type=int, default=CONFIG['max_cells_per_request'])
    p.add_argument('--db', type=Path, default=DEFAULT_DB)
    p.add_argument('--metadata-only', action='store_true', help='Check API endpoints and save metadata without editing database')
    args = p.parse_args()
    if args.latest_years is not None and args.latest_years < 1 or args.max_cells < 1:
        p.error('latest-years and max-cells must be positive')
    if not args.metadata_only:
        args.db.parent.mkdir(parents=True, exist_ok=True)
    with requests.Session() as session:
        session.headers.update({'User-Agent':'EstoniaMigrationStudentResearch/0.2 (academic PxWeb client)'})
        con = sqlite3.connect(args.db) if not args.metadata_only else None
        try:
            if con:
                initialise(con)
            for code in args.tables:
                entry = CONFIG['tables'][code]
                try:
                    url, meta = discover(session, code, entry)
                    if args.metadata_only:
                        directory = ROOT / 'data' / 'metadata'
                        directory.mkdir(parents=True, exist_ok=True)
                        (directory / f'{code}.json').write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding='utf-8')
                        print(f'{code}: metadata OK at {url}')
                    else:
                        rows = replace_table(con, code, entry, url, meta, session, args.latest_years, args.max_cells)
                        con.execute('INSERT INTO extra_load_log(table_code,loaded_at_utc,success,message) VALUES (?,?,1,?)', (code, datetime.now(timezone.utc).isoformat(), f'{rows} rows'))
                        con.commit()
                except Exception as exc:
                    if con:
                        con.execute('INSERT INTO extra_load_log(table_code,loaded_at_utc,success,message) VALUES (?,?,0,?)', (code, datetime.now(timezone.utc).isoformat(), str(exc)[:1000]))
                        con.commit()
                    print(f'FAILED {code}: {exc}', flush=True)
                    raise
        finally:
            if con:
                con.close()
    print('Finished. Database:', args.db if not args.metadata_only else 'unchanged')


if __name__ == '__main__':
    main()
