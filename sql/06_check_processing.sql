-- Execute using: python3 scripts/check_er_processing.py (preferred) or sqlite3 -header -column DB < this_file
SELECT MIN(year) AS min_year, MAX(year) AS max_year, COUNT(*) AS observations FROM fact_observation;
SELECT sex_label, COUNT(*) AS observations FROM fact_observation JOIN dim_sex USING(sex_id) GROUP BY sex_label ORDER BY sex_label;
SELECT COUNT(*) AS violations_outside_period FROM fact_observation WHERE year NOT BETWEEN 2000 AND 2025 OR year IS NULL;
SELECT COUNT(*) AS old_missing_tokens FROM fact_observation WHERE value_raw IN ('..', ':', '-', '.', '…', '', 'NA', 'N/A', 'null');
SELECT COUNT(*) AS duplicated_provenance FROM (SELECT dataset_id,source_rowid,source_measure,COUNT(*) c FROM fact_observation GROUP BY 1,2,3 HAVING c > 1);
PRAGMA foreign_key_check;
PRAGMA integrity_check;
