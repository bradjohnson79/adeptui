"""Project password protection — server-side hashing, unlock grants, route enforcement."""

from .service import ensure_tables, require_unlocked, is_protected, is_unlocked

__all__ = ["ensure_tables", "require_unlocked", "is_protected", "is_unlocked"]
