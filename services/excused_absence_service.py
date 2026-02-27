from __future__ import annotations

from typing import Iterable, List, Optional

from db import get_conn


def list_classes() -> List[str]:
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute("SELECT id FROM classes ORDER BY id")
        return [row["id"] for row in cur.fetchall()]
    finally:
        conn.close()


def list_students_for_class(class_id: str) -> List[str]:
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute(
            """SELECT StudentId || ' - ' || Surname || ' ' || Name AS label
                   FROM students
                   WHERE classId=?
                   ORDER BY Name, Surname""",
            (class_id,),
        )
        return [row["label"] for row in cur.fetchall()]
    finally:
        conn.close()


def list_session_types_for_class(class_id: str) -> List[dict]:
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute(
            """
                SELECT DISTINCT st.id, st.subject_code || '-' || st.type AS label
                FROM session_types st
                JOIN sessions s ON s.sessionTypeId = st.id
                WHERE s.classId=?
                ORDER BY label
            """,
            (class_id,),
        )
        return [dict(row) for row in cur.fetchall()]
    finally:
        conn.close()


def list_session_types_any() -> List[dict]:
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT DISTINCT id, subject_code || '-' || type AS label FROM session_types ORDER BY label"
        )
        return [dict(row) for row in cur.fetchall()]
    finally:
        conn.close()


def list_excused_absences(
    scope: str,
    class_id: Optional[str],
    student_id: Optional[str],
    session_type_id: Optional[int],
) -> List[dict]:
    where_clauses: List[str] = []
    params: List[object] = []

    if scope in ("طالب محدد", "student"):
        if not (class_id and student_id):
            return []
        where_clauses.extend(["e.StudentId=?", "e.classId=?"])
        params.extend([student_id, class_id])
    elif scope in ("قسم كامل", "class"):
        if not class_id:
            return []
        where_clauses.append("e.classId=?")
        params.append(class_id)

    if session_type_id:
        where_clauses.append("e.sessionTypeId=?")
        params.append(session_type_id)

    where_sql = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""

    query = f"""
        WITH session_dates AS (
            SELECT sessionToken, date(MIN(SessionDate)) AS d
            FROM sessions
            GROUP BY sessionToken
        )
        SELECT
            st.StudentId AS sid,
            st.Name,
            st.Surname,
            st.classId AS classId,
            sd.d,
            e.sessionTypeId,
            COALESCE(e.justification_path, '') AS justification,
            COALESCE(stype.subject_code || '-' || stype.type, '') AS stype_label
        FROM excused_absences e
        JOIN students st ON st.StudentId = e.StudentId
        LEFT JOIN session_dates sd ON sd.sessionToken = e.sessionToken
        LEFT JOIN session_types stype ON stype.id = e.sessionTypeId
        {where_sql}
        ORDER BY sd.d, st.Name, st.Surname
    """

    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute(query, tuple(params))
        return [dict(row) for row in cur.fetchall()]
    finally:
        conn.close()


def list_sessions_for_excuse(
    class_id: str,
    student_id: str,
    session_type_id: int,
    start_date: str,
    end_date: str,
) -> List[dict]:
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute(
            """
                SELECT s.sessionToken, MIN(s.SessionDate) AS the_date
                FROM sessions s
                WHERE s.classId=?
                AND s.sessionTypeId=?
                AND date(s.SessionDate) BETWEEN date(?) AND date(?)
                GROUP BY s.sessionToken
                ORDER BY the_date
            """,
            (class_id, session_type_id, start_date, end_date),
        )
        tokens = cur.fetchall()

        rows: List[dict] = []
        for token_row in tokens:
            token = token_row["sessionToken"]

            cur.execute(
                """
                    SELECT presence FROM sessions
                    WHERE sessionToken=? AND StudentId=? LIMIT 1
                """,
                (token, student_id),
            )
            presence_row = cur.fetchone()
            is_absent = (presence_row is None) or (presence_row["presence"] == 0)

            if not is_absent:
                continue

            cur.execute(
                """
                    SELECT 1 FROM excused_absences
                    WHERE StudentId=? AND sessionToken=? AND sessionTypeId=? AND classId=?
                    LIMIT 1
                """,
                (student_id, token, session_type_id, class_id),
            )
            already_excused = cur.fetchone()
            if already_excused:
                continue

            cur.execute("SELECT date(?) AS d", (token_row["the_date"],))
            date_row = cur.fetchone()
            rows.append({
                "sessionToken": token,
                "date": date_row["d"] if date_row else None,
            })

        return rows
    finally:
        conn.close()


def add_excused_absences(
    student_id: str,
    session_type_id: int,
    class_id: str,
    justification: Optional[str],
    session_tokens: Iterable[str],
) -> int:
    conn = get_conn()
    inserted = 0
    try:
        cur = conn.cursor()
        for token in session_tokens:
            cur.execute(
                """
                    INSERT INTO excused_absences
                        (StudentId, sessionToken, sessionTypeId, classId, justification_path)
                    VALUES (?, ?, ?, ?, ?)
                """,
                (student_id, token, session_type_id, class_id, justification or None),
            )
            if cur.rowcount:
                inserted += 1
        conn.commit()
        return inserted
    finally:
        conn.close()


def delete_excused_absence(
    student_id: str,
    class_id: Optional[str],
    session_type_id: Optional[int],
    session_date: str,
) -> int:
    conn = get_conn()
    try:
        cur = conn.cursor()
        params: List[object] = [student_id]
        query = "DELETE FROM excused_absences WHERE StudentId=?"

        if session_type_id is not None:
            query += " AND sessionTypeId=?"
            params.append(session_type_id)

        if class_id:
            query += " AND classId=?"
            params.append(class_id)

        query += """
            AND sessionToken IN (
                SELECT sessionToken FROM sessions WHERE date(SessionDate)=date(?)
            )
        """
        params.append(session_date)

        cur.execute(query, tuple(params))
        conn.commit()
        return cur.rowcount
    finally:
        conn.close()