from __future__ import annotations

from typing import List, Optional

from db import get_conn


def list_session_type_labels() -> List[str]:
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute("SELECT subject_code, type FROM session_types ORDER BY subject_code, type")
        rows = cur.fetchall()
        return [f"{row['subject_code']}-{row['type']}" for row in rows]
    finally:
        conn.close()


def fetch_session_types() -> List[dict]:
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute("SELECT id, subject_code, type FROM session_types ORDER BY subject_code, type")
        return [dict(row) for row in cur.fetchall()]
    finally:
        conn.close()


def add_session_type(subject_code: str, session_type: str) -> bool:
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO session_types (subject_code, type) VALUES (?, ?)",
            (subject_code, session_type),
        )
        conn.commit()
        return cur.rowcount > 0
    finally:
        conn.close()


def delete_session_type(session_type_id: int) -> bool:
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute("DELETE FROM session_types WHERE id=?", (session_type_id,))
        conn.commit()
        return cur.rowcount > 0
    finally:
        conn.close()


def ensure_session_type(subject_code: str, session_type: str) -> Optional[int]:
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
