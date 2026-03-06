from __future__ import annotations

import sqlite3
from enum import StrEnum
from pathlib import Path
from typing import Any

import petname as petname_lib

DEFAULT_DB_PATH = Path.home() / ".dsf" / "tasks.db"

SCHEMA = """\
CREATE TABLE IF NOT EXISTS tasks (
    id           INTEGER PRIMARY KEY,
    petname      TEXT UNIQUE NOT NULL,
    name         TEXT NOT NULL,
    prompt       TEXT NOT NULL,
    github_repo  TEXT,
    status       TEXT DEFAULT 'submitted',
    error        TEXT,
    created_at   TEXT DEFAULT (datetime('now')),
    started_at   TEXT,
    completed_at TEXT
);
"""


class TaskStatus(StrEnum):
    SUBMITTED = "submitted"
    RUNNING = "running"
    PUSHING = "pushing"
    COMPLETED = "completed"
    FAILED = "failed"


class TaskDb:
    def __init__(self, db_path: Path = DEFAULT_DB_PATH) -> None:
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(db_path))
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.execute(SCHEMA)
        self.conn.commit()

    def _generate_petname(self) -> str:
        for _ in range(100):
            name: str = petname_lib.generate(words=2, separator="-")
            row = self.conn.execute("SELECT 1 FROM tasks WHERE petname = ?", (name,)).fetchone()
            if row is None:
                return name
        raise RuntimeError("Failed to generate unique petname after 100 attempts")

    def create_task(self, name: str, prompt: str, github_repo: str) -> str:
        pn = self._generate_petname()
        self.conn.execute(
            "INSERT INTO tasks (petname, name, prompt, github_repo) VALUES (?, ?, ?, ?)",
            (pn, name, prompt, github_repo),
        )
        self.conn.commit()
        return pn

    def get_task(self, petname: str) -> dict[str, Any] | None:
        row = self.conn.execute("SELECT * FROM tasks WHERE petname = ?", (petname,)).fetchone()
        return dict(row) if row else None

    def list_tasks(self) -> list[dict[str, Any]]:
        rows = self.conn.execute("SELECT * FROM tasks ORDER BY created_at DESC").fetchall()
        return [dict(r) for r in rows]

    def claim_next(self) -> dict[str, Any] | None:
        row = self.conn.execute(
            "UPDATE tasks SET status = 'running', started_at = datetime('now') "
            "WHERE id = (SELECT id FROM tasks WHERE status = 'submitted' "
            "ORDER BY created_at LIMIT 1) "
            "RETURNING *"
        ).fetchone()
        self.conn.commit()
        return dict(row) if row else None

    def update_status(self, petname: str, status: TaskStatus, error: str | None = None) -> None:
        if status in (TaskStatus.COMPLETED, TaskStatus.FAILED):
            self.conn.execute(
                "UPDATE tasks SET status = ?, error = ?, completed_at = datetime('now') "
                "WHERE petname = ?",
                (status.value, error, petname),
            )
        else:
            self.conn.execute(
                "UPDATE tasks SET status = ?, error = ? WHERE petname = ?",
                (status.value, error, petname),
            )
        self.conn.commit()
