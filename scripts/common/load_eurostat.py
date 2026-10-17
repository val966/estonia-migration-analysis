"""Eurostat migr_imm4ctb, Estonia; all years and birth-region groups; TOTAL/M,F,T."""
import argparse, itertools
from international_common import CONFIG, DEFAULT_DB, get_json, publish, identifier


def decode_jsonstat(data):
    ids=data.get('id'); size=data.get('size'); dim=data.get('dimension',{})
    if not isinstance(ids,list) or not isinstance(size,list) or len(ids)!=len(size):
        raise ValueError('Eurostat response is not JSON-stat with dimensions')
    expected={'geo':'EE','age':'TOTAL','sex':{'M','F','T'},'freq':'A','unit':'NR','agedef':'REACH'}
    lookups=[]
    for name, length in zip(ids,size):
        cat=dim[name]['category']; index=cat['index']
        if isinstance(index,dict):
            lookup=[None]*length
            for code,idx in index.items(): lookup[idx]=code
        else: lookup=list(index)
        if len(lookup)!=length or any(x is None for x in lookup):
            raise ValueError('Invalid Eurostat category index')
        lookups.append(lookup)
    required={'geo','age','sex','c_birth','time'}
    if not required.issubset(ids): raise ValueError('Missing dimensions: '+str(required-set(ids)))
    if any(k not in ids for k in ('freq','unit','agedef')):
        raise ValueError('Missing methodological filter dimensions')
    for k,v in expected.items():
        present=set(lookups[ids.index(k)])
        allowed=v if isinstance(v,set) else {v}
        if not present.issubset(allowed): raise ValueError(f'Unexpected {k}: {present}')
    values=data.get('value',{})
    statuses=data.get('status',{})
    if isinstance(values,list): values={str(i):v for i,v in enumerate(values) if v is not None}
    if isinstance(statuses,list): statuses={str(i):v for i,v in enumerate(statuses) if v is not None}
    # iterate observed cells only, preserving flags for missing cells if published
    keys=set(values)|set(statuses)
    rows=[]
    for key in keys:
        linear=int(key); coords=[None]*len(size); offset=linear
        for i in range(len(size)-1,-1,-1):
            coords[i]=offset%size[i]; offset//=size[i]
        if offset: raise ValueError('JSON-stat index out of bounds')
        entry={name:lookups[i][coords[i]] for i,name in enumerate(ids)}
        raw_value=values.get(str(key))
        value=None if raw_value is None else float(raw_value)
        rows.append((int(entry['time']),entry['geo'],entry['c_birth'],entry['sex'],entry['age'],entry['freq'],entry['unit'],entry['agedef'],value,statuses.get(str(key))))
    rows.sort(key=lambda r:(r[0],r[2],r[3]))
    return rows, {k:lookups[ids.index(k)] for k in ids}


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--db',default=str(DEFAULT_DB))
    a=p.parse_args(); cfg=CONFIG['eurostat']
    params={'lang':'EN','geo':cfg['geo'],'age':cfg['age'],'freq':cfg['freq'],
            'unit':cfg['unit'],'agedef':cfg['agedef'],'sex':cfg['sex']}
    data,url=get_json(cfg['url'],params)
    rows, categories=decode_jsonstat(data)
    if not rows: raise ValueError('Empty Eurostat dataset (refusing to replace existing table)')
    keys=[r[:8] for r in rows]
    if len(keys)!=len(set(keys)): raise ValueError('Duplicate Eurostat dimension combinations')
    table=cfg['table']; q=identifier(table)
    ddl=f'''CREATE TABLE {q} (
       year INTEGER NOT NULL, geo TEXT NOT NULL, c_birth TEXT NOT NULL,
       sex TEXT NOT NULL, age TEXT NOT NULL, freq TEXT NOT NULL,
       unit TEXT NOT NULL, agedef TEXT NOT NULL, value REAL, obs_flag TEXT,
       PRIMARY KEY(year,geo,c_birth,sex,age,freq,unit,agedef))'''
    sql=f'''INSERT INTO {q} (year,geo,c_birth,sex,age,freq,unit,agedef,value,obs_flag)
             VALUES (?,?,?,?,?,?,?,?,?,?)'''
    n=publish(a.db,table,ddl,rows,sql,'eurostat',cfg['dataset'],url,cfg,
              {'dimensions':categories,'updated':data.get('updated'),'label':data.get('label')})
    print(f'Created {table}: {n} rows in {a.db}; years {min(r[0] for r in rows)}–{max(r[0] for r in rows)}')

if __name__=='__main__': main()
