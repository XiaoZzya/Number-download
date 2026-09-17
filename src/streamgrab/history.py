from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from .paths import data_dir


@dataclass(frozen=True, slots=True)
class HistoryEntry:
    media_id: str
    title: str
    created_at: str
    output_path: str
    status: str
    tool_version: str


class HistoryStore:
    def __init__(self, path: Path | None = None):
        self.path = path or data_dir() / "history.sqlite3"

    def _connect(self) -> sqlite3.Connection:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.path)
        connection.execute(
            """CREATE TABLE IF NOT EXISTS downloads (
                id INTEGER PRIMARY KEY,
                media_id TEXT NOT NULL,
                title TEXT NOT NULL,
                created_at TEXT NOT NULL,
                output_path TEXT NOT NULL,
                status TEXT NOT NULL,
                tool_version TEXT NOT NULL
            )"""
        )
        return connection

    def add(self, media_id: str, title: str, output_path: Path, status: str, tool_version: str = "unknown") -> None:
        with self._connect() as connection:
            connection.execute(
                "INSERT INTO downloads(media_id,title,created_at,output_path,status,tool_version) VALUES(?,?,?,?,?,?)",
                (media_id, title, datetime.now(timezone.utc).isoformat(), str(output_path), status, tool_version),
            )

    def list(self, limit: int = 20) -> list[HistoryEntry]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT media_id,title,created_at,output_path,status,tool_version FROM downloads ORDER BY id DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [HistoryEntry(*row) for row in rows]

