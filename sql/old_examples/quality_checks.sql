SELECT
    'RVR03' AS source,
    COUNT(*) AS total_rows,
    COUNT(DISTINCT "Year") AS years_count,
    MIN("Year") AS first_year,
    MAX("Year") AS last_year
FROM rvr03

UNION ALL

SELECT
    'RVR05',
    COUNT(*),
    COUNT(DISTINCT "Year"),
    MIN("Year"),
    MAX("Year")
FROM rvr05

UNION ALL

SELECT
    'RVR08',
    COUNT(*),
    COUNT(DISTINCT "Year"),
    MIN("Year"),
    MAX("Year")
FROM rvr08

UNION ALL

SELECT
    'RVR051',
    COUNT(*),
    COUNT(DISTINCT "Year"),
    MIN("Year"),
    MAX("Year")
FROM rvr051;

SELECT
    "Indicator",
    "Type of migration",
    COUNT(*) AS row_count
FROM rvr03
GROUP BY
    "Indicator",
    "Type of migration"
ORDER BY
    "Indicator",
    "Type of migration";

SELECT
    "Year",
    "Sex",
    "Age group",
    "Indicator",
    "Type of migration",
    COUNT(*) AS duplicates
FROM rvr03
GROUP BY
    "Year",
    "Sex",
    "Age group",
    "Indicator",
    "Type of migration"
HAVING COUNT(*) > 1;

SELECT
    "RVR03: MIGRATION" AS raw_value,
    COUNT(*) AS occurrences
FROM rvr03
WHERE "RVR03: MIGRATION" IS NULL
   OR TRIM("RVR03: MIGRATION") = ''
   OR TRIM("RVR03: MIGRATION") = '-'
   OR TRIM("RVR03: MIGRATION") GLOB '*[^0-9-]*'
GROUP BY "RVR03: MIGRATION"
ORDER BY occurrences DESC;

SELECT
    "Year" AS year,
    "Indicator" AS indicator,
    "RVR03: MIGRATION" AS people
FROM rvr03
WHERE "Sex" = 'Males and females'
  AND "Age group" = 'Age groups total'
  AND "Type of migration" = 'External migration'
  AND CAST("Year" AS INTEGER) >= 2015
ORDER BY
    CAST("Year" AS INTEGER),
    "Indicator";
