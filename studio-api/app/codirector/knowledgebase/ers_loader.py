"""Deterministic Environment Reference Sheet knowledgebase loader.

No RAG. No embeddings. Reads ERS_SPEC.md and optionally lists the two
exemplar PNG paths. Used only when purpose=environment_reference_sheet.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

ERS_KB_DIR = Path(__file__).resolve().parent / "environment-reference-sheet"
ERS_SPEC_NAME = "ERS_SPEC.md"
ERS_EXEMPLAR_NAMES = ("ERS_REFERENCE_01.png", "ERS_REFERENCE_02.png")


@dataclass(frozen=True)
class ERSKnowledgebase:
    spec_text: str
    spec_path: Path
    exemplar_paths: tuple[Path, ...] = field(default_factory=tuple)

    @property
    def spec_summary(self) -> str:
        """First-pass deterministic summary: required-section headings from the spec."""
        keep: list[str] = []
        for line in self.spec_text.splitlines():
            stripped = line.strip()
            if stripped.startswith("## ") or stripped.startswith("### "):
                keep.append(stripped.lstrip("# ").strip())
            elif stripped[:1].isdigit() and "**" in stripped:
                keep.append(stripped)
        return "\n".join(keep) if keep else self.spec_text[:1200]


def load_ers_knowledgebase(*, root: Path | None = None) -> ERSKnowledgebase:
    """Load the on-disk ERS spec and list real exemplar files only."""
    kb_dir = Path(root) if root is not None else ERS_KB_DIR
    spec_path = kb_dir / ERS_SPEC_NAME
    spec_text = spec_path.read_text(encoding="utf-8") if spec_path.is_file() else ""
    exemplars = tuple(
        path for name in ERS_EXEMPLAR_NAMES if (path := kb_dir / name).is_file()
    )
    return ERSKnowledgebase(
        spec_text=spec_text,
        spec_path=spec_path,
        exemplar_paths=exemplars,
    )


def list_ers_exemplar_paths(*, root: Path | None = None) -> tuple[Path, ...]:
    return load_ers_knowledgebase(root=root).exemplar_paths
