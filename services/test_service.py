from __future__ import annotations

from datetime import datetime
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

from db import get_conn


def list_class_ids() -> List[str]:
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute("SELECT id FROM classes ORDER BY id")
        return [row["id"] for row in cur.fetchall()]
    finally:
        conn.close()


def list_tests(filter_class: Optional[str] = None) -> List[dict]:
    conn = get_conn()
    try:
        cur = conn.cursor()
        if filter_class:
            cur.execute(
                """
                SELECT t.IdTest, t.TestName, st.subject_code || '-' || st.type AS session_label
                FROM tests t
                LEFT JOIN session_types st ON t.sessionTypeId = st.id
                WHERE t.classId=?
                ORDER BY t.CreatedAt DESC
                """,
                (filter_class,),
            )
        else:
            cur.execute(
                """
                SELECT t.IdTest, t.TestName, st.subject_code || '-' || st.type AS session_label
                FROM tests t
                LEFT JOIN session_types st ON t.sessionTypeId = st.id
                ORDER BY t.CreatedAt DESC
                """,
            )
        return [dict(row) for row in cur.fetchall()]
    finally:
        conn.close()


def list_session_type_labels_with_ids() -> Dict[str, int]:
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute("SELECT id, subject_code, type FROM session_types ORDER BY subject_code, type")
        rows = cur.fetchall()
        return {f"{row['subject_code']}-{row['type']}": row["id"] for row in rows}
    finally:
        conn.close()


def fetch_tests_for_class(class_id: str) -> List[dict]:
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT t.IdTest, t.TestName, t.TestType,
                   st.subject_code || '-' || st.type AS session_label
            FROM tests t
            LEFT JOIN session_types st ON t.sessionTypeId = st.id
            WHERE t.classId=?
            ORDER BY t.CreatedAt DESC
            """,
            (class_id,),
        )
        return [dict(row) for row in cur.fetchall()]
    finally:
        conn.close()


def fetch_test_for_edit(test_id: int, class_id: str) -> Optional[dict]:
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT t.TestName, t.TestType,
                   st.subject_code || '-' || st.type AS session_label
            FROM tests t
            LEFT JOIN session_types st ON t.sessionTypeId = st.id
            WHERE t.IdTest=? AND t.classId=?
            """,
            (test_id, class_id),
        )
        row = cur.fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def _has_results_entered(cur, test_id: int) -> bool:
    cur.execute(
        "SELECT COUNT(*) AS cnt FROM test_results WHERE TestId=? AND degree IS NOT NULL",
        (test_id,),
    )
    row = cur.fetchone()
    return bool(row and (row["cnt"] or 0) > 0)


def update_test(
    test_id: int,
    class_id: str,
    name: str,
    test_type: str,
    session_type_id: int,
) -> None:
    conn = get_conn()
    try:
        cur = conn.cursor()
        if _has_results_entered(cur, test_id):
            raise ValueError("RESULTS_ENTERED")

        cur.execute(
            """
            SELECT 1 FROM tests
            WHERE classId=? AND sessionTypeId=? AND LOWER(TestName)=LOWER(?) AND IdTest<>?
            """,
            (class_id, session_type_id, name, test_id),
        )
        if cur.fetchone():
            raise ValueError("DUPLICATE_NAME")

        cur.execute(
            """
            UPDATE tests SET TestName=?, TestType=?, sessionTypeId=? WHERE IdTest=?
            """,
            (name, test_type, session_type_id, test_id),
        )
        conn.commit()
    finally:
        conn.close()


def create_tests(
    class_ids: Sequence[str],
    name: str,
    test_type: str,
    session_type_id: int,
) -> Tuple[List[str], List[str]]:
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    created: List[str] = []
    duplicates: List[str] = []
    conn = get_conn()
    try:
        cur = conn.cursor()
        for class_id in class_ids:
            cur.execute(
                """
                SELECT 1 FROM tests
                WHERE classId=? AND sessionTypeId=? AND LOWER(TestName)=LOWER(?)
                """,
                (class_id, session_type_id, name),
            )
            if cur.fetchone():
                duplicates.append(class_id)
                continue

            cur.execute(
                """
                INSERT INTO tests (TestName, TestType, classId, sessionTypeId, CreatedAt)
                VALUES (?,?,?,?,?)
                """,
                (name, test_type, class_id, session_type_id, timestamp),
            )
            new_test_id = cur.lastrowid

            cur.execute("SELECT StudentId FROM students WHERE classId=?", (class_id,))
            for row in cur.fetchall():
                cur.execute(
                    "INSERT INTO test_results (TestId, StudentId, degree) VALUES (?,?,?)",
                    (new_test_id, row["StudentId"], None),
                )
            created.append(class_id)
        conn.commit()
        return created, duplicates
    finally:
        conn.close()


def delete_test(test_id: int) -> None:
    conn = get_conn()
    try:
        cur = conn.cursor()
        if _has_results_entered(cur, test_id):
            raise ValueError("RESULTS_ENTERED")
        cur.execute("DELETE FROM test_results WHERE TestId=?", (test_id,))
        cur.execute("DELETE FROM tests WHERE IdTest=?", (test_id,))
        conn.commit()
    finally:
        conn.close()


def list_test_results(
    class_id: Optional[str],
    test_id: Optional[int],
) -> List[dict]:
    sql = """
        SELECT t.IdTest, t.TestName, t.TestType, t.classId,
               tr.StudentId, tr.degree, s.Name AS nm, s.Surname AS sur,
               stype.subject_code || '-' || stype.type AS sessionInfo
        FROM tests t
        JOIN test_results tr ON t.IdTest=tr.TestId
        JOIN students s ON tr.StudentId=s.StudentId
        LEFT JOIN session_types stype ON t.sessionTypeId=stype.id
        WHERE 1=1
    """
    params: List[object] = []
    if class_id:
        sql += " AND t.classId=?"
        params.append(class_id)
    if test_id:
        sql += " AND t.IdTest=?"
        params.append(test_id)
    sql += " ORDER BY t.CreatedAt DESC, nm, sur"

    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute(sql, tuple(params))
        return [dict(row) for row in cur.fetchall()]
    finally:
        conn.close()


def update_degree(test_id: int, student_id: str, degree: Optional[float]) -> None:
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute(
            "UPDATE test_results SET degree=? WHERE TestId=? AND StudentId=?",
            (degree, test_id, student_id),
        )
        conn.commit()
    finally:
        conn.close()


def import_degrees_for_test(
    test_id: int,
    rows: Iterable[dict],
) -> dict:
    """Import/update degrees for a given test.

        Expected row shape:
            {"StudentId": str, "degree": Optional[float], "absent": bool}

    Rules:
    - Students not belonging to the test's class (i.e., no row in test_results for this TestId)
      are reported as "not_in_group" and skipped.
    - Absent rows do not update degree (keeps NULL).
    - degree==None is treated as absent (no update).

    Returns a report dict.
    """
    conn = get_conn()
    try:
        cur = conn.cursor()

        cur.execute("SELECT StudentId FROM test_results WHERE TestId=?", (test_id,))
        allowed_ids = {str(r["StudentId"]).strip() for r in cur.fetchall()}

        updated = 0
        skipped_absent = 0
        not_in_group: set[str] = set()
        seen_in_file: set[str] = set()

        for row in rows:
            sid = str(row.get("StudentId", "") or "").strip()
            if not sid:
                continue
            seen_in_file.add(sid)

            if sid not in allowed_ids:
                not_in_group.add(sid)
                continue

            is_absent = bool(row.get("absent"))
            degree = row.get("degree")

            if is_absent or degree is None:
                skipped_absent += 1
                continue

            cur.execute(
                "UPDATE test_results SET degree=? WHERE TestId=? AND StudentId=?",
                (degree, test_id, sid),
            )
            if cur.rowcount > 0:
                updated += 1

        conn.commit()

        missing_in_file = sorted(allowed_ids - seen_in_file)

        # Optional: include missing student names for better UX.
        missing_details: list[dict] = []
        if missing_in_file:
            placeholders = ",".join(["?"] * len(missing_in_file))
            cur.execute(
                f"SELECT StudentId, Name, Surname FROM students WHERE StudentId IN ({placeholders})",
                tuple(missing_in_file),
            )
            missing_details = [dict(r) for r in cur.fetchall()]

        # After import, consider any remaining NULL degrees as absents/not-graded.
        cur.execute(
            "SELECT StudentId FROM test_results WHERE TestId=? AND degree IS NULL",
            (test_id,),
        )
        absents = [str(r["StudentId"]).strip() for r in cur.fetchall()]

        return {
            "updated": updated,
            "skipped_absent": skipped_absent,
            "not_in_group": sorted(not_in_group),
            "absents": absents,
            "seen_in_file": sorted(seen_in_file),
            "missing_in_file": missing_in_file,
            "missing_in_file_details": missing_details,
            "group_size": len(allowed_ids),
        }
    finally:
        conn.close()
