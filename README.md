# Estonia Migration Analysis

Проект по сбору и анализу официальной статистики миграции Эстонии. Данные загружаются из **Statistics Estonia** в одну базу **SQLite**; SQL и Python используются для проверки качества, исследования тенденций и поиска аномалий.

**Источник:** [Statistics Estonia — Migration](https://andmed.stat.ee/en/stat/rahvastik__rahvastikusundmused__ranne) · [API](https://andmed.stat.ee/abi/API-manual.pdf)

## Технологии и версии

| Компонент | Версия / требование | Назначение |
|---|---|---|
| Python | **3.10+** (первоначальная среда: 3.10.12) | Загрузка и анализ данных |
| `pandas` | **>=2.1,<3** | Таблицы и вычисления |
| `requests` | **>=2.31,<3** | Запросы к API Statistics Estonia |
| SQLite / `sqlite3` | Версия зависит от установленного SQLite и Python | Хранение данных и SQL-запросы; модуль `sqlite3` входит в Python |
| Git + GitHub | Версия Git зависит от среды | Совместная работа и история изменений |
| VS Code + Ubuntu/WSL | Версии не фиксируются | Рекомендуемая среда разработки |

`requirements.txt` задаёт **диапазоны версий**, а не точные версии установленной среды. Проверить фактические версии:

```bash
python3 --version
sqlite3 --version
python3 -c "import sqlite3; print('SQLite (Python):', sqlite3.sqlite_version)"
git --version
# После активации .venv:
python -m pip show pandas requests
```

## Структура проекта

| Файл / каталог | Назначение |
|---|---|
| `README.md` | Общая инструкция по проекту |
| `requirements.txt` | Обязательные зависимости Python |
| `.gitignore` | Исключения для Git (виртуальная среда, локальные артефакты) |
| `DATA_DICTIONARY.md` | Описание таблиц, полей и ограничений интерпретации |
| `scripts/download.py` | Загрузка таблиц из API и обновление локальной SQLite-базы |
| `scripts/inspect_db.py` | Список таблиц, столбцов, число строк и примеры записей |
| `scripts/validate_release.py` | Проверка целостности БД; формирование отчёта и SHA-256 |
| `scripts/anomalies.py` | Предварительный поиск резких изменений в RVR03 (порог 50%) |
| `scripts/test_yearly_anomalies.py`* | Тест Modified Z-score для годовой внешней иммиграции |
| `scripts/create_snapshot.py`* | Создание отдельных `.db`-снимков базы |
| `sql/examples.sql` | Примеры запросов к исходным таблицам |
| `sql/quality_checks.sql` | Проверки охвата, категорий, дубликатов и необычных значений |
| `sql/migration_yearly.sql` | Временный VIEW годовой внешней миграции и проверка сальдо |
| `data/estonia_migration.sqlite` | **Рабочая база** (создаётся при загрузке, не хранится в Git) |
| `data/metadata/RVR*.json` | Метаданные таблиц, полученные из API |
| `data/candidate_anomalies.csv` | Результат `anomalies.py` |
| `data/yearly_anomalies.csv`* | Результат теста Modified Z-score |
| `data/snapshots/*.db`* | Локальные снимки базы |
| `release/validation_report.json` | Отчёт о проверке конкретной версии БД |
| `release/SHA256SUMS` | SHA-256-хеш проверенной БД для сверки при передаче |

\* **Дополнительные файлы:** используй соответствующие команды только в том случае, если эти файлы созданы и добавлены в репозиторий. Папки `data/` и `release/` частично формируются автоматически и могут отсутствовать сразу после `git clone`.

**Текущие исходные таблицы:** `rvr03` (2000–2025), `rvr05`, `rvr08`, `rvr051` (2004–2025); служебная таблица `source_registry` хранит источники, даты получения и число строк. В дальнейшем планируется добавление демографических таблиц.

## Первый запуск (Ubuntu / VS Code)

Выполняй команды **из корня проекта**, где лежит `requirements.txt`:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

Для следующих сеансов достаточно перейти в каталог проекта и выполнить `source .venv/bin/activate`.

## Основные команды

```bash
# Полная загрузка/обновление всех четырёх исходных таблиц
python scripts/download.py

# Обновить одну исходную таблицу
python scripts/download.py --tables RVR05

# Посмотреть структуру и записи
python scripts/inspect_db.py

# Первичный поиск кандидатов в аномалии (RVR03)
python scripts/anomalies.py

# Дополнительный тест
python scripts/test_yearly_anomalies.py
```

**Важно:** `download.py` **заменяет содержимое запрашиваемой исходной таблицы**. Для воспроизводимого анализа используйте общий проверенный снимок, а не независимо перезагруженные данные.

### SQL-проверки

Понадобится установленный SQLite CLI (`sudo apt install sqlite3`). Из корня проекта:

```bash
sqlite3 -readonly -header -column data/estonia_migration.sqlite < sql/quality_checks.sql
sqlite3 -readonly -header -column data/estonia_migration.sqlite < sql/migration_yearly.sql
```

`migration_yearly.sql` создаёт **временный VIEW** только для текущего подключения, а затем выводит годовые показатели и проверку `immigration - emigration = net_migration`; исходная база не изменяется.

### Снимок базы и подготовка к передаче

```bash
# Создать согласованную копию SQLite с расширением .db
sqlite3 data/estonia_migration.sqlite ".backup 'data/estonia_migration_v0.1.db'"

# Проверить именно эту копию и получить release/validation_report.json и SHA256SUMS
python scripts/validate_release.py --db data/estonia_migration_v0.1.db

# Проверить структуру файла
sqlite3 -readonly data/estonia_migration_v0.1.db "PRAGMA integrity_check;"
```

Если присутствует `scripts/create_snapshot.py`, альтернативный запуск: `python scripts/create_snapshot.py`. **`.db` и `.sqlite` — один формат SQLite; расширение не требует конвертации.**

Для передачи другой команде публикуем **один неизменяемый `.db`-снимок** вместе с `release/validation_report.json` и `release/SHA256SUMS` в **GitHub Release**. Приложенные контрольные суммы должны относиться именно к публикуемому файлу. Для Python 3.10 в `validate_release.py` должна использоваться совместимая реализация SHA-256 без `hashlib.file_digest()`.
