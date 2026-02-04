"""Database models and setup for job tracking."""

import sqlite3
import hashlib
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional

DB_PATH = Path(__file__).parent / "data" / "jobs.db"


@dataclass
class Job:
    """Represents a job posting."""
    company_id: str
    job_title: str
    job_url: str
    location: Optional[str] = None
    department: Optional[str] = None
    posted_date: Optional[str] = None
    description_full: Optional[str] = None
    is_barcelona: bool = False
    is_data_role: bool = False
    mentions_visa: bool = False
    mentions_relocation: bool = False

    @property
    def id(self) -> str:
        """Generate unique ID from company_id and job_url."""
        raw = f"{self.company_id}:{self.job_url}"
        return hashlib.sha256(raw.encode()).hexdigest()[:16]


def init_db() -> None:
    """Initialize the SQLite database with required tables."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS jobs (
            id TEXT PRIMARY KEY,
            company_id TEXT NOT NULL,
            job_title TEXT NOT NULL,
            job_url TEXT NOT NULL UNIQUE,
            location TEXT,
            department TEXT,
            posted_date TEXT,
            scraped_date TEXT NOT NULL,
            description_full TEXT,
            is_barcelona BOOLEAN,
            is_data_role BOOLEAN,
            mentions_visa BOOLEAN,
            mentions_relocation BOOLEAN,
            status TEXT DEFAULT 'new',
            user_notes TEXT
        )
    """)

    cursor.execute("CREATE INDEX IF NOT EXISTS idx_company ON jobs(company_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_scraped_date ON jobs(scraped_date)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_status ON jobs(status)")

    conn.commit()
    conn.close()


def save_job(job: Job) -> bool:
    """
    Save a job to the database. Returns True if new, False if already exists.
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    try:
        cursor.execute("""
            INSERT INTO jobs (
                id, company_id, job_title, job_url, location, department,
                posted_date, scraped_date, description_full, is_barcelona,
                is_data_role, mentions_visa, mentions_relocation
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            job.id,
            job.company_id,
            job.job_title,
            job.job_url,
            job.location,
            job.department,
            job.posted_date,
            datetime.utcnow().isoformat(),
            job.description_full,
            job.is_barcelona,
            job.is_data_role,
            job.mentions_visa,
            job.mentions_relocation,
        ))
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False
    finally:
        conn.close()


def get_new_jobs_since(since_date: str) -> list[dict]:
    """Get all jobs scraped since the given date."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute("""
        SELECT * FROM jobs
        WHERE scraped_date >= ?
        AND is_barcelona = 1
        AND is_data_role = 1
        ORDER BY scraped_date DESC
    """, (since_date,))

    rows = cursor.fetchall()
    conn.close()

    return [dict(row) for row in rows]


if __name__ == "__main__":
    init_db()
    print(f"Database initialized at {DB_PATH}")
