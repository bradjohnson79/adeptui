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
    from .aspect import normalize_storyboard_aspect

    page_size = int(doc.get("pageSize") or 9)
    aspect = normalize_storyboard_aspect(doc.get("aspectRatio"))
    cols = 4 if aspect == "9:16" else (3 if page_size in (6, 9) else 4)
    frame_ratio = "9 / 16" if aspect == "9:16" else "16 / 9"
    cards = []
    for p in panels:
        aid = p.get("assetId") or ""
        img = (
            f'<img src="/api/projects/{project_id}/assets/{aid}/file" alt="" />'
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
.card img,.empty{{width:100%;aspect-ratio:{frame_ratio};object-fit:cover;display:block;background:#000}}
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
        from .aspect import normalize_storyboard_aspect

        page_size = int(doc.get("pageSize") or 9)
        aspect = normalize_storyboard_aspect(doc.get("aspectRatio"))
        try:
            from .compose import grid_for_page_size

            cols, rows = grid_for_page_size(page_size, aspect)
        except Exception:
            cols = 3 if page_size in (6, 9) else 4
            rows = (page_size + cols - 1) // cols
            if aspect == "9:16":
                cols, rows = rows, cols
        margin = 0.6 * inch
        gap = 0.2 * inch
        usable_w = width - 2 * margin
        usable_h = height - 1.4 * inch
        cell_w = (usable_w - gap * (cols - 1)) / cols
        cell_h = (usable_h - gap * (rows - 1)) / rows

        c.setFont("Helvetica-Bold", 14)
        c.drawString(margin, height - 0.55 * inch, title)
        c.setFont("Helvetica", 9)
        c.drawString(
            margin,
            height - 0.75 * inch,
            f"Adept Storyboard · {aspect} · {data.get('exportedAt')} · {len(panels)} panels",
        )

        for idx, p in enumerate(panels[:page_size]):
            r = idx // cols
            col = idx % cols
            x = margin + col * (cell_w + gap)
            y = height - 1.1 * inch - (r + 1) * cell_h - r * gap
            aw, ah = (9, 16) if aspect == "9:16" else (16, 9)
            max_w = cell_w - 4
            max_h = max(12, cell_h - 28)
            frame_h = max_h
            frame_w = frame_h * aw / ah
            if frame_w > max_w:
                frame_w = max_w
                frame_h = frame_w * ah / aw
            frame_x = x + (cell_w - frame_w) / 2
            frame_y = y + 18 + max(0, (max_h - frame_h) / 2)
            c.setStrokeColorRGB(0.3, 0.3, 0.3)
            c.rect(x, y, cell_w, cell_h)
            c.rect(frame_x, frame_y, frame_w, frame_h)
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
                                frame_x,
                                frame_y,
                                width=frame_w,
                                height=frame_h,
                                preserveAspectRatio=True,
                                mask="auto",
                            )
                            drawn = True
                            break
                        except Exception:
                            continue
            if not drawn:
                c.setFillColorRGB(0.9, 0.9, 0.9)
                c.rect(frame_x, frame_y, frame_w, frame_h, fill=1, stroke=0)
                c.setFillColorRGB(0.2, 0.2, 0.2)
                c.setFont("Helvetica", 8)
                c.drawCentredString(frame_x + frame_w / 2, frame_y + frame_h / 2, "No image")
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

    return _fallback_pdf(title, data, doc, panels, assets_root), filename


def _pdf_escape(text: str) -> str:
    return text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def _jpeg_for_asset(assets_root: Path, asset_id: str) -> tuple[bytes, int, int] | None:
    try:
        from PIL import Image
    except Exception:
        return None
    for path in list(assets_root.glob(f"**/{asset_id}.*"))[:3]:
        if path.suffix.lower() not in {".png", ".jpg", ".jpeg", ".webp"}:
            continue
        try:
            image = Image.open(path).convert("RGB")
            buf = io.BytesIO()
            image.save(buf, format="JPEG", quality=70)
            return buf.getvalue(), image.width, image.height
        except Exception:
            continue
    return None


def _fallback_pdf(
    title: str,
    data: dict[str, Any],
    doc: dict[str, Any],
    panels: list[dict[str, Any]],
    assets_root: Path,
) -> bytes:
    """Letter page with one aspect-correct frame per panel. No ReportLab required."""
    from .aspect import normalize_storyboard_aspect
    from .compose import grid_for_page_size

    aspect = normalize_storyboard_aspect(doc.get("aspectRatio"))
    page_size = int(doc.get("pageSize") or 9)
    cols, rows = grid_for_page_size(page_size, aspect)
    page_w, page_h = 612.0, 792.0
    margin = 36.0
    header = 56.0
    gap = 8.0
    usable_w = page_w - 2 * margin
    usable_h = page_h - margin - header
    cell_w = (usable_w - gap * (cols - 1)) / max(cols, 1)
    cell_h = (usable_h - gap * (rows - 1)) / max(rows, 1)
    aw, ah = (9.0, 16.0) if aspect == "9:16" else (16.0, 9.0)

    images: list[tuple[bytes, int, int]] = []
    ops: list[str] = [
        f"BT /F1 12 Tf {margin:.2f} {page_h - 28:.2f} Td ({_pdf_escape(title[:80])}) Tj ET",
        (
            f"BT /F1 8 Tf {margin:.2f} {page_h - 42:.2f} Td ("
            + _pdf_escape(
                f"Adept Storyboard · {aspect} · {data.get('exportedAt')} · {len(panels)} panels"
            )
            + ") Tj ET"
        ),
    ]
    for idx, panel in enumerate(panels[:page_size]):
        row = idx // cols
        col = idx % cols
        x = margin + col * (cell_w + gap)
        top = page_h - header - row * (cell_h + gap)
        y = top - cell_h
        caption_h = 14.0
        max_w = cell_w - 4.0
        max_h = max(8.0, cell_h - caption_h - 4.0)
        frame_h = max_h
        frame_w = frame_h * aw / ah
        if frame_w > max_w:
            frame_w = max_w
            frame_h = frame_w * ah / aw
        frame_x = x + (cell_w - frame_w) / 2.0
        frame_y = y + caption_h + max(0.0, (max_h - frame_h) / 2.0)
        ops.append("0.93 g")
        ops.append(f"{frame_x:.2f} {frame_y:.2f} {frame_w:.2f} {frame_h:.2f} re f")
        aid = str(panel.get("assetId") or "")
        jpeg = _jpeg_for_asset(assets_root, aid) if aid else None
        if jpeg:
            blob, src_w, src_h = jpeg
            images.append((blob, src_w, src_h))
            name = f"Im{len(images) - 1}"
            scale = min(frame_w / max(src_w, 1), frame_h / max(src_h, 1))
            draw_w = src_w * scale
            draw_h = src_h * scale
            draw_x = frame_x + (frame_w - draw_w) / 2.0
            draw_y = frame_y + (frame_h - draw_h) / 2.0
            ops.append("q")
            ops.append(f"{draw_w:.2f} 0 0 {draw_h:.2f} {draw_x:.2f} {draw_y:.2f} cm")
            ops.append(f"/{name} Do")
            ops.append("Q")
        ops.append("0 G")
        ops.append(f"{frame_x:.2f} {frame_y:.2f} {frame_w:.2f} {frame_h:.2f} re S")
        label = str(panel.get("label") or f"Panel {idx + 1}")[:32]
        ops.append(
            f"BT /F1 6 Tf {x + 2:.2f} {y + 3:.2f} Td ({_pdf_escape(label)}) Tj ET"
        )

    content = "\n".join(ops).encode("latin-1", errors="replace")
    xobjects = []
    for index, (blob, src_w, src_h) in enumerate(images):
        obj_num = 6 + index
        xobjects.append(
            (
                obj_num,
                (
                    f"{obj_num} 0 obj<< /Type /XObject /Subtype /Image /Width {src_w} "
                    f"/Height {src_h} /ColorSpace /DeviceRGB /BitsPerComponent 8 "
                    f"/Filter /DCTDecode /Length {len(blob)} >>stream\n"
                ).encode("latin-1")
                + blob
                + b"\nendstream\nendobj\n",
            )
        )
    xobject_refs = " ".join(f"/Im{i} {6 + i} 0 R" for i in range(len(images)))
    objects: list[bytes] = [
        b"1 0 obj<< /Type /Catalog /Pages 2 0 R >>endobj\n",
        b"2 0 obj<< /Type /Pages /Kids [3 0 R] /Count 1 >>endobj\n",
        (
            "3 0 obj<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
            "/Contents 4 0 R /Resources << /Font << /F1 5 0 R >> /XObject << "
            f"{xobject_refs} >> >> >>endobj\n"
        ).encode("latin-1"),
        f"4 0 obj<< /Length {len(content)} >>stream\n".encode("latin-1")
        + content
        + b"\nendstream\nendobj\n",
        b"5 0 obj<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>endobj\n",
    ]
    objects.extend(blob for _num, blob in xobjects)
    out = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for obj in objects:
        offsets.append(len(out))
        out.extend(obj)
    xref_pos = len(out)
    xref = [f"xref\n0 {len(objects) + 1}\n", "0000000000 65535 f \n"]
    xref.extend(f"{off:010d} 00000 n \n" for off in offsets[1:])
    xref.append(
        f"trailer<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref_pos}\n%%EOF\n"
    )
    out.extend("".join(xref).encode("latin-1"))
    return bytes(out)
