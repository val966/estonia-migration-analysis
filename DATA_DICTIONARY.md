# Data dictionary / Словарь данных

This project preserves the **original API response columns** within each table (`rvr03`, `rvr05`, `rvr08`, `rvr051`) and adds:
- `source_table`: official Statistics Estonia table ID
- `retrieved_at_utc`: time when a chunk was downloaded (UTC ISO 8601)

Column names and statistical definitions must be checked against the JSON metadata saved to `data/metadata/RVR*.json` after download. Original fields are initially loaded as **TEXT**, including measures, to avoid changing source values. Numeric analyses must explicitly convert them, treating missing/suppressed values carefully.

`source_registry`: `table_code` (PK), `records` (row count), `retrieved_at_utc`, `source_url`.

## Interpretation warnings

- Do not sum rows across different RVR tables: they are alternative cross-tabulations and may duplicate the same events.
- Do not sum subtotals (e.g. all ages, both sexes) with detailed categories.
- Check discontinuities in official migration methodology (especially around 2016) before labeling outliers.
- `candidate_anomalies.csv` contains exploratory flags, not statistically verified anomalies.

Before publishing v1.0, supplement this file with actual source field names and category descriptions based on the metadata and the downloaded snapshot.
