"""Storyboard export — Adept JSON, contact-sheet HTML, and real PDF bytes."""

from __future__ import annotations

import io
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ..config import settings
from .documents import hydrate_panels


def export_adept_json(project_id: str, document_id: str | None = None) -> dict[str, Any]:
    payload = hydrate_panels(project_id, document_id)
    return {
        "format": "adept.storyboard.v1",
        "exportedAt": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "projectId": project_id,
        "document": payload.get("document"),
        "panels": payload.get("panels") or [],
    }


def export_contact_sheet_html(project_id: str, document_id: str | None = None) -> str:
    data = export_adept_json(project_id, document_id)
    doc = data.get("document") or {}
    panels = data.get("panels") or []
    page_size = int(doc.get("pageSize") or 9)
    cols = 3 if page_size in (6, 9) else 4
    cards = []
    for p in panels:
        aid = p.get("assetId") or ""
        img = (
            f'<img src="/api/assets/{aid}/file" alt="" />'
            if aid
            else '<div class="empty">Empty</div>'
        )
        label = (p.get("label") or "")[:80]
        sync = p.get("scriptLinkStatus") or "unlinked"
        cards.append(
            f'<figure class="card">{img}<figcaption>{label}<br/><span>{sync}</span></figcaption></figure>'
        )
    body = "\n".join(cards) or "<p>No panels</p>"
    title = doc.get("title") or "Storyboard"
    return f"""<!doctype html>
<html><head><meta charset="utf-8"/><title>{title}</title>
<style>
body{{font-family:Georgia,serif;background:#111;color:#eee;padding:24px}}
h1{{font-weight:600}}
.grid{{display:grid;grid-template-columns:repeat({cols},1fr);gap:12px}}
.card{{margin:0;border:1px solid #333;border-radius:6px;overflow:hidden;background:#1a1a1a}}
.card img,.empty{{width:100%;aspect-ratio:16/9;object-fit:cover;display:block;background:#000}}
.empty{{display:grid;place-items:center;opacity:.6}}
figcaption{{padding:8px;font-size:12px}}
@media print{{body{{background:#fff;color:#000}}.card{{border-color:#999}}}}
</style></head>
<body>
<h1>{title}</h1>
<p>Adept Storyboard contact sheet · {data.get("exportedAt")} · Print to PDF</p>
<div class="grid">{body}</div>
</body></html>"""


def export_pdf_bytes(project_id: str, document_id: str | None = None) -> tuple[bytes, str]:
    """
    Return (pdf_bytes, filename). Uses reportlab when available; otherwise a minimal
    PDF built without external deps so Export PDF always returns application/pdf.
    """
    data = export_adept_json(project_id, document_id)
    doc = data.get("document") or {}
    panels = data.get("panels") or []
    title = str(doc.get("title") or "Storyboard")
    filename = f"storyboard-{project_id[:8]}.pdf"

    # Try embedding thumbnails from asset files
    assets_root = Path(settings.data_dir) / "assets"

    try:
        from reportlab.lib.pagesizes import letter
        from reportlab.lib.units import inch
        from reportlab.pdfgen import canvas

        buf = io.BytesIO()
        c = canvas.Canvas(buf, pagesize=letter)
        width, height = letter
        page_size = int(doc.get("pageSize") or 9)
        try:
            from .compose import grid_for_page_size

            cols, rows = grid_for_page_size(page_size)
        except Exception:
            cols = 3 if page_size in (6, 9) else 4
            rows = (page_size + cols - 1) // cols
        margin = 0.6 * inch
        gap = 0.2 * inch
        usable_w = width - 2 * margin
        usable_h = height - 1.4 * inch
        cell_w = (usable_w - gap * (cols - 1)) / cols
        cell_h = (usable_h - gap * (rows - 1)) / rows

        c.setFont("Helvetica-Bold", 14)
        c.drawString(margin, height - 0.55 * inch, title)
        c.setFont("Helvetica", 9)
        c.drawString(margin, height - 0.75 * inch, f"Adept Storyboard · {data.get('exportedAt')} · {len(panels)} panels")

        for idx, p in enumerate(panels[:page_size]):
            r = idx // cols
            col = idx % cols
            x = margin + col * (cell_w + gap)
            y = height - 1.1 * inch - (r + 1) * cell_h - r * gap
            c.setStrokeColorRGB(0.3, 0.3, 0.3)
            c.rect(x, y, cell_w, cell_h)
            aid = p.get("assetId")
            drawn = False
            if aid:
                # Common layout: data/assets/{project}/{asset}.png or data/assets/{asset}/...
                candidates = list(assets_root.glob(f"**/{aid}.*"))[:3]
                for path in candidates:
                    if path.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp"}:
                        try:
                            c.drawImage(
                                str(path),
                                x + 2,
                                y + 18,
                                width=cell_w - 4,
                                height=cell_h - 28,
                                preserveAspectRatio=True,
                                mask="auto",
                            )
                            drawn = True
                            break
                        except Exception:
                            continue
            if not drawn:
                c.setFillColorRGB(0.9, 0.9, 0.9)
                c.rect(x + 2, y + 18, cell_w - 4, cell_h - 28, fill=1, stroke=0)
                c.setFillColorRGB(0.2, 0.2, 0.2)
                c.setFont("Helvetica", 8)
                c.drawCentredString(x + cell_w / 2, y + cell_h / 2, "No image")
            c.setFillColorRGB(0, 0, 0)
            c.setFont("Helvetica", 8)
            label = str(p.get("label") or f"Panel {idx + 1}")[:40]
            sync = str(p.get("scriptLinkStatus") or "")
            c.drawString(x + 4, y + 6, f"{label} · {sync}")

        c.showPage()
        c.save()
        return buf.getvalue(), filename
    except Exception:
        pass

    # Minimal valid PDF fallback (text-only)
    lines = [title, f"Exported {data.get('exportedAt')}", f"Panels: {len(panels)}"]
    for i, p in enumerate(panels[:40]):
        lines.append(
            f"{i + 1}. {p.get('label') or 'Panel'} asset={p.get('assetId') or '-'} sync={p.get('scriptLinkStatus')}"
        )
    content = "\\n".join(lines).replace("(", "\\(").replace(")", "\\)")
    # Very small hand-rolled PDF
    stream = f"BT /F1 10 Tf 50 750 Td ({content[:1200]}) Tj ET"
    objects = []
    objects.append("1 0 obj<< /Type /Catalog /Pages 2 0 R >>endobj\n")
    objects.append("2 0 obj<< /Type /Pages /Kids [3 0 R] /Count 1 >>endobj\n")
    objects.append(
        "3 0 obj<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
        "/Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>endobj\n"
    )
    objects.append(f"4 0 obj<< /Length {len(stream)} >>stream\n{stream}\nendstream\nendobj\n")
    objects.append("5 0 obj<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>endobj\n")
    out = ["%PDF-1.4\n"]
    offsets = [0]
    for obj in objects:
        offsets.append(sum(len(x.encode("latin-1", errors="replace")) for x in out))
        out.append(obj)
    xref_pos = sum(len(x.encode("latin-1", errors="replace")) for x in out)
    out.append(f"xref\n0 {len(objects) + 1}\n")
    out.append("0000000000 65535 f \n")
    for off in offsets[1:]:
        out.append(f"{off:010d} 00000 n \n")
    out.append(f"trailer<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref_pos}\n%%EOF\n")
    return "".join(out).encode("latin-1", errors="replace"), filename
