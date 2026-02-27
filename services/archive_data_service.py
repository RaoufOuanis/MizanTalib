"""Read-only data helpers used by the archive tab."""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from db import get_conn


def fetch_archive_classes() -> list[str]:
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute("SELECT id FROM classes ORDER BY id")
        rows = cur.fetchall()
        return [row["id"] for row in rows]
    finally:
        conn.close()


def fetch_sessions(class_id: Optional[str]) -> list[tuple[str, datetime, str, str, int]]:
    conn = get_conn()
    try:
        cur = conn.cursor()
        query = (
            """
            SELECT
                s.sessionToken AS token,
                MIN(s.SessionDate) AS first_date,
                s.classId,
                st.subject_code || '-' || st.type AS session_label,
                COUNT(*) AS cnt
            FROM sessions s
            LEFT JOIN session_types st ON s.sessionTypeId = st.id
            WHERE s.sessionToken!='TYPE_REF'
            """
        )
        params: list[str] = []
        if class_id:
            query += " AND s.classId=?"
            params.append(class_id)
        query += " GROUP BY s.sessionToken, s.classId, session_label ORDER BY first_date DESC"
        cur.execute(query, tuple(params))
        rows = cur.fetchall()
        return [
            (row["token"], row["first_date"], row["classId"], row["session_label"], row["cnt"])
            for row in rows
        ]
    finally:
        conn.close()


def fetch_session_details(token: str, class_id: str, session_label: str) -> list[tuple]:
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT s.StudentId,
                   st.Name   AS nm,
                   st.Surname AS sur,
                   s.classId,
                   stypes.subject_code || '-' || stypes.type AS session_label,
                   s.participation
            FROM sessions s
            LEFT JOIN students st ON s.StudentId=st.StudentId
            LEFT JOIN session_types stypes ON s.sessionTypeId = stypes.id
            WHERE s.sessionToken=? AND s.classId=? AND (stypes.subject_code || '-' || stypes.type)=?
            ORDER BY st.Name, st.Surname
            """,
            (token, class_id, session_label),
        )
        rows = cur.fetchall()
        return [
            (row["StudentId"], row["nm"], row["sur"], row["classId"], row["session_label"], row["participation"])
            for row in rows
        ]
    finally:
        conn.close()


def fetch_session_attendance(token: str, class_id: str, session_label: str) -> list[dict]:
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT s.StudentId,
                   st.Name AS nm,
                   st.Surname AS sur,
                   s.participation,
                   s.SessionDate AS session_date,
                   s.presence
            FROM sessions s
            LEFT JOIN students st ON s.StudentId = st.StudentId
            LEFT JOIN session_types stypes ON s.sessionTypeId = stypes.id
            WHERE s.sessionToken=? AND s.classId=? AND (stypes.subject_code || '-' || stypes.type)=?
            ORDER BY st.Name, st.Surname
            """,
            (token, class_id, session_label),
        )
        return [dict(row) for row in cur.fetchall()]
    finally:
        conn.close()


def fetch_students_for_class(class_id: str) -> list[dict]:
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT StudentId AS sid, Name AS nm, Surname AS sur
            FROM students
            WHERE classId=?
            ORDER BY nm, sur
            """,
            (class_id,),
        )
        return [dict(row) for row in cur.fetchall()]
    finally:
        conn.close()


def search_student_sessions(student_id: str, name: str, surname: str) -> list[tuple]:
    conn = get_conn()
    try:
        cur = conn.cursor()
        query = (
            """
            SELECT st.StudentId,
                   st.Name    AS nm,
                   st.Surname AS sur,
                   st.classId,
                   stypes.subject_code || '-' || stypes.type AS session_label,
                   COUNT(DISTINCT s.sessionToken) AS total_sessions,
                   SUM(s.participation) AS total_part
            FROM sessions s
            LEFT JOIN students st ON s.StudentId=st.StudentId
            LEFT JOIN session_types stypes ON s.sessionTypeId = stypes.id
            WHERE s.sessionToken!='TYPE_REF'
            """
        )
        params: list[str] = []
        if student_id:
            query += " AND st.StudentId LIKE ? COLLATE NOCASE"
            params.append(f"%{student_id}%")
        if name:
            query += " AND st.Name LIKE ? COLLATE NOCASE"
            params.append(f"%{name}%")
        if surname:
            query += " AND st.Surname LIKE ? COLLATE NOCASE"
            params.append(f"%{surname}%")
        query += " GROUP BY st.StudentId, session_label ORDER BY st.Name, st.Surname"
        cur.execute(query, tuple(params))
        rows = cur.fetchall()
        return [
            (row["StudentId"], row["nm"], row["sur"], row["classId"], row["session_label"], row["total_part"] or 0)
            for row in rows
        ]
    finally:
        conn.close()


def fetch_class_statistics() -> tuple[list[dict], list[dict]]:
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT s.classId,
                   stypes.subject_code || '-' || stypes.type AS session_label,
                   COUNT(DISTINCT s.sessionToken) AS sessions,
                   COUNT(DISTINCT s.StudentId)   AS students,
                   SUM(s.participation)          AS total_part
            FROM sessions s
            LEFT JOIN session_types stypes ON s.sessionTypeId = stypes.id
            WHERE s.sessionToken!='TYPE_REF'
            GROUP BY s.classId, session_label
            ORDER BY s.classId, session_label
            """
        )
        stats_rows = [dict(row) for row in cur.fetchall()]
        cur.execute(
            """
            SELECT MIN(s.SessionDate) AS session_date
            FROM sessions s
            WHERE s.sessionToken!='TYPE_REF'
            GROUP BY s.sessionToken
            """
        )
        date_rows = [dict(row) for row in cur.fetchall()]
        return stats_rows, date_rows
    finally:
        conn.close()


def fetch_student_summary(student_id: str) -> tuple[list[dict], list[dict]]:
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT st.StudentId, st.Name, st.Surname, st.classId,
                   stypes.subject_code || '-' || stypes.type AS session_label,
                   COUNT(DISTINCT s.sessionToken) AS total_sessions,
                   SUM(s.participation) AS total_part,
                   MIN(s.SessionDate) AS first_session,
                   MAX(s.SessionDate) AS last_session
            FROM sessions s
            LEFT JOIN students st ON s.StudentId=st.StudentId
            LEFT JOIN session_types stypes ON s.sessionTypeId = stypes.id
            WHERE st.StudentId=? AND s.sessionToken!='TYPE_REF'
            GROUP BY st.StudentId, session_label
            ORDER BY session_label
            """,
            (student_id,),
        )
        summary_rows = [dict(row) for row in cur.fetchall()]
        cur.execute(
            """
            SELECT s.sessionToken, s.SessionDate, s.classId,
                   stypes.subject_code || '-' || stypes.type AS session_label,
                   s.participation
            FROM sessions s
            LEFT JOIN session_types stypes ON s.sessionTypeId = stypes.id
            WHERE s.StudentId=? AND s.sessionToken!='TYPE_REF'
            ORDER BY s.SessionDate DESC
            """,
            (student_id,),
        )
        detail_rows = [dict(row) for row in cur.fetchall()]
        return summary_rows, detail_rows
    finally:
        conn.close()


def fetch_session_type_id(token: str, class_id: str) -> Optional[int]:
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT st.id AS stype_id
            FROM sessions s
            LEFT JOIN session_types st ON s.sessionTypeId = st.id
            WHERE s.sessionToken=? AND s.classId=? LIMIT 1
            """,
            (token, class_id),
        )
        row = cur.fetchone()
        if not row:
            return None
        return row["stype_id"]
    finally:
        conn.close()
