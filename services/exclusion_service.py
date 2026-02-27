from __future__ import annotations

import math
from typing import Dict, Iterable, List, Optional, Sequence

from db import (
    get_conn,
    get_subgroup_mode,
    get_app_setting,
    set_app_setting,
    list_exclusion_exceptions,
    add_exclusion_exception,
    remove_exclusion_exception,
)


_EXCLUSION_START_DATE_KEY = "exclusion_start_date"


def get_oldest_session_date() -> Optional[str]:
    """Return the oldest session date in DB as YYYY-MM-DD (best effort)."""
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT date(MIN(SessionDate)) AS d
            FROM sessions
            WHERE sessionToken!='TYPE_REF'
            """
        )
        row = cur.fetchone()
        if not row:
            return None
        d = row["d"] if isinstance(row, dict) or hasattr(row, "keys") else row[0]
        return str(d) if d else None
    except Exception:
        return None
    finally:
        conn.close()


def get_default_exclusion_start_date() -> Optional[str]:
    """Default date shown in UI: last user choice; else oldest session date."""
    last = (get_app_setting(_EXCLUSION_START_DATE_KEY, "") or "").strip()
    if last:
        return last
    return get_oldest_session_date()


def set_default_exclusion_start_date(value: str) -> None:
    """Persist last user-chosen start date (YYYY-MM-DD)."""
    set_app_setting(_EXCLUSION_START_DATE_KEY, (value or "").strip())


def list_classes() -> List[str]:
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute("SELECT DISTINCT id FROM classes ORDER BY id")
        return [row["id"] for row in cur.fetchall()]
    finally:
        conn.close()


def list_session_types_for_class(class_id: str) -> List[dict]:
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT DISTINCT st.id, st.subject_code || '-' || st.type AS label
            FROM sessions s JOIN session_types st ON st.id = s.sessionTypeId
            WHERE s.classId=?
            UNION
            SELECT DISTINCT st.id, st.subject_code || '-' || st.type AS label
            FROM tests t JOIN session_types st ON st.id = t.sessionTypeId
            WHERE t.classId=?
            """,
            (class_id, class_id),
        )
        return [dict(row) for row in cur.fetchall()]
    finally:
        conn.close()


def list_students_for_class(class_id: str) -> List[dict]:
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT StudentId, Name, Surname FROM students WHERE classId=? ORDER BY Name, Surname",
            (class_id,),
        )
        return [dict(row) for row in cur.fetchall()]
    finally:
        conn.close()


def compute_exclusion_risk(
    class_id: str,
    session_type_id: int,
    threshold: int,
    start_date: Optional[str] = None,
) -> List[tuple]:
    conn = get_conn()
    try:
        cur = conn.cursor()

        cur.execute(
            "SELECT StudentId, Name, Surname FROM students WHERE classId=? ORDER BY Name, Surname",
            (class_id,),
        )
        students = cur.fetchall()
        student_ids = [row["StudentId"] for row in students]

        attendance_map: Dict[str, float] = {}
        if student_ids:
            placeholders = ",".join("?" for _ in student_ids)
            params: List[object] = list(student_ids)
            # NOTE: Students may attend sessions with a different group/class.
            # Sessions are recorded with the session's classId, not necessarily the student's home classId.
            # For exclusion risk, we should treat presence in ANY class session of the same sessionType as attendance.
            params.append(session_type_id)
            date_clause = ""
            if start_date:
                date_clause = " AND date(SessionDate) >= date(?)"
                params.append(start_date)
            cur.execute(
                f"""
                    SELECT StudentId, COUNT(DISTINCT sessionToken) AS attended
                    FROM sessions
                    WHERE StudentId IN ({placeholders})
                      AND sessionTypeId=?
                      AND sessionToken!='TYPE_REF'
                      {date_clause}
                    GROUP BY StudentId
                """,
                params,
            )
            attendance_map = {row["StudentId"]: row["attended"] for row in cur.fetchall()}

        denom_params: List[object] = [class_id, session_type_id]
        denom_date_clause = ""
        if start_date:
            denom_date_clause = " AND date(SessionDate) >= date(?)"
            denom_params.append(start_date)
        cur.execute(
            f"""
            SELECT DISTINCT sessionToken
            FROM sessions
            WHERE classId=?
              AND sessionTypeId=?
              AND sessionToken!='TYPE_REF'
              {denom_date_clause}
            """,
            denom_params,
        )
        denom_count = len({row["sessionToken"] for row in cur.fetchall()})

        try:
            if get_subgroup_mode(class_id, session_type_id):
                denom_count = max(1, int(math.ceil(float(denom_count) / 2.0)))
        except Exception:
            pass

        excused_map: Dict[str, float] = {}
        if student_ids:
            placeholders = ",".join("?" for _ in student_ids)
            params = list(student_ids)
            params.extend([class_id, session_type_id])
            excused_date_clause = ""
            if start_date:
                # Filter excused absences based on the session date, not the record creation date.
                excused_date_clause = " AND sessionToken IN (SELECT DISTINCT sessionToken FROM sessions WHERE classId=? AND sessionTypeId=? AND sessionToken!='TYPE_REF' AND date(SessionDate) >= date(?))"
                params.extend([class_id, session_type_id, start_date])
            cur.execute(
                f"""
                    SELECT StudentId, SUM(COALESCE(weight, 1)) AS excused
                    FROM excused_absences
                    WHERE StudentId IN ({placeholders})
                      AND classId=?
                      AND sessionTypeId=?
                      {excused_date_clause}
                    GROUP BY StudentId
                """,
                params,
            )
            excused_map = {row["StudentId"]: row["excused"] for row in cur.fetchall()}

        try:
            exceptions = list_exclusion_exceptions(class_id, session_type_id)
        except Exception:
            exceptions = set()

        results: List[tuple] = []
        denom_value = float(denom_count or 1)
        for student in students:
            sid = student["StudentId"]
            if sid in exceptions:
                continue
            attended = float(attendance_map.get(sid, 0) or 0) + float(
                excused_map.get(sid, 0) or 0
            )
            absences = max(0.0, denom_value - attended)
            results.append(
                (
                    sid,
                    student["Name"],
                    student["Surname"],
                    attended,
                    int(denom_value),
                    int(math.ceil(absences)),
                )
            )

        at_risk = [row for row in results if row[5] >= threshold]
        return at_risk
    finally:
        conn.close()


def export_exclusion_to_workbook(rows: Sequence[tuple], headers: Sequence[str], workbook) -> None:
    ws = workbook.active
    ws.title = "Exclusion Risk"
    ws.append(list(headers))
    for row in rows:
        ws.append(list(row))


def list_exceptions(class_id: str, session_type_id: int) -> set:
    try:
        return set(list_exclusion_exceptions(class_id, session_type_id))
    except Exception:
        return set()


def add_exception(class_id: str, session_type_id: int, student_id: str) -> None:
    add_exclusion_exception(class_id, session_type_id, student_id)


def remove_exception(class_id: str, session_type_id: int, student_id: str) -> None:
    remove_exclusion_exception(class_id, session_type_id, student_id)