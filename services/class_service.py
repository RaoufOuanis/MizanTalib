from __future__ import annotations

from typing import List

from db import get_conn


def list_classes() -> List[dict]:
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute("SELECT * FROM classes ORDER BY id")
        return [dict(row) for row in cur.fetchall()]
    finally:
        conn.close()


def delete_class(class_id: str) -> bool:
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute("DELETE FROM classes WHERE id=?", (class_id,))
        conn.commit()
        return cur.rowcount > 0
    finally:
        conn.close()
