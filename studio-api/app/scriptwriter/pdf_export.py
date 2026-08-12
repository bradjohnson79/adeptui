"""Professional-ish screenplay PDF export (reportlab if available, else plain text fallback)."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from .fountain import to_fountain
from .models import ScriptDocument
from .errors import SCRIPT_EXPORT_FAILED, ScriptwriterError


def export_pdf(doc: ScriptDocument, out_path: Path, *, include_notes: bool = False) -> Path:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    elements = [e for e in doc.elements if include_notes or e.type != "note"]
    try:
        from reportlab.lib.pagesizes import letter
        from reportlab.lib.units import inch
        from reportlab.pdfgen import canvas

        c = canvas.Canvas(str(out_path), pagesize=letter)
        width, height = letter
        # Screenplay-ish margins
        left = 1.5 * inch
        right = width - 1.0 * inch
        top = height - 1.0 * inch
        y = top
        page = 1
        c.setFont("Courier", 12)

        def new_page() -> None:
            nonlocal y, page
            c.showPage()
            page += 1
            c.setFont("Courier", 12)
            c.drawRightString(width - 0.75 * inch, height - 0.5 * inch, str(page))
            y = top

        # Title page
        c.drawCentredString(width / 2, height - 3 * inch, doc.title or "Untitled")
        c.drawCentredString(width / 2, height - 3.4 * inch, "Written by")
        c.drawCentredString(width / 2, height - 3.7 * inch, "Adept UI Studio")
        c.drawString(left, 1.5 * inch, f"Draft: {doc.draftStatus}")
        c.drawString(left, 1.2 * inch, f"Project: {doc.projectId[:8]}")
        new_page()

        for el in sorted(elements, key=lambda e: e.order):
            if el.omitted:
                continue
            text = el.text or ""
            if el.type == "scene_heading":
                text = text.upper()
                x = left
            elif el.type == "character":
                text = text.upper()
                x = left + 2.2 * inch
            elif el.type == "parenthetical":
                x = left + 1.6 * inch
            elif el.type == "dialogue":
                x = left + 1.0 * inch
                right_local = left + 3.5 * inch
            elif el.type == "transition":
                text = text.upper()
                x = right - 2.0 * inch
            else:
                x = left
                right_local = right

            if el.type != "dialogue":
                right_local = right

            # wrap
            words = text.split()
            line = ""
            lines: list[str] = []
            max_chars = max(20, int((right_local - x) / 7))
            for w in words or [""]:
                trial = (line + " " + w).strip()
                if len(trial) > max_chars and line:
                    lines.append(line)
                    line = w
                else:
                    line = trial
            if line or not words:
                lines.append(line)
            if y - 14 * len(lines) < 1.0 * inch:
                new_page()
            for ln in lines:
                c.drawString(x, y, ln)
                y -= 14
            if el.type in ("action", "scene_heading", "dialogue", "transition"):
                y -= 8
        c.save()
        return out_path
    except ImportError:
        # Fallback: write .pdf.txt so export path still succeeds honestly
        fallback = out_path.with_suffix(".fountain.txt")
        fallback.write_text(to_fountain(elements, title=doc.title), encoding="utf-8")
        raise ScriptwriterError(
            SCRIPT_EXPORT_FAILED,
            "reportlab not installed; wrote Fountain text fallback instead.",
            details={"fallbackPath": str(fallback)},
            recovery_action="install_reportlab_or_use_fountain",
        )
