"""Project Wiki export helpers.

Creator-facing exports are derived from the normalized Project Wiki model rather than scraped UI.
"""

from __future__ import annotations

import io
import json
import mimetypes
import re
import textwrap
import zipfile
from dataclasses import dataclass
from html import escape
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from ..db import Asset
from .wiki import build_project_wiki

_SAFE_FILE_RE = re.compile(r"[^A-Za-z0-9._-]+")
_UUID_RE = re.compile(
    r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[1-5][0-9a-fA-F]{3}-[89abAB][0-9a-fA-F]{3}-[0-9a-fA-F]{12}\b"
)

_IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp", ".svg", ".gif", ".bmp"}
_AUDIO_EXTS = {".mp3", ".wav", ".ogg", ".m4a", ".flac"}
_VIDEO_EXTS = {".mp4", ".webm", ".mov", ".mkv", ".m4v"}
_MEDIA_KIND_BUCKETS = {
    "image": ("images", "references"),
    "audio": ("audio", ""),
    "video": ("video", ""),
}
_MIME_OVERRIDES = {
    ".bmp": "image/bmp",
    ".flac": "audio/flac",
    ".gif": "image/gif",
    ".m4a": "audio/mp4",
    ".m4v": "video/x-m4v",
    ".mkv": "video/x-matroska",
    ".mov": "video/quicktime",
}
_EXPORT_STRIP_KEYS = {
    "assetId",
    "asset_id",
    "projectId",
    "project_id",
    "proposalId",
    "proposal_id",
    "sceneId",
    "scene_id",
    "sourceMessageId",
    "source_message_id",
    "toolId",
    "tool_id",
    "toolInvocationId",
    "tool_invocation_id",
}


@dataclass
class WikiExportOptions:
    export_title: str = ""
    include_cover: bool = True
    include_toc: bool = True
    include_open_questions: bool = True
    include_unresolved: bool = True
    include_images: bool = True
    include_audio_video: bool = True
    include_production_metadata: bool = True
    sections_mode: str = "all"
    selected_sections: tuple[str, ...] = ()
    size_mode: str = "optimized"


def _safe_name(value: str, fallback: str) -> str:
    cleaned = _SAFE_FILE_RE.sub("-", value or "").strip("-._")
    return cleaned or fallback


def _sanitize_text(value: str) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    text = text.replace("\\", "/")
    if "/" in text:
        text = text.split("/")[-1]
    text = _UUID_RE.sub("", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip(" -_/") or ""


def _sanitize_export_value(value: Any) -> Any:
    if isinstance(value, dict):
        out: dict[str, Any] = {}
        for key, item in value.items():
            if key in _EXPORT_STRIP_KEYS:
                continue
            out[key] = _sanitize_export_value(item)
        return out
    if isinstance(value, list):
        return [_sanitize_export_value(item) for item in value]
    if isinstance(value, str) and _UUID_RE.fullmatch(value.strip()):
        return ""
    return value


def _read_prompt_meta(asset: Asset) -> dict[str, Any]:
    try:
        raw = json.loads(asset.prompt_meta_json or "{}")
    except Exception:
        return {}
    return raw if isinstance(raw, dict) else {}


def _first_text(meta: dict[str, Any], *keys: str) -> str:
    for key in keys:
        value = meta.get(key)
        if isinstance(value, str) and value.strip():
            return value
    return ""


def _classify_asset_kind(asset: Asset) -> str | None:
    kind = str(asset.kind or "").strip().lower()
    if kind in {"image", "audio", "video"}:
        return kind
    suffix = Path(asset.filename or "").suffix.lower()
    if suffix in _IMAGE_EXTS:
        return "image"
    if suffix in _AUDIO_EXTS:
        return "audio"
    if suffix in _VIDEO_EXTS:
        return "video"
    return None


def _guess_mime_type(filename: str, kind: str) -> str:
    suffix = Path(filename or "").suffix.lower()
    if suffix in _MIME_OVERRIDES:
        return _MIME_OVERRIDES[suffix]
    guessed = mimetypes.guess_type(filename or "")[0]
    if guessed:
        return guessed
    if kind == "image":
        return "image/*"
    if kind == "audio":
        return "audio/*"
    if kind == "video":
        return "video/*"
    return "application/octet-stream"


def _section_entries(wiki: dict[str, Any], options: WikiExportOptions) -> dict[str, Any]:
    sections = dict((wiki.get("sections") or {}))
    if options.sections_mode == "selected" and options.selected_sections:
        sections = {key: value for key, value in sections.items() if key in set(options.selected_sections)}
    if not options.include_open_questions:
        sections.pop("openQuestions", None)
    if not options.include_unresolved:
        for section in sections.values():
            section["entries"] = [entry for entry in section.get("entries") or [] if entry.get("state") != "unresolved"]
    return sections


def _relative_asset_path(export_id: str, kind: str, filename: str, title: str) -> str:
    ext = Path(filename or "").suffix.lower()
    bucket, subdir = _MEDIA_KIND_BUCKETS[kind]
    rel_dir = f"assets/{bucket}/{subdir}".rstrip("/")
    stem = _safe_name(_sanitize_text(Path(filename or "").stem) or title, f"{kind}-asset")
    return f"{rel_dir}/{export_id}-{stem}{ext}"


def _collect_assets(
    db: Session, project_id: str, options: WikiExportOptions
) -> tuple[list[dict[str, Any]], list[str], dict[str, bytes], dict[str, bytes]]:
    assets = (
        db.query(Asset)
        .filter(Asset.project_id == project_id)
        .order_by(Asset.created_at.desc())
        .all()
    )
    manifest: list[dict[str, Any]] = []
    warnings: list[str] = []
    payloads: dict[str, bytes] = {}
    inline_media: dict[str, bytes] = {}
    counters = {"image": 0, "audio": 0, "video": 0}
    for asset in assets:
        approval = str(asset.production_approval or "none").lower()
        if approval == "rejected":
            continue
        kind = _classify_asset_kind(asset)
        if kind is None:
            warnings.append(f"Skipped unsupported asset format: {_sanitize_text(asset.filename) or 'asset'}")
            continue
        if kind == "image" and not options.include_images:
            continue
        if kind in {"audio", "video"} and not options.include_audio_video:
            continue
        meta = _read_prompt_meta(asset)
        title = _sanitize_text(asset.tag or Path(asset.filename or "").stem or "Project media") or "Project media"
        caption = _sanitize_text(_first_text(meta, "caption", "description", "label", "title") or title) or title
        alt = _sanitize_text(_first_text(meta, "alt", "altText", "alt_text", "description", "label", "title") or title) or title
        status = "approved" if approval == "approved" else "reference"
        counters[kind] += 1
        export_id = f"{kind}-{counters[kind]:02d}"
        entry: dict[str, Any] = {
            "exportId": export_id,
            "kind": kind,
            "title": title,
            "status": status,
            "mimeType": _guess_mime_type(asset.filename or "", kind),
            "caption": caption,
            "alt": alt,
        }
        source = Path(asset.path or "")
        if source.exists():
            rel_path = _relative_asset_path(export_id, kind, asset.filename or "", title)
            payload = source.read_bytes()
            payloads[rel_path] = payload
            entry["relativePath"] = rel_path
            if kind == "image":
                inline_media[export_id] = payload
        else:
            warnings.append(f"Media bytes were not available for {title}. Metadata was exported without the file.")
        if status == "reference":
            warnings.append(f"Included reference asset: {title}")
        manifest.append(entry)
    return manifest, warnings, payloads, inline_media


def build_export_model(
    db: Session, project_id: str, options: WikiExportOptions
) -> tuple[dict[str, Any], dict[str, bytes], dict[str, bytes]]:
    wiki = build_project_wiki(db, project_id)
    sections = _section_entries(wiki, options)
    assets, warnings, payloads, inline_media = _collect_assets(db, project_id, options)
    export_title = options.export_title.strip() or wiki.get("title") or "Project Wiki"
    export_model = {
        "schemaVersion": "1.0",
        "exportType": "adept-project-wiki",
        "title": export_title,
        "projectId": wiki.get("projectId"),
        "projectType": wiki.get("projectType"),
        "status": wiki.get("status"),
        "overview": wiki.get("overview"),
        "sections": sections,
        "assets": assets,
        "warnings": warnings,
        "exportedAt": wiki.get("updatedAt"),
        "preferences": {
            "cover": options.include_cover,
            "toc": options.include_toc,
            "openQuestions": options.include_open_questions,
            "unresolved": options.include_unresolved,
            "images": options.include_images,
            "audioVideo": options.include_audio_video,
            "productionMetadata": options.include_production_metadata,
            "sizeMode": options.size_mode,
        },
    }
    return _sanitize_export_value(export_model), payloads, inline_media


def _fallback_pdf_bytes(lines: list[str], filename: str) -> tuple[bytes, str]:
    content = "\n".join(lines)[:4000].replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
    stream = f"BT /F1 10 Tf 50 750 Td ({content}) Tj ET"
    objects = [
        "1 0 obj<< /Type /Catalog /Pages 2 0 R >>endobj\n",
        "2 0 obj<< /Type /Pages /Kids [3 0 R] /Count 1 >>endobj\n",
        "3 0 obj<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>endobj\n",
        f"4 0 obj<< /Length {len(stream)} >>stream\n{stream}\nendstream\nendobj\n",
        "5 0 obj<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>endobj\n",
    ]
    out = ["%PDF-1.4\n"]
    offsets = [0]
    for obj in objects:
        offsets.append(sum(len(part.encode("latin-1", errors="replace")) for part in out))
        out.append(obj)
    xref_pos = sum(len(part.encode("latin-1", errors="replace")) for part in out)
    out.append(f"xref\n0 {len(objects) + 1}\n")
    out.append("0000000000 65535 f \n")
    for off in offsets[1:]:
        out.append(f"{off:010d} 00000 n \n")
    out.append(f"trailer<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref_pos}\n%%EOF\n")
    return "".join(out).encode("latin-1", errors="replace"), filename


def export_pdf_bytes(db: Session, project_id: str, options: WikiExportOptions) -> tuple[bytes, str]:
    model, _, inline_media = build_export_model(db, project_id, options)
    title = str(model.get("title") or "Project Wiki")
    filename = f"{_safe_name(title, 'Project-Wiki')}.pdf"
    fallback_lines = [title, f"Status: {model.get('status') or 'Unknown'}", ""]
    overview = str(model.get("overview") or "").strip()
    if overview:
        fallback_lines.extend(["Overview", overview, ""])
    for section_key, section in (model.get("sections") or {}).items():
        label = re.sub(r"([a-z])([A-Z])", r"\1 \2", section_key).title()
        fallback_lines.append(label)
        for entry in section.get("entries") or []:
            fallback_lines.append(f"- {entry.get('state', 'note').title()}: {entry.get('text')}")
        if not (section.get("entries") or []) and section.get("emptyState"):
            fallback_lines.append(f"- {section.get('emptyState')}")
        fallback_lines.append("")
    for asset in model.get("assets") or []:
        fallback_lines.append(f"Media: {asset.get('title')} ({asset.get('kind')}, {asset.get('status')})")
        if asset.get("kind") == "image":
            fallback_lines.append(
                "  Image embedded when possible; otherwise omitted with a note in richer PDF readers."
            )
        else:
            fallback_lines.append(
                f"  {str(asset.get('kind') or 'Media').title()} metadata only in PDF. Use the offline HTML export for local playback."
            )

    try:
        from PIL import Image
        from reportlab.lib.pagesizes import letter
        from reportlab.lib.units import inch
        from reportlab.lib.utils import ImageReader
        from reportlab.pdfgen import canvas

        buf = io.BytesIO()
        c = canvas.Canvas(buf, pagesize=letter)
        width, height = letter
        margin = 0.7 * inch
        y = height - margin
        max_text_width = width - (2 * margin)

        def ensure_space(required: float) -> None:
            nonlocal y
            if y - required < margin:
                c.showPage()
                y = height - margin

        def draw_wrapped(text: str, *, font: str = "Helvetica", size: int = 10, extra_gap: float = 2) -> None:
            nonlocal y
            wrapped = textwrap.wrap(text or "", width=95) or [""]
            for line in wrapped:
                ensure_space(size + extra_gap)
                c.setFont(font, size)
                c.drawString(margin, y, line)
                y -= size + extra_gap

        c.setTitle(title)
        draw_wrapped(title, font="Helvetica-Bold", size=16, extra_gap=6)
        draw_wrapped(f"Status: {model.get('status') or 'Unknown'}", font="Helvetica", size=10, extra_gap=8)
        if overview:
            draw_wrapped("Overview", font="Helvetica-Bold", size=12, extra_gap=4)
            draw_wrapped(overview)
            y -= 4

        for section_key, section in (model.get("sections") or {}).items():
            label = re.sub(r"([a-z])([A-Z])", r"\1 \2", section_key).title()
            draw_wrapped(label, font="Helvetica-Bold", size=12, extra_gap=4)
            entries = section.get("entries") or []
            if entries:
                for entry in entries:
                    draw_wrapped(f"- {entry.get('state', 'note').title()}: {entry.get('text')}")
            elif section.get("emptyState"):
                draw_wrapped(f"- {section.get('emptyState')}")
            y -= 4

        media = model.get("assets") or []
        if media:
            draw_wrapped("Media", font="Helvetica-Bold", size=12, extra_gap=4)
            for asset in media:
                label = f"{asset.get('title')} ({asset.get('kind')}, {asset.get('status')})"
                draw_wrapped(label, font="Helvetica-Bold", size=10, extra_gap=3)
                if asset.get("caption"):
                    draw_wrapped(str(asset.get("caption")), size=9, extra_gap=3)
                if asset.get("kind") == "image":
                    payload = inline_media.get(str(asset.get("exportId") or ""))
                    if payload:
                        try:
                            image = Image.open(io.BytesIO(payload))
                            image.load()
                            draw_width = max_text_width
                            scale = min(draw_width / max(image.width, 1), 3.2 * inch / max(image.height, 1))
                            target_w = max(image.width * scale, 1)
                            target_h = max(image.height * scale, 1)
                            ensure_space(target_h + 12)
                            c.drawImage(
                                ImageReader(image),
                                margin,
                                y - target_h,
                                width=target_w,
                                height=target_h,
                                preserveAspectRatio=True,
                                mask="auto",
                            )
                            y -= target_h + 10
                        except Exception:
                            draw_wrapped("Image omitted from PDF because it could not be embedded safely.", size=9)
                    else:
                        draw_wrapped("Image omitted from PDF because the file bytes were not included in the export.", size=9)
                else:
                    draw_wrapped(
                        f"{str(asset.get('kind') or 'Media').title()} metadata only in PDF. Use the offline HTML export for the local file.",
                        size=9,
                    )
                y -= 4

        c.save()
        return buf.getvalue(), filename
    except Exception:
        return _fallback_pdf_bytes(fallback_lines, filename)


def export_offline_html_zip(db: Session, project_id: str, options: WikiExportOptions) -> tuple[bytes, str]:
    model, payloads, _ = build_export_model(db, project_id, options)
    title = str(model.get("title") or "Project Wiki")
    root_name = f"{_safe_name(title, 'Project-Wiki')}"
    archive_name = f"{root_name}.zip"
    embedded_json = json.dumps(model, ensure_ascii=False).replace("</", "<\\/")
    html = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>{escape(title)}</title>
  <link rel="stylesheet" href="assets/css/wiki.css" />
</head>
<body>
  <header class="hero">
    <h1>{escape(title)}</h1>
    <p id="overview"></p>
    <input id="wiki-search" type="search" placeholder="Search this Project Wiki" />
    <nav id="toc"></nav>
  </header>
  <main id="wiki-sections"></main>
  <section id="media-section" hidden>
    <h2>Project Media</h2>
    <div id="media-grid" class="media-grid"></div>
  </section>
  <script id="wiki-data" type="application/json">{embedded_json}</script>
  <script src="assets/js/wiki.js"></script>
</body>
</html>
"""
    css = """
body { font-family: Arial, sans-serif; margin: 0; background: #f7faf9; color: #16211d; }
.hero { padding: 2rem; background: #ffffff; border-bottom: 1px solid #d9e8e3; position: sticky; top: 0; }
#wiki-sections { padding: 1.5rem; display: grid; gap: 1rem; }
section { background: #ffffff; border: 1px solid #d9e8e3; border-radius: 16px; padding: 1rem; }
ul { padding-left: 1.1rem; }
.state { font-size: 0.8rem; color: #45635a; text-transform: uppercase; letter-spacing: 0.04em; }
.media-grid { display: grid; gap: 1rem; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); }
.media-card { background: #ffffff; border: 1px solid #d9e8e3; border-radius: 16px; padding: 0.85rem; }
.media-card img,
.media-card video { width: 100%; display: block; border-radius: 12px; background: #dfe9e5; }
.media-card audio { width: 100%; margin-top: 0.5rem; }
.media-card a { color: #1d5d4f; font-weight: 600; text-decoration: none; }
.media-card p { margin: 0.35rem 0 0; color: #45635a; font-size: 0.92rem; }
.media-status { display: inline-block; margin: 0.15rem 0 0.5rem; padding: 0.2rem 0.55rem; border-radius: 999px; background: #edf7f3; color: #1d5d4f; font-size: 0.8rem; font-weight: 600; text-transform: capitalize; }
.media-note { font-style: italic; }
@media print { .hero { position: static; } }
"""
    js = """
const rawData = document.getElementById('wiki-data')?.textContent || '{}';
const data = JSON.parse(rawData);
(() => {
  document.getElementById('overview').textContent = data.overview || '';
  const toc = document.getElementById('toc');
  const root = document.getElementById('wiki-sections');
  const mediaSection = document.getElementById('media-section');
  const mediaGrid = document.getElementById('media-grid');
  const sections = data.sections || {};
  Object.entries(sections).forEach(([key, section]) => {
    const id = `section-${key}`;
    const nav = document.createElement('a');
    nav.href = `#${id}`;
    nav.textContent = key.replace(/([a-z])([A-Z])/g, '$1 $2');
    nav.style.marginRight = '0.75rem';
    toc.appendChild(nav);
    const node = document.createElement('section');
    node.id = id;
    const h2 = document.createElement('h2');
    h2.textContent = nav.textContent;
    node.appendChild(h2);
    const items = section.entries || [];
    if (items.length) {
      const list = document.createElement('ul');
      items.forEach((entry) => {
        const li = document.createElement('li');
        const state = document.createElement('span');
        state.className = 'state';
        state.textContent = entry.state || '';
        li.appendChild(state);
        const text = document.createElement('div');
        text.textContent = entry.text || '';
        li.appendChild(text);
        list.appendChild(li);
      });
      node.appendChild(list);
    } else if (section.emptyState) {
      const p = document.createElement('p');
      p.textContent = section.emptyState;
      node.appendChild(p);
    }
    root.appendChild(node);
  });
  const assets = Array.isArray(data.assets) ? data.assets : [];
  if (assets.length && mediaSection && mediaGrid) {
    mediaSection.hidden = false;
    assets.forEach((asset) => {
      const card = document.createElement('article');
      card.className = 'media-card';
      const title = document.createElement('h3');
      title.textContent = asset.title || 'Project media';
      card.appendChild(title);
      const status = document.createElement('span');
      status.className = 'media-status';
      status.textContent = asset.status || 'reference';
      card.appendChild(status);
      const relPath = asset.relativePath || '';
      const kind = String(asset.kind || '').toLowerCase();
      if (relPath) {
        if (kind === 'image') {
          const img = document.createElement('img');
          img.src = relPath;
          img.alt = asset.alt || asset.title || 'Project image';
          card.appendChild(img);
        } else if (kind === 'audio') {
          const audio = document.createElement('audio');
          audio.controls = true;
          audio.src = relPath;
          card.appendChild(audio);
        } else if (kind === 'video') {
          const video = document.createElement('video');
          video.controls = true;
          video.src = relPath;
          card.appendChild(video);
        }
        const link = document.createElement('a');
        link.href = relPath;
        link.textContent = 'Open local media file';
        link.target = '_blank';
        link.rel = 'noreferrer';
        card.appendChild(link);
      } else {
        const note = document.createElement('p');
        note.className = 'media-note';
        note.textContent = 'This export includes metadata for this asset, but not the local file bytes.';
        card.appendChild(note);
      }
      if (asset.caption) {
        const caption = document.createElement('p');
        caption.textContent = asset.caption;
        card.appendChild(caption);
      }
      const meta = document.createElement('p');
      meta.textContent = `Type: ${asset.kind || 'media'} · Status: ${asset.status || 'reference'}`;
      card.appendChild(meta);
      mediaGrid.appendChild(card);
    });
  }
  const search = document.getElementById('wiki-search');
  search?.addEventListener('input', () => {
    const q = String(search.value || '').toLowerCase();
    root.querySelectorAll('section').forEach((section) => {
      const text = section.textContent?.toLowerCase() || '';
      section.style.display = !q || text.includes(q) ? '' : 'none';
    });
  });
})();
"""
    readme = (
        "Adept Project Wiki Offline Export\n\n"
        "Open index.html in a browser. This package is self-contained and does not require Adept UI or internet access.\n"
    )

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        prefix = f"{root_name}/"
        archive.writestr(prefix + "index.html", html)
        archive.writestr(prefix + "assets/css/wiki.css", css)
        archive.writestr(prefix + "assets/js/wiki.js", js)
        archive.writestr(prefix + "data/wiki.json", json.dumps(model, indent=2, ensure_ascii=False))
        archive.writestr(prefix + "README.txt", readme)
        for rel_path, payload in payloads.items():
            archive.writestr(prefix + rel_path, payload)
    return buffer.getvalue(), archive_name

