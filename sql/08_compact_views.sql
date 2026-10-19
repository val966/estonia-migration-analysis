-- SQLite views: no rows are copied from underlying sources.
-- All source tables remain unchanged.
DROP VIEW IF EXISTS vw_education_source;
CREATE VIEW vw_education_source AS
SELECT CAST(substr("Reference period",1,4) AS INTEGER) AS year,
       "County of residence" AS source_region,
       "Sex" AS sex,
       "Language of instruction" AS language_of_instruction,
       "Indicator" AS indicator,
       "HT140U: ENROLMENTS, DROPOUTS AND GRADE REPEATERS IN GENERAL EDUCATION" AS value_raw,
       CASE WHEN trim("HT140U: ENROLMENTS, DROPOUTS AND GRADE REPEATERS IN GENERAL EDUCATION") IN ('', '..', ':','-','…','.')
            THEN NULL ELSE CAST("HT140U: ENROLMENTS, DROPOUTS AND GRADE REPEATERS IN GENERAL EDUCATION" AS REAL) END AS value_num
FROM ht140u WHERE CAST(substr("Reference period",1,4) AS INTEGER) BETWEEN 2000 AND 2025;

DROP VIEW IF EXISTS vw_housing_source;
CREATE VIEW vw_housing_source AS
SELECT CAST(substr("Reference period",1,4) AS INTEGER) AS year,
       "Reference period" AS source_period,
       "County" AS source_region,
       "Indicator" AS indicator,
       "Type of permit" AS permit_type,
       "EH045: GRANTED BUILDING PERMITS AND COMPLETED DWELLINGS BY TYPE OF CONSTRUCTION, COUNTY AND TYPE OF RESIDENTIAL BUILDING" AS value_raw,
       CASE WHEN trim("EH045: GRANTED BUILDING PERMITS AND COMPLETED DWELLINGS BY TYPE OF CONSTRUCTION, COUNTY AND TYPE OF RESIDENTIAL BUILDING") IN ('', '..', ':','-','…','.')
            THEN NULL ELSE CAST("EH045: GRANTED BUILDING PERMITS AND COMPLETED DWELLINGS BY TYPE OF CONSTRUCTION, COUNTY AND TYPE OF RESIDENTIAL BUILDING" AS REAL) END AS value_num
FROM eh045 WHERE CAST(substr("Reference period",1,4) AS INTEGER) BETWEEN 2000 AND 2025;

-- Conservative nationwide subset of NH01, not a replacement for its complete regional data.
DROP VIEW IF EXISTS vw_health_estonia;
CREATE VIEW vw_health_estonia AS
SELECT CAST("Year" AS INTEGER) AS year,
       "Diagnosis (ICD-10)" AS diagnosis,
       "Sex" AS sex,
       "Number Estonia" AS value_raw,
       CASE WHEN trim("Number Estonia") IN ('', '..', ':','-','…','.')
            THEN NULL ELSE CAST("Number Estonia" AS REAL) END AS number_cases
FROM nh01 WHERE CAST("Year" AS INTEGER) BETWEEN 2000 AND 2025;
