#!/usr/bin/env python3
"""Populate a source-preserving constellation from existing SQLite tables.
Run only after 01_create_dimensions.sql and 02_create_facts.sql.
"""
import argparse
import hashlib
import json
import re
import sqlite3
from pathlib import Path

TABLES = ['rvr03','rvr05','rvr08','rvr051','rv028u','tt4661','js009','ht140u','eh045','nh01','worldbank_estonia','eurostat_migr_imm4ctb','lfsa_eegatm']
PROVIDERS = {'nh01':'TAI','worldbank_estonia':'World Bank','eurostat_migr_imm4ctb':'Eurostat','lfsa_eegatm':'Eurostat'}
COUNTIES = ['Harju','Hiiu','Ida-Viru','Jõgeva','Järva','Lääne','Lääne-Viru','Põlva','Pärnu','Rapla','Saare','Tartu','Valga','Viljandi','Võru']


def column(columns,*options):
    for x in options:
        if x in columns: return x
    return None

def is_missing(raw, missing):
    return raw is None or str(raw).strip().casefold() in missing


def normalize_sex(raw, aliases):
    if raw is None: return None
    for code, names in aliases.items():
        if str(raw).strip().casefold() in {str(n).casefold() for n in names}:
            return code
    return None


def exact_row_fingerprint(record, columns):
    # Exclude ETL metadata: same official observation imported twice counts as a duplicate.
    stable = [(col, record.get(col)) for col in columns if col not in ('source_table', 'retrieved_at_utc')]
    return hashlib.sha256(json.dumps(stable, ensure_ascii=False, default=str, separators=(',', ':')).encode()).hexdigest()


def number(raw):
    if raw is None: return None
    t=str(raw).strip().replace('\u00a0','').replace(' ','')
    if t in ('','..',':','-','…','.'): return None
    try: return float(t.replace(',','.'))
    except ValueError: return None

def year_of(text):
    m=re.search(r'(?<!\d)(?:19|20)\d{2}(?!\d)',str(text or ''))
    return int(m.group(0)) if m else None

def normalized_region(text):
    if text is None: return None
    s=str(text).strip().lstrip('.').lower()
    if s in ('estonia','whole country','ee'): return 'Estonia'
    for c in COUNTIES:
        if s in (c.lower(),(c+' county').lower()): return c+' county'
    return None

def main():
    a=argparse.ArgumentParser()
    a.add_argument('--db',default='data/estonia_migration.sqlite')
    a.add_argument('--replace',action='store_true',help='Rebuild dimension and fact rows in one transaction')
    a.add_argument('--rules',default='config/processing_rules.json',help='JSON processing rules')
    args=a.parse_args()
    rules=json.loads(Path(args.rules).read_text(encoding='utf-8'))
    min_year=int(rules['years']['min']); max_year=int(rules['years']['max'])
    if not 1800 <= min_year <= max_year <= 2200: raise ValueError('Invalid year range')
    missing_tokens={str(x).strip().casefold() for x in rules['missing_values']}
    conn=sqlite3.connect(args.db)
    conn.row_factory=sqlite3.Row
    conn.execute('PRAGMA foreign_keys=ON')
    existing={r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    missing=set(TABLES)-existing
    if missing: raise SystemExit(f'Missing source tables: {sorted(missing)}')
    if 'fact_observation' not in existing: raise SystemExit('Run SQL files 01 and 02 first')
    if conn.execute('SELECT COUNT(*) FROM fact_observation').fetchone()[0] and not args.replace:
        raise SystemExit('Facts already populated. Use --replace to rebuild.')
    try:
        conn.execute('BEGIN')
        if args.replace:
            for t in ('fact_observation','dim_indicator','dim_age_group','dim_sex','dim_region','dim_year','dim_dataset'):
                conn.execute(f'DELETE FROM {t}')
        for t in TABLES:
            conn.execute('INSERT INTO dim_dataset(dataset_code,source_table,provider) VALUES(?,?,?)',(t.upper(),t,PROVIDERS.get(t,'Statistics Estonia')))
        for reg in ['Estonia']+[c+' county' for c in COUNTIES]:
            conn.execute('INSERT INTO dim_region(region_name,region_level) VALUES(?,?)',(reg,'country' if reg=='Estonia' else 'county'))
        region_ids=dict(conn.execute('SELECT region_name,region_id FROM dim_region').fetchall())
        conn.execute('CREATE TEMP TABLE IF NOT EXISTS seen_source_records (fingerprint TEXT PRIMARY KEY) WITHOUT ROWID')
        dataset_ids=dict(conn.execute('SELECT source_table,dataset_id FROM dim_dataset').fetchall())
        cache_sex={}; cache_age={}; cache_indicator={}; seen_year=set()
        def lookup(table,cache,key,fields):
            if key not in cache:
                marks=','.join('?' for _ in key)
                conn.execute(f'INSERT INTO {table}({fields}) VALUES({marks})',key)
                cache[key]=conn.execute('SELECT last_insert_rowid()').fetchone()[0]
            return cache[key]
        for t in TABLES:
            did=dataset_ids[t]
            cols=[row[1] for row in conn.execute(f'PRAGMA table_info("{t}")')]
            year_c=column(cols,'Year','year','TIME_PERIOD','Reference period')
            region_c=column(cols,'County','County of residence','Place of residence','Region/county','geo')
            sex_c=column(cols,'Sex','sex')
            age_c=column(cols,'Age group','age')
            indicator_c=column(cols,'indicator_code','Indicator','Degree/type of offence','Diagnosis (ICD-10)','emp_cont','c_birth')
            flag_c=column(cols,'OBS_FLAG','obs_flag','obs_status')
            unit_c=column(cols,'unit','unit_source')
            measurements=[c for c in cols if c.startswith((t.upper()+':',))]
            if t=='nh01': measurements=[c for c in cols if c.startswith('Number ')]
            if t in ('worldbank_estonia','eurostat_migr_imm4ctb','lfsa_eegatm'): measurements=['value' if 'value' in cols else 'OBS_VALUE']
            if not measurements: raise ValueError(f'Cannot identify measurement column(s) for {t}')
            sql=f'SELECT rowid AS __source_rowid__, * FROM "{t}"'
            batch=[]; n=0; skipped_year=0; skipped_duplicates=0; missing_count=0
            if not year_c: raise ValueError(f'Missing year column for {t}')
            conn.execute('DELETE FROM seen_source_records')
            for row in conn.execute(sql):
                d=dict(row)
                y=year_of(d.get(year_c))
                if y is None or not min_year <= y <= max_year:
                    skipped_year+=1
                    continue
                fp=exact_row_fingerprint(d, cols)
                inserted=conn.execute('INSERT OR IGNORE INTO seen_source_records(fingerprint) VALUES(?)',(fp,)).rowcount
                if not inserted:
                    skipped_duplicates+=1
                    continue
                if y not in seen_year:
                    conn.execute('INSERT INTO dim_year(year) VALUES(?)',(y,));seen_year.add(y)

                raw_region=d.get(region_c)
                sex=d.get(sex_c)
                age=d.get(age_c)
                canonical_sex=normalize_sex(sex,rules['sex_aliases'])
                sex_id=lookup('dim_sex',cache_sex,(canonical_sex,),'sex_label') if canonical_sex else None
                age_id=lookup('dim_age_group',cache_age,(did,str(age)),'source_dataset_id,age_label') if age is not None else None
                for measure in measurements:
                    reg=(' '.join(measure.split(' ')[1:]) if t=='nh01' else raw_region)
                    norm=normalized_region(reg)
                    ind=str(d.get(indicator_c) or measure)
                    unit=str(d.get(unit_c) or '')
                    iid=lookup('dim_indicator',cache_indicator,(did,ind,unit),'source_dataset_id,indicator_label,unit_label')
                    v=d.get(measure)
                    if is_missing(v, missing_tokens):
                        missing_count+=1
                        value_num=None
                        value_raw=None
                    else:
                        value_num=number(v)
                        value_raw=str(v)
                    batch.append((did,d['__source_rowid__'],measure,y,str(d.get(year_c)) if year_c else None,region_ids.get(norm),str(reg) if reg is not None else None,sex_id,age_id,iid,value_num,value_raw,str(d.get(flag_c)) if d.get(flag_c) is not None else None))
                    if len(batch)>=5000:
                        conn.executemany('INSERT INTO fact_observation(dataset_id,source_rowid,source_measure,year,period_label,region_id,source_region_label,sex_id,age_group_id,indicator_id,value_num,value_raw,observation_flag) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)',batch);n+=len(batch);batch=[]
            if batch:
                conn.executemany('INSERT INTO fact_observation(dataset_id,source_rowid,source_measure,year,period_label,region_id,source_region_label,sex_id,age_group_id,indicator_id,value_num,value_raw,observation_flag) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)',batch);n+=len(batch)
            print(f'{t}: {n} observations; outside_period={skipped_year}; exact_duplicates={skipped_duplicates}; missing_values={missing_count}')
        problems=conn.execute('PRAGMA foreign_key_check').fetchall()
        if problems: raise ValueError(f'Foreign key violations: {problems[:3]}')
        conn.commit()
    except Exception:
        conn.rollback();raise
    finally: conn.close()

if __name__=='__main__': main()
