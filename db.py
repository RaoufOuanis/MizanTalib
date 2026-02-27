# db.py - نسخة جديدة مع جدول excused_absences
import os
import sqlite3
from datetime import datetime

DB_FILE = "attendance.db"

def get_conn():
    conn = sqlite3.connect(DB_FILE)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.row_factory = sqlite3.Row
    return conn

# ---------------- init db ----------------
def init_db():
    conn = get_conn(); cur = conn.cursor()

    # أقسام
    cur.execute("""
    CREATE TABLE IF NOT EXISTS classes (
        id TEXT PRIMARY KEY,
        cycle TEXT NOT NULL,
        year INTEGER NOT NULL,
        groupNbr INTEGER,
        section TEXT,
        specialty TEXT
    )
    """)

    # طلبة
    cur.execute("""
    CREATE TABLE IF NOT EXISTS students (
        StudentId TEXT PRIMARY KEY,
        Name TEXT,
        Surname TEXT,
        classId TEXT,
        FOREIGN KEY (classId) REFERENCES classes(id) ON DELETE CASCADE
    )
    """)

    # أنواع الحصص
    cur.execute("""
    CREATE TABLE IF NOT EXISTS session_types (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        subject_code TEXT NOT NULL,
        type TEXT NOT NULL,
        UNIQUE(subject_code, type)
    )
    """)

    # جلسات
    cur.execute("""
    CREATE TABLE IF NOT EXISTS sessions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        sessionToken TEXT,
        StudentId TEXT,
        presence INTEGER DEFAULT 1,
        participation REAL DEFAULT 0,
        SessionDate TEXT,
        classId TEXT,
        sessionTypeId INTEGER,
        FOREIGN KEY (StudentId) REFERENCES students(StudentId) ON DELETE CASCADE,
        FOREIGN KEY (classId) REFERENCES classes(id) ON DELETE CASCADE,
        FOREIGN KEY (sessionTypeId) REFERENCES session_types(id) ON DELETE SET NULL
    )
    """)

    # إزالة السجلات المكررة قبل فرض قيد التفرد على (sessionToken, StudentId)
    cur.execute("""
    DELETE FROM sessions
    WHERE id NOT IN (
        SELECT MIN(id)
        FROM sessions
        GROUP BY sessionToken, StudentId
    )
    """)

    # منع التكرار لنفس الطالب في نفس الجلسة مستقبلًا
    cur.execute("""
    CREATE UNIQUE INDEX IF NOT EXISTS idx_sessions_token_student
    ON sessions(sessionToken, StudentId)
    """)

    # أوزان
    cur.execute("""
    CREATE TABLE IF NOT EXISTS weights (
        id INTEGER PRIMARY KEY CHECK(id=1),
        attendance_weight REAL DEFAULT 10,
        quiz_weight REAL DEFAULT 5,
        homework_weight REAL DEFAULT 5,
        participation_weight REAL DEFAULT 5,
        total_sessions_expected REAL DEFAULT 20,
        max_participation_points REAL DEFAULT 10,
        max_quiz_points REAL DEFAULT 20,
        max_homework_points REAL DEFAULT 10,
        excused_weight REAL DEFAULT 1   -- 👈 الوزن الافتراضي للغياب المبرر
    )
    """)
    cur.execute("INSERT OR IGNORE INTO weights (id) VALUES (1)")

    # إعدادات
    cur.execute("""
    CREATE TABLE IF NOT EXISTS settings (
        key TEXT PRIMARY KEY,
        value TEXT
    )
    """)

    # اختبارات
    cur.execute("""
    CREATE TABLE IF NOT EXISTS tests (
        IdTest INTEGER PRIMARY KEY AUTOINCREMENT,
        TestName TEXT NOT NULL,
        TestType TEXT NOT NULL,
        classId TEXT NOT NULL,
        sessionTypeId INTEGER,
        CreatedAt TEXT NOT NULL,
        FOREIGN KEY (classId) REFERENCES classes(id) ON DELETE CASCADE,
        FOREIGN KEY (sessionTypeId) REFERENCES session_types(id) ON DELETE SET NULL
    )
    """)

    # نتائج الاختبارات
    cur.execute("""
    CREATE TABLE IF NOT EXISTS test_results (
        IdResult INTEGER PRIMARY KEY AUTOINCREMENT,
        TestId INTEGER NOT NULL,
        StudentId TEXT NOT NULL,
        degree REAL,
        FOREIGN KEY (TestId) REFERENCES tests(IdTest) ON DELETE CASCADE,
        FOREIGN KEY (StudentId) REFERENCES students(StudentId) ON DELETE CASCADE
    )
    """)

    # Ensure one (test, student) row and repair any missing assignments.
    # 1) Remove duplicates before adding uniqueness.
    cur.execute(
        """
        DELETE FROM test_results
        WHERE IdResult NOT IN (
            SELECT MIN(IdResult)
            FROM test_results
            GROUP BY TestId, StudentId
        )
        """
    )

    # 2) Enforce uniqueness going forward.
    cur.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS idx_test_results_test_student
        ON test_results(TestId, StudentId)
        """
    )

    # 3) Backfill missing rows for existing tests/students in the same class.
    cur.execute(
        """
        INSERT INTO test_results (TestId, StudentId, degree)
        SELECT t.IdTest, s.StudentId, NULL
        FROM tests t
        JOIN students s ON s.classId = t.classId
        LEFT JOIN test_results tr
               ON tr.TestId = t.IdTest AND tr.StudentId = s.StudentId
        WHERE tr.IdResult IS NULL
        """
    )

    # 👇 جدول جديد للتبريرات
    cur.execute("""
    CREATE TABLE IF NOT EXISTS excused_absences (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        StudentId TEXT NOT NULL,
        sessionToken TEXT NOT NULL,
        sessionTypeId INTEGER NOT NULL,
        classId TEXT NOT NULL,
        excuse_date TEXT NOT NULL DEFAULT (datetime('now')),
        weight REAL DEFAULT NULL,  -- إذا NULL نستعمل القيمة الافتراضية من weights
        justification_path TEXT,   -- اختياري: مسار ملف أو صورة للشهادة الطبية
        FOREIGN KEY (StudentId) REFERENCES students(StudentId) ON DELETE CASCADE,
        FOREIGN KEY (classId) REFERENCES classes(id) ON DELETE CASCADE,
        FOREIGN KEY (sessionTypeId) REFERENCES session_types(id) ON DELETE CASCADE
    )
    """)

    # جدول استثناءات الإقصاء: يمنع حساب الطالب في تقارير الإقصاء
    cur.execute("""
    CREATE TABLE IF NOT EXISTS exclusion_exceptions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        classId TEXT NOT NULL,
        sessionTypeId INTEGER NOT NULL,
        StudentId TEXT NOT NULL,
        reason TEXT,
        created_by TEXT,
        created_at TEXT DEFAULT (datetime('now')),
        UNIQUE(classId, sessionTypeId, StudentId)
    )
    """)

    conn.commit()
    conn.close()
def set_subgroup_mode(class_id: str, session_type_id: int, enabled: bool):
    """Persist a per-(class,sessionType) flag that indicates subgroup counting should apply.

    enabled: True -> divide official session count by 2 for reports for this class+type
    """
    conn = get_conn(); cur = conn.cursor()
    cur.execute(
        "CREATE TABLE IF NOT EXISTS subgroup_modes (classId TEXT NOT NULL, sessionTypeId INTEGER NOT NULL, enabled INTEGER NOT NULL, PRIMARY KEY(classId, sessionTypeId))"
    )
    cur.execute(
        "INSERT OR REPLACE INTO subgroup_modes (classId, sessionTypeId, enabled) VALUES (?,?,?)",
        (class_id, session_type_id, 1 if enabled else 0),
    )
    conn.commit(); conn.close()


def get_subgroup_mode(class_id: str, session_type_id: int) -> bool:
    """Return True if subgroup mode is enabled for this class+sessionType.

    If no explicit setting exists, returns False.
    """
    conn = get_conn(); cur = conn.cursor()
    # ensure table exists
    cur.execute(
        "CREATE TABLE IF NOT EXISTS subgroup_modes (classId TEXT NOT NULL, sessionTypeId INTEGER NOT NULL, enabled INTEGER NOT NULL, PRIMARY KEY(classId, sessionTypeId))"
    )
    cur.execute(
        "SELECT enabled FROM subgroup_modes WHERE classId=? AND sessionTypeId=? LIMIT 1",
        (class_id, session_type_id),
    )
    row = cur.fetchone()
    conn.close()
    return bool(row and row[0])


def add_exclusion_exception(class_id: str, session_type_id: int, student_id: str, reason: str = None, created_by: str = None):
    conn = get_conn(); cur = conn.cursor()
    cur.execute("INSERT OR IGNORE INTO exclusion_exceptions (classId, sessionTypeId, StudentId, reason, created_by) VALUES (?,?,?,?,?)",
                (class_id, session_type_id, student_id, reason, created_by))
    conn.commit(); conn.close()


def remove_exclusion_exception(class_id: str, session_type_id: int, student_id: str):
    conn = get_conn(); cur = conn.cursor()
    cur.execute("DELETE FROM exclusion_exceptions WHERE classId=? AND sessionTypeId=? AND StudentId=?",
                (class_id, session_type_id, student_id))
    conn.commit(); conn.close()


def _ensure_app_settings_table(cur):
    cur.execute(
        "CREATE TABLE IF NOT EXISTS app_settings (key TEXT PRIMARY KEY, value TEXT)"
    )


def set_app_setting(key: str, value: str) -> None:
    conn = get_conn()
    try:
        cur = conn.cursor()
        _ensure_app_settings_table(cur)
        cur.execute(
            "INSERT OR REPLACE INTO app_settings (key, value) VALUES (?, ?)",
            (key, value),
        )
        conn.commit()
    finally:
        conn.close()


def get_app_setting(key: str, default: str = "") -> str:
    conn = get_conn()
    try:
        cur = conn.cursor()
        _ensure_app_settings_table(cur)
        cur.execute("SELECT value FROM app_settings WHERE key=? LIMIT 1", (key,))
        row = cur.fetchone()
        if not row:
            return default
        try:
            return row["value"]
        except Exception:
            return row[0] if row[0] is not None else default
    finally:
        conn.close()


def list_exclusion_exceptions(class_id: str, session_type_id: int):
    conn = get_conn(); cur = conn.cursor()
    cur.execute("SELECT StudentId FROM exclusion_exceptions WHERE classId=? AND sessionTypeId=?",
                (class_id, session_type_id))
    rows = [r['StudentId'] for r in cur.fetchall()]
    conn.close()
    return set(rows)
