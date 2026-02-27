from __future__ import annotations

import math
from typing import Dict, Iterable, List, Sequence, Tuple

from db import (
    get_conn,
    get_subgroup_mode as db_get_subgroup_mode,
    set_subgroup_mode as db_set_subgroup_mode,
)


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
            FROM sessions s
            JOIN session_types st ON st.id = s.sessionTypeId
            WHERE s.classId=?
            UNION
            SELECT DISTINCT st.id, st.subject_code || '-' || st.type AS label
            FROM tests t
            JOIN session_types st ON st.id = t.sessionTypeId
            WHERE t.classId=?
            ORDER BY label
            """,
            (class_id, class_id),
        )
        return [dict(row) for row in cur.fetchall()]
    finally:
        conn.close()


def get_subgroup_mode(class_id: str, session_type_id: int) -> bool:
    return bool(db_get_subgroup_mode(class_id, session_type_id))


def set_subgroup_mode(class_id: str, session_type_id: int, enabled: bool) -> None:
    db_set_subgroup_mode(class_id, session_type_id, enabled)


def compute_final_scores(
    class_id: str,
    session_type_id: int,
    weights: Dict[str, float],
    subgroup_mode: bool,
) -> List[tuple]:
    att_w = float(weights.get("attendance_weight", 0) or 0)
    part_w = float(weights.get("participation_weight", 0) or 0)
    quiz_w = float(weights.get("quiz_weight", 0) or 0)
    hw_w = float(weights.get("homework_weight", 0) or 0)
    excused_weight = float(weights.get("excused_weight", 1) or 1)

    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT StudentId, Name, Surname
            FROM students
            WHERE classId=?
            ORDER BY Name, Surname
            """,
            (class_id,),
        )
        students = cur.fetchall()
        student_ids = [row["StudentId"] for row in students]

        attendance_map: Dict[str, Dict[str, float]] = {}
        if student_ids:
            placeholders = ",".join("?" for _ in student_ids)
            params = list(student_ids)
            params.append(session_type_id)
            cur.execute(
                f"""
                    SELECT StudentId,
                           COUNT(DISTINCT sessionToken) AS attended,
                           SUM(COALESCE(participation, 0)) AS participation_sum
                    FROM sessions
                    WHERE StudentId IN ({placeholders})
                      AND sessionTypeId=?
                      AND sessionToken!='TYPE_REF'
                    GROUP BY StudentId
                """,
                params,
            )
            attendance_map = {
                row["StudentId"]: {"attended": row["attended"], "participation_sum": row["participation_sum"]}
                for row in cur.fetchall()
            }

        cur.execute(
            """
            SELECT DISTINCT sessionToken
            FROM sessions
            WHERE classId=? AND sessionTypeId=?
            """,
            (class_id, session_type_id),
        )
        denom_count = len({row["sessionToken"] for row in cur.fetchall()})
        if subgroup_mode:
            denom_count = max(1, int(math.ceil(float(denom_count) / 2.0)))
        total_sessions_actual = float(denom_count) if denom_count > 0 else 1.0

        excused_map: Dict[str, float] = {}
        if student_ids:
            placeholders = ",".join("?" for _ in student_ids)
            params: List[object] = [excused_weight] + student_ids + [session_type_id]
            cur.execute(
                f"""
                    SELECT StudentId,
                           SUM(COALESCE(weight, ?)) AS excused
                    FROM excused_absences
                    WHERE StudentId IN ({placeholders}) AND sessionTypeId=?
                    GROUP BY StudentId
                """,
                params,
            )
            excused_map = {row["StudentId"]: row["excused"] for row in cur.fetchall()}

        cur.execute(
            """
            SELECT tr.StudentId, t.TestType, COALESCE(tr.degree, 0) AS degree
            FROM test_results tr
            JOIN tests t ON t.IdTest = tr.TestId
            WHERE t.classId=? AND t.sessionTypeId=?
            """,
            (class_id, session_type_id),
        )
        quiz_map: Dict[str, float] = {}
        hw_map: Dict[str, float] = {}
        legacy_type_map = {
            "امتحان جزئي": "تقديم",
            "امتحان نهائي": "امتحان عن بعد",
        }
        quiz_keywords = {"quiz", "اختبار", "امتحان", "استجواب", "تقديم"}
        hw_keywords = {"home", "واجب"}
        for row in cur.fetchall():
            sid = row["StudentId"]
            category_raw = (row["TestType"] or "").strip()
            category = legacy_type_map.get(category_raw, category_raw).lower()
            if any(keyword in category for keyword in quiz_keywords):
                quiz_map[sid] = quiz_map.get(sid, 0) + row["degree"]
            elif any(keyword in category for keyword in hw_keywords):
                hw_map[sid] = hw_map.get(sid, 0) + row["degree"]

        rows_data: List[tuple] = []
        for stu in students:
            sid = stu["StudentId"]
            attendance_row = attendance_map.get(sid, {})
            attended = float(attendance_row.get("attended", 0) or 0)
            participation_sum = float(attendance_row.get("participation_sum", 0) or 0)
            excused_value = float(excused_map.get(sid, 0) or 0)

            total_attended = attended + excused_value
            att_ratio = min(total_attended / total_sessions_actual, 1.0)
            att_pts = round(att_ratio * att_w, 2)

            part_cap = max(part_w, 0)
            part_pts = round(min(participation_sum, part_cap), 2)

            quiz_total = float(quiz_map.get(sid, 0) or 0)
            quiz_pts = round(min(quiz_total, quiz_w), 2)

            hw_total = float(hw_map.get(sid, 0) or 0)
            hw_pts = round(min(hw_total, hw_w), 2)

            total_score = round(att_pts + part_pts + quiz_pts + hw_pts, 2)

            rows_data.append(
                (
                    sid,
                    stu["Name"],
                    stu["Surname"],
                    att_pts,
                    part_pts,
                    quiz_pts,
                    hw_pts,
                    total_score,
                )
            )

        return rows_data
    finally:
        conn.close()


def list_interrogation_tests(class_id: str, session_type_id: int) -> List[dict]:
    """Return tests of type 'استجواب' for a given class + session type.

    Used by Excel export to add one column per interrogation.
    """
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT IdTest, TestName, TestType, CreatedAt
            FROM tests
            WHERE classId=? AND sessionTypeId=?
            ORDER BY CreatedAt ASC, IdTest ASC
            """,
            (class_id, session_type_id),
        )
        legacy_type_map = {
            "امتحان جزئي": "تقديم",
            "امتحان نهائي": "امتحان عن بعد",
        }
        out: List[dict] = []
        for row in cur.fetchall():
            ttype_raw = (row["TestType"] or "").strip()
            ttype = legacy_type_map.get(ttype_raw, ttype_raw).strip()
            if "استجواب" in ttype:
                out.append({"IdTest": row["IdTest"], "TestName": row["TestName"], "CreatedAt": row["CreatedAt"]})
        return out
    finally:
        conn.close()


def fetch_degrees_for_tests(test_ids: Sequence[int]) -> Dict[Tuple[str, int], float | None]:
    """Return mapping (StudentId, TestId) -> degree for the provided tests."""
    if not test_ids:
        return {}
    conn = get_conn()
    try:
        cur = conn.cursor()
        placeholders = ",".join(["?"] * len(test_ids))
        cur.execute(
            f"""
            SELECT StudentId, TestId, degree
            FROM test_results
            WHERE TestId IN ({placeholders})
            """,
            tuple(int(tid) for tid in test_ids),
        )
        return {(str(r["StudentId"]), int(r["TestId"])): r["degree"] for r in cur.fetchall()}
    finally:
        conn.close()
