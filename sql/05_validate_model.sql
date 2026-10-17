PRAGMA foreign_keys=ON;
PRAGMA integrity_check;
PRAGMA foreign_key_check;
SELECT d.dataset_code, COUNT(f.observation_id) AS fact_rows
FROM dim_dataset d LEFT JOIN fact_observation f ON f.dataset_id=d.dataset_id
GROUP BY d.dataset_id ORDER BY d.dataset_code;
SELECT 'unlinked_dataset' AS issue,COUNT(*) FROM fact_observation WHERE dataset_id IS NULL
UNION ALL SELECT 'nonexistent_source_row', COUNT(*) FROM fact_observation WHERE source_rowid IS NULL;
