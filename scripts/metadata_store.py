"""Shared metadata persistence for all ingestion methods."""
import json
import uuid
from datetime import datetime, timezone

def now_utc():
    return datetime.now(timezone.utc).isoformat()

def ensure_metadata(con):
    con.execute("""CREATE TABLE IF NOT EXISTS source_registry (
        table_code TEXT PRIMARY KEY, provider TEXT, sqlite_table TEXT,
        source_url TEXT, ui_url TEXT, records INTEGER, possible_cells INTEGER,
        retrieved_at_utc TEXT, metadata_sha256 TEXT, partial_years INTEGER,
        legacy_details_json TEXT NOT NULL DEFAULT '{}')""")
    con.execute("""CREATE TABLE IF NOT EXISTS import_log (
        id INTEGER PRIMARY KEY, original_log TEXT NOT NULL,
        original_id TEXT NOT NULL, dataset_code TEXT, provider TEXT,
        sqlite_table TEXT, import_method TEXT NOT NULL, imported_at_utc TEXT,
        status TEXT, row_count INTEGER, source_url TEXT, details_json TEXT NOT NULL,
        UNIQUE(original_log,original_id))""")

def upsert_source(con, code, provider, table, url, ui_url=None, records=None,
                  possible_cells=None, metadata_sha256=None, partial_years=None,
                  retrieved_at_utc=None):
    ensure_metadata(con)
    con.execute("""INSERT INTO source_registry
        (table_code,provider,sqlite_table,source_url,ui_url,records,possible_cells,
        retrieved_at_utc,metadata_sha256,partial_years,legacy_details_json)
        VALUES (?,?,?,?,?,?,?,?,?,?,'{}') ON CONFLICT(table_code) DO UPDATE SET
        provider=COALESCE(excluded.provider,source_registry.provider),
        sqlite_table=COALESCE(excluded.sqlite_table,source_registry.sqlite_table),
        source_url=COALESCE(excluded.source_url,source_registry.source_url),
        ui_url=COALESCE(excluded.ui_url,source_registry.ui_url),
        records=COALESCE(excluded.records,source_registry.records),
        possible_cells=COALESCE(excluded.possible_cells,source_registry.possible_cells),
        retrieved_at_utc=COALESCE(excluded.retrieved_at_utc,source_registry.retrieved_at_utc),
        metadata_sha256=COALESCE(excluded.metadata_sha256,source_registry.metadata_sha256),
        partial_years=COALESCE(excluded.partial_years,source_registry.partial_years)""",
        (code,provider,table,url,ui_url,records,possible_cells,retrieved_at_utc or now_utc(),metadata_sha256,partial_years))

def log_import(con, code, provider, table, method, status, rows=None,
               source_url=None, details=None, timestamp=None):
    ensure_metadata(con)
    # New log entries use a unique dedicated origin namespace, distinct from migrated legacy IDs.
    payload=json.dumps(details or {},ensure_ascii=False,sort_keys=True,default=str)
    cursor=con.execute("""INSERT INTO import_log
        (original_log,original_id,dataset_code,provider,sqlite_table,import_method,
         imported_at_utc,status,row_count,source_url,details_json)
         VALUES ('unified',?,?,?,?,?,?,?,?,?,?)""",
         (uuid.uuid4().hex,code,provider,table,method,timestamp or now_utc(),status,rows,source_url,payload))
    return cursor.lastrowid
