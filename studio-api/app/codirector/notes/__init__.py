"""Co-Director Notes — messy working memory (not Wiki)."""

from .contracts import NOTE_CATEGORIES, NOTE_STATUSES, WorkingNote
from .service import (
    dismiss_note,
    list_notes,
    promote_note_to_wiki,
    upsert_notes_from_texts,
)

__all__ = [
    "NOTE_CATEGORIES",
    "NOTE_STATUSES",
    "WorkingNote",
    "dismiss_note",
    "list_notes",
    "promote_note_to_wiki",
    "upsert_notes_from_texts",
]
