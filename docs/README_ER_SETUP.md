# Full ER model add-on for Estonia Migration SQLite project

No source tables, ETL code or existing config are changed. Copy `sql/`, `scripts/populate_model.py` and `docs/` into corresponding folders of your repository (do not overwrite existing scripts).

## WSL terminal, from repository root

1. Close all programs writing to the database; check path: `ls -l data/estonia_migration.sqlite`.
2. Back up: `sqlite3 data/estonia_migration.sqlite ".backup 'data/estonia_migration_before_er.sqlite'"`
3. Create dimensions: `sqlite3 -bail data/estonia_migration.sqlite < sql/01_create_dimensions.sql`
4. Create fact: `sqlite3 -bail data/estonia_migration.sqlite < sql/02_create_facts.sql`
5. Populate: `python3 scripts/populate_model.py --db data/estonia_migration.sqlite`
6. Validate: `sqlite3 -header -column data/estonia_migration.sqlite < sql/05_validate_model.sql`
7. Render ER diagram in `docs/ER_MODEL.md` on GitHub or https://mermaid.live/.

If any tables already exist from an older minimal ER model (`dim_year`, `dim_region`, `dim_dataset`, `fact_migration_county`, `fact_crime_county`), use a fresh copy of the original DB or review/remove that old model first. **Do not delete any source tables**. The new builder refuses to append to populated `fact_observation`; use `--replace` only after backup.

## Operational cautions

- This materializes roughly 1+ million fact cells; SQLite size increases substantially. Keep it out of Git commits if above GitHub's file size limit; publish DB via Release.
- The foreign-key `PRAGMA` is connection-local. Enable `PRAGMA foreign_keys=ON` when editing the model.
- If the original source tables are refreshed later, rebuild facts, as the references to rowids may change.
- Data model captures source heterogeneity deliberately. The wide NH01 is expanded; no per-county migration/crime relationship or numerical causality is asserted.
- Dimensional relationships do not guarantee that two categories can be added or directly joined; use distinct country/year/indicator definitions.
- Keep checks and README committed to GitHub. Avoid checking in the 122 MB original database file as a normal Git object.
