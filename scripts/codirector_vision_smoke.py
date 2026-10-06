"""Live Co-Director full-stack vision smoke against Schnick Coffee / Korri.

Verdicts:
  PASS — CODIRECTOR FULL-STACK VISION SMOKE
  FAIL — CODIRECTOR FULL-STACK VISION SMOKE
"""

from __future__ import annotations

import json
import os
import sys
import time
import uuid
from pathlib import Path

import httpx
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
API = os.environ.get("STUDIO_API_BASE", "http://127.0.0.1:8758")
PROJECT_ID = os.environ.get("ADEPT_PROJECT_ID", "2347bf46-3762-4763-86c5-4a6032522278")
KORRI_ID = os.environ.get("ADEPT_KORRI_ID", "c49371ed-ba6b-4c16-ba98-a8b28b72118b")
ANADRIYA_ID = os.environ.get("ADEPT_ANADRIYA_ID", "b7086f85-3ee3-44db-a395-ae1a94e37fe1")
EVIDENCE = ROOT / "docs" / "release-gate" / "codirector" / "evidence"
VISUAL_QUESTION = (
    "Describe the exact arrangement of Korri's visible outfit and the "
    "placement/pattern of major markings in the current reference. "
    "Include any unusual labels, color treatments, or footwear."
)
IMAGE_ONLY_CANDIDATES = (
    "starbucks",
    "magenta",
    "olive",
    "pouches",
    "boots",
    "buckle",
    "grime",
    "smudge",
    "apron",
    "pinafore",
    "tattered",
    "frayed",
    "thermal",
    "scavenger",
)


def _fail(reason: str) -> int:
    print(f"FAIL — CODIRECTOR FULL-STACK VISION SMOKE")
    print(f"BLOCKER: {reason}")
    return 1


def _norm(text: str) -> str:
    return " ".join((text or "").lower().split())


def _leak_corpus(db, project_id: str, character_id: str) -> str:
    from app.character_identity.crs_service import get_crs_summary
    from app.character_identity.service import get_profile
    from app.codirector.service import _character_context_block

    profile = get_profile(db, project_id, character_id)
    crs = get_crs_summary(db, project_id, character_id)
    parts = [
        profile.name or "",
        profile.description or "",
        profile.visual_description or "",
        profile.visual_style or "",
        profile.species_or_type or "",
        profile.height_description or "",
        profile.body_type or "",
        profile.apparent_age or "",
        _character_context_block(db, project_id=project_id, character_id=character_id),
        json.dumps(crs.model_dump(), default=str) if crs else "",
    ]
    return _norm("\n".join(parts))


def _stream(payload: dict) -> tuple[str, dict, list[dict]]:
    traces: list[dict] = []
    chunks: list[str] = []
    events: list[dict] = []
    with httpx.Client(timeout=600.0) as client:
        with client.stream("POST", f"{API}/api/codirector/chat/stream", json=payload) as resp:
            resp.raise_for_status()
            for raw in resp.iter_lines():
                if not raw:
                    continue
                line = raw.decode("utf-8", errors="ignore") if isinstance(raw, bytes) else raw
                if not line.startswith("data:"):
                    continue
                body = json.loads(line[5:].strip() or "{}")
                events.append(body)
                if body.get("type") == "vision_trace":
                    traces.append(body)
                if body.get("type") == "token":
                    chunks.append(str(body.get("content") or ""))
                if body.get("type") == "error":
                    raise RuntimeError(json.dumps(body.get("error") or body))
                if body.get("type") in {"completed", "cancelled"}:
                    break
    reply = "".join(chunks).strip()
    trace = traces[-1] if traces else {}
    return reply, trace, events


def main() -> int:
    sys.path.insert(0, str(ROOT / "studio-api"))
    from app.character_identity.visual_context import resolve_character_visual_context
    from app.codirector.service import _prepare_chat_request
    from app.codirector.vision_input import load_vision_image
    from app.db import SessionLocal
    import asyncio

    EVIDENCE.mkdir(parents=True, exist_ok=True)
    db = SessionLocal()
    try:
        visual = resolve_character_visual_context(db, PROJECT_ID, KORRI_ID)
        if not visual:
            return _fail("Korri visual context did not resolve an asset")
        loaded = load_vision_image(
            db, visual.asset_id, project_id=PROJECT_ID, source=visual.source
        )
        leak = _leak_corpus(db, PROJECT_ID, KORRI_ID)
        image_only = [token for token in IMAGE_ONLY_CANDIDATES if token not in leak]
        if len(image_only) < 2:
            return _fail("not enough image-only tokens after leak-corpus filter")

        provider, chat_request, _manifest = asyncio.run(
            _prepare_chat_request(
                db,
                messages=[{"role": "user", "content": VISUAL_QUESTION}],
                project_id=PROJECT_ID,
                scene_id=None,
                mode="chat",
                model="qwen3.6:35b-a3b",
                provider_id="ollama",
                request_id=f"vision-smoke-prep-{uuid.uuid4().hex[:8]}",
                character_id=KORRI_ID,
            )
        )
        last_user = next(m for m in reversed(chat_request.messages) if m.get("role") == "user")
        if not last_user.get("images"):
            return _fail("prepared ChatRequest last user has no images[]")
        if not chat_request.vision_trace or not chat_request.vision_trace.get("hasImages"):
            return _fail("prepared ChatRequest missing vision_trace")

        reply, trace, _events = _stream(
            {
                "messages": [{"role": "user", "content": VISUAL_QUESTION}],
                "project_id": PROJECT_ID,
                "character_id": KORRI_ID,
                "characterId": KORRI_ID,
                "model": "qwen3.6:35b-a3b",
                "mode": "chat",
                "request_id": f"vision-smoke-korri-{uuid.uuid4().hex[:8]}",
            }
        )
        if not reply:
            return _fail("empty Korri vision reply")
        if not trace.get("hasImages") and not trace.get("imageCount"):
            types = [str(ev.get("type") or "") for ev in _events[:20]]
            return _fail(
                "live stream did not emit vision_trace with images; "
                f"eventTypes={types}; reply={reply[:200]!r}"
            )
        if int(trace.get("imageCount") or 0) < 1:
            return _fail("vision_trace imageCount < 1")
        lower = _norm(reply)
        hits = [token for token in image_only if token in lower]
        if len(hits) < 2:
            (EVIDENCE / "codirector-vision-smoke-failed-reply.txt").write_text(reply, encoding="utf-8")
            return _fail(
                f"vision reply lacked image-only details {image_only}; hits={hits}; reply={reply[:400]}"
            )

        text_blocked = False
        try:
            _stream(
                {
                    "messages": [{"role": "user", "content": VISUAL_QUESTION}],
                    "project_id": PROJECT_ID,
                    "model": "qwen3.6:35b-a3b",
                    "mode": "chat",
                    "request_id": f"vision-smoke-text-{uuid.uuid4().hex[:8]}",
                }
            )
        except RuntimeError as exc:
            if "VISION_UNAVAILABLE" not in str(exc):
                return _fail(f"text-only Co-Director contrast unexpected error: {exc}")
            text_blocked = True
        with httpx.Client(timeout=600.0) as client:
            ollama = client.post(
                "http://127.0.0.1:11434/api/chat",
                json={
                    "model": "qwen3.6:35b-a3b",
                    "messages": [{"role": "user", "content": VISUAL_QUESTION}],
                    "stream": False,
                    "options": {"temperature": 0.55, "num_ctx": 2048},
                },
            )
            ollama.raise_for_status()
            text_only = str(((ollama.json() or {}).get("message") or {}).get("content") or "")
        text_hits = [token for token in image_only if token in _norm(text_only)]
        if text_hits:
            return _fail(
                f"text-only contrast already named image-only details {text_hits}; "
                f"question is invalid; reply={text_only[:300]!r}"
            )

        fixture = EVIDENCE / "direct-upload-fixture.png"
        img = Image.new("RGB", (256, 256), (180, 20, 200))
        draw = ImageDraw.Draw(img)
        draw.polygon([(128, 24), (24, 220), (232, 220)], fill=(240, 230, 40))
        img.save(fixture, format="PNG")
        with httpx.Client(timeout=60.0) as client:
            uploaded = client.post(
                f"{API}/api/projects/{PROJECT_ID}/assets",
                files={"file": (fixture.name, fixture.read_bytes(), "image/png")},
                data={"tag": "vision-smoke-upload", "kind": "image"},
            )
            if uploaded.status_code >= 300:
                return _fail(f"direct upload failed: {uploaded.status_code} {uploaded.text[:200]}")
            asset_id = (uploaded.json() or {}).get("id") or (uploaded.json() or {}).get("assetId")
        if not asset_id:
            return _fail("direct upload returned no asset id")
        upload_q = "Describe the hairstyle, visible clothing, pose, and distinctive visual details in this image."
        upload_reply, upload_trace, _ = _stream(
            {
                "messages": [{"role": "user", "content": upload_q}],
                "project_id": PROJECT_ID,
                "attachment_ids": [asset_id],
                "model": "qwen3.6:35b-a3b",
                "mode": "chat",
                "request_id": f"vision-smoke-upload-{uuid.uuid4().hex[:8]}",
            }
        )
        if not upload_trace.get("hasImages") and not upload_trace.get("imageCount"):
            return _fail("direct upload stream missing vision_trace images")
        if not any(token in _norm(upload_reply) for token in ("triangle", "yellow", "magenta", "purple", "pink")):
            return _fail(f"direct upload reply was not grounded: {upload_reply[:300]}")

        switch_error = None
        try:
            _stream(
                {
                    "messages": [
                        {
                            "role": "user",
                            "content": "Describe the visible clothing and markings from her current reference.",
                        }
                    ],
                    "project_id": PROJECT_ID,
                    "character_id": ANADRIYA_ID,
                    "characterId": ANADRIYA_ID,
                    "model": "qwen3.6:35b-a3b",
                    "mode": "chat",
                    "request_id": f"vision-smoke-switch-{uuid.uuid4().hex[:8]}",
                }
            )
        except RuntimeError as exc:
            switch_error = str(exc)
        if not switch_error or "VISION_UNAVAILABLE" not in switch_error:
            return _fail(
                "Anadriya visual turn did not block stale Korri vision "
                f"(expected VISION_UNAVAILABLE); got {switch_error!r}"
            )

        report = {
            "verdict": "PASS — CODIRECTOR FULL-STACK VISION SMOKE",
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "model": "qwen3.6:35b-a3b",
            "korri": {
                "assetId": visual.asset_id,
                "source": visual.source,
                "jpegWidth": loaded.width,
                "jpegHeight": loaded.height,
                "mime": loaded.mime,
                "visionTrace": {
                    k: trace.get(k)
                    for k in (
                        "assetIds",
                        "imageCount",
                        "dimensions",
                        "firstImageLength",
                        "hasImages",
                        "modelId",
                        "mimeType",
                        "numCtx",
                    )
                },
                "imageOnlyCandidates": image_only,
                "imageOnlyHits": hits,
                "replyExcerpt": reply[:1200],
            },
            "leakCorpusChars": len(leak),
            "textOnlyBlockedByCoDirector": text_blocked,
            "textOnlyHits": text_hits,
            "directUpload": {
                "assetId": asset_id,
                "visionTrace": {
                    k: upload_trace.get(k)
                    for k in ("assetIds", "imageCount", "hasImages", "firstImageLength")
                },
                "replyExcerpt": upload_reply[:600],
            },
            "characterSwitch": {"anadriyaBlocked": True},
        }
        (EVIDENCE / "codirector-vision-smoke.json").write_text(
            json.dumps(report, indent=2), encoding="utf-8"
        )
        print("PASS — CODIRECTOR FULL-STACK VISION SMOKE")
        print(json.dumps(report["korri"]["visionTrace"], indent=2))
        print("image-only hits:", hits)
        return 0
    except Exception as exc:  # noqa: BLE001
        return _fail(str(exc))
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
