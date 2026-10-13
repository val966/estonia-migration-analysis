"""Validate unified SQLite snapshots and optionally prepare release manifest.

Examples:
  python scripts/validate.py
  python scripts/validate.py --require-all --require-full --release
"""
import argparse
import hashlib
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONFIG = json.loads((ROOT / 'config' / 'datasets.json').read_text(encoding='utf-8'))
DEFAULT_DB = ROOT / 'data' / 'estonia_migration.sqlite'


def quote_identifier(identifier):
    return '"' + identifier.replace('"', '""') + '"'


def validate_database(db_path, require_all=False, require_full=False):
    path = Path(db_path).resolve()
    if not path.is_file():
        raise ValueError(f'Missing SQLite file: {path}')
    # Immutable opens do not read hot rollback journals. Use ordinary read-only mode.
    with sqlite3.connect(path.as_uri() + '?mode=ro', uri=True) as con:
        integrity = con.execute('PRAGMA integrity_check').fetchone()[0]
        if integrity != 'ok':
            raise ValueError(f'PRAGMA integrity_check: {integrity}')
        tables = {r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        registries = {}
        if 'dataset_registry' in tables:
            cols = ('table_code', 'sqlite_table', 'provider', 'source_url', 'ui_url',
                    'records', 'possible_cells', 'retrieved_at_utc', 'metadata_sha256', 'partial_years')
            registries = {r[0]: dict(zip(cols, r)) for r in con.execute('SELECT '+','.join(cols)+' FROM dataset_registry')}
        # In older databases the data tables may exist but are not yet unified.
        findings = {}
        failures = []
        for code, entry in CONFIG['tables'].items():
            table = entry['sqlite_table']
            if code not in registries:
                findings[code] = {'table': table, 'status': 'not_loaded'}
                if require_all:
                    failures.append(f'{code}: no dataset_registry record (run unified ETL)')
                continue
            registry = registries[code]
            if registry['sqlite_table'] != table:
                failures.append(f'{code}: configured table does not match registry')
            if table not in tables:
                failures.append(f'{code}: missing SQLite table {table}')
                continue
            columns = [r[1] for r in con.execute('PRAGMA table_info('+quote_identifier(table)+')')]
            count = con.execute('SELECT COUNT(*) FROM '+quote_identifier(table)).fetchone()[0]
            if len(columns) < 2 or len(columns) != len(set(columns)):
                failures.append(f'{code}: invalid column schema')
            if count <= 0 or count != registry['records']:
                failures.append(f'{code}: actual rows {count}, registry {registry["records"]}')
            if registry['partial_years'] and require_full:
                failures.append(f'{code}: partial --latest-years load')
            if registry['provider'] != entry['provider']:
                failures.append(f'{code}: provider differs from config')
            findings[code] = {'table': table, 'status': 'loaded', 'rows': count,
                              'columns': columns, 'provider': registry['provider'],
                              'partial_years': bool(registry['partial_years'])}
        # Validate both legacy and additional registry when present, not only configured datasets.
        for registry_table, mapping in [('source_registry', [('table_code','records')]),
                                        ('extra_source_registry', [('table_code','row_count')])]:
            if registry_table not in tables:
                continue
            for code, rows in con.execute(f'SELECT table_code,{mapping[0][1]} FROM '+quote_identifier(registry_table)):
                table = code.lower() if registry_table == 'source_registry' else 'raw_'+code.lower()
                if table not in tables:
                    failures.append(f'{registry_table}: missing table {table}')
                else:
                    actual = con.execute('SELECT COUNT(*) FROM '+quote_identifier(table)).fetchone()[0]
                    if actual != rows:
                        failures.append(f'{registry_table}: {code} mismatch ({actual}!={rows})')
        report = {'generated_at_utc': datetime.now(timezone.utc).isoformat(),
                  'database': path.name, 'integrity_check': integrity, 'datasets': findings,
                  'errors': failures, 'status': 'ok' if not failures else 'failed'}
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--db', type=Path, default=DEFAULT_DB)
    parser.add_argument('--require-all', action='store_true', help='Require all configured datasets')
    parser.add_argument('--require-full', action='store_true', help='Reject smoke-test/partial-year datasets')
    parser.add_argument('--release', action='store_true', help='Write release report and SHA256SUMS; requires --require-all --require-full')
    parser.add_argument('--output-dir', type=Path, default=ROOT / 'release')
    args = parser.parse_args()
    if args.release and not (args.require_all and args.require_full):
        parser.error('--release requires --require-all and --require-full')
    try:
        report = validate_database(args.db, args.require_all, args.require_full)
        out = args.output_dir if args.release else ROOT / 'data'
        out.mkdir(parents=True, exist_ok=True)
        filename = 'validation_report.json' if args.release else 'validation_current.json'
        (out / filename).write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        print(json.dumps({'status': report['status'], 'errors': report['errors'],
                          'loaded_tables': sum(d['status']=='loaded' for d in report['datasets'].values())}, indent=2))
        print('Report:', out / filename)
        if report['errors']:
            raise ValueError('Validation failed; see report')
        if args.release:
            db = args.db.resolve()
            # WAL may contain uncheckpointed changes; refuse to hash an incomplete copy.
            if db.with_name(db.name+'-wal').exists():
                raise ValueError('SQLite WAL file exists; close writers and checkpoint before release')
            digest = hashlib.sha256(db.read_bytes()).hexdigest()
            (out / 'SHA256SUMS').write_text(f'{digest}  {db.name}\n', encoding='utf-8')
            print('SHA-256:', digest)
    except (OSError, sqlite3.Error, ValueError) as exc:
        parser.exit(1, f'ERROR: {exc}\n')


if __name__ == '__main__':
    main()
