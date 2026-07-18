"""
Conversation memory — persistent SQLite store.
Saves every message so the agent can recall past conversations,
even across restarts. Also exposes a search tool.
"""
from __future__ import annotations

import json
import os
import sqlite3
import threading
import uuid
from datetime import datetime, timezone
from typing import Any

DB_PATH = os.getenv("CONVERSATION_DB_PATH",
                     os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                                  "data", "conversations.db"))


class ConversationStore:
    """Thread-safe SQLite-backed conversation store."""

    def __init__(self, path: str = DB_PATH):
        self.path = path
        self._lock = threading.Lock()
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        self._init_db()

    def _init_db(self):
        with self._lock, sqlite3.connect(self.path) as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS sessions (
                    id        TEXT PRIMARY KEY,
                    title     TEXT DEFAULT 'New conversation',
                    created   TEXT NOT NULL,
                    updated   TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS messages (
                    id         INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL REFERENCES sessions(id),
                    role       TEXT NOT NULL,
                    content    TEXT NOT NULL,
                    metadata   TEXT DEFAULT '{}',
                    created    TEXT NOT NULL,
                    token_count INTEGER DEFAULT 0
                );
                CREATE INDEX IF NOT EXISTS idx_messages_session
                    ON messages(session_id, id);
                CREATE INDEX IF NOT EXISTS idx_sessions_updated
                    ON sessions(updated DESC);
                -- Full-text search for message content
                CREATE VIRTUAL TABLE IF NOT EXISTS messages_fts
                    USING fts5(content, content=messages, content_rowid=id);
                CREATE TRIGGER IF NOT EXISTS messages_ai AFTER INSERT ON messages BEGIN
                    INSERT INTO messages_fts(rowid, content) VALUES (new.id, new.content);
                END;
                CREATE TRIGGER IF NOT EXISTS messages_ad AFTER DELETE ON messages BEGIN
                    INSERT INTO messages_fts(messages_fts, rowid, content) VALUES('delete', old.id, old.content);
                END;
            """)

    # ---- Session management ----

    def get_or_create_session(self, session_id: str | None = None) -> str:
        """Return a session ID, creating a new one if not given or not found."""
        sid = session_id or str(uuid.uuid4())[:12]
        now = datetime.now(timezone.utc).isoformat()
        with self._lock, sqlite3.connect(self.path) as db:
            if session_id:
                row = db.execute("SELECT id FROM sessions WHERE id = ?", (sid,)).fetchone()
                if row:
                    db.execute("UPDATE sessions SET updated = ? WHERE id = ?", (now, sid))
                    return sid
            db.execute(
                "INSERT INTO sessions (id, title, created, updated) VALUES (?, ?, ?, ?)",
                (sid, "New conversation", now, now))
        return sid

    def list_sessions(self, limit: int = 20) -> list[dict]:
        with self._lock, sqlite3.connect(self.path) as db:
            rows = db.execute(
                "SELECT id, title, created, updated FROM sessions ORDER BY updated DESC LIMIT ?",
                (limit,)).fetchall()
        return [{"id": r[0], "title": r[1], "created": r[2], "updated": r[3]} for r in rows]

    def rename_session(self, session_id: str, title: str) -> None:
        with self._lock, sqlite3.connect(self.path) as db:
            db.execute("UPDATE sessions SET title = ?, updated = ? WHERE id = ?",
                       (title, datetime.now(timezone.utc).isoformat(), session_id))

    # ---- Messages ----

    def save_message(self, session_id: str, role: str, content: str,
                     metadata: dict | None = None) -> int:
        now = datetime.now(timezone.utc).isoformat()
        with self._lock, sqlite3.connect(self.path) as db:
            # ensure session exists
            db.execute(
                "INSERT OR IGNORE INTO sessions (id, title, created, updated) VALUES (?, ?, ?, ?)",
                (session_id, "New conversation", now, now))
            cur = db.execute(
                "INSERT INTO messages (session_id, role, content, metadata, created) VALUES (?, ?, ?, ?, ?)",
                (session_id, role, content, json.dumps(metadata or {}), now))
            db.execute("UPDATE sessions SET updated = ? WHERE id = ?", (now, session_id))
            return cur.lastrowid

    def get_history(self, session_id: str, limit: int = 50) -> list[dict]:
        with self._lock, sqlite3.connect(self.path) as db:
            rows = db.execute(
                "SELECT role, content FROM messages WHERE session_id = ? ORDER BY id DESC LIMIT ?",
                (session_id, limit)).fetchall()
        rows.reverse()
        return [{"role": r[0], "content": r[1]} for r in rows]

    def get_recent(self, limit: int = 10) -> list[dict]:
        """Get the most recent messages across all sessions (for search)."""
        with self._lock, sqlite3.connect(self.path) as db:
            rows = db.execute("""
                SELECT m.session_id, s.title, m.role, m.content, m.created
                FROM messages m
                JOIN sessions s ON s.id = m.session_id
                ORDER BY m.id DESC LIMIT ?
            """, (limit,)).fetchall()
        rows.reverse()
        return [{"session_id": r[0], "session_title": r[1], "role": r[2],
                 "content": r[3], "created": r[4]} for r in rows]

    # ---- Search ----

    def search(self, query: str, limit: int = 10) -> list[dict]:
        """Full-text search over all conversation messages."""
        # Sanitise query for FTS5 — escape special chars
        safe = " ".join(word for word in query.split() if word.strip())
        if not safe:
            return []
        with self._lock, sqlite3.connect(self.path) as db:
            try:
                rows = db.execute("""
                    SELECT m.session_id, s.title, m.role, m.content, m.created
                    FROM messages_fts f
                    JOIN messages m ON m.id = f.rowid
                    JOIN sessions s ON s.id = m.session_id
                    WHERE messages_fts MATCH ?
                    ORDER BY rank
                    LIMIT ?
                """, (safe, limit)).fetchall()
            except sqlite3.OperationalError:
                # FTS5 query syntax error — fall back to LIKE
                like = f"%{query}%"
                rows = db.execute("""
                    SELECT m.session_id, s.title, m.role, m.content, m.created
                    FROM messages m
                    JOIN sessions s ON s.id = m.session_id
                    WHERE m.content LIKE ?
                    ORDER BY m.id DESC LIMIT ?
                """, (like, limit)).fetchall()
        return [{"session_id": r[0], "session_title": r[1], "role": r[2],
                 "content": r[3][:500], "created": r[4]} for r in rows]

    # ---- Delete ----

    def delete_session(self, session_id: str) -> bool:
        with self._lock, sqlite3.connect(self.path) as db:
            db.execute("DELETE FROM messages WHERE session_id = ?", (session_id,))
            cur = db.execute("DELETE FROM sessions WHERE id = ?", (session_id,))
            return cur.rowcount > 0


# Singleton for the app
_store: ConversationStore | None = None


def get_store() -> ConversationStore:
    global _store
    if _store is None:
        _store = ConversationStore()
    return _store
