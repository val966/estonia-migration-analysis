
from pathlib import Path
from datetime import datetime, timezone
import sqlite3

ROOT = Path(__file__).resolve().parents[1]

SOURCE = ROOT / "data" / "estonia_migration.sqlite"
SNAPSHOTS = ROOT / "data" / "db_copies"

def create_snapshot():
    if not SOURCE.is_file():
        raise FileNotFoundError(f"Database not found: {SOURCE}")

    SNAPSHOTS.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now(timezone.utc).strftime(
        "%Y%m%d_%H%M%S"
    )

    destination = SNAPSHOTS / (
        f"estonia_migration_{timestamp}.db"
    )

    if destination.exists():
        raise FileExistsError(destination)

    # SQLite backup API
    with sqlite3.connect(
        SOURCE.as_uri() + "?mode=ro", uri=True
    ) as source_db:
        with sqlite3.connect(destination) as target_db:
            source_db.backup(target_db)

    # Check the snapshot
    with sqlite3.connect(
        destination.as_uri() + "?mode=ro", uri=True
    ) as db:
        integrity = db.execute(
            "PRAGMA integrity_check"
        ).fetchone()[0]

    if integrity != "ok":
        destination.unlink()
        raise RuntimeError(f"Integrity check failed: {integrity}")

    print(f"Snapshot created: {destination}")
    print("Integrity check: OK")


if __name__ == "__main__":
    create_snapshot()
