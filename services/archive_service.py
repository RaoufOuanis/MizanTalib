"""Business logic for archiving and restoring attendance databases."""

from datetime import datetime
from pathlib import Path
import shutil

from db import init_db


def list_archives(archives_dir: Path) -> list[tuple[Path, datetime]]:
    archives_dir.mkdir(parents=True, exist_ok=True)
    results: list[tuple[Path, datetime]] = []
    for entry in archives_dir.glob("attendance_*.db"):
        try:
            created = datetime.fromtimestamp(entry.stat().st_mtime)
        except OSError:
            continue
        results.append((entry, created))
    results.sort(key=lambda item: item[1], reverse=True)
    return results


def create_archive(db_path: Path, archives_dir: Path) -> Path:
    archives_dir.mkdir(parents=True, exist_ok=True)
    if not db_path.exists():
        raise FileNotFoundError("Current database file not found")

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = archives_dir / f"attendance_{timestamp}.db"
    shutil.copy2(db_path, backup_path)

    try:
        db_path.unlink()
    except FileNotFoundError:
        pass
    init_db()
    return backup_path


def restore_archive(db_path: Path, backup_path: Path) -> Path:
    if not backup_path.exists():
        raise FileNotFoundError("Selected archive does not exist")

    try:
        db_path.unlink()
    except FileNotFoundError:
        pass
    shutil.copy2(backup_path, db_path)
    init_db()
    return backup_path
