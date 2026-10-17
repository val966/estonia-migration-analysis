"""World Bank country=EST: six annual indicators, full available history."""
import argparse, json
from international_common import CONFIG, DEFAULT_DB, get_json, publish, identifier


def parse_worldbank(payload, expected_code):
    if not isinstance(payload, list) or len(payload) != 2 or not isinstance(payload[1], list):
        raise ValueError('Unexpected World Bank API response: ' + str(payload)[:250])
    rows = []
    for obj in payload[1]:
        if obj.get('indicator', {}).get('id') != expected_code: continue
        if str(obj.get('countryiso3code')) != 'EST': continue
        year = str(obj.get('date', ''))
        if len(year) != 4 or not year.isdigit(): continue
        value = obj.get('value')
        rows.append((int(year),expected_code, float(value) if value is not None else None,
                     obj.get('unit') or None, obj.get('obs_status') or None, obj.get('decimal')))
    return rows


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--db', default=str(DEFAULT_DB))
    a = p.parse_args()
    cfg = CONFIG['worldbank']
    all_rows, urls, pages = [], [], {}
    for indicator in cfg['indicators']:
        base = cfg['url'].rstrip('/') + '/' + indicator
        payload, url = get_json(base, {'format':'json','per_page':20000, 'page':1})
        if not isinstance(payload,list) or not payload or not isinstance(payload[0], dict):
            raise ValueError(f'World Bank metadata missing for {indicator}')
        page_count = int(payload[0].get('pages',1))
        chunk = parse_worldbank(payload, indicator)
        for page in range(2,page_count+1):
            more,_ = get_json(base, {'format':'json','per_page':20000, 'page':page})
            chunk.extend(parse_worldbank(more,indicator))
        if not chunk: raise ValueError(f'No data for {indicator}')
        keyset = [(r[0],r[1]) for r in chunk]
        if len(keyset)!=len(set(keyset)): raise ValueError(f'Duplicate years: {indicator}')
        all_rows.extend(chunk)
        urls.append(url); pages[indicator]=page_count
        print(f'{indicator}: {len(chunk)} years, {sum(r[2] is not None for r in chunk)} published values')
    table = cfg['table']; q = identifier(table)
    ddl = f'''CREATE TABLE {q} (
       year INTEGER NOT NULL, indicator_code TEXT NOT NULL, value REAL,
       unit_source TEXT, obs_status TEXT, decimal_places INTEGER,
       PRIMARY KEY (year,indicator_code))'''
    sql = f'INSERT INTO {q} (year,indicator_code,value,unit_source,obs_status,decimal_places) VALUES (?,?,?,?,?,?)'
    n=publish(a.db,table,ddl,all_rows,sql,'worldbank','EST/indicators',cfg['url'],cfg,{'request_urls':urls,'pages':pages})
    print(f'Created {table}: {n} rows in {a.db}')

if __name__=='__main__': main()
