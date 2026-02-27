from __future__ import annotations

from typing import List

from db import get_conn


def list_classes_ids() -> List[str]:
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute("SELECT id FROM classes ORDER BY id")
        return [row["id"] for row in cur.fetchall()]
    finally:
        conn.close()


def search_students_by_class(class_id: str, needle: str | None = None) -> List[dict]:
    conn = get_conn()
    try:
        cur = conn.cursor()
        if needle:
            like = f"%{needle}%"
            cur.execute(
                """SELECT StudentId, Surname, Name
                       FROM students
                       WHERE classId=? AND (
                             StudentId LIKE ? OR Surname LIKE ? OR Name LIKE ?
                       )
                       ORDER BY Name""",
                (class_id, like, like, like),
            )
        else:
            cur.execute(
                """SELECT StudentId, Surname, Name
                       FROM students
                       WHERE classId=?
                       ORDER BY Name""",
                (class_id,),
            )
        return [dict(row) for row in cur.fetchall()]
    finally:
        conn.close()


def determine_student_class(student_id: str) -> str | None:
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute("SELECT classId FROM students WHERE StudentId=?", (student_id,))
        row = cur.fetchone()
        return row["classId"] if row else None
    finally:
        conn.close()
