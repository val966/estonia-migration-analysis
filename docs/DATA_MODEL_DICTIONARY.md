# Relational data dictionary

| Table | Primary key | Foreign keys | Description |
|---|---|---|---|
| `dim_dataset` | `dataset_id` | — | 13 original statistical dataset identities and providers |
| `dim_year` | `year` | — | Year of statistical observation |
| `dim_region` | `region_id` | — | Estonia plus 15 counties; special geographic labels not forced into county |
| `dim_sex` | `sex_id` | — | Observed labels exactly as supplied |
| `dim_age_group` | `age_group_id` | `source_dataset_id` → `dim_dataset` | Source-scoped age categories |
| `dim_indicator` | `indicator_id` | `source_dataset_id` → `dim_dataset` | Source-scoped indicators and original units |
| `fact_observation` | `observation_id` | `dataset_id`, `year`, `region_id`, `sex_id`, `age_group_id`, `indicator_id` | One source measurement cell |

Other `fact_observation` columns: `source_rowid` (the source SQLite rowid), `source_measure` (original measure column name), `period_label` (original year/quarter), `source_region_label` (original geography), `value_num` (parsed if numeric), `value_raw` (original value), `observation_flag` (quality annotation).

The constraint `UNIQUE(dataset_id,source_rowid,source_measure)` avoids duplicate loading of the same source cell. For reliable comparability, verify original dimensions (e.g., country, migrant status, offence types) in the original source table before aggregating. Some categories (especially total values) overlap.
