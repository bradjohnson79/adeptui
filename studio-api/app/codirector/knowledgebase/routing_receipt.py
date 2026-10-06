"""Shared Co-Director knowledge routing/landing receipt.

Written only after a real ``knowledge_reply`` / chat hook execution.
The Status probe and chat share this file — do not invent a second bus.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

RECEIPT_SCHEMA = "adept-codirector-knowledge-routing-receipt/v1"
CONSUMER_CHAT = "codirector.chat"
CONSUMER_STREAM = "codirector.chat.stream"
CONSUMER_PROBE = "codirector.status.probe"


def _receipt_dir() -> Path:
    from ...config import settings

    path = settings.data_dir / "codirector"
    path.mkdir(parents=True, exist_ok=True)
    return path


def receipt_path(*, project_id: str | None = None) -> Path:
    if project_id:
        path = _receipt_dir() / "projects" / str(project_id)
        path.mkdir(parents=True, exist_ok=True)
        return path / "knowledge_routing_receipt.json"
    return _receipt_dir() / "knowledge_routing_receipt.json"


def record_routing_receipt(
    *,
    query: str,
    retrieved_ids: list[str] | tuple[str, ...] = (),
    consumer: str = CONSUMER_CHAT,
    landed: bool = True,
    project_id: str | None = None,
    reply_excerpt: str | None = None,
) -> dict[str, Any]:
    receipt: dict[str, Any] = {
        "schema": RECEIPT_SCHEMA,
        "query": (query or "").strip(),
        "retrievedIds": [str(item) for item in retrieved_ids if item],
        "consumer": consumer,
        "landed": bool(landed),
        "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "projectId": project_id,
        "replyExcerpt": (reply_excerpt or "")[:240] or None,
    }
    payload = json.dumps(receipt, indent=2)
    receipt_path().write_text(payload, encoding="utf-8")
    if project_id:
        receipt_path(project_id=project_id).write_text(payload, encoding="utf-8")
    return receipt


def last_routing_receipt(*, project_id: str | None = None) -> Optional[dict[str, Any]]:
    # A project read stays on that project's receipt. The unscoped file is a
    # different project’s last turn and must not count as this project’s routing.
    candidates: list[Path] = [receipt_path(project_id=project_id) if project_id else receipt_path()]
    for path in candidates:
        if not path.is_file():
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        if isinstance(data, dict) and data.get("schema") == RECEIPT_SCHEMA:
            return data
    return None
