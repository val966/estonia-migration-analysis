SELECT
    d.dataset_code,
    COUNT(f.observation_id) AS observations,
    MIN(f.year) AS first_year,
    MAX(f.year) AS last_year
FROM dim_dataset d
LEFT JOIN fact_observation f
    ON d.dataset_id = f.dataset_id
GROUP BY d.dataset_id, d.dataset_code
ORDER BY d.dataset_code;