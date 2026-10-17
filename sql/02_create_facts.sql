PRAGMA foreign_keys=ON;
BEGIN;
CREATE TABLE IF NOT EXISTS fact_observation (
 observation_id INTEGER PRIMARY KEY,
 dataset_id INTEGER NOT NULL REFERENCES dim_dataset(dataset_id),
 source_rowid INTEGER NOT NULL,
 source_measure TEXT NOT NULL DEFAULT '',
 year INTEGER REFERENCES dim_year(year),
 period_label TEXT,
 region_id INTEGER REFERENCES dim_region(region_id),
 source_region_label TEXT,
 sex_id INTEGER REFERENCES dim_sex(sex_id),
 age_group_id INTEGER REFERENCES dim_age_group(age_group_id),
 indicator_id INTEGER REFERENCES dim_indicator(indicator_id),
 value_num REAL,
 value_raw TEXT,
 observation_flag TEXT,
 UNIQUE(dataset_id, source_rowid, source_measure)
);
CREATE INDEX IF NOT EXISTS idx_fact_year ON fact_observation(year);
CREATE INDEX IF NOT EXISTS idx_fact_region_year ON fact_observation(region_id,year);
CREATE INDEX IF NOT EXISTS idx_fact_dataset ON fact_observation(dataset_id);
CREATE INDEX IF NOT EXISTS idx_fact_indicator ON fact_observation(indicator_id);
COMMIT;
