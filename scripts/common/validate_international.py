"""Quality checks for World Bank + Eurostat; read-only, does not modify source data."""
import argparse, json, sqlite3
from pathlib import Path
from international_common import CONFIG, DEFAULT_DB, identifier


def validate(db):
    problems=[]; stats={}
    with sqlite3.connect(Path(db).resolve().as_uri()+'?mode=ro',uri=True) as c:
        if c.execute('PRAGMA integrity_check').fetchone()[0]!='ok': problems.append('SQLite integrity_check failed')
        if c.execute('PRAGMA foreign_key_check').fetchall(): problems.append('SQLite foreign_key_check failed')
        tables={x[0] for x in c.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        if 'international_import_log' not in tables: problems.append('international_import_log missing')
        for provider, cfg in CONFIG.items():
            t=cfg['table']; info={'table':t}
            if t not in tables:
                problems.append(t+' missing'); stats[provider]=info; continue
            info['rows']=c.execute('SELECT COUNT(*) FROM '+identifier(t)).fetchone()[0]
            if not info['rows']: problems.append(t+' is empty')
            if 'international_import_log' in tables:
                log=c.execute('''SELECT row_count,status,config_json FROM international_import_log
                      WHERE provider=? AND table_name=? ORDER BY id DESC LIMIT 1''',(provider,t)).fetchone()
                if not log: problems.append(provider+' lacks import log')
                else:
                    if log[0]!=info['rows'] or log[1]!='complete': problems.append(provider+' row count/status disagree with log')
                    if json.loads(log[2])!=cfg: problems.append(provider+' configuration changed since download')
            if provider=='worldbank':
                info['non_null']=c.execute('SELECT COUNT(*) FROM '+identifier(t)+' WHERE value IS NOT NULL').fetchone()[0]
                codes={r[0] for r in c.execute('SELECT DISTINCT indicator_code FROM '+identifier(t))}
                if codes!=set(cfg['indicators']): problems.append('World Bank indicator set mismatch')
                if c.execute('SELECT COUNT(*) FROM '+identifier(t)+' WHERE year<1900 OR year>2100').fetchone()[0]: problems.append('World Bank invalid year')
                dup=c.execute('SELECT COUNT(*) FROM (SELECT year,indicator_code FROM '+identifier(t)+' GROUP BY year,indicator_code HAVING COUNT(*)>1)').fetchone()[0]
                if dup: problems.append('World Bank duplicate year/indicator')
            else:
                query='SELECT DISTINCT geo,age,sex,freq,unit,agedef FROM '+identifier(t)
                combos=c.execute(query).fetchall()
                for geo,age,sex,freq,unit,agedef in combos:
                    if geo!='EE' or age!='TOTAL' or sex not in ('M','F','T') or freq!='A' or unit!='NR' or agedef!='REACH':
                        problems.append('Eurostat unexpected dimension values');break
                if not {'M','F','T'}.issubset({x[2] for x in combos}): problems.append('Eurostat missing requested sex categories')
                info['years']=c.execute('SELECT MIN(year),MAX(year) FROM '+identifier(t)).fetchone()
                info['birth_groups']=c.execute('SELECT COUNT(DISTINCT c_birth) FROM '+identifier(t)).fetchone()[0]
                info['missing_value_rows']=c.execute('SELECT COUNT(*) FROM '+identifier(t)+' WHERE value IS NULL').fetchone()[0]
            stats[provider]=info
    return {'ok':not problems,'problems':problems,'datasets':stats}

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--db',default=str(DEFAULT_DB))
    a=p.parse_args()
    try:
        report=validate(a.db);print(json.dumps(report,indent=2,ensure_ascii=False))
        if not report['ok']:raise SystemExit(1)
    except (OSError,sqlite3.Error,ValueError) as e: raise SystemExit('ERROR: '+str(e))
