-- Safe exploration: no assumptions about localized CSV column names.
SELECT * FROM source_registry;
SELECT * FROM rvr03 LIMIT 10;
SELECT * FROM rvr05 LIMIT 10;
-- Check the actual column labels with python scripts/inspect_db.py
-- Do not sum different RVR tables: they contain overlapping measurements.
-- Also avoid aggregating both 'Total' and component age/sex/country categories.
