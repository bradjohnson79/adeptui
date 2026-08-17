"""Prompt knowledgebase loader + compile-prompt pipeline.

KB root: studio-api/knowledgebase/generation/
Intention → Structured Spec → capability check → retrieve relevant markdown →
model-specific compiler → Generation Package (with citations + knowledge version).

Precedence: user instruction > shot overrides > master sheet > spatial >
script/storyboard > project rules > profiles > model KB > shared > defaults
"""
from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from .db import Project, Scene, get_db

router = APIRouter(tags=["knowledgebase"])

KB_ROOT = Path(__file__).resolve().parent.parent / "knowledgebase" / "generation"
PRODUCTION_KB_ROOT = Path(__file__).resolve().parent.parent / "knowledgebase" / "production"
KNOWLEDGE_VERSION = "2026.07.23-foundation"


def _read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except Exception:
        return ""


def _model_dirs() -> list[Path]:
    root = KB_ROOT / "video_models"
    if not root.exists():
        return []
    return [p for p in root.iterdir() if p.is_dir()]


@router.get("/knowledgebase/generation/models")
def list_models():
    models = []
    for d in _model_dirs():
        mf = d / "model.json"
        if mf.exists():
            try:
                data = json.loads(mf.read_text(encoding="utf-8"))
                models.append(data)
                continue
            except Exception:
                pass
        models.append({"id": d.name, "label": d.name, "path": str(d.relative_to(KB_ROOT))})
    return models


@router.get("/knowledgebase/generation/models/{model_id}")
def get_model(model_id: str):
    mf = KB_ROOT / "video_models" / model_id / "model.json"
    if not mf.exists():
        raise HTTPException(404, "Model not found")
    return json.loads(mf.read_text(encoding="utf-8"))


@router.get("/knowledgebase/generation/doc")
def get_doc(path: str):
    # Prevent path escape
    target = (KB_ROOT / path).resolve()
    if not str(target).startswith(str(KB_ROOT.resolve())):
        raise HTTPException(400, "Invalid path")
    if not target.exists() or not target.is_file():
        raise HTTPException(404, "Doc not found")
    return {"path": path, "content": target.read_text(encoding="utf-8")}


class CompileBody(BaseModel):
    intention: str
    model_id: str = "ltx_2_5_distilled"
    mode: str = "creative"  # creative | structured | model | advanced
    project_id: Optional[str] = None
    scene_id: Optional[str] = None
    task: Optional[str] = None
    shot_overrides: dict[str, str] = Field(default_factory=dict)
    projectContext: dict[str, Any] = Field(default_factory=dict)


def _retrieve(model_id: str, mode: str, task: str | None) -> list[tuple[str, str]]:
    """Retrieve a small set of relevant markdown docs — not the entire library."""
    cites: list[tuple[str, str]] = []
    shared = KB_ROOT / "shared"
    picks = ["cinematic_language.md", "negative_prompting.md", "prompt_validation.md"]
    if "camera" in (task or "") or mode in ("structured", "model"):
        picks.append("camera_language.md")
    if "motion" in (task or mode):
        picks.append("motion_prompting.md")
    if "spatial" in (task or ""):
        picks.append("spatial_prompting.md")
    if "character" in (task or "") or "consistency" in (task or ""):
        picks.append("character_consistency.md")
    for name in picks[:5]:
        p = shared / name
        if p.exists():
            cites.append((f"shared/{name}", _read(p)[:1800]))

    vm = KB_ROOT / "video_models" / model_id
    for name in ("overview.md", "prompt_language.md", "negative_prompts.md"):
        p = vm / name
        if p.exists():
            cites.append((f"video_models/{model_id}/{name}", _read(p)[:2000]))
    if model_id.startswith("ltx") and (vm / "ingredients_workflow.md").exists():
        cites.append(
            (
                f"video_models/{model_id}/ingredients_workflow.md",
                _read(vm / "ingredients_workflow.md")[:2200],
            )
        )
    if task:
        wf = KB_ROOT / "workflows" / f"{task}.md"
        if wf.exists():
            cites.append((f"workflows/{task}.md", _read(wf)[:1500]))
    # Avatar Studio knowledge
    if task and ("avatar" in task or "talking" in task or "lip" in task):
        av = KB_ROOT / "avatar"
        for name in ("overview.md", "talking_portrait.md", "lip_sync.md", "mouth_masking.md", "failure_modes.md"):
            p = av / name
            if p.exists():
                cites.append((f"avatar/{name}", _read(p)[:1800]))
    # Production / Editor knowledge
    if task and any(k in task for k in ("editor", "assemble", "mix", "edit", "pacing", "continuity", "export")):
        prod_picks = [
            ("editing", "overview.md"),
            ("pacing", "overview.md"),
            ("continuity", "overview.md"),
            ("sound_design", "overview.md"),
            ("dialogue_editing", "overview.md"),
            ("final_export", "overview.md"),
        ]
        if "mix" in task or "sound" in task or "audio" in task:
            prod_picks = [("sound_design", "overview.md"), ("dialogue_editing", "overview.md")] + prod_picks
        if "assemble" in task or "editor" in task:
            prod_picks = [("editing", "overview.md"), ("pacing", "overview.md")] + prod_picks
        seen: set[str] = set()
        for folder, name in prod_picks:
            key = f"{folder}/{name}"
            if key in seen:
                continue
            seen.add(key)
            p = PRODUCTION_KB_ROOT / folder / name
            if p.exists():
                cites.append((f"production/{key}", _read(p)[:1800]))
            if len(seen) >= 4:
                break
    return cites


def _compile_prompt(
    intention: str,
    model_id: str,
    mode: str,
    master: dict[str, Any] | None,
    scene: Scene | None,
    overrides: dict[str, str],
    cites: list[tuple[str, str]],
) -> dict[str, Any]:
    explain: list[str] = []
    explain.append(f"Mode={mode}; model={model_id}; knowledge={KNOWLEDGE_VERSION}")
    explain.append("Precedence: user > shot overrides > master sheet > scene > model KB > shared")

    parts: list[str] = []
    # user intention highest
    if intention.strip():
        parts.append(intention.strip())
        explain.append("Applied user intention")
    for k, v in overrides.items():
        if v:
            parts.append(f"{k}: {v}")
            explain.append(f"Shot override: {k}")

    if master:
        explain.append("Merged Master Sheet ingredients")
        ings = master.get("ingredients") or []
        for kind in ("action", "character", "environment", "lighting", "camera", "style"):
            chunk = [
                (i.get("description") or i.get("label") or "")
                for i in ings
                if i.get("kind") == kind and i.get("priority") != "Exclude"
            ]
            chunk = [c for c in chunk if c]
            if chunk:
                parts.append(", ".join(chunk))
        if master.get("prompt") and mode in ("structured", "advanced", "model"):
            parts.append(master["prompt"])
            explain.append("Included master sheet prompt")

    if scene and scene.prompt and mode != "creative":
        parts.append(scene.prompt)
        explain.append("Included scene prompt")

    # Light model-specific shaping from KB snippets
    kb_text = "\n".join(t for _, t in cites)
    if model_id.startswith("ltx"):
        explain.append("LTX: prefer concrete final-scene language; ingredients are visual material, not collage")
        if "ingredients" in kb_text.lower():
            explain.append("Cited LTX ingredients_workflow")
    elif model_id.startswith("wan"):
        explain.append("WAN: emphasize motion clarity and temporal consistency")
    elif model_id in ("seedance", "kling", "veo", "runway"):
        explain.append("fal cloud model: keep prompts concise; respect API duration limits")

    prompt = ". ".join(dict.fromkeys(p.strip().rstrip(".") for p in parts if p.strip()))
    # Strip collage language
    banned = re.compile(
        r"\b(collage|mood board|reference sheet|character sheet|contact sheet|grid layout|multi-panel|white background)\b",
        re.I,
    )
    if banned.search(prompt):
        prompt = banned.sub("", prompt)
        explain.append("Stripped collage/mood-board language from prompt")

    neg_bits = [
        "collage",
        "mood board",
        "reference sheet",
        "grid layout",
        "white background",
        "identity drift",
        "blurry",
        "low quality",
        "watermark",
    ]
    if master and master.get("negative_prompt"):
        neg = master["negative_prompt"]
    else:
        neg = ", ".join(neg_bits)

    issues: list[str] = []
    if len(prompt) < 12:
        issues.append("Prompt too short")
    if banned.search(prompt):
        issues.append("Collage language still present")
    if not cites:
        issues.append("No KB docs retrieved — check knowledgebase path")

    return {
        "version": "v1",
        "model_id": model_id,
        "mode": mode,
        "prompt": re.sub(r"\s+", " ", prompt).strip(),
        "negative_prompt": neg,
        "citations": [{"path": p, "title": Path(p).stem} for p, _ in cites],
        "knowledge_version": KNOWLEDGE_VERSION,
        "validation": {"ok": len(issues) == 0, "issues": issues},
        "explain": explain,
        "created_at": datetime.utcnow().isoformat() + "Z",
    }


@router.post("/codirector/compile-prompt")
def compile_prompt(body: CompileBody, db: Session = Depends(get_db)):
    master = None
    scene = None
    if body.project_id and body.scene_id:
        try:
            from .master_sheet import get_master_sheet

            master = get_master_sheet(body.project_id, body.scene_id, db)
        except Exception:
            master = None
        scene = db.get(Scene, body.scene_id)
    task = body.task
    if not task and body.intention:
        low = body.intention.lower()
        if any(k in low for k in ("avatar", "talking", "lip sync", "mouth mask", "presenter")):
            task = "avatar"
        elif any(k in low for k in ("assemble", "editor", "rough cut", "stitch")):
            task = "editor"
        elif any(k in low for k in ("mix", "foley", "ambience", "sfx")):
            task = "mix"
    cites = _retrieve(body.model_id, body.mode, task)
    pkg = _compile_prompt(
        body.intention,
        body.model_id,
        body.mode,
        master,
        scene,
        body.shot_overrides,
        cites,
    )
    pkg["spec"] = {
        "intention": body.intention,
        "mode": body.mode,
        "model_id": body.model_id,
        "task": task,
        "sources": [{"kind": "user_intention"}, *([{"kind": "master_sheet"}] if master else [])],
    }
    ctx = dict(body.projectContext or {})
    if ctx:
        policy = str(ctx.get("promptLanguagePolicy") or "auto")
        source = str(ctx.get("sourceLanguage") or "")
        canonical = str(ctx.get("projectPrimaryLocale") or "")
        pkg["promptLanguagePolicy"] = policy
        pkg["sourceLanguage"] = source
        pkg["projectPrimaryLocale"] = canonical
        notes = pkg.setdefault("explain", [])
        notes.append(f"Prompt language policy: {policy}")
        if policy == "bilingual":
            notes.append("Bilingual English-first + Simplified Chinese")
        elif policy == "english":
            notes.append("Prompt language forced to English")
        elif policy == "project_canonical" and canonical:
            notes.append(f"Prompt language uses project canonical locale {canonical}")
        elif source:
            notes.append(f"Source language: {source}")
    return pkg
