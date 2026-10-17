PRAGMA foreign_keys=ON;
BEGIN;
CREATE TABLE IF NOT EXISTS dim_dataset (dataset_id INTEGER PRIMARY KEY, dataset_code TEXT NOT NULL UNIQUE, source_table TEXT NOT NULL UNIQUE, provider TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS dim_year (year INTEGER PRIMARY KEY CHECK(year BETWEEN 1800 AND 2200));
CREATE TABLE IF NOT EXISTS dim_region (region_id INTEGER PRIMARY KEY, region_name TEXT NOT NULL UNIQUE, region_level TEXT NOT NULL CHECK(region_level IN ('country','county')));
CREATE TABLE IF NOT EXISTS dim_sex (sex_id INTEGER PRIMARY KEY, sex_label TEXT NOT NULL UNIQUE);
CREATE TABLE IF NOT EXISTS dim_age_group (age_group_id INTEGER PRIMARY KEY, source_dataset_id INTEGER NOT NULL REFERENCES dim_dataset(dataset_id), age_label TEXT NOT NULL, UNIQUE(source_dataset_id,age_label));
CREATE TABLE IF NOT EXISTS dim_indicator (indicator_id INTEGER PRIMARY KEY, source_dataset_id INTEGER NOT NULL REFERENCES dim_dataset(dataset_id), indicator_label TEXT NOT NULL, unit_label TEXT NOT NULL DEFAULT '', UNIQUE(source_dataset_id,indicator_label,unit_label));
COMMIT;
