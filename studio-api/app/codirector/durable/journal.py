"""Durable-runtime journal.

Stores admission envelopes, mutation evidence, and workflow events.
This is not Adept Master and it is not the conversation transcript.
"""

from __future__ import annotations

import json
import os
import sqlite3
import threading
from pathlib import Path
from typing import Any

from ...config import settings

_LOCK = threading.Lock()


def journal_path() -> Path:
    override = os.environ.get("ADEPT_CD_JOURNAL_PATH", "").strip()
    if override:
        path = Path(override)
    else:
        path = settings.data_dir / "codirector_durable" / "journal.sqlite"
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(str(journal_path()), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def ensure_schema() -> None:
    with _LOCK:
        conn = _connect()
        try:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS admission (
                    workflow_id TEXT PRIMARY KEY,
                    payload_json TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS mutation_evidence (
                    mutation_id TEXT PRIMARY KEY,
                    workflow_id TEXT NOT NULL,
                    tool_id TEXT NOT NULL,
                    target TEXT NOT NULL,
                    action TEXT NOT NULL,
                    before_hash TEXT,
                    after_hash TEXT,
                    status TEXT NOT NULL,
                    receipt_json TEXT
                );
                CREATE TABLE IF NOT EXISTS workflow_events (
                    workflow_id TEXT NOT NULL,
                    seq INTEGER NOT NULL,
                    event_json TEXT NOT NULL,
                    PRIMARY KEY (workflow_id, seq)
                );
                CREATE TABLE IF NOT EXISTS workflow_status (
                    workflow_id TEXT PRIMARY KEY,
                    status TEXT NOT NULL,
                    result_json TEXT
                );
                CREATE TABLE IF NOT EXISTS legacy_invocation (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                );
                CREATE TABLE IF NOT EXISTS proposal_links (
                    proposal_id TEXT PRIMARY KEY,
                    originating_workflow_id TEXT NOT NULL,
                    project_id TEXT NOT NULL,
                    scene_id TEXT,
                    tool_id TEXT NOT NULL,
                    intended_text TEXT,
                    approval_id TEXT
                );
                CREATE TABLE IF NOT EXISTS crash_consumed (
                    scope_id TEXT NOT NULL,
                    checkpoint TEXT NOT NULL,
                    PRIMARY KEY (scope_id, checkpoint)
                );
                CREATE TABLE IF NOT EXISTS executor_calls (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    scope_id TEXT NOT NULL
                );
                """
            )
            columns = {row[1] for row in conn.execute("PRAGMA table_info(proposal_links)")}
            if "plan_json" not in columns:
                conn.execute("ALTER TABLE proposal_links ADD COLUMN plan_json TEXT")
            conn.commit()
        finally:
            conn.close()


def save_admission(workflow_id: str, payload: dict[str, Any]) -> None:
    ensure_schema()
    with _LOCK:
        conn = _connect()
        try:
            conn.execute(
                "INSERT OR REPLACE INTO admission (workflow_id, payload_json) VALUES (?, ?)",
                (workflow_id, json.dumps(payload, sort_keys=True, default=str)),
            )
            conn.commit()
        finally:
            conn.close()


def load_admission(workflow_id: str) -> dict[str, Any] | None:
    ensure_schema()
    with _LOCK:
        conn = _connect()
        try:
            row = conn.execute(
                "SELECT payload_json FROM admission WHERE workflow_id = ?",
                (workflow_id,),
            ).fetchone()
        finally:
            conn.close()
    if row is None:
        return None
    return json.loads(row["payload_json"])


def begin_mutation(
    *,
    mutation_id: str,
    workflow_id: str,
    tool_id: str,
    target: str,
    action: str,
    before_hash: str | None,
) -> dict[str, Any] | None:
    """Insert the intent row. Returns the existing row when this identity already began."""

    ensure_schema()
    with _LOCK:
        conn = _connect()
        try:
            existing = conn.execute(
                "SELECT * FROM mutation_evidence WHERE mutation_id = ?",
                (mutation_id,),
            ).fetchone()
            if existing is not None:
                return dict(existing)
            conn.execute(
                """
                INSERT INTO mutation_evidence (
                    mutation_id, workflow_id, tool_id, target, action, before_hash, status
                ) VALUES (?, ?, ?, ?, ?, ?, 'intended')
                """,
                (mutation_id, workflow_id, tool_id, target, action, before_hash),
            )
            conn.commit()
            return None
        finally:
            conn.close()


def mark_executing(mutation_id: str) -> None:
    ensure_schema()
    with _LOCK:
        conn = _connect()
        try:
            conn.execute(
                "UPDATE mutation_evidence SET status = 'executing' WHERE mutation_id = ?",
                (mutation_id,),
            )
            conn.commit()
        finally:
            conn.close()


def save_receipt(mutation_id: str, *, after_hash: str | None, status: str, receipt: dict[str, Any]) -> None:
    ensure_schema()
    with _LOCK:
        conn = _connect()
        try:
            conn.execute(
                """
                UPDATE mutation_evidence
                SET after_hash = ?, status = ?, receipt_json = ?
                WHERE mutation_id = ?
                """,
                (after_hash, status, json.dumps(receipt, default=str), mutation_id),
            )
            conn.commit()
        finally:
            conn.close()


def get_mutation(mutation_id: str) -> dict[str, Any] | None:
    ensure_schema()
    with _LOCK:
        conn = _connect()
        try:
            row = conn.execute(
                "SELECT * FROM mutation_evidence WHERE mutation_id = ?",
                (mutation_id,),
            ).fetchone()
        finally:
            conn.close()
    return dict(row) if row is not None else None


def receipts_for(workflow_id: str) -> list[dict[str, Any]]:
    ensure_schema()
    with _LOCK:
        conn = _connect()
        try:
            rows = conn.execute(
                "SELECT receipt_json FROM mutation_evidence WHERE workflow_id = ? AND receipt_json IS NOT NULL",
                (workflow_id,),
            ).fetchall()
        finally:
            conn.close()
    out: list[dict[str, Any]] = []
    for row in rows:
        out.append(json.loads(row["receipt_json"]))
    return out


def append_event(workflow_id: str, event: dict[str, Any]) -> int:
    ensure_schema()
    with _LOCK:
        conn = _connect()
        try:
            current = conn.execute(
                "SELECT COALESCE(MAX(seq), 0) AS seq FROM workflow_events WHERE workflow_id = ?",
                (workflow_id,),
            ).fetchone()
            seq = int(current["seq"]) + 1
            conn.execute(
                "INSERT INTO workflow_events (workflow_id, seq, event_json) VALUES (?, ?, ?)",
                (workflow_id, seq, json.dumps(event, default=str)),
            )
            conn.commit()
            return seq
        finally:
            conn.close()


def events_from(workflow_id: str, after_seq: int) -> list[dict[str, Any]]:
    ensure_schema()
    with _LOCK:
        conn = _connect()
        try:
            rows = conn.execute(
                """
                SELECT seq, event_json FROM workflow_events
                WHERE workflow_id = ? AND seq > ?
                ORDER BY seq
                """,
                (workflow_id, after_seq),
            ).fetchall()
        finally:
            conn.close()
    return [{"seq": int(row["seq"]), "event": json.loads(row["event_json"])} for row in rows]


def set_status(workflow_id: str, status: str, result: dict[str, Any] | None = None) -> None:
    ensure_schema()
    with _LOCK:
        conn = _connect()
        try:
            conn.execute(
                "INSERT OR REPLACE INTO workflow_status (workflow_id, status, result_json) VALUES (?, ?, ?)",
                (workflow_id, status, json.dumps(result, default=str) if result is not None else None),
            )
            conn.commit()
        finally:
            conn.close()


def get_status(workflow_id: str) -> str | None:
    ensure_schema()
    with _LOCK:
        conn = _connect()
        try:
            row = conn.execute(
                "SELECT status FROM workflow_status WHERE workflow_id = ?",
                (workflow_id,),
            ).fetchone()
        finally:
            conn.close()
    return None if row is None else str(row["status"])


def save_proposal_link(
    *,
    proposal_id: str,
    originating_workflow_id: str,
    project_id: str,
    scene_id: str | None,
    tool_id: str,
    intended_text: str,
    approval_id: str,
    plan: list[dict[str, Any]] | None = None,
) -> None:
    ensure_schema()
    with _LOCK:
        conn = _connect()
        try:
            conn.execute(
                """
                INSERT OR REPLACE INTO proposal_links (
                    proposal_id, originating_workflow_id, project_id, scene_id,
                    tool_id, intended_text, approval_id, plan_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    proposal_id,
                    originating_workflow_id,
                    project_id,
                    scene_id,
                    tool_id,
                    intended_text,
                    approval_id,
                    json.dumps(plan) if plan else None,
                ),
            )
            conn.commit()
        finally:
            conn.close()


def proposal_for_workflow(workflow_id: str) -> dict[str, Any] | None:
    """The first proposal this turn already stored. A retry must not create another."""

    ensure_schema()
    with _LOCK:
        conn = _connect()
        try:
            row = conn.execute(
                """
                SELECT proposal_id, tool_id, intended_text
                FROM proposal_links
                WHERE originating_workflow_id = ?
                ORDER BY rowid
                LIMIT 1
                """,
                (workflow_id,),
            ).fetchone()
        finally:
            conn.close()
    if row is None:
        return None
    return {
        "proposal_id": str(row["proposal_id"]),
        "tool_id": str(row["tool_id"]),
        "intended_text": str(row["intended_text"] or ""),
    }


def load_proposal_link(proposal_id: str) -> dict[str, Any] | None:
    ensure_schema()
    with _LOCK:
        conn = _connect()
        try:
            row = conn.execute(
                "SELECT * FROM proposal_links WHERE proposal_id = ?",
                (proposal_id,),
            ).fetchone()
        finally:
            conn.close()
    return dict(row) if row is not None else None


def crash_consumed(scope_id: str, checkpoint: str) -> bool:
    ensure_schema()
    with _LOCK:
        conn = _connect()
        try:
            row = conn.execute(
                "SELECT 1 FROM crash_consumed WHERE scope_id = ? AND checkpoint = ?",
                (scope_id, checkpoint),
            ).fetchone()
        finally:
            conn.close()
    return row is not None


def mark_crash_consumed(scope_id: str, checkpoint: str) -> None:
    ensure_schema()
    with _LOCK:
        conn = _connect()
        try:
            conn.execute(
                "INSERT OR IGNORE INTO crash_consumed (scope_id, checkpoint) VALUES (?, ?)",
                (scope_id, checkpoint),
            )
            conn.commit()
        finally:
            conn.close()


def record_executor_call(scope_id: str) -> None:
    ensure_schema()
    with _LOCK:
        conn = _connect()
        try:
            conn.execute("INSERT INTO executor_calls (scope_id) VALUES (?)", (scope_id,))
            conn.commit()
        finally:
            conn.close()


def executor_call_count(scope_id: str) -> int:
    ensure_schema()
    with _LOCK:
        conn = _connect()
        try:
            row = conn.execute(
                "SELECT COUNT(*) AS n FROM executor_calls WHERE scope_id = ?",
                (scope_id,),
            ).fetchone()
        finally:
            conn.close()
    return int(row["n"] if row is not None else 0)


def record_legacy(name: str) -> None:
    ensure_schema()
    with _LOCK:
        conn = _connect()
        try:
            conn.execute("INSERT INTO legacy_invocation (name) VALUES (?)", (name,))
            conn.commit()
        finally:
            conn.close()


def legacy_names() -> list[str]:
    ensure_schema()
    with _LOCK:
        conn = _connect()
        try:
            rows = conn.execute("SELECT name FROM legacy_invocation ORDER BY id").fetchall()
        finally:
            conn.close()
    return [str(row["name"]) for row in rows]
