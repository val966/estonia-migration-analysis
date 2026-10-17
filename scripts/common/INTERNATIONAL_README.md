# International extension — World Bank and Eurostat

This extension is **additive** to the v4 SQLite repository. It does not update the original migration / demography / crime / education / health tables or `dataset_registry`. Your locally renamed original tables and their configuration remain unchanged. It creates only:

- `worldbank_estonia`: annual values for 6 selected World Bank indicators (one row per year + indicator). Unavailable observations remain SQL `NULL`.
- `eurostat_migr_imm4ctb`: Eurostat immigration, geo `EE`, age `TOTAL`, sex `M`, `F`, `T`, all available years and all country-of-birth groups, with source observation flags.
- `international_import_log`: source, exact request/configuration and metadata for each completed import.

## Setup (WSL / VS Code)

```bash
python3 -m pip install -r requirements.txt
python3 scripts/load_worldbank.py
python3 scripts/load_eurostat.py
python3 scripts/validate_international.py
python3 scripts/validate.py
python3 -m unittest discover -s tests -p 'test_international.py' -v
```

Both scripts default to `data/estonia_migration.sqlite`. To use another location, pass `--db /path/to/file.sqlite`. Close other SQLite writers before loading. **Make a database backup before the first run** (`sqlite3 data/estonia_migration.sqlite '.backup data/estonia_migration_backup.sqlite'`).

If you already use a renamed table schema, keep your `config/datasets.json` from your current repository; this extension only adds `config/international.json`. Never replace your locally edited `datasets.json` with an old copy.

## Why separate scripts?

`load_worldbank.py` and `load_eurostat.py` understand their respective APIs and can be rerun independently. `international_common.py` manages HTTP retries, publication transactions, and the common log. None of them depend on the PxWeb API logic.

## Data granularity and limitations

World Bank: each indicator has its own period of coverage; `NULL` is *not* zero. Unemployment here is a national modelled ILO estimate and need not match a detailed Statistics Estonia employment series. World Bank's net migration indicator is used for **comparison**, not added to migration flows.

Eurostat: `c_birth` codes are **groups of birth countries**, not citizenship and not country of previous residence. Do **not sum** hierarchical birth groups or `M+F+T` (T is already a total). Age definition `REACH` is explicit in the request. Missing data and provider flags are retained for supplied cells; unreported cells do not become zeros. Eurostat revisions may cause historical figures to change when re-downloaded.

Validation checks format, dimensions, indicator coverage, SQLite integrity and import-log counts. It does **not** guarantee the statistical correctness, official completeness of all years, or that values remain unchanged on the provider side. Before public release, create a frozen SQLite snapshot, run both validation scripts, and attach a SHA-256 checksum.

## Useful SQL

```sql
SELECT year, indicator_code, value
FROM worldbank_estonia WHERE year >= 2015 ORDER BY year, indicator_code;

SELECT year, c_birth, sex, value, obs_flag
FROM eurostat_migr_imm4ctb
WHERE year >= 2020 AND sex = 'T'
ORDER BY year, c_birth;
```

## Official resources

- World Bank Indicators API: https://api.worldbank.org/v2/country/EST/indicator/NY.GDP.PCAP.KD?format=json
- Eurostat data browser: https://ec.europa.eu/eurostat/databrowser/view/migr_imm4ctb/default/table?lang=en
- Eurostat Statistics API: https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/migr_imm4ctb?geo=EE&age=TOTAL
