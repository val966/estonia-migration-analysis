
from pathlib import Path
import sqlite3
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DB = ROOT / "data" / "estonia_migration.sqlite"

# 1. Загружаем годовую внешнюю иммиграцию
query = """
SELECT
    CAST("Year" AS INTEGER) AS year,
    "RVR03: MIGRATION" AS raw_value
FROM rvr03
WHERE "Indicator" = 'Immigration'
  AND "Type of migration" = 'External migration'
  AND "Sex" = 'Males and females'
  AND "Age group" = 'Age groups total'
  AND CAST("Year" AS INTEGER) BETWEEN 2015 AND 2025
ORDER BY year
"""

with sqlite3.connect(f"file:{DB}?mode=ro", uri=True) as conn:
    df = pd.read_sql_query(query, conn)

if df.empty:
    raise ValueError("No matching immigration data found")

df["immigration"] = pd.to_numeric(
    df["raw_value"], errors="raise"
)

if df["year"].duplicated().any():
    raise ValueError("Duplicate years found")

if not df["year"].diff().dropna().eq(1).all():
    raise ValueError("Missing years in the time series")

# 2. Вычисляем изменения между годами
df["change"] = df["immigration"].diff()
df["change_pct"] = df["immigration"].pct_change() * 100

changes = df["change"].dropna()

# 3. Вычисляем медиану и MAD
median_change = changes.median()
mad = (changes - median_change).abs().median()

if mad == 0:
    raise ValueError("MAD is zero; another method is needed")

# 4. Modified Z-score
df["modified_z"] = (
    0.6745 * (df["change"] - median_change) / mad
)

# 5. Отмечаем потенциальные аномалии
df["is_anomaly"] = df["modified_z"].abs() > 3.5

columns = [
    "year", "immigration", "change",
    "change_pct", "modified_z", "is_anomaly"
]

print(df[columns].round(2).to_string(index=False))

# 6. Сохраняем результаты
output = ROOT / "data" / "yearly_anomalies.csv"
df[columns].to_csv(output, index=False)

print(f"\nResults saved to: {output}")
