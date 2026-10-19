"""Transactional international-data loading, without changing existing tables."""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from metadata_store import ensure_metadata, upsert_source, log_import
import sqlite3, hashlib, json, time
from datetime import datetime, timezone
import requests

ROOT = Path(__file__).resolve().parents[1]
CONFIG = json.loads((ROOT / '..' / 'config' / 'international.json').read_text(encoding='utf-8'))
DEFAULT_DB = ROOT / '..' / 'data' / 'estonia_migration.sqlite'
    
def get_json(url, params):
    with requests.Session() as s:
        s.headers.update({'User-Agent': 'EstoniaMigrationResearch/1.0 (academic data ingestion)'})
        for attempt in range(5):
            try:
                r = s.get(url, params=params, timeout=(15, 120))
                if r.status_code in (429, 500, 502, 503, 504):
                    raise requests.HTTPError(f'HTTP {r.status_code}', response=r)
                r.raise_for_status()
                return r.json(), r.url
            except (requests.RequestException, ValueError):
                if attempt == 4: raise
                time.sleep(min(2**attempt, 15))

def identifier(name):
    if not name.replace('_','').isalnum() or not name[0].isalpha():
        raise ValueError(f'Invalid SQL identifier {name!r}')
    return '"' + name + '"'

def publish(db, table, ddl, rows, insert_sql, provider, dataset, source_url, config, metadata=None):
    """Atomic replace of only the requested destination table and its import manifest."""
    if not rows: raise ValueError('Refusing to replace table with zero rows')
    db = Path(db)
    if not db.parent.exists(): db.parent.mkdir(parents=True)
    stamp = datetime.now(timezone.utc).isoformat()
    config_json = json.dumps(config, sort_keys=True, ensure_ascii=False)
    metadata_json = json.dumps(metadata or {}, sort_keys=True, ensure_ascii=False)
    with sqlite3.connect(db, timeout=30) as con:
        con.execute('PRAGMA foreign_keys=ON')
        con.execute('BEGIN IMMEDIATE')
        ensure_metadata(con)
        # Drop only named international table, never any original data.
        con.execute('DROP TABLE IF EXISTS ' + identifier(table))
        con.execute(ddl)
        con.executemany(insert_sql, rows)
        n = con.execute('SELECT COUNT(*) FROM '+identifier(table)).fetchone()[0]
        if n != len(rows): raise ValueError('Inserted count mismatch')
        upsert_source(con, table.upper(), provider, table, source_url, None,
                      n, n, None, 0, stamp)
        log_import(con, table.upper(), provider, table, 'api', 'complete', n,
                   source_url, {'config_json': config_json, 'metadata_json': metadata_json}, stamp)
        con.commit()
    return n
