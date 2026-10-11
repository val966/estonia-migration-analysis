"""Find unusual year-on-year changes in RVR03 within identical dimension combinations.

This is exploratory screening, not a statistical claim. It keeps original categories,
including aggregates; inspect category names to avoid double-counting in summary results.
"""
import sqlite3
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DB = ROOT / 'data' / 'estonia_migration.sqlite'
OUT = ROOT / 'data' / 'candidate_anomalies.csv'

with sqlite3.connect(DB) as conn:
    df = pd.read_sql_query('SELECT * FROM rvr03', conn)

# Statistics Estonia English CSV labels can vary: detect date and measure by values.
reserved = {'source_table', 'retrieved_at_utc'}
year_candidates = []
for c in df.columns:
    if c in reserved:
        continue
    vals = pd.to_numeric(df[c], errors='coerce')
    valid = vals.dropna()
    if len(valid) and valid.between(1950, 2100).mean() > 0.9 and vals.notna().mean() > 0.9:
        year_candidates.append(c)
if not year_candidates:
    raise ValueError('No year column found. Inspect raw fields with inspect_db.py')
year_col = next((c for c in year_candidates if 'year' in c.lower()), year_candidates[0])

numeric_columns = []
for c in df.columns:
    if c in reserved or c == year_col:
        continue
    vals = pd.to_numeric(df[c].astype(str).str.replace(',', '.', regex=False), errors='coerce')
    if vals.notna().mean() > 0.7:
        numeric_columns.append(c)
if not numeric_columns:
    raise ValueError('No numeric measure found. Inspect raw fields with inspect_db.py')
value_col = next((c for c in numeric_columns if c.lower() in ('value', 'values')), numeric_columns[-1])

features = [c for c in df.columns if c not in reserved | {year_col, value_col}]
df['year_num'] = pd.to_numeric(df[year_col], errors='coerce')
df['value_num'] = pd.to_numeric(df[value_col].astype(str).str.replace(',', '.', regex=False), errors='coerce')
df = df.dropna(subset=['year_num', 'value_num']).sort_values(features + ['year_num'])
if features:
    groups = df.groupby(features, dropna=False)
    df['previous_year'] = groups['year_num'].shift(1)
    df['previous_value'] = groups['value_num'].shift(1)
else:
    df['previous_year'] = df['year_num'].shift(1)
    df['previous_value'] = df['value_num'].shift(1)
df['absolute_change'] = df['value_num'] - df['previous_value']
df['relative_change'] = df['absolute_change'] / df['previous_value'].abs().where(df['previous_value'].abs() >= 100)
candidates = df.loc[(df['year_num'] - df['previous_year'] == 1) &
                    (df['relative_change'].abs() >= 0.5)].copy()
candidates = candidates.sort_values('relative_change', key=lambda s: s.abs(), ascending=False)
OUT.parent.mkdir(parents=True, exist_ok=True)
candidates.to_csv(OUT, index=False)
print(f'Flagged {len(candidates)} candidates (>= 50% YoY from baseline >=100): {OUT}')
print(candidates[[year_col] + features + ['previous_value', 'value_num', 'relative_change']].head(15).to_string(index=False))
print('These are candidates only; review methodology, totals and event context.')
