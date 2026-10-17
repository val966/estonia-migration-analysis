CREATE TEMP VIEW IF NOT EXISTS v_external_migration_yearly AS
SELECT
    CAST("Year" AS INTEGER) AS year,

    MAX(CASE
        WHEN "Indicator" = 'Immigration'
        THEN CAST("RVR03: MIGRATION" AS INTEGER)
    END) AS immigration,

    MAX(CASE
        WHEN "Indicator" = 'Emigration'
        THEN CAST("RVR03: MIGRATION" AS INTEGER)
    END) AS emigration,

    MAX(CASE
        WHEN "Indicator" = 'Net migration'
        THEN CAST("RVR03: MIGRATION" AS INTEGER)
    END) AS net_migration

FROM rvr03

WHERE "Sex" = 'Males and females'
  AND "Age group" = 'Age groups total'
  AND "Type of migration" = 'External migration'

GROUP BY CAST("Year" AS INTEGER);

SELECT
    year,
    immigration,
    emigration,
    net_migration,
    immigration - emigration AS calculated_net,
    net_migration - (immigration - emigration) AS difference
FROM v_external_migration_yearly
ORDER BY year;