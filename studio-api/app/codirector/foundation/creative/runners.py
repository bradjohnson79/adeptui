"""Heuristic specialist runners for Co-Director foundation Phase 2."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from app.codirector.foundation.contracts import (
    ContinuityFlag,
    Recommendation,
    SpecialistRequest,
    SpecialistResult,
)

from .roster import is_known_specialist

try:
    from app.codirector.foundation.knowledge import query_knowledge, get_knowledge_pack
except Exception:  # pragma: no cover - Phase 1.5 may land in parallel.
    query_knowledge = None
    get_knowledge_pack = None


_SPECIALIST_FOCUS: dict[str, dict[str, Any]] = {
    "story_architect": {
        "summary": "Clarifies the dramatic spine and story movement.",
        "recommendation": "Center the next iteration on a clear turn, visible stakes, and one memorable reveal.",
        "finding": "The request benefits from a cleaner cause-and-effect beat progression.",
        "opportunity": "Sharpen the midpoint or ending beat so the audience feels purposeful momentum.",
        "question": "Which story beat needs to land hardest right now?",
    },
    "character_architect": {
        "summary": "Protects character wants, contradictions, and readable arcs.",
        "recommendation": "Anchor the revision in a specific want, fear, and behavioral tell for the lead character.",
        "finding": "Character choices will feel stronger when motivation is explicit in the scene design.",
        "opportunity": "Add one signature action or line choice that distinguishes the character immediately.",
        "question": "What should the audience understand about this character after the next pass?",
    },
    "world_builder": {
        "summary": "Ensures the environment supports story logic and creative identity.",
        "recommendation": "Tie locations, props, and rules of the world directly to the emotional purpose of the moment.",
        "finding": "The surrounding world can carry more narrative meaning instead of functioning as neutral backdrop.",
        "opportunity": "Promote one environmental detail into a recurring story signal.",
        "question": "Which piece of the world should feel most unmistakably yours?",
    },
    "cinematic_psychology": {
        "summary": "Tracks emotional effect, audience perception, and tension control.",
        "recommendation": "Choose a single audience feeling to steer and let pacing, framing, and reveal timing reinforce it.",
        "finding": "The moment will read more clearly if the emotional target is narrowed before execution choices multiply.",
        "opportunity": "Increase contrast between setup and payoff so the emotional shift feels earned.",
        "question": "What should the audience be feeling by the end of this beat?",
    },
    "cinematography_director": {
        "summary": "Translates intent into shot language, lensing, and coverage strategy.",
        "recommendation": "Commit to one dominant framing pattern so the camera language feels authored instead of reactive.",
        "finding": "Coverage decisions will stay cleaner if the visual objective is chosen before shot variety expands.",
        "opportunity": "Use one hero angle or lens choice as the visual anchor for the sequence.",
        "question": "Do you want this beat to feel intimate, observational, or kinetic?",
    },
    "lighting_director": {
        "summary": "Shapes mood, clarity, and visual hierarchy through lighting choices.",
        "recommendation": "Use lighting contrast to point the eye and reinforce the emotional shift in the scene.",
        "finding": "Lighting can carry more story load by separating subject focus from background information.",
        "opportunity": "Reserve one lighting cue for the emotional or narrative turn.",
        "question": "Should the mood feel inviting, unstable, or severe?",
    },
    "production_designer": {
        "summary": "Aligns physical detail, props, palette, and set language with the concept.",
        "recommendation": "Consolidate the visual world around a few deliberate design motifs rather than many loose details.",
        "finding": "Production design can strengthen authorship by making the world feel curated instead of generic.",
        "opportunity": "Select one prop, texture, or palette choice that instantly communicates context.",
        "question": "Which physical detail should the audience remember first?",
    },
    "editor": {
        "summary": "Optimizes sequence flow, emphasis, and viewer comprehension.",
        "recommendation": "Structure the material around a clear setup, emphasis point, and release so the pacing reads confidently.",
        "finding": "The sequence will land better if redundant beats are compressed before new complexity is added.",
        "opportunity": "Save time downstream by deciding where the cut or transition should do the storytelling work.",
        "question": "Where should the energy rise or drop in the next version?",
    },
    "sound_director": {
        "summary": "Uses dialogue, ambience, and sonic contrast to deepen the experience.",
        "recommendation": "Let one intentional sonic layer carry the scene identity instead of stacking many competing elements.",
        "finding": "Sound can clarify geography and emotion earlier than visuals alone in this request.",
        "opportunity": "Design a single memorable cue, texture, or silence beat to define the moment.",
        "question": "What should the audience hear first when the moment begins?",
    },
    "performance_director": {
        "summary": "Shapes delivery, subtext, and behavior into playable direction.",
        "recommendation": "Express the note as an action the performer can play rather than an abstract emotional adjective.",
        "finding": "Performance clarity will improve if the underlying intention is actionable and specific.",
        "opportunity": "Convert tone notes into verbs, tactics, or playable shifts between beats.",
        "question": "What does the performer need to try to get in this moment?",
    },
    "continuity_supervisor": {
        "summary": "Protects consistency across story logic, assets, and evolving revisions.",
        "recommendation": "Lock any must-match details now so later iterations do not quietly drift from the approved direction.",
        "finding": "This request introduces a real chance of continuity drift unless the core anchors are named explicitly.",
        "opportunity": "Turn continuity-sensitive details into a short checklist before asset generation or edit passes.",
        "question": "Which existing detail must not change in the next pass?",
    },
}


def _normalize_text(value: Any) -> str:
    return " ".join(str(value or "").strip().split())


def _normalize_intent(request: SpecialistRequest) -> str:
    return _normalize_text(request.intent).lower()


def _collect_context_strings(request: SpecialistRequest) -> list[str]:
    values: list[str] = []
    context = request.context
    if not context:
        return values
    for fact in getattr(context, "facts", []) or []:
        key = getattr(fact, "key", None)
        value = getattr(fact, "value", None)
        if key:
            values.append(str(key))
        if value is not None:
            values.append(str(value))
    return values


def _extract_pack_ids(payload: Any) -> list[str]:
    ids: list[str] = []

    def visit(node: Any) -> None:
        if node is None:
            return
        if isinstance(node, str):
            if node.startswith("pack") or node.startswith("kp_") or node.startswith("knowledge:"):
                ids.append(node)
            return
        if hasattr(node, "packId"):
            ids.append(str(getattr(node, "packId")))
        if isinstance(node, dict):
            for key in ("packId", "knowledgePackId", "id"):
                value = node.get(key)
                if isinstance(value, str) and (key != "id" or value.startswith(("pack", "kp_", "knowledge:"))):
                    ids.append(value)
            for key in ("packIds", "knowledgePackIds", "packs", "items", "results"):
                value = node.get(key)
                if isinstance(value, Iterable) and not isinstance(value, (str, bytes)):
                    for item in value:
                        visit(item)
            return
        if isinstance(node, Iterable) and not isinstance(node, (str, bytes)):
            for item in node:
                visit(item)

    visit(payload)
    seen: set[str] = set()
    ordered: list[str] = []
    for pack_id in ids:
        if pack_id and pack_id not in seen:
            seen.add(pack_id)
            ordered.append(pack_id)
    return ordered


def _consult_knowledge(request: SpecialistRequest) -> tuple[list[str], list[str]]:
    """Consult shared Knowledge Framework; return (packIds, principle snippets)."""

    refs = list(request.knowledgeRefs or [])
    principles: list[str] = []
    if query_knowledge is None:
        return refs, principles

    try:
        hits = query_knowledge(
            intent=request.userMessage or request.intent or request.specialistId,
            limit=4,
        )
    except Exception:
        return refs, principles

    for hit in hits or []:
        pack_id = getattr(hit, "packId", None)
        frame = getattr(hit, "frame", None)
        if pack_id:
            refs.append(str(pack_id))
        if frame is None:
            continue
        title = getattr(frame, "title", "") or ""
        for principle in list(getattr(frame, "principles", None) or [])[:2]:
            text = _normalize_text(principle)
            if text:
                principles.append(f"{title}: {text}" if title else text)
        for pattern in list(getattr(frame, "patterns", None) or [])[:1]:
            text = _normalize_text(pattern)
            if text:
                principles.append(f"Pattern — {text}")

    # Also hydrate explicitly requested packs.
    if get_knowledge_pack is not None:
        for pack_id in list(refs):
            try:
                pack = get_knowledge_pack(pack_id)
            except Exception:
                pack = None
            if not pack or not getattr(pack, "frames", None):
                continue
            frame = pack.frames[0]
            for principle in list(frame.principles or [])[:1]:
                text = _normalize_text(principle)
                if text:
                    principles.append(f"{pack.title}: {text}")

    seen_refs: set[str] = set()
    ordered_refs: list[str] = []
    for ref in refs:
        normalized = _normalize_text(ref)
        if normalized and normalized not in seen_refs:
            seen_refs.add(normalized)
            ordered_refs.append(normalized)

    seen_principles: set[str] = set()
    ordered_principles: list[str] = []
    for principle in principles:
        if principle and principle not in seen_principles:
            seen_principles.add(principle)
            ordered_principles.append(principle)
    return ordered_refs[:8], ordered_principles[:4]


def _message_signals(request: SpecialistRequest) -> dict[str, bool]:
    text = " ".join(
        [
            request.userMessage or "",
            request.creativeStage or "",
            request.creativeSubstate or "",
            _normalize_intent(request),
            *request.domainProfileIds,
            *_collect_context_strings(request),
        ]
    ).lower()
    return {
        "continuity": any(token in text for token in ("continuity", "match", "callback", "existing", "already approved")),
        "performance": any(token in text for token in ("dialogue", "voice", "actor", "performance", "subtext")),
        "visual": any(token in text for token in ("shot", "camera", "frame", "lighting", "palette", "visual")),
        "sound": any(token in text for token in ("sound", "music", "audio", "ambience")),
        "revision": any(token in text for token in ("revise", "change", "refine", "version", "update")),
        "complex": any(token in text for token in ("sequence", "multi", "series", "pipeline", "production")),
    }


def _build_flags(request: SpecialistRequest, specialist_id: str) -> list[ContinuityFlag]:
    text = " ".join([request.userMessage or "", _normalize_intent(request)]).lower()
    flags: list[ContinuityFlag] = []
    if specialist_id == "continuity_supervisor" or any(token in text for token in ("continuity", "match", "same", "existing")):
        flags.append(
            ContinuityFlag(
                flagId=f"{specialist_id}:continuity-anchor",
                severity="warning",
                summary="Existing approved details should be treated as continuity anchors before revising this beat.",
            )
        )
    if "final" in text and any(token in text for token in ("change", "revise", "replace")):
        flags.append(
            ContinuityFlag(
                flagId=f"{specialist_id}:late-change-risk",
                severity="info",
                summary="Late-stage changes may ripple into dependent assets or decisions.",
            )
        )
    return flags


def _build_risks(signals: dict[str, bool], specialist_id: str) -> list[str]:
    risks: list[str] = []
    if signals["revision"]:
        risks.append("Revision scope can expand unless the creator locks the exact note being addressed.")
    if signals["complex"]:
        risks.append("Multi-step execution may drift if the next deliverable is not chosen before exploration continues.")
    if specialist_id == "continuity_supervisor":
        risks.append("Approved canon can drift if recurring details are changed without a comparison pass.")
    if specialist_id in {"lighting_director", "cinematography_director", "production_designer"} and signals["visual"]:
        risks.append("Visual choices may compete unless one dominant look is treated as the anchor.")
    if specialist_id in {"sound_director", "performance_director"} and signals["sound"]:
        risks.append("Tone can become noisy if too many expressive layers change at once.")
    return risks[:3]


def _build_requirements(request: SpecialistRequest, specialist_id: str, signals: dict[str, bool]) -> list[str]:
    requirements = ["Confirm the single most important outcome for the next pass."]
    if request.domainProfileIds:
        requirements.append("Respect the active domain profile conventions already chosen for this project.")
    if signals["continuity"] or specialist_id == "continuity_supervisor":
        requirements.append("Reference approved details or prior outputs before changing anything that should match.")
    if signals["visual"] and specialist_id in {"cinematography_director", "lighting_director", "production_designer"}:
        requirements.append("Choose one visual anchor before adding secondary style flourishes.")
    if signals["sound"] and specialist_id == "sound_director":
        requirements.append("Decide whether dialogue, ambience, or music should lead the moment.")
    return requirements[:3]


def _build_blockers(request: SpecialistRequest, specialist_id: str, signals: dict[str, bool]) -> list[str]:
    blockers: list[str] = []
    if specialist_id == "continuity_supervisor" and signals["continuity"] and not request.context:
        blockers.append("Continuity-sensitive request is missing project context or approved reference details.")
    if signals["complex"] and not request.creativeStage:
        blockers.append("Creative stage is unspecified, making sequencing advice less reliable.")
    return blockers[:2]


def _build_result(request: SpecialistRequest, specialist_id: str) -> SpecialistResult:
    blueprint = _SPECIALIST_FOCUS[specialist_id]
    signals = _message_signals(request)
    message = _normalize_text(request.userMessage)
    knowledge_refs, knowledge_principles = _consult_knowledge(request)

    findings = [blueprint["finding"]]
    opportunities = [blueprint["opportunity"]]
    # Apply shared craft doctrine — do not invent a second private copy of structures/theory.
    for principle in knowledge_principles:
        findings.append(f"From shared creative knowledge — {principle}")
    if signals["revision"]:
        findings.append("The request is revision-oriented, so preserving the strongest existing choice matters as much as adding novelty.")
    if request.domainProfileIds:
        opportunities.append(f"Use the active profile(s) {', '.join(request.domainProfileIds[:2])} to narrow the next choice set.")

    questions: list[str] = []
    if not request.metadata.get("questionAnswered"):
        questions.append(blueprint["question"])

    recommendation_text = blueprint["recommendation"]
    if knowledge_principles:
        recommendation_text = (
            f"{blueprint['recommendation']} Ground this in: {knowledge_principles[0]}"
        )

    recommendations = [
        Recommendation(
            text=recommendation_text,
            priority="high" if specialist_id in {"story_architect", "continuity_supervisor"} else "medium",
            knowledgeRefs=knowledge_refs,
        )
    ]
    if signals["complex"]:
        recommendations.append(
            Recommendation(
                text="Reduce the next action to one reviewable deliverable before branching into multiple downstream tasks.",
                priority="medium",
                knowledgeRefs=knowledge_refs,
            )
        )

    evidence_refs = list(knowledge_refs)
    if message:
        evidence_refs.append("user_message")
    if request.context:
        evidence_refs.append("context_package")

    summary = blueprint["summary"]
    if message:
        summary = f"{summary} Request focus: {message[:120]}"
    if knowledge_refs:
        summary = f"{summary} Knowledge: {', '.join(knowledge_refs[:3])}."

    return SpecialistResult(
        specialistId=specialist_id,
        summary=summary,
        recommendation=recommendation_text,
        findings=findings[:6],
        opportunities=opportunities[:2],
        questions=questions[:1],
        continuityFlags=_build_flags(request, specialist_id),
        recommendations=recommendations,
        evidenceRefs=evidence_refs,
        knowledgeRefs=knowledge_refs,
        requirements=_build_requirements(request, specialist_id, signals),
        risks=_build_risks(signals, specialist_id),
        blockingIssues=_build_blockers(request, specialist_id, signals),
        optionalImprovements=opportunities[:2],
        assumptions=[
            "The creator wants foundation-level guidance, not direct execution.",
            "Any approved canon or locked project choices should remain the source of truth.",
            "Craft doctrine comes from the shared Creative Knowledge Framework.",
        ],
        confidence=0.76 if not _build_blockers(request, specialist_id, signals) else 0.62,
        status="validated",
    )


def run_specialist(request: SpecialistRequest) -> SpecialistResult:
    """Run a lightweight heuristic specialist without calling the creator directly."""

    specialist_id = _normalize_text(request.specialistId)
    if not is_known_specialist(specialist_id) or specialist_id == "creative_director":
        return SpecialistResult(
            specialistId=specialist_id or "unknown",
            summary="Requested specialist is unavailable in the Phase 2 heuristic roster.",
            recommendation="Route the request to a supported specialist id before continuing.",
            findings=["The specialist id is not part of the frozen foundation creative roster."],
            blockingIssues=["Unsupported specialist id."],
            knowledgeRefs=list(request.knowledgeRefs or []),
            confidence=0.0,
            status="failed",
        )
    return _build_result(request, specialist_id)


__all__ = ["run_specialist"]
