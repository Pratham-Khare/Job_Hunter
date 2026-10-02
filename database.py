import sqlite3
from pathlib import Path

DB_PATH = Path("data/jobs.db")


def get_conn():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _ensure_column(conn, table, column, definition):
    cols = {row[1] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}
    if column not in cols:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")


def init_db():
    conn = get_conn()
    conn.executescript("""
    CREATE TABLE IF NOT EXISTS jobs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        canonical_id TEXT UNIQUE NOT NULL,
        company TEXT NOT NULL,
        title TEXT NOT NULL,
        category TEXT,
        location TEXT,
        work_mode TEXT,
        experience TEXT,
        education TEXT,
        skills TEXT,
        description TEXT,
        salary TEXT,
        posted_date TEXT,
        deadline TEXT,
        source TEXT,
        source_url TEXT,
        official_url TEXT,
        status TEXT DEFAULT 'ACTIVE',
        eligibility TEXT,
        skill_match REAL DEFAULT 0,
        match_score REAL DEFAULT 0,
        is_tech INTEGER DEFAULT 1,
        fresher_eligible INTEGER DEFAULT 0,
        discovered_at TEXT,
        last_verified TEXT,
        notes TEXT,
        last_seen_at TEXT
    );

    CREATE TABLE IF NOT EXISTS applications (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        job_id INTEGER UNIQUE,
        date_applied TEXT,
        status TEXT DEFAULT 'NOT_APPLIED',
        oa_date TEXT,
        interview_date TEXT,
        hr_date TEXT,
        result TEXT,
        notes TEXT,
        FOREIGN KEY(job_id) REFERENCES jobs(id)
    );

    CREATE TABLE IF NOT EXISTS alert_runs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        run_at TEXT NOT NULL,
        jobs_found INTEGER DEFAULT 0,
        email_sent INTEGER DEFAULT 0
    );

    CREATE INDEX IF NOT EXISTS idx_jobs_score ON jobs(match_score DESC);
    CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status);
    CREATE INDEX IF NOT EXISTS idx_jobs_source ON jobs(source);
    CREATE INDEX IF NOT EXISTS idx_jobs_discovered ON jobs(discovered_at);
    CREATE INDEX IF NOT EXISTS idx_jobs_last_seen ON jobs(last_seen_at);
    """)

    # Migrate databases created by earlier V2 releases.
    _ensure_column(conn, "jobs", "last_seen_at", "TEXT")
    _ensure_column(conn, "applications", "result", "TEXT")

    # Existing jobs are considered already known, not newly discovered today.
    conn.execute("UPDATE jobs SET last_seen_at = COALESCE(last_seen_at, last_verified, discovered_at)")
    conn.commit()
    conn.close()


def last_alert_run():
    conn = get_conn()
    row = conn.execute("SELECT run_at FROM alert_runs ORDER BY id DESC LIMIT 1").fetchone()
    conn.close()
    return row["run_at"] if row else None


def record_alert_run(run_at, jobs_found, email_sent=False):
    conn = get_conn()
    conn.execute(
        "INSERT INTO alert_runs(run_at, jobs_found, email_sent) VALUES (?, ?, ?)",
        (run_at, jobs_found, 1 if email_sent else 0),
    )
    conn.commit()
    conn.close()
