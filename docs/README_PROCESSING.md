# Processing rules for the ER model (SQLite)

This is a PATCH for `estonia_full_er_model.zip`, **not** a replacement for the full project.

## Installation
- Copy `scripts/populate_model.py` over the previous ER-model script.
- Copy `config/processing_rules.json` into the project (new folder if necessary).
- Copy `sql/06_check_processing.sql` into the project.
- Keep existing `sql/01_create_dimensions.sql` and `sql/02_create_facts.sql` (their schema supports the new rules).
- Do **not** change the raw/source statistical tables.

## Commands from project root

```bash
sqlite3 data/estonia_migration.sqlite ".backup 'data/estonia_migration_before_processing.sqlite'"
python3 scripts/populate_model.py --db data/estonia_migration.sqlite --rules config/processing_rules.json --replace
sqlite3 -header -column data/estonia_migration.sqlite < sql/06_check_processing.sql
```

If dimensions and fact table do not exist yet, run `sql/01_create_dimensions.sql` and `sql/02_create_facts.sql` before Python. The script refuses to append to an already populated fact table without `--replace`.

## Semantics
- Only records with a **recognized year between 2000 and 2025, inclusive** are copied to `fact_observation`. Quarterly periods (e.g. 2025 Q4) remain distinguishable in `period_label`. Unknown-year records are omitted from the **derived model only**.
- Missing measurement tokens `..`, `:`, etc. (configurable) become `NULL` in `value_num` AND `value_raw` of **derived observations**. The untouched source table retains the exact published symbol. Non-numeric but non-missing values are retained in `value_raw` and have `value_num = NULL`.
- `M/F/T` sex codes merge only known labels. Unknown and unrecognized labels receive `NULL` sex_id, not an invented category; original labels remain in the raw sources.
- Only **exact county names**, plus `Estonia/Whole country/EE`, map to `dim_region`. City, county-excluding-city, unknown, or unspecified labels are preserved in `source_region_label`, but `region_id` stays NULL to prevent a false relationship.
- Duplicate policy: SHA-256 of the source row fields, excluding only ingestion metadata (`source_table`, `retrieved_at_utc`), checked independently for each dataset. Only a repeated *fully identical statistical row* is skipped. Genuine different categories / measurements are kept. Database uniqueness also prevents duplicate `(dataset_id, source_rowid, source_measure)`.
- The code keeps `source_rowid`, `source_measure`, original period and source region labels, preserving traceability to each original table.
- Other dimensions (country of birth, language, etc.) are still retained in the raw tables and not yet fully standardized in this generic model.

### Important
Rebuilding the complete model might take several minutes and consume additional disk space. The `--replace` transaction retains previous committed model data if it fails (SQLite transaction rollback), but still back up first. Ensure the SQLite file and parent directory are writable in WSL.

## Verification
`06_check_processing.sql` should report years 2000–2025 only; zero `violations_outside_period`, `old_missing_tokens`, and `duplicated_provenance`; no output from `foreign_key_check`; and `ok` from `integrity_check`.

**Integration test:** script tested successfully against a representative SQLite subset containing the 13 official source tables. A full-scale run on the 122 MB database was attempted but did not complete within the runtime limit, so the full run remains to be verified on your computer.
