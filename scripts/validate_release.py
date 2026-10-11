"""Validate SQLite snapshot; write reproducible integrity metadata."""
import argparse
import hashlib
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT = ROOT / 'data' / 'estonia_migration.sqlite'


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--db', type=Path, default=DEFAULT)
    p.add_argument('--output-dir', type=Path, default=ROOT / 'release')
    args = p.parse_args()
    db = args.db.resolve()
    if not db.is_file():
        p.error(f'Database does not exist: {db}; run scripts/download.py first')
    with sqlite3.connect(f'file:{db}?mode=ro', uri=True) as con:
        integrity = con.execute('PRAGMA integrity_check').fetchone()[0]
        tables = [r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name")]
        counts = {t: con.execute(f'SELECT COUNT(*) FROM "{t}"').fetchone()[0] for t in tables}
        schema = {t: [dict(zip(('cid','name','type','notnull','default','pk'), row)) for row in con.execute(f'PRAGMA table_info("{t}")')] for t in tables}
        registry = [dict(zip(('table_code','records','retrieved_at_utc','source_url'), row)) for row in con.execute('SELECT table_code, records, retrieved_at_utc, source_url FROM source_registry ORDER BY table_code')] if 'source_registry' in tables else []
    if integrity != 'ok':
        raise RuntimeError(f'Integrity test failed: {integrity}')
    if not registry:
        raise RuntimeError('No source registry; database may be empty')
    for r in registry:
        table = r['table_code'].lower()
        if table not in counts or counts[table] != r['records']:
            raise RuntimeError(f"Record-count mismatch: {table}")
    sha256 = hashlib.sha256()

    with db.open('rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            sha256.update(chunk)

    digest = sha256.hexdigest()
    
    out = args.output_dir.resolve()
    out.mkdir(parents=True, exist_ok=True)
    report = {'generated_at_utc': datetime.now(timezone.utc).isoformat(), 'file_name': db.name, 'size_bytes': db.stat().st_size, 'sha256': digest, 'integrity_check': integrity, 'row_counts': counts, 'schema': schema, 'source_registry': registry}
    (out / 'validation_report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    (out / 'SHA256SUMS').write_text(f'{digest}  {db.name}\n', encoding='utf-8')
    print(json.dumps({'integrity': integrity, 'sha256': digest, 'row_counts': counts}, indent=2))
    print('Reports in:', out)


if __name__ == '__main__':
    main()
