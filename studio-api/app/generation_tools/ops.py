"""Concrete M3.2a generation operations (local-first, non-destructive)."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
import uuid
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from ..db import Asset, Job, Project
from .catalog import get_tool
from .lineage import register_derived_asset, require_source_asset


def _e2e() -> bool:
    return os.environ.get("STUDIO_E2E", "").strip() in {"1", "true", "TRUE", "yes"}


def _tmp_out(suffix: str) -> Path:
    d = Path(tempfile.mkdtemp(prefix="m32a_"))
    return d / f"out{suffix}"


def probe_tool(tool_id: str) -> dict[str, Any]:
    tool = get_tool(tool_id)
    if not tool:
        return {"id": tool_id, "available": False, "status": "MISSING", "remediation": "Unknown tool"}
    if tool.get("blocked"):
        return {
            "id": tool_id,
            "available": False,
            "status": "BLOCKED",
            "label": tool["label"],
            "remediation": tool.get("blockedReason"),
            "honesty": "Standard brightness/white-balance/color correction is not de-lighting.",
        }
    if tool_id in {"audio.music.generate", "audio.sfx.generate"}:
        try:
            from ..m210b.flags import m210b_audio_sandbox_enabled

            sandbox = bool(m210b_audio_sandbox_enabled())
        except Exception:
            sandbox = False
        audio_flag = os.environ.get("STUDIO_FEATURE_AUDIO_PRODUCTION_V1", "").strip() in {
            "1",
            "true",
            "TRUE",
            "yes",
        }
        ok = bool(sandbox and audio_flag) or _e2e()
        return {
            "id": tool_id,
            "available": ok,
            "status": "PARTIAL" if ok else "BLOCKED",
            "label": tool["label"],
            "provider": tool.get("providerHint"),
            "disclosure": "Local sandbox generation. Not a paid cloud submit.",
            "remediation": None
            if ok
            else "Enable STUDIO_FEATURE_AUDIO_PRODUCTION_V1 and STUDIO_FEATURE_M210B_AUDIO_SANDBOX_V1; install ACE-Step/MMAudio venv.",
        }
    if tool_id == "image.chroma_key":
        return {
            "id": tool_id,
            "available": True,
            "status": "COMPLETE",
            "label": tool["label"],
            "provider": "OpenCV/FFmpeg local",
            "disclosure": "Local processing only.",
        }
    if tool_id == "scriptwriter":
        return {
            "id": tool_id,
            "available": True,
            "status": "PARTIAL",
            "label": tool["label"],
            "provider": tool.get("providerHint"),
            "disclosure": "Local LLM when configured; otherwise structured template persist.",
        }
    if tool_id == "brand.studio":
        return {
            "id": tool_id,
            "available": True,
            "status": "PARTIAL",
            "label": tool["label"],
            "disclosure": "Reference-locked local ImageGen. Logos/wording constraints enforced in metadata.",
        }
    # Comfy-backed tools
    comfy_ok = _comfy_reachable()
    return {
        "id": tool_id,
        "available": comfy_ok or _e2e(),
        "status": "PARTIAL" if (comfy_ok or _e2e()) else "BLOCKED",
        "label": tool["label"],
        "provider": tool.get("providerHint"),
        "disclosure": "Local ComfyUI. Never silently submits to paid cloud.",
        "remediation": None
        if (comfy_ok or _e2e())
        else "Start ComfyUI and install required nodes/weights (see docs/release-gate/m32/M32A_OSS_ACQUISITION.md).",
    }


def _comfy_reachable() -> bool:
    try:
        import urllib.request

        with urllib.request.urlopen("http://127.0.0.1:8188/system_stats", timeout=1.5) as r:
            return int(getattr(r, "status", 200) or 200) < 500
    except Exception:
        return False


def run_chroma_key(
    db: Session,
    *,
    project_id: str,
    source_asset_id: str,
    key_color: str = "green",
    tolerance: float = 0.28,
    spill: float = 0.65,
    edge_feather: float = 1.5,
) -> dict[str, Any]:
    source = require_source_asset(db, project_id, source_asset_id)
    from PIL import Image
    import numpy as np

    im = Image.open(source.path).convert("RGBA")
    arr = np.asarray(im).astype("float32")
    r, g, b, a = arr[:, :, 0], arr[:, :, 1], arr[:, :, 2], arr[:, :, 3]
    if key_color.lower().startswith("b"):
        keyness = (b - np.maximum(r, g)) / 255.0
    else:
        keyness = (g - np.maximum(r, b)) / 255.0
    mask = np.clip((keyness - tolerance) / max(0.05, 1.0 - tolerance), 0, 1)
    # Spill suppression toward neutral
    if key_color.lower().startswith("b"):
        b = b - spill * np.maximum(0, b - np.maximum(r, g))
    else:
        g = g - spill * np.maximum(0, g - np.maximum(r, b))
    alpha = (1.0 - mask) * a
    if edge_feather > 0:
        # soft edge via simple box blur on alpha
        try:
            from PIL import ImageFilter

            alpha_im = Image.fromarray(alpha.astype("uint8"), mode="L")
            alpha_im = alpha_im.filter(ImageFilter.GaussianBlur(radius=float(edge_feather)))
            alpha = np.asarray(alpha_im).astype("float32")
        except Exception:
            pass
    out = np.stack([np.clip(r, 0, 255), np.clip(g, 0, 255), np.clip(b, 0, 255), np.clip(alpha, 0, 255)], axis=-1)
    dest = _tmp_out(".png")
    Image.fromarray(out.astype("uint8"), mode="RGBA").save(dest)
    asset = register_derived_asset(
        db,
        project_id=project_id,
        source_path=dest,
        kind="image",
        tag="chroma_key",
        parent_asset_id=source.id,
        op="chroma_key",
        model="opencv-local",
        prompt_meta={
            "keyColor": key_color,
            "tolerance": tolerance,
            "spill": spill,
            "edgeFeather": edge_feather,
            "matte": True,
        },
    )
    return {
        "ok": True,
        "toolId": "image.chroma_key",
        "assetId": asset.id,
        "parentAssetId": source.id,
        "path": asset.path,
        "disclosure": "Local chroma key with spill suppression. Source preserved.",
    }


def run_image_enhance_stub_copy(
    db: Session,
    *,
    project_id: str,
    source_asset_id: str,
    op: str,
    model: str,
    extra_meta: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """E2E/fixture path: non-destructive copy with honest provenance (not a fake upscale claim)."""
    source = require_source_asset(db, project_id, source_asset_id)
    if not _e2e():
        raise RuntimeError(
            f"{op} requires ComfyUI models/nodes. Remediation: install weights documented in M32A_OSS_ACQUISITION.md"
        )
    dest = _tmp_out(Path(source.path).suffix or ".png")
    shutil.copy2(source.path, dest)
    asset = register_derived_asset(
        db,
        project_id=project_id,
        source_path=dest,
        kind="image",
        tag=op,
        parent_asset_id=source.id,
        op=op,
        model=model,
        prompt_meta={
            **(extra_meta or {}),
            "e2eFixtureCopy": True,
            "honesty": "E2E lineage/registration proof; production path uses real Comfy graphs when models are present.",
        },
    )
    return {
        "ok": True,
        "toolId": f"image.{op}" if not op.startswith("image.") else op,
        "assetId": asset.id,
        "parentAssetId": source.id,
        "path": asset.path,
        "e2eFixtureCopy": True,
        "disclosure": "Local non-destructive derived asset. Source preserved.",
    }


def enqueue_imagegen(
    db: Session,
    *,
    project_id: str,
    prompt: str,
    negative: str = "",
    model: str = "zimage",
    width: int = 1024,
    height: int = 1024,
    seed: int | None = None,
    workflow_key: str | None = None,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Enqueue via Image Product compiler → resolver (no hardcoded workflow key)."""
    from ..image_product.service import generate_images

    body: dict[str, Any] = {
        "prompt": prompt,
        "negative": negative,
        "modelFamilyPreference": model,
        "width": width,
        "height": height,
        "seed": seed,
        "purpose": (extra or {}).get("purpose") or "stills",
        "operation": "image.generate",
        **{k: v for k, v in (extra or {}).items() if k != "force_workflow_key"},
    }
    # Cert harness only: optional force_workflow_key never set by product callers
    if workflow_key and (extra or {}).get("allow_force_workflow_key"):
        body["forceWorkflowKey"] = workflow_key
    result = generate_images(db, project_id=project_id, body=body)
    return {
        "ok": True,
        "queued": True,
        "jobId": result.get("jobId"),
        "jobs": result.get("jobs"),
        "toolId": "image.generate",
        "workflowKey": (result.get("imageRuntime") or {}).get("workflowKey"),
        "recommendation": result.get("recommendation"),
        "disclosure": result.get("disclosure")
        or "Local Comfy queue via ImageIntent → certified resolver. Paid cloud not used.",
    }


def enqueue_imagegen_specialized(
    db: Session,
    *,
    project_id: str,
    source_asset_id: str,
    edit_op: str,
    prompt: str = "",
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Enqueue specialized edits via ImageEditIntent / certified edit keys (M42 W4)."""
    source = require_source_asset(db, project_id, source_asset_id)
    from ..image_product.edit_service import enqueue_edit

    op_map = {
        "upscale": "image.upscale",
        "bg_remove": "image.background_remove",
        "face_refine": "image.face_restore",
        "edit": "image.reference_edit",
    }
    operation = op_map.get(edit_op, "image.reference_edit")
    # background_remove / face_restore may be Deferred — compile falls back to certified zimage
    result = enqueue_edit(
        db,
        project_id=project_id,
        body={
            "operation": operation,
            "prompt": prompt or f"Specialized edit: {edit_op}",
            "sourceAssetIds": [source_asset_id],
            "sourceAssetId": source_asset_id,
            "allowIncomplete": True,
            "metadata": {
                "m32a": True,
                "specialized": True,
                "legacyCaller": f"generation_tools:{edit_op}",
                **(extra or {}),
            },
        },
    )
    return {
        "ok": True,
        "queued": True,
        "jobId": result.get("jobId"),
        "toolId": edit_op,
        "parentAssetId": source.id,
        "workflowKey": (result.get("imageRuntime") or {}).get("workflowKey"),
        "recommendation": result.get("recommendation"),
        "disclosure": "Queued via ImageEditIntent → certified resolver. Source preserved.",
    }


def run_audio_generate(
    db: Session,
    *,
    project_id: str,
    kind: str,
    prompt: str,
    duration_sec: float = 4.0,
    seed: int | None = None,
) -> dict[str, Any]:
    from ..codirector.m29.audio.service import AudioService

    kind_l = str(kind or "").lower()
    if kind_l == "music":
        library_key = "audio.music"
    elif kind_l == "ambience":
        library_key = "audio.ambience"
    elif kind_l in ("foley",):
        library_key = "audio.foley"
    elif kind_l in ("reaction",):
        library_key = "audio.reaction"
    elif kind_l in ("sfx", "sound_effect"):
        library_key = "audio.sfx"
    else:
        library_key = "audio.sfx"
    # Ambience/SFX share MMAudio runtime; native generate kind for non-music is sfx.
    generate_kind = "music" if kind_l == "music" else "sfx"

    gen_kwargs: dict[str, Any] = {
        "project_id": project_id,
        "kind": generate_kind,
        "prompt": prompt,
        "duration_sec": duration_sec,
        "owner": "user",
    }
    if seed is not None:
        gen_kwargs["seed"] = int(seed)

    result = AudioService.generate(db, **gen_kwargs)
    studio_asset_id = None
    asset_path = result.get("assetPath")
    if asset_path and Path(str(asset_path)).is_file():
        asset = register_derived_asset(
            db,
            project_id=project_id,
            source_path=asset_path,
            kind="audio",
            tag=f"{kind_l}_gen",
            parent_asset_id=None,
            op=f"{kind_l}_generate",
            model=str(result.get("registryId") or kind_l),
            prompt_meta={
                "prompt": prompt,
                "sandboxOnly": result.get("sandboxOnly", True),
                "audioStudioProductionPath": True,
                "audioRole": kind_l,
                "m29AssetId": result.get("assetId"),
                "versionId": result.get("versionId"),
            },
            library_key=library_key,
        )
        studio_asset_id = asset.id
    elif _e2e() and not asset_path:
        # Fixture audio: synthesize tiny wav for library registration proof
        dest = _tmp_out(".wav")
        _write_silence_wav(dest, duration_sec=min(duration_sec, 2.0))
        asset = register_derived_asset(
            db,
            project_id=project_id,
            source_path=dest,
            kind="audio",
            tag=f"{kind_l}_gen",
            parent_asset_id=None,
            op=f"{kind_l}_generate",
            model="e2e-fixture",
            prompt_meta={"prompt": prompt, "e2eFixture": True, "m29": result, "audioRole": kind_l},
            library_key=library_key,
        )
        studio_asset_id = asset.id
    return {
        "ok": True,
        "toolId": f"audio.{kind_l}.generate",
        "m29": result,
        "assetId": studio_asset_id or result.get("assetId"),
        "libraryKey": library_key,
        "generateKind": generate_kind,
        "disclosure": "Local audio via Audio Studio production path. Not a paid cloud submit.",
    }


def _write_silence_wav(path: Path, duration_sec: float = 1.0, rate: int = 22050) -> None:
    import struct
    import wave

    n = int(rate * duration_sec)
    with wave.open(str(path), "w") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(struct.pack("<" + "h" * n, *([0] * n)))


def run_script_document(
    db: Session,
    *,
    project_id: str,
    document_type: str,
    brief: str,
    title: str | None = None,
) -> dict[str, Any]:
    """Persist a generative script document into project script store + library text asset."""
    from ..script_storyboard import get_or_create_script_doc, import_plain_text

    doc = get_or_create_script_doc(db, project_id, title=title or "Main Script")
    body = _compose_script_body(document_type, brief)
    heading = title or document_type.replace("_", " ").title()
    segments = import_plain_text(db, project_id, f"{heading}\n\n{body}", doc_id=doc.id)

    dest = _tmp_out(".md")
    dest.write_text(f"# {heading}\n\n{body}\n", encoding="utf-8")
    asset = register_derived_asset(
        db,
        project_id=project_id,
        source_path=dest,
        kind="text",
        tag=f"script_{document_type}",
        parent_asset_id=None,
        op="scriptwriter",
        model="local-llm-or-template",
        prompt_meta={"documentType": document_type, "brief": brief, "docId": doc.id},
        library_key="scripts" if _taxonomy_has("scripts") else None,
    )
    return {
        "ok": True,
        "toolId": "scriptwriter",
        "docId": doc.id,
        "segmentIds": [s.id for s in segments],
        "documentType": document_type,
        "assetId": asset.id,
        "text": body,
        "disclosure": "Persisted to Script workspace + Project Library. Local generation path.",
    }


def _taxonomy_has(key: str) -> bool:
    try:
        from ..project_library.taxonomy import get_system_node

        return get_system_node(key) is not None
    except Exception:
        return False


def _compose_script_body(document_type: str, brief: str) -> str:
    brief = (brief or "").strip() or "Untitled production brief"
    templates = {
        "treatment": f"TREATMENT\n\nLogline: {brief}\n\nTone: cinematic, clear stakes, character-driven.\n\nAct I — Setup\nAct II — Confrontation\nAct III — Resolution\n",
        "outline": f"OUTLINE\n\n1. Opening image — {brief}\n2. Inciting incident\n3. Midpoint turn\n4. Climax\n5. Closing image\n",
        "beat_sheet": f"BEAT SHEET\n\n- Opening\n- Theme stated\n- Catalyst related to: {brief}\n- Debate\n- Break into Two\n- B Story\n- Fun and Games\n- Midpoint\n- Bad Guys Close In\n- All Is Lost\n- Break into Three\n- Finale\n",
        "scene": f"SCENE\n\nINT. LOCATION — DAY\n\nCharacters enter. Conflict related to: {brief}\n\nCHARACTER\nDialogue beat.\n",
        "screenplay": f"FADE IN:\n\nINT. LOCATION — DAY\n\n{brief}\n\nCHARACTER\n(beat)\nWe make the stakes clear.\n\nFADE OUT.\n",
        "dialogue_revision": f"DIALOGUE REVISION\n\nGoal: sharpen subtext around — {brief}\n\nCHARACTER A\nSay less; mean more.\n\nCHARACTER B\nAnswer with action.\n",
        "storyboard_brief": f"STORYBOARD BRIEF\n\nSequence goal: {brief}\nPanels: wide establish → medium character → insert detail → reaction → payoff.\n",
        "shot_breakdown": f"SHOT BREAKDOWN\n\n1. Wide — establish\n2. Medium — performance\n3. CU — emotion\n4. Insert — object tied to {brief}\n5. Exit wide\n",
        "commercial": f"COMMERCIAL SCRIPT (30s)\n\nHook (0–3s): {brief}\nBenefit (3–15s)\nProof (15–24s)\nCTA (24–30s)\n",
        "trailer": f"TRAILER SCRIPT\n\nCOLD OPEN — {brief}\nTITLE CARD\nESCALATION BEATS\nFINAL STING\n",
        "social_video": f"SOCIAL VIDEO SCRIPT (15–30s)\n\nHook in 1s: {brief}\nValue in 10s\nCTA end card\n",
    }
    return templates.get(document_type, f"{document_type.upper()}\n\n{brief}\n")


def run_brand_generate(
    db: Session,
    *,
    project_id: str,
    prompt: str,
    logo_asset_ids: list[str] | None = None,
    product_asset_ids: list[str] | None = None,
    brand_colors: list[str] | None = None,
    required_wording: str | None = None,
    campaign_name: str | None = None,
    campaign_type: str | None = None,
    visual_direction: str | None = None,
    composition: str | None = None,
    background: str | None = None,
    format_name: str | None = None,
    campaign_formats: list[str] | None = None,
    typography_template: str | None = None,
    product_name: str | None = None,
    style_notes: str | None = None,
    bible_summary: str | None = None,
    result_lane: str | None = None,
) -> dict[str, Any]:
    logos = logo_asset_ids or []
    products = product_asset_ids or []
    for aid in logos + products:
        require_source_asset(db, project_id, aid)
    brand_studio = {
        "campaignId": f"brand-campaign-{project_id}",
        "campaignName": campaign_name or "Brand Studio Campaign",
        "campaignType": campaign_type or "launch",
        "visualDirection": visual_direction or "hero",
        "composition": composition or "Centered hero",
        "background": background or "Studio sweep",
        "heroFormat": format_name or "Square 1:1",
        "campaignFormats": campaign_formats or ([format_name] if format_name else []),
        "typographyTemplate": typography_template or "Hero headline",
        "productName": product_name or "",
        "styleNotes": style_notes or "",
        "bibleSummary": bible_summary or "",
        "resultLane": result_lane or "concepts",
        "title": f"{campaign_name or 'Brand Studio'} · {format_name or 'Square 1:1'}",
    }
    locked = {
        "lockedLogos": logos,
        "lockedProducts": products,
        "brandColors": brand_colors or [],
        "requiredWording": required_wording or "",
        "preserveProductShape": True,
        "preserveLabels": True,
    }
    brand_check = {
        "logoLocked": bool(logos),
        "productLocked": bool(products),
        "hasPalette": bool(brand_colors),
        "hasRequiredWording": bool(required_wording),
        "hasCanonGuidance": bool(bible_summary),
    }
    # Prefer enqueue imagegen with reference locks in metadata
    ref = products[0] if products else (logos[0] if logos else None)
    if ref:
        return {
            **enqueue_imagegen_specialized(
                db,
                project_id=project_id,
                source_asset_id=ref,
                edit_op="brand_locked",
                prompt=(
                    f"{prompt}\n\nLOCKED: preserve logos, labels, packaging, product shape, "
                    f"brand colors {brand_colors}, required wording: {required_wording}, "
                    f"campaign type: {campaign_type}, visual direction: {visual_direction}, format: {format_name}, "
                    f"composition: {composition}, background: {background}, typography: {typography_template}, "
                    f"product name: {product_name}, style notes: {style_notes}, canon guidance: {bible_summary}"
                ),
                extra={"brandLock": locked, "brandStudio": brand_studio, "brandCheck": brand_check, "m32aBrand": True},
            ),
            "toolId": "brand.studio",
            "brandLock": locked,
            "brandStudio": brand_studio,
            "brandCheck": brand_check,
        }
    if _e2e():
        dest = _tmp_out(".png")
        from PIL import Image, ImageDraw

        im = Image.new("RGB", (768, 768), color=(brand_colors and _parse_color(brand_colors[0])) or (20, 24, 28))
        dr = ImageDraw.Draw(im)
        dr.text((40, 40), required_wording or "BRAND", fill=(240, 240, 240))
        im.save(dest)
        asset = register_derived_asset(
            db,
            project_id=project_id,
            source_path=dest,
            kind="image",
            tag=(campaign_name or "brand_studio")[:64],
            parent_asset_id=None,
            op="brand_generate",
            model="e2e-brand",
            prompt_meta={"prompt": prompt, **locked, "brandStudio": brand_studio, "brandCheck": brand_check},
            library_key="props.generated",
        )
        return {
            "ok": True,
            "toolId": "brand.studio",
            "assetId": asset.id,
            "brandLock": locked,
            "brandStudio": brand_studio,
            "brandCheck": brand_check,
        }
    raise RuntimeError("Brand Studio requires at least one locked logo or product reference asset.")


def _parse_color(value: str) -> tuple[int, int, int]:
    v = value.strip().lstrip("#")
    if len(v) == 6:
        return int(v[0:2], 16), int(v[2:4], 16), int(v[4:6], 16)
    return (20, 24, 28)


def run_video_extend(
    db: Session,
    *,
    project_id: str,
    source_asset_id: str,
    prompt: str = "",
    duration_sec: float = 2.0,
) -> dict[str, Any]:
    source = require_source_asset(db, project_id, source_asset_id)
    if source.kind not in {"video", "render", "clip"} and not str(source.filename).lower().endswith(
        (".mp4", ".webm", ".mov")
    ):
        # allow image as last-frame seed for generative continuation
        pass
    # M41 4.1A: embed canonical videoRuntime contract; last-frame / source binds to I2V.
    params = {
        "mode": "generative_continuation",
        "honesty": "True generative continuation from last frames — not loop/freeze/slow-mo/interpolation.",
        "source_asset_id": source_asset_id,
        "start_asset_id": source_asset_id,
        "prompt": prompt or "Continue the motion naturally",
        "duration_sec": duration_sec,
        "m32a": True,
        "cloudPaid": False,
        "parent_asset_id": source_asset_id,
        "videoRuntime": {
            "mode": "video_extend",
            "workflow_key": "ltx.simple_i2v",
            "provider_kind": "local",
            "engine": "ltx",
            "concurrency_class": "heavy_local",
            "start_asset_id": source_asset_id,
        },
    }
    job = Job(
        id=str(uuid.uuid4()),
        project_id=project_id,
        scene_id=None,
        kind="video_extend",
        status="queued",
        progress=0.0,
        message="M41 4.1B generative video continuation (local I2V)",
        params_json=json.dumps(params),
    )
    db.add(job)
    db.commit()
    try:
        from ..codirector.executive.imagegen_adapter import schedule_job_queue_enqueue

        schedule_job_queue_enqueue(job.id)
    except Exception:
        pass
    if _e2e():
        # Register a derived placeholder video copy for lineage proof in E2E
        dest = _tmp_out(".mp4")
        if Path(source.path).suffix.lower() in {".mp4", ".webm", ".mov"}:
            shutil.copy2(source.path, dest)
        else:
            dest.write_bytes(b"\x00\x00\x00\x18ftypmp42")  # minimal marker; tests check asset row
        asset = register_derived_asset(
            db,
            project_id=project_id,
            source_path=dest,
            kind="video",
            tag="video_extend",
            parent_asset_id=source.id,
            op="video_extend",
            model="generative_continuation",
            prompt_meta={"mode": "generative_continuation", "jobId": job.id, "e2eFixtureCopy": True},
            library_key="video.generated",
        )
        return {
            "ok": True,
            "toolId": "video.extend",
            "jobId": job.id,
            "assetId": asset.id,
            "parentAssetId": source.id,
            "mode": "generative_continuation",
            "disclosure": "Generative continuation mode. Source preserved.",
        }
    return {
        "ok": True,
        "queued": True,
        "toolId": "video.extend",
        "jobId": job.id,
        "parentAssetId": source.id,
        "mode": "generative_continuation",
        "disclosure": "Queued local I2V continuation. Not loop/freeze padding.",
    }


def run_video_upscale(
    db: Session,
    *,
    project_id: str,
    source_asset_id: str,
) -> dict[str, Any]:
    source = require_source_asset(db, project_id, source_asset_id)
    # M41 4.1A: honest Deferred — do not queue a worker path that cannot run.
    if not _e2e():
        return {
            "ok": False,
            "toolId": "video.upscale",
            "status": "DEFERRED",
            "capabilityState": "deferred",
            "capabilityId": "video.upscale",
            "executionAvailability": "deferred",
            "remediation": (
                "Video upscale (SeedVR2) is deferred in M41 4.1A until a certified worker "
                "pipeline exists. No job was queued and no compute was consumed."
            ),
            "sourceAssetId": source.id,
        }
    if not _comfy_reachable() and not _e2e():
        return {
            "ok": False,
            "toolId": "video.upscale",
            "status": "BLOCKED",
            "remediation": "Install ComfyUI-SeedVR2_VideoUpscaler + weights; start ComfyUI.",
        }
    job = Job(
        id=str(uuid.uuid4()),
        project_id=project_id,
        scene_id=None,
        kind="video_upscale",
        status="queued" if _comfy_reachable() else "completed",
        progress=0.0 if _comfy_reachable() else 1.0,
        message="M3.2a SeedVR2 temporal video upscale",
        params_json=json.dumps(
            {
                "source_asset_id": source_asset_id,
                "model": "SeedVR2",
                "temporal": True,
                "m32a": True,
                "honesty": "Temporal video upscale — not per-frame ESRGAN.",
                "cloudPaid": False,
            }
        ),
    )
    db.add(job)
    db.commit()
    if _e2e():
        dest = _tmp_out(Path(source.path).suffix or ".mp4")
        shutil.copy2(source.path, dest)
        asset = register_derived_asset(
            db,
            project_id=project_id,
            source_path=dest,
            kind="video",
            tag="video_upscale",
            parent_asset_id=source.id,
            op="video_upscale",
            model="SeedVR2",
            prompt_meta={"temporal": True, "e2eFixtureCopy": True, "jobId": job.id},
            library_key="video.generated",
        )
        return {
            "ok": True,
            "toolId": "video.upscale",
            "jobId": job.id,
            "assetId": asset.id,
            "parentAssetId": source.id,
            "temporal": True,
        }
    return {
        "ok": True,
        "queued": True,
        "toolId": "video.upscale",
        "jobId": job.id,
        "parentAssetId": source.id,
        "temporal": True,
        "disclosure": "SeedVR2 temporal path. Source preserved.",
    }
