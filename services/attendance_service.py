from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable, List, Optional

from db import get_conn


def list_session_types() -> List[str]:
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute("SELECT subject_code, type FROM session_types ORDER BY subject_code, type")
        rows = cur.fetchall()
        return [f"{row['subject_code']}-{row['type']}" for row in rows]
    finally:
        conn.close()


def list_students_for_manual_add(class_id: str, needle: str | None = None) -> List[dict]:
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


def resolve_student_class(student_id: str, fallback_class: str | None = None) -> str | None:
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute("SELECT classId FROM students WHERE StudentId=?", (student_id,))
        row = cur.fetchone()
        if row:
            return row["classId"]
        return fallback_class
    finally:
        conn.close()


def fetch_student_by_id(student_id: str) -> Optional[dict]:
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT StudentId, Name, Surname, classId FROM students WHERE StudentId=?",
            (student_id,),
        )
        row = cur.fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def count_students_in_class(class_id: str | None) -> int:
    if not class_id:
        return 0
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) as cnt FROM students WHERE classId=?", (class_id,))
        row = cur.fetchone()
        return int(row["cnt"]) if row else 0
    finally:
        conn.close()


def get_session_type_id(subject_code: str, session_type: str) -> Optional[int]:
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT id FROM session_types WHERE subject_code=? AND type=?",
            (subject_code, session_type),
        )
        row = cur.fetchone()
        return int(row["id"]) if row else None
    finally:
        conn.close()


def ensure_unique_session_token(candidate: str, base_token: str | None = None) -> str:
    token = candidate or base_token or "SESSION"
    base = base_token or token
    conn = None
    try:
        conn = get_conn()
        cur = conn.cursor()
        suffix = 1
        current = token
        while True:
            cur.execute("SELECT 1 FROM sessions WHERE sessionToken=? LIMIT 1", (current,))
            if not cur.fetchone():
                return current
            suffix += 1
            current = f"{base}{suffix}"
    except Exception:
        return token
    finally:
        if conn:
            conn.close()


@dataclass
class SessionSaveResult:
    inserted: int = 0
    updated: int = 0
    skipped: List[str] = field(default_factory=list)


def save_session_records(
    token: str,
    session_type_id: int,
    session_datetime: str,
    entries: Iterable[dict],
) -> SessionSaveResult:
    conn = get_conn()
    result = SessionSaveResult()
    try:
        cur = conn.cursor()
        for entry in entries:
            sid = str(entry.get("student_id", "")).strip()
            if not sid:
                continue
            class_id = str(entry.get("class_id", "")).strip()
            presence = int(entry.get("presence", 1) or 0)
            try:
                part_val = float(entry.get("participation", 0.0) or 0.0)
            except (TypeError, ValueError):
                part_val = 0.0

            cur.execute(
                """INSERT OR IGNORE INTO sessions
                    (sessionToken, StudentId, presence, participation, SessionDate, classId, sessionTypeId)
                    VALUES (?,?,?,?,?,?,?)""",
                (token, sid, presence, part_val, session_datetime, class_id, session_type_id),
            )

            if cur.rowcount:
                result.inserted += 1
                continue

            cur.execute(
                """UPDATE sessions
                        SET presence=?, participation=?, SessionDate=?, classId=?, sessionTypeId=?
                        WHERE sessionToken=? AND StudentId=?""",
                (presence, part_val, session_datetime, class_id, session_type_id, token, sid),
            )

            if cur.rowcount:
                result.updated += 1
            else:
                result.skipped.append(sid)

        conn.commit()
        return result
    finally:
        conn.close()
