"""Audit students without assigned tests.

This project models test assignment via rows in `test_results`.
A student can appear to have "no assigned exams" in two main cases:
1) Their class has no tests at all (normal situation).
2) Their class has tests, but `test_results` rows are missing (data inconsistency).

Run:
  python tools/audit_students_without_tests.py
  python tools/audit_students_without_tests.py --db path/to/attendance.db

Output:
  - Students in classes with tests but missing assignments
  - Students in classes with no tests
"""

from __future__ import annotations

import argparse
import sqlite3
from pathlib import Path
from typing import Iterable


def _connect(db_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA foreign_keys = ON")
    conn.row_factory = sqlite3.Row
    return conn


def _print_rows(title: str, rows: Iterable[sqlite3.Row]) -> None:
    rows = list(rows)
    print("\n" + title)
    print("-" * len(title))
    if not rows:
        print("(none)")
        return
    for r in rows:
        # Keep output stable and easy to scan.
        print(
            f"StudentId={r['StudentId']} | {r['Surname']} {r['Name']} | classId={r['classId']}"
        )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--db",
        default="attendance.db",
        help="Path to SQLite database (default: attendance.db)",
    )
    args = parser.parse_args()

    db_path = Path(args.db)
    if not db_path.exists():
        # Try relative to repo root (common when run from tools/).
        repo_candidate = Path(__file__).resolve().parent.parent / args.db
        if repo_candidate.exists():
            db_path = repo_candidate
        else:
            print(f"Database not found: {args.db}")
            return 2

    conn = _connect(db_path)
    try:
        cur = conn.cursor()

        # Case 1: Class has tests, but assignments missing (no test_results rows for those tests).
        # We detect missing per-student rows by checking whether there exists at least one test in the
        # student's class that has no matching test_results row for that student.
        cur.execute(
            """
            SELECT DISTINCT s.StudentId, s.Surname, s.Name, s.classId
            FROM students s
            WHERE s.classId IS NOT NULL
              AND EXISTS (
                    SELECT 1
                    FROM tests t
                    WHERE t.classId = s.classId
              )
              AND EXISTS (
                    SELECT 1
                    FROM tests t
                    LEFT JOIN test_results tr
                           ON tr.TestId = t.IdTest AND tr.StudentId = s.StudentId
                    WHERE t.classId = s.classId
                      AND tr.IdResult IS NULL
              )
            ORDER BY s.classId, s.Surname, s.Name
            """
        )
        missing_assignments = cur.fetchall()

        # Case 2: Class has no tests at all (normal).
        cur.execute(
            """
            SELECT s.StudentId, s.Surname, s.Name, s.classId
            FROM students s
            WHERE s.classId IS NOT NULL
              AND NOT EXISTS (
                    SELECT 1
                    FROM tests t
                    WHERE t.classId = s.classId
              )
            ORDER BY s.classId, s.Surname, s.Name
            """
        )
        no_tests_in_class = cur.fetchall()

        print(f"DB: {db_path}")
        _print_rows(
            "Students in classes WITH tests but MISSING assignments (inconsistency)",
            missing_assignments,
        )
        _print_rows(
            "Students in classes with NO tests (normal)",
            no_tests_in_class,
        )

        # Exit non-zero if inconsistency detected (useful for CI / manual checks).
        return 1 if missing_assignments else 0
    finally:
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main())
