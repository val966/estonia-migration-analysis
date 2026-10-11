# Estonia Migration: Open-data starter project

Official source: [Statistics Estonia — Migration](https://andmed.stat.ee/en/stat/rahvastik__rahvastikusundmused__ranne)
API specification: https://andmed.stat.ee/abi/API-manual.pdf

## First run

1. Install Python 3.10+ and enter project folder.
2. `python -m pip install -r requirements.txt`
3. Quick test: `python scripts/download.py --tables RVR03 --latest-years 2`
4. All four tables, all published years: `python scripts/download.py`
5. Inspect database: `python scripts/inspect_db.py`

Generated artifacts:
- `data/estonia_migration.sqlite`: SQLite database; one table per RVR identifier
- `data/metadata/RVRxx.json`: official dimension metadata (codes and labels)
- `source_registry`: download date, row counts, source URLs

## Google Colab

Upload this ZIP through the Files pane and run:

```python
!unzip -q estonia_migration_starter.zip
%cd estonia_migration_starter
!pip -q install -r requirements.txt
!python scripts/download.py --tables RVR03 --latest-years 2
!python scripts/inspect_db.py
```

Then remove `--latest-years 2` to download all years (some tables may take time).

## Important limitations

- No data is included in this ZIP. The extractor needs network access when run.
- This project has NOT been live-tested against the official API in the current environment. The official URL and GET/POST protocol are documented, but the live server may require adjustments.
- CSV fields are ingested as TEXT, preserving missing-value codes and labels. Cast carefully before numeric analysis.
- The database is not published automatically. To publish a small vetted snapshot, remove the `data/*.sqlite` entry from `.gitignore`, ensure file size <100 MB, and commit it.
- Do not add up values across distinct tables or duplicate 'total' categories.
- Changes in migration methodology affect time series comparability (especially 2016).
- Source attribution: Statistics Estonia; check applicable attribution/share-alike license before redistributing database extracts.
- Never put Supabase credentials or API keys in the public repository.

## First exploratory anomaly screen

`python scripts/anomalies.py`

Analyzes RVR03 time series separately for each category combination, flagging year-to-year
changes of at least 50% when the prior year's absolute value is at least 100. It writes
`data/candidate_anomalies.csv`. **This is an arbitrary screening heuristic, not proof
of anomalies**. The script detects year/value columns heuristically; check results carefully.

## SQLite + GitHub: handing off exactly the same data

Keep Python/SQL/metadata files under version control. The `.gitignore` excludes generated SQLite files: do not accidentally commit a large or unvalidated database. After your final data refresh:

```bash
python scripts/download.py
python scripts/inspect_db.py
python scripts/validate_release.py
```

Review `release/validation_report.json` (tables, columns and record counts). Upload **the exact file** `data/estonia_migration.sqlite` plus `release/SHA256SUMS`, `release/validation_report.json` and your code/metadata to a *tagged GitHub Release*, e.g. `v1.0`. Use an immutable release and record its URL in the README. Everyone should download this frozen database rather than rerun the API when reproducing the team's analyses. The shared database should be opened read-only for ordinary analysis.

Check the SHA-256 digest of the downloaded `.sqlite` against `SHA256SUMS`. Any different checksum means it is not identical. Do not write modifications to the published snapshot: make a working copy for experiments.

The script verifies SQLite `PRAGMA integrity_check`, row-count agreement with `source_registry`, and lists schema; it cannot certify correctness against the original API unless the full extraction is successfully run and inspected. A test with `--latest-years 2` is **not** a full release snapshot. Missing-value rules, source category meaning and aggregates must be audited separately.
