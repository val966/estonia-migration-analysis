# Estonia Migration Analysis

Projekt obsahuje oficiálne údaje o migrácii v Estónsku a súvisiace demografické, ekonomické a sociálne ukazovatele. Hlavným výstupom je databáza **SQLite**.

## Stiahnutie a otvorenie databázy

Súbory na stiahnutie sa zverejňujú v sekcii [GitHub Releases](https://github.com/val966/estonia-migration-analysis/releases):

- **`estonia_migration.sqlite`** – hotová databáza, ktorú možno priamo otvoriť v DBeaver alebo DB Browser for SQLite.
- **`estonia_migration.sql.gz`** – komprimovaný SQL export na obnovenie databázy v SQLite.

Na obnovenie z exportu (Linux, macOS alebo WSL) použite **nový, prázdny cieľový súbor**:

```bash
gzip -dc estonia_migration.sql.gz | sqlite3 -bail estonia_migration.sqlite
```

Kontrola obnovenej databázy:

```bash
sqlite3 estonia_migration.sqlite "PRAGMA integrity_check; PRAGMA foreign_key_check;"
```

Správny výsledok je `ok` a žiadny výstup z kontroly cudzích kľúčov.

## MySQL a PostgreSQL

Databáza a SQL export sú pripravené pre **SQLite**. Pri použití MySQL alebo PostgreSQL treba údaje a schému skonvertovať; SQL export nie je priamo kompatibilný s týmito systémami.

## Obsah databázy

- **13 zdrojových tabuliek** zo Statistics Estonia, Eurostatu, World Bank a TAI.
- **6 dimenzií** (`dim_year`, `dim_region`, `dim_sex`, `dim_age_group`, `dim_indicator`, `dim_dataset`).
- **1 faktová tabuľka** `fact_observation` – kompaktný analytický model pre 10 zdrojových tabuliek.
- **2 pomocné tabuľky** `source_registry` a `import_log` – zdroje a história načítania.
- **3 pohľady (VIEW)** `vw_education_source`, `vw_housing_source` a `vw_health_estonia` – prístup k ďalším trom zdrojovým tabuľkám bez kopírovania dát do faktovej tabuľky.

Podrobnosti: [`docs/ER_MODEL.md`](docs/ER_MODEL.md), [`docs/DATA_MODEL_DICTIONARY.md`](docs/DATA_MODEL_DICTIONARY.md), [`docs/DATA_DICTIONARY.md`](docs/DATA_DICTIONARY.md).

## Inštalácia pre prácu so skriptmi

Pre samotné otvorenie hotovej databázy nie je Python potrebný. Ak chcete spúšťať skripty, potrebujete **Python 3.10+**, SQLite a balíky zo súboru `requirements.txt`:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

Nasledujúce príkazy sa spúšťajú **z koreňového priečinka projektu**. Pred načítaním alebo prestavbou dát si urobte zálohu databázy.

## Skripty a odporúčané poradie

| Poradie | Súbor | Účel |
|---|---|---|
| 1 | `scripts/own/etl.py` | Načítanie tabuliek zo Statistics Estonia a prípadne TAI cez PxWeb API; výber pomocou `--tables`. |
| 2 | `scripts/own/import_csv.py` | Import ručne stiahnutých CSV, najmä `NH01` a `LFSA_EEGATM`; pri existujúcej tabuľke vyžaduje `--replace`. |
| 3 | `scripts/common/load_worldbank.py` | Získanie ukazovateľov World Bank pre Estónsko. |
| 4 | `scripts/common/load_eurostat.py` | Získanie údajov Eurostat (`migr_imm4ctb`). |
| 5 | `scripts/own/validate.py` | Kontrola tabuliek zo `config/datasets.json` a registra zdrojov. |
| 6 | `scripts/common/validate_international.py` | Kontrola obsahu a metadát World Bank a Eurostatu. |
| 7 | `scripts/populate_model.py` | Naplnenie dimenzií a `fact_observation` podľa `config/processing_rules.json`. |
| 8 | `scripts/inspect_db.py` | Výpis tabuliek, stĺpcov, počtu riadkov a ukážok záznamov. |
| Voliteľne | `scripts/create_db_copy.py` | Vytvorenie časovo označenej záložnej `.db` kópie do `data/db_copies/`. |
| Podporný modul | `scripts/common/international_common.py` | Spoločná logika pre medzinárodné API; **nespúšťa sa samostatne**. |

**Dôležité:** Pomocný modul `scripts/metadata_store.py` je súčasťou projektu. Pred spustením ETL používajte opravenú verziu `scripts/own/etl.py` s cestami odvodenými od koreňa projektu. Pôvodné dáta pri opätovnom načítaní môžu byť prepísané; pracujte s kópiou databázy.

### Príklady príkazov

Kontrola hotovej databázy:

```bash
python scripts/own/validate.py --db data/estonia_migration.sqlite
python scripts/common/validate_international.py --db data/estonia_migration.sqlite
python scripts/inspect_db.py
```

Po oprave chýbajúceho modulu a ciest je možné načítať údaje, napríklad:

```bash
python scripts/own/etl.py --tables RVR03 RVR05 --db data/estonia_migration.sqlite
python scripts/own/import_csv.py cesta/k/NH01.csv --dataset NH01 --db data/estonia_migration.sqlite
python scripts/common/load_worldbank.py --db data/estonia_migration.sqlite
python scripts/common/load_eurostat.py --db data/estonia_migration.sqlite
```

Analytický model sa vytvára **až po načítaní všetkých zdrojov**:

```bash
sqlite3 -bail data/estonia_migration.sqlite < sql/01_create_dimensions.sql
sqlite3 -bail data/estonia_migration.sqlite < sql/02_create_facts.sql
python scripts/populate_model.py --db data/estonia_migration.sqlite --rules config/processing_rules.json
sqlite3 -bail data/estonia_migration.sqlite < sql/08_compact_views.sql
sqlite3 -header -column data/estonia_migration.sqlite < sql/05_validate_model.sql
sqlite3 -header -column data/estonia_migration.sqlite < sql/06_check_processing.sql
sqlite3 -header -column data/estonia_migration.sqlite < sql/07_check_coverage.sql
```

**Pozor:** Tvorba dimenzií a faktov je postup pre novú databázu. Na existujúcej databáze s naplneným modelom ju nespúšťajte bez kontroly; prepínač `--replace` v `populate_model.py` prestavia odvodené dáta.

## Konfigurácia a dokumentácia

- `config/datasets.json` – zdroje, identifikátory a nastavenia domácich štatistických tabuliek.
- `config/international.json` – konfigurácia World Bank a Eurostatu.
- `config/processing_rules.json` – časový rozsah, chýbajúce hodnoty a pravidlá kompaktného modelu.
- `sql/01_create_dimensions.sql`, `02_create_facts.sql` – vytvorenie analytickej schémy.
- `sql/03_populate_dimensions.sql`, `04_populate_facts.sql` – informačné súbory; skutočné naplnenie robí Python skript `populate_model.py`.
- `sql/05_validate_model.sql` až `07_check_coverage.sql` – kontrolné dotazy.
- `sql/08_compact_views.sql` – definície troch SQL pohľadov.
- `docs/` – dokumentácia modelu a spracovania; `reports/data_audit.json` – záznam skoršieho auditu.

## Zdroje údajov

[Statistics Estonia](https://andmed.stat.ee/en/stat) · [Eurostat](https://ec.europa.eu/eurostat) · [World Bank](https://data.worldbank.org/country/estonia) · [TAI](https://statistika.tai.ee/pxweb/en/Andmebaas/)
