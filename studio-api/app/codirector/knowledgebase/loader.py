"""Load Adept platform knowledge Markdown with YAML front matter.

Walks ``knowledgebase/**/*.md`` (including ``video-generators/*.md``).
Skips ``multimodal_continuity`` Python packages. Caches by file mtime.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable

import yaml

KB_ROOT = Path(__file__).resolve().parent

_SKIP_DIR_NAMES = frozenset(
    {
        "multimodal_continuity",
        "__pycache__",
        ".pytest_cache",
    }
)

_BODY_SNIPPET_CHARS = 1200

# Active CD chat retrieve must not surface these packets as spoken context.
# Files stay on disk for Settings / archival / silent shelf routing.
CREATOR_CHAT_EXCLUDED_IDS = frozenset(
    {
        "adept-platform",
        "adept-system-map",
        "spatial-map",
        "posecraft",
    }
)

_cache: dict[str, tuple[float, "KnowledgeDocument"]] = {}


@dataclass(frozen=True)
class KnowledgeDocument:
    id: str
    title: str
    spoken: str
    body: str
    aliases: tuple[str, ...] = ()
    tags: tuple[str, ...] = ()
    workspaces: tuple[str, ...] = ()
    domains: tuple[str, ...] = ()
    product_ids: tuple[str, ...] = ()
    registry_ids: tuple[str, ...] = ()
    kind: str = ""
    creator_chat: bool = True
    path: Path = field(default_factory=Path)
    mtime: float = 0.0
    meta: dict[str, Any] = field(default_factory=dict)

    @property
    def snippet(self) -> str:
        excerpt = _first_body_excerpt(self.body, _BODY_SNIPPET_CHARS)
        parts = [part for part in (self.title.strip(), self.spoken.strip(), excerpt) if part]
        return "\n".join(parts)

    @property
    def match_ids(self) -> tuple[str, ...]:
        seen: list[str] = []
        for token in (self.id, *self.product_ids, *self.registry_ids):
            key = str(token or "").strip()
            if key and key not in seen:
                seen.append(key)
        return tuple(seen)


def split_front_matter(text: str) -> tuple[dict[str, Any], str]:
    """Parse YAML front matter. Returns (meta, body)."""
    raw = (text or "").lstrip("\ufeff")
    if not raw.startswith("---"):
        return {}, text or ""
    rest = raw[3:]
    if rest.startswith("\r\n"):
        rest = rest[2:]
    elif rest.startswith("\n"):
        rest = rest[1:]
    for marker in ("\n---\n", "\n---\r\n", "\r\n---\r\n", "\r\n---\n"):
        idx = rest.find(marker)
        if idx >= 0:
            payload = rest[:idx]
            body = rest[idx + len(marker) :]
            break
    else:
        return {}, raw
    try:
        parsed = yaml.safe_load(payload)
    except yaml.YAMLError:
        return {}, raw
    if not isinstance(parsed, dict):
        return {}, raw
    return parsed, body


def _string_tuple(value: Any) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, str):
        token = value.strip()
        return (token,) if token else ()
    if isinstance(value, (list, tuple, set)):
        out: list[str] = []
        for item in value:
            token = str(item or "").strip()
            if token and token not in out:
                out.append(token)
        return tuple(out)
    return ()


def _heading_title(body: str, fallback: str) -> str:
    for line in (body or "").splitlines():
        stripped = line.strip()
        if stripped.startswith("# "):
            return stripped[2:].strip()
    return fallback


def _first_body_excerpt(body: str, limit: int) -> str:
    chunks: list[str] = []
    used = 0
    in_fence = False
    for line in (body or "").splitlines():
        stripped = line.strip()
        if stripped.startswith("```"):
            in_fence = not in_fence
            continue
        if in_fence or not stripped:
            continue
        if stripped.startswith("#") or stripped.startswith("|") or stripped.startswith("Sources:"):
            continue
        if stripped in {"---", "***"}:
            continue
        take = stripped
        if used + len(take) > limit:
            take = take[: max(0, limit - used)].rstrip()
            if take:
                chunks.append(take)
            break
        chunks.append(take)
        used += len(take) + 1
        if used >= limit:
            break
    return " ".join(chunks).strip()


def _should_skip(meta: dict[str, Any], body: str) -> bool:
    if meta.get("skip") in {True, "true", "yes", 1, "1"}:
        return True
    status = str(meta.get("status") or "").strip().lower()
    if status in {"moved", "skip", "deprecated"}:
        return True
    heading = ""
    for line in (body or "").splitlines():
        if line.strip():
            heading = line.strip()
            break
    return heading in {"# Moved", "# Deprecated"}


def _iter_markdown_paths(root: Path) -> Iterable[Path]:
    if not root.is_dir():
        return
    for path in root.rglob("*.md"):
        if any(part in _SKIP_DIR_NAMES for part in path.parts):
            continue
        if not path.is_file():
            continue
        yield path


def _document_from_path(path: Path, mtime: float) -> KnowledgeDocument | None:
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError:
        return None
    meta, body = split_front_matter(raw)
    if _should_skip(meta, body):
        return None
    doc_id = str(meta.get("id") or path.stem).strip() or path.stem
    title = str(meta.get("title") or "").strip() or _heading_title(body, doc_id)
    spoken = str(meta.get("spoken") or "").strip()
    aliases = _string_tuple(meta.get("aliases"))
    workspaces = _string_tuple(
        meta.get("workspace_tags") or meta.get("workspaces") or meta.get("workspace")
    )
    tags = _string_tuple(meta.get("tags"))
    domains = _string_tuple(meta.get("domains") or meta.get("domain"))
    product_ids = _string_tuple(meta.get("product_ids"))
    registry_ids = _string_tuple(meta.get("registry_ids"))
    creator_chat_raw = meta.get("creator_chat")
    if creator_chat_raw is None:
        creator_chat = doc_id not in CREATOR_CHAT_EXCLUDED_IDS
    else:
        creator_chat = creator_chat_raw not in {False, "false", "no", 0, "0"}
        if doc_id in CREATOR_CHAT_EXCLUDED_IDS:
            creator_chat = False
    return KnowledgeDocument(
        id=doc_id,
        title=title,
        spoken=spoken,
        body=(body or "").strip(),
        aliases=aliases,
        tags=tags,
        workspaces=workspaces,
        domains=domains,
        product_ids=product_ids,
        registry_ids=registry_ids,
        kind=str(meta.get("kind") or "").strip(),
        creator_chat=creator_chat,
        path=path,
        mtime=mtime,
        meta=meta,
    )


def clear_document_cache() -> None:
    _cache.clear()


def load_all_documents(*, root: Path | None = None, force: bool = False) -> list[KnowledgeDocument]:
    kb = Path(root) if root is not None else KB_ROOT
    if force:
        for key in list(_cache):
            if key.startswith(str(kb.resolve())) or root is None:
                _cache.pop(key, None)
    docs: list[KnowledgeDocument] = []
    live: set[str] = set()
    for path in _iter_markdown_paths(kb):
        try:
            resolved = str(path.resolve())
            mtime = path.stat().st_mtime
        except OSError:
            continue
        live.add(resolved)
        cached = _cache.get(resolved)
        if not force and cached is not None and cached[0] == mtime:
            docs.append(cached[1])
            continue
        doc = _document_from_path(path, mtime)
        if doc is None:
            _cache.pop(resolved, None)
            continue
        _cache[resolved] = (mtime, doc)
        docs.append(doc)
    for key in list(_cache):
        if key not in live and (root is None or key.startswith(str(kb.resolve()))):
            _cache.pop(key, None)
    docs.sort(key=lambda item: item.id)
    return docs


def get_document(doc_id: str, *, root: Path | None = None) -> KnowledgeDocument | None:
    token = str(doc_id or "").strip()
    if not token:
        return None
    lowered = token.lower()
    for doc in load_all_documents(root=root):
        if doc.id.lower() == lowered:
            return doc
        if any(item.lower() == lowered for item in doc.match_ids):
            return doc
    return None


def list_documents(*, root: Path | None = None) -> list[KnowledgeDocument]:
    return load_all_documents(root=root)
