"""M028: Co-Director persistent memory — append-only conversation events.

Creates `codirector_conversation_events`, adds a `revision` column to
`codirector_conversations` for optimistic concurrency, and backfills every
existing `messages_json` row into the new event log so the event store becomes
the single source of truth on the day this migration lands. Reversible in
intent: the legacy `messages_json` column is left intact so a rollback simply
ignores the new table and column.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime

from sqlalchemy.engine import Connection

from .registry import Migration

REVISION = "0028"
CHECKSUM_SOURCE = "M028:codirector-conversation-events:v1"

_DDL = [
    """
    CREATE TABLE IF NOT EXISTS codirector_conversation_events (
        id VARCHAR(36) NOT NULL PRIMARY KEY,
        project_id VARCHAR(36) NOT NULL,
        sequence INTEGER NOT NULL,
        event_type VARCHAR(32) NOT NULL DEFAULT 'message',
        role VARCHAR(16) NOT NULL DEFAULT 'user',
        message_id VARCHAR(64),
        client_request_id VARCHAR(64),
        content TEXT,
        message_type VARCHAR(32),
        status VARCHAR(32),
        attachments_json TEXT,
        tool_id VARCHAR(64),
        tool_arguments_json TEXT,
        tool_result_json TEXT,
        request_id VARCHAR(64),
        actor VARCHAR(32) NOT NULL DEFAULT 'user',
        created_at DATETIME NOT NULL
    )
    """,
    "CREATE INDEX IF NOT EXISTS ix_convo_events_project ON codirector_conversation_events (project_id)",
    "CREATE INDEX IF NOT EXISTS ix_convo_events_sequence ON codirector_conversation_events (sequence)",
    "CREATE INDEX IF NOT EXISTS ix_convo_events_message_id ON codirector_conversation_events (message_id)",
    "CREATE INDEX IF NOT EXISTS ix_convo_events_client_request_id ON codirector_conversation_events (client_request_id)",
    "CREATE INDEX IF NOT EXISTS ix_convo_events_tool_id ON codirector_conversation_events (tool_id)",
    "CREATE INDEX IF NOT EXISTS ix_convo_events_request_id ON codirector_conversation_events (request_id)",
    # Unique idempotency keys: at most one event per (project, client_request_id) and
    # per (project, message_id). Both are nullable; SQLite treats NULLs as distinct,
    # so the constraint only fires when the client supplies a key — exactly what we want.
    """
    CREATE UNIQUE INDEX IF NOT EXISTS ux_convo_events_client_request
        ON codirector_conversation_events (project_id, client_request_id)
        WHERE client_request_id IS NOT NULL
    """,
    """
    CREATE UNIQUE INDEX IF NOT EXISTS ux_convo_events_message_id
        ON codirector_conversation_events (project_id, message_id)
        WHERE message_id IS NOT NULL
    """,
]


def _column_names(conn: Connection, table: str) -> set[str]:
    rows = conn.exec_driver_sql(f"PRAGMA table_info({table})").fetchall()
    return {row[1] for row in rows}


def _add_col(conn: Connection, table: str, name: str, ddl: str) -> None:
    cols = _column_names(conn, table)
    if not cols or name in cols:
        return
    conn.exec_driver_sql(f"ALTER TABLE {table} ADD COLUMN {ddl}")


def _backfill_events(conn: Connection) -> None:
    """Migrate every existing `codirector_conversations.messages_json` into events.

    Idempotent: a row that already has events (matched by message_id) is skipped,
    so re-running the migration after a partial failure never duplicates events.
    """

    # Guard: on a fresh engine (no Base.metadata.create_all), the legacy
    # header table may not exist yet. The migration is a no-op then — the
    # event log simply starts empty. In production, init_db() creates the
    # header table before migrations run, so this branch is only hit by
    # bare migration-runner tests.
    if not _column_names(conn, "codirector_conversations"):
        return

    rows = conn.exec_driver_sql(
        "SELECT project_id, messages_json, model_id, provider_id FROM codirector_conversations"
    ).fetchall()
    for project_id, messages_json, _model_id, _provider_id in rows:
        try:
            messages = json.loads(messages_json or "[]")
        except Exception:
            messages = []
        if not isinstance(messages, list):
            messages = []
        # Determine the next sequence by scanning existing events for this project.
        max_seq_row = conn.exec_driver_sql(
            "SELECT COALESCE(MAX(sequence), -1) FROM codirector_conversation_events WHERE project_id = ?",
            (project_id,),
        ).fetchone()
        seq = int(max_seq_row[0]) if max_seq_row and max_seq_row[0] is not None else -1
        for msg in messages:
            if not isinstance(msg, dict):
                continue
            message_id = msg.get("id") or None
            if message_id:
                # Skip if an event with this message_id already exists for this project.
                existing = conn.exec_driver_sql(
                    "SELECT 1 FROM codirector_conversation_events WHERE project_id = ? AND message_id = ? LIMIT 1",
                    (project_id, message_id),
                ).fetchone()
                if existing:
                    continue
            role = str(msg.get("role") or "user")
            content = str(msg.get("content") or "")
            created_at = msg.get("created_at") or msg.get("createdAt") or datetime.utcnow().isoformat()
            attachments = msg.get("attachments") or msg.get("attachment_ids") or []
            try:
                attachments_json = json.dumps(attachments)
            except Exception:
                attachments_json = "[]"
            seq += 1
            conn.exec_driver_sql(
                """
                INSERT INTO codirector_conversation_events (
                    id, project_id, sequence, event_type, role, message_id,
                    client_request_id, content, message_type, status,
                    attachments_json, actor, created_at
                ) VALUES (?, ?, ?, 'message', ?, ?, NULL, ?, ?, ?, ?, ?, ?)
                """,
                (
                    str(uuid.uuid4()),
                    project_id,
                    seq,
                    role,
                    message_id,
                    content,
                    msg.get("messageType") or msg.get("message_type"),
                    msg.get("status"),
                    attachments_json,
                    "user" if role == "user" else "assistant",
                    created_at,
                ),
            )
        # Bump the header revision so optimistic concurrency sees the backfill.
        conn.exec_driver_sql(
            "UPDATE codirector_conversations SET revision = ? WHERE project_id = ?",
            (seq + 1, project_id),
        )


def apply(conn: Connection) -> None:
    for stmt in _DDL:
        conn.exec_driver_sql(stmt)
    _add_col(conn, "codirector_conversations", "revision", "revision INTEGER DEFAULT 0")
    _backfill_events(conn)


MIGRATION = Migration(
    revision=REVISION,
    description="Co-Director persistent memory: append-only conversation events + backfill",
    apply=apply,
    checksum_source=CHECKSUM_SOURCE,
    rollback_notes=(
        "Drop codirector_conversation_events and ignore the new revision column on "
        "codirector_conversations. messages_json is preserved, so the legacy "
        "full-replace path continues to work after rollback."
    ),
    reversible=False,
)
