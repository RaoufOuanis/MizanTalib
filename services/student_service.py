from __future__ import annotations

from typing import Iterable, Literal, Sequence

from db import get_conn

FilterType = Literal["all", "year", "class"]


def fetch_class_filter_metadata() -> dict[str, list[tuple[str, str]]]:
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute("SELECT DISTINCT cycle, year FROM classes ORDER BY cycle, year")
        years = [(row["cycle"], row["year"]) for row in cur.fetchall()]
        cur.execute("SELECT id, cycle, year FROM classes ORDER BY year, id")
        classes = [(row["id"], row["cycle"], row["year"]) for row in cur.fetchall()]
        return {"years": years, "classes": classes}
    finally:
        conn.close()


def fetch_class_ids() -> list[str]:
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute("SELECT id FROM classes ORDER BY id")
        return [row["id"] for row in cur.fetchall()]
    finally:
        conn.close()


def fetch_students(filter_type: FilterType, value: Sequence[str] | str | None) -> list[dict]:
    conn = get_conn()
    try:
        cur = conn.cursor()
        if filter_type == "class" and isinstance(value, str) and value:
            cur.execute("SELECT * FROM students WHERE classId=?", (value,))
        elif filter_type == "year" and isinstance(value, Sequence) and len(value) == 2:
            cur.execute(
                """SELECT s.* FROM students s JOIN classes c ON s.classId=c.id
                       WHERE c.cycle=? AND c.year=?""",
                tuple(value),
            )
        else:
            cur.execute("SELECT * FROM students")
        rows = cur.fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


def add_student(student_id: str, surname: str, name: str, class_id: str) -> bool:
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute(
            "INSERT OR IGNORE INTO students (StudentId, Surname, Name, classId) VALUES (?,?,?,?)",
            (student_id, surname, name, class_id),
        )
        inserted = cur.rowcount > 0
        if inserted:
            cur.execute("SELECT IdTest FROM tests WHERE classId=?", (class_id,))
            for row in cur.fetchall():
                cur.execute(
                    "INSERT OR IGNORE INTO test_results (TestId, StudentId, degree) VALUES (?,?,?)",
                    (row["IdTest"], student_id, None),
                )
        conn.commit()
        return inserted
    finally:
        conn.close()


def update_student(student_id: str, surname: str, name: str, class_id: str) -> bool:
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute("SELECT classId FROM students WHERE StudentId=?", (student_id,))
        existing = cur.fetchone()
        previous_class = existing["classId"] if existing else None
        cur.execute(
            "UPDATE students SET Surname=?, Name=?, classId=? WHERE StudentId=?",
            (surname, name, class_id, student_id),
        )
        updated = cur.rowcount > 0
        if updated and previous_class != class_id:
            cur.execute("SELECT IdTest FROM tests WHERE classId=?", (class_id,))
            for row in cur.fetchall():
                cur.execute(
                    "INSERT OR IGNORE INTO test_results (TestId, StudentId, degree) VALUES (?,?,?)",
                    (row["IdTest"], student_id, None),
                )
        conn.commit()
        return updated
    finally:
        conn.close()


def remove_student(student_id: str) -> bool:
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute("DELETE FROM students WHERE StudentId=?", (student_id,))
        conn.commit()
        return cur.rowcount > 0
    finally:
        conn.close()


def bulk_insert_students(rows: Iterable[dict], default_class_id: str) -> int:
    conn = get_conn()
    inserted = 0
    try:
        cur = conn.cursor()
        tests_cache: dict[str, list[int]] = {}
        for row in rows:
            student_id = str(row.get("StudentId", "")).strip()
            surname = str(row.get("Surname", "")).strip()
            name = str(row.get("Name", "")).strip()
            class_id = str(row.get("classId", default_class_id) or default_class_id).strip()
            if not (student_id and surname and name and class_id):
                continue
            cur.execute(
                "INSERT OR IGNORE INTO students (StudentId, Surname, Name, classId) VALUES (?,?,?,?)",
                (student_id, surname, name, class_id),
            )
            if cur.rowcount > 0:
                inserted += 1
                if class_id not in tests_cache:
                    cur.execute("SELECT IdTest FROM tests WHERE classId=?", (class_id,))
                    tests_cache[class_id] = [row["IdTest"] for row in cur.fetchall()]
                for test_id in tests_cache.get(class_id, []):
                    cur.execute(
                        "INSERT OR IGNORE INTO test_results (TestId, StudentId, degree) VALUES (?,?,?)",
                        (test_id, student_id, None),
                    )
        conn.commit()
        return inserted
    finally:
        conn.close()