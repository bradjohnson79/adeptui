"""Layer B — director scene breakdown. User request is source intent, not prompt copy.

Universal mapping: verified references + `SceneUnderstanding` (LLM or
deterministic) → `DirectorSceneIntent`. No franchise patterns. ACTION is
synthesized from ordered beats, dialogue, and reveal gating — never copied
from the creator's raw instruction.
"""

from __future__ import annotations

import re

from .canonical_tags import prompt_facing_tag, prefix_for_asset_type
from .contracts import (
    CameraPlan,
    DialogueLine,
    DirectorSceneIntent,
    ResolvedReference,
    RevealConstraint,
    SceneBeat,
    SceneIntentEnvironment,
    SceneIntentSubject,
    SceneProductionSpec,
    TimedBeat,
)
from .instruction_copy import strip_instruction_copy
from .scene_understanding import (
    LlmFn,
    SceneUnderstanding,
    extract_scene_understanding,
)


def _found(references: list[ResolvedReference], asset_type: str) -> list[ResolvedReference]:
    return [
        item
        for item in references
        if item.status == "found" and (item.asset_type or item.expected_type) == asset_type
    ]


def _norm(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", (value or "").lower())


def _scale_for(name: str, spec: SceneProductionSpec) -> str:
    for rel in spec.scale_relationships:
        if name and name.lower() in (rel.subject_a or "").lower():
            return rel.subject_a_length
        if name and name.lower() in (rel.subject_b or "").lower():
            return rel.subject_b_length
        if name and any(part in (rel.subject_a or "").lower() for part in name.lower().split() if len(part) > 3):
            return rel.subject_a_length
        if name and any(part in (rel.subject_b or "").lower() for part in name.lower().split() if len(part) > 3):
            return rel.subject_b_length
    return ""


def _subject_from_ref(ref: ResolvedReference, spec: SceneProductionSpec, role: str) -> SceneIntentSubject:
    tag = prompt_facing_tag(
        prefix_for_asset_type(ref.asset_type or ref.expected_type),
        ref.canonical_tag or ref.identity_tag,
        ref.display_name or ref.query,
    )
    return SceneIntentSubject(
        name=ref.display_name or ref.query,
        tag=tag,
        role=role,
        verified=ref.status == "found" and ref.verification in {"found", "global_found"},
        verification=ref.verification if ref.verification != "missing" else ("global_found" if ref.is_global else "found"),
        scale=_scale_for(ref.display_name or ref.query, spec),
        asset_type=ref.asset_type or ref.expected_type,
        is_global=ref.is_global,
    )


def _assign_subjects(
    spec: SceneProductionSpec,
    props: list[ResolvedReference],
    chars: list[ResolvedReference],
) -> list[SceneIntentSubject]:
    """Generic roles — no vessel/vehicle assumptions."""
    subjects: list[SceneIntentSubject] = []
    for index, char in enumerate(chars):
        role = "lead character" if index == 0 else "supporting character"
        subjects.append(_subject_from_ref(char, spec, role))
    for index, prop in enumerate(props):
        role = "primary subject" if not chars and index == 0 else ("key prop" if index == 0 else "supporting prop")
        subjects.append(_subject_from_ref(prop, spec, role))
    return subjects


def _match_subject(name: str, subjects: list[SceneIntentSubject]) -> SceneIntentSubject | None:
    token = _norm(name)
    if not token:
        return None
    for subject in subjects:
        if _norm(subject.name) == token:
            return subject
    for subject in subjects:
        candidate = _norm(subject.name)
        if token and (token in candidate or candidate in token):
            return subject
    parts = [part for part in re.findall(r"[a-z0-9]+", name.lower()) if len(part) > 3]
    for subject in subjects:
        blob = subject.name.lower()
        if parts and all(part in blob for part in parts):
            return subject
    return None


def _match_environment(name: str, environment: SceneIntentEnvironment) -> None:
    if environment.name or not name:
        return
    environment.name = name.strip()


def _beat_index_for_event(beats: list[SceneBeat], event_language: str) -> int | None:
    """Locate the beat that realizes a reveal-gate event ('the laser blast')."""
    words = [w for w in re.findall(r"[a-z]+", (event_language or "").lower()) if len(w) > 3]
    if not words:
        return None
    best: tuple[int, int] | None = None
    for beat in beats:
        blob = beat.description.lower()
        hits = sum(1 for w in words if w in blob)
        if hits and (best is None or hits > best[1]):
            best = (beat.index, hits)
    if best is not None and best[1] >= max(1, len(words) // 2):
        return best[0]
    return None


def _dialogue_beat_index(
    beats: list[SceneBeat],
    speaker: str,
    after_beat: int | None,
    line: str = "",
    source_text: str = "",
) -> int | None:
    if after_beat is not None and 0 <= after_beat < len(beats):
        return after_beat
    # Position-based placement: the line lands after the last beat whose
    # source sentence precedes the dialogue line in the original request.
    if line and source_text:
        line_pos = source_text.find(line.strip())
        if line_pos >= 0:
            placed: int | None = None
            for beat in beats:
                anchor = (beat.description or "")[:40].strip()
                if not anchor:
                    continue
                pos = source_text.find(anchor)
                if 0 <= pos < line_pos:
                    placed = beat.index
            if placed is not None:
                return placed
    token = _norm(speaker)
    for beat in beats:
        if re.search(r"\b(?:says|said|asks|whispers|speaks|lines?)\b", beat.description, re.I):
            return beat.index
    speaker_beats = [b.index for b in beats if token and token in _norm(b.description)]
    if speaker_beats:
        return speaker_beats[-1]
    for beat in reversed(beats):
        if beat.kind in {"approach", "reveal", "action", "hold"}:
            return beat.index
    return beats[-1].index if beats else None


def _strip_gate_clause(
    sentence: str,
    reveal_subjects: set[str],
    not_visible_re: re.Pattern[str],
) -> str:
    """Remove visibility-gate clauses that mention a reveal subject.

    Clause-level, not sentence-level: the sentence is split at coordinating
    conjunctions and only the clause(s) carrying the gate are dropped, so a
    merged beat like "The shot holds and the camera pushes closer while Cade
    O'Connor remains hidden" keeps both staged events. A whole-sentence gate
    ("Cade is not yet visible.") collapses to empty so the beat is dropped.
    Gates about subjects with no reveal constraint pass through unchanged.
    """
    if not not_visible_re.search(sentence):
        return sentence
    if not any(token and token in _norm(sentence) for token in reveal_subjects):
        return sentence
    parts = re.split(r"(\b(?:as|while|and|but|with)\b)", sentence, flags=re.I)
    clauses: list[str] = [parts[0]]
    for index in range(1, len(parts), 2):
        clauses.append(parts[index] + (parts[index + 1] if index + 1 < len(parts) else ""))
    kept = [
        clause
        for clause in clauses
        if not (
            not_visible_re.search(clause)
            and any(token and token in _norm(clause) for token in reveal_subjects)
        )
    ]
    text = " ".join(kept).strip()
    # A dropped first clause leaves a leading conjunction behind.
    text = re.sub(r"^(?:as|while|and|but|with)\b\s*", "", text, flags=re.I).strip(" ;,.")
    if not text:
        return ""
    return text[0].upper() + text[1:]


def _timed_beats(duration: float, beats: list[SceneBeat]) -> list[TimedBeat]:
    if not beats:
        return []
    span = max(float(duration or 10.0), 1.0)
    holds = sum(float(beat.hold_seconds or 0.0) for beat in beats)
    flexible = [beat for beat in beats if not beat.hold_seconds]
    remaining = max(span - holds, 0.5 * len(flexible))
    step = remaining / max(len(flexible), 1)
    planned: list[TimedBeat] = []
    cursor = 0.0
    for beat in beats:
        length = float(beat.hold_seconds or step)
        planned.append(
            TimedBeat(
                start_sec=round(cursor, 2),
                end_sec=round(min(cursor + length, span), 2),
                description=beat.description,
            )
        )
        cursor += length
    return planned


def _spatial_rules(
    spec: SceneProductionSpec,
    subjects: list[SceneIntentSubject],
    understanding: SceneUnderstanding,
) -> list[str]:
    rules: list[str] = []
    for item in understanding.spatial:
        cleaned = item.strip().rstrip(".")
        if cleaned:
            rules.append(cleaned)
    if spec.scale_relationships:
        rel = spec.scale_relationships[0]
        rule = (
            f"{rel.subject_a} occupies substantially more visual mass than {rel.subject_b}; "
            "do not compose them as peer-sized subjects"
        )
        if rule.lower() not in {item.lower() for item in rules}:
            rules.append(rule)
    elif len(subjects) >= 2:
        rules.append("all subjects remain readable and spatially grounded in the environment")
    return rules


def _continuity_rules(
    environment: SceneIntentEnvironment,
    subjects: list[SceneIntentSubject],
    understanding: SceneUnderstanding,
) -> list[str]:
    rules: list[str] = []
    if environment.verified and environment.tag:
        rules.append(f"preserve {environment.name} environment ({environment.tag})")
    for item in subjects:
        if item.verified and item.tag:
            rules.append(f"preserve approved {item.name} design ({item.tag})")
    for item in understanding.continuity:
        cleaned = item.strip().rstrip(".")
        if cleaned and cleaned.lower() not in {rule.lower() for rule in rules}:
            rules.append(cleaned)
    return rules


def _scale_summary(spec: SceneProductionSpec, subjects: list[SceneIntentSubject]) -> str:
    if spec.scale_relationships:
        rel = spec.scale_relationships[0]
        return f"{rel.subject_a} {rel.subject_a_length}; {rel.subject_b} {rel.subject_b_length}"
    bits = [f"{item.name} {item.scale}" for item in subjects if item.scale]
    return "; ".join(bits)


def _sentence(text: str) -> str:
    cleaned = re.sub(r"\s+", " ", (text or "").strip())
    if not cleaned:
        return ""
    cleaned = cleaned[:1].upper() + cleaned[1:]
    return cleaned if cleaned.endswith((".", "!", "?", '"')) else cleaned + "."


def synthesize_cinematic_action(intent: DirectorSceneIntent) -> str:
    """Layer C ACTION language — on-screen events only, assembled from beats.

    Dialogue is embedded at its beat with the exact line. Reveal gating is
    stated as staging language. No meta or runtime language may survive.
    """
    sentences: list[str] = []
    dialogue_by_beat: dict[int, list[DialogueLine]] = {}
    orphan_dialogue: list[DialogueLine] = []
    for line in intent.dialogue:
        if line.beat_index is not None:
            dialogue_by_beat.setdefault(line.beat_index, []).append(line)
        else:
            orphan_dialogue.append(line)

    beats = sorted(intent.scene_beats, key=lambda beat: beat.index)
    # Intentional repetition: consecutive beats with identical normalized
    # prose stage the same action N times ("Mara raises her hand." × 2). The
    # compiled ACTION must express the count ("…twice", "…three times") —
    # repeating the sentence verbatim is a duplicate-staging defect, and
    # silently dropping the later stagings loses the creator's choreography.
    _REPETITION_COUNT_WORDS = {2: "twice", 3: "three times", 4: "four times", 5: "five times", 6: "six times"}
    runs: list[tuple[SceneBeat, int, str]] = []
    for beat in beats:
        key = re.sub(r"\s+", " ", (beat.description or "").strip().lower()).strip(" .")
        if runs and key and key == runs[-1][2]:
            runs[-1] = (runs[-1][0], runs[-1][1] + 1, key)
        else:
            runs.append((beat, 1, key))
    for beat, count, _key in runs:
        description = _sentence(strip_instruction_copy(beat.description))
        if description:
            if count > 1:
                phrase = _REPETITION_COUNT_WORDS.get(count, f"{count} times")
                description = description.rstrip(".!?") + f" {phrase}."
            sentences.append(description)
        for line in dialogue_by_beat.get(beat.index, []):
            sentences.append(_dialogue_sentence(line))
    for line in orphan_dialogue:
        sentences.append(_dialogue_sentence(line))

    for reveal in intent.reveals:
        gate = _reveal_sentence(reveal, intent)
        subject_token = (reveal.subject or "").lower()
        gated = any(
            subject_token and subject_token in s.lower()
            and re.search(r"\b(?:not yet visible|remains? hidden|do not reveal|hidden until|unseen)\b", s, re.I)
            for s in sentences
        )
        if gate and not gated:
            sentences.append(gate)

    action = " ".join(sentences).strip()
    action = strip_instruction_copy(action)
    return action


def _dialogue_sentence(line: DialogueLine) -> str:
    speaker = line.speaker or "The speaker"
    exact = (line.line or "").strip()
    if not exact:
        return ""
    delivery = (line.delivery or line.voice_characteristics or "").strip()
    if delivery:
        if re.search(r"\bvoice\b", delivery, re.I):
            return f'{speaker} says in a {delivery}: "{exact}"'
        return f'{speaker} says ({delivery}): "{exact}"'
    return f'{speaker} says: "{exact}"'


def _reveal_sentence(reveal: RevealConstraint, intent: DirectorSceneIntent) -> str:
    subject = reveal.subject or "the subject"
    until = (reveal.hidden_until or "").strip()
    parts = [part for part in reveal.reveal_order if part.strip()]
    if until:
        gate = f"{subject} remains hidden until {until.rstrip('.')}."
    else:
        gate = f"{subject} remains hidden until the reveal moment."
    if parts:
        gate += " Reveal in stages: " + " → ".join(parts) + "."
    return gate


def _legacy_fields(
    intent: DirectorSceneIntent,
    beats: list[SceneBeat],
) -> None:
    """Populate legacy summary fields from structured beats (compat)."""
    if not beats:
        return
    intent.opening_state = intent.opening_state or beats[0].description
    for beat in beats:
        if beat.vfx and not intent.vfx_event:
            intent.vfx_event = beat.description
        if beat.kind == "reveal" and not intent.entrance:
            intent.entrance = beat.description
        if beat.kind in {"approach", "action"} and not intent.movement:
            intent.movement = beat.description
    intent.end_state = intent.end_state or beats[-1].description
    intent.beats = [beat.description for beat in beats]


def build_director_scene_intent(
    spec: SceneProductionSpec,
    references: list[ResolvedReference],
    *,
    llm_fn: LlmFn | None = None,
    allow_llm: bool = True,
    understanding: SceneUnderstanding | None = None,
    understanding_source: str = "",
    fallback_reason: str = "",
) -> DirectorSceneIntent:
    envs = _found(references, "environment")
    props = _found(references, "prop")
    chars = _found(references, "character")

    environment = SceneIntentEnvironment()
    if envs:
        env = envs[0]
        environment = SceneIntentEnvironment(
            name=env.display_name or env.query,
            tag=prompt_facing_tag("#", env.canonical_tag or env.identity_tag, env.display_name or env.query),
            verified=True,
            verification="global_found" if env.is_global else "found",
        )
    subjects = _assign_subjects(spec, props, chars)

    if understanding is None:
        understanding, source, fallback_reason = extract_scene_understanding(
            spec.source_user_prompt or spec.scene_intent or "",
            llm_fn=llm_fn,
            allow_llm=allow_llm,
        )
    else:
        source = understanding_source or "llm"

    _match_environment(understanding.environment_name, environment)

    # Beats that merely restate a visibility gate ("Cade is NOT yet visible")
    # are dropped when a reveal constraint already covers that subject — the
    # reveal staging language carries the gate without duplicating it. The
    # dedup is clause-level, not beat-level: a beat that stages a real event
    # AND restates the gate ("The shot holds for one second. Cade O'Connor is
    # not yet visible.") keeps the event and sheds only the gate clause.
    reveal_subjects = {
        _norm(item.subject)
        for item in understanding.reveals
        if (item.subject or "").strip()
    }
    _NOT_VISIBLE_RE = re.compile(r"\b(?:not yet visible|remains? hidden|stays? hidden|unseen)\b", re.I)

    scene_beats: list[SceneBeat] = []
    for beat in understanding.beats:
        description = beat.description or ""
        if reveal_subjects and _NOT_VISIBLE_RE.search(description):
            kept_parts: list[str] = []
            for part in re.split(r"(?<=[.!?])\s+", description):
                stripped = _strip_gate_clause(part, reveal_subjects, _NOT_VISIBLE_RE)
                if not stripped:
                    continue
                if not stripped.endswith((".", "!", "?", '"')):
                    stripped += "."
                kept_parts.append(stripped)
            description = " ".join(kept_parts).strip()
            if not description:
                continue
        mapped_subjects: list[str] = []
        for name in beat.subjects:
            subject = _match_subject(name, subjects)
            mapped_subjects.append(subject.name if subject else name)
        scene_beats.append(
            SceneBeat(
                index=len(scene_beats),
                kind=beat.kind,
                description=description,
                subjects=mapped_subjects,
                camera=beat.camera,
                hold_seconds=beat.hold_seconds,
                vfx=beat.vfx,
            )
        )

    reveals: list[RevealConstraint] = []
    for item in understanding.reveals:
        subject = _match_subject(item.subject, subjects)
        reveals.append(
            RevealConstraint(
                subject=subject.name if subject else item.subject,
                subject_tag=subject.tag if subject else "",
                hidden_until=item.hidden_until,
                hidden_until_beat=_beat_index_for_event(scene_beats, item.hidden_until),
                reveal_order=item.reveal_order,
                condition=item.condition,
            )
        )

    dialogue: list[DialogueLine] = []
    for item in understanding.dialogue:
        speaker = _match_subject(item.speaker, subjects)
        dialogue.append(
            DialogueLine(
                speaker=speaker.name if speaker else item.speaker,
                speaker_tag=speaker.tag if speaker else "",
                line=item.line,
                delivery=item.delivery,
                voice_characteristics=item.voice_characteristics,
                filtering=item.filtering,
                beat_index=_dialogue_beat_index(
                    scene_beats,
                    item.speaker,
                    item.after_beat,
                    line=item.line,
                    source_text=spec.source_user_prompt or "",
                ),
            )
        )

    camera_plan = CameraPlan(
        shot_type=understanding.camera.shot_type or spec.camera.shot_type or spec.camera_intent,
        movement=understanding.camera.movement or spec.camera.movement,
        framing=understanding.camera.framing or spec.camera.framing,
        target=understanding.camera.target,
        evolution=understanding.camera.evolution,
    )

    intent = DirectorSceneIntent(
        scene_type=understanding.scene_type,
        purpose=understanding.purpose,
        mood=understanding.mood,
        shot_type=camera_plan.shot_type or "cinematic",
        environment=environment,
        subjects=subjects,
        scene_beats=scene_beats,
        reveals=reveals,
        dialogue=dialogue,
        subtitle_policy=understanding.subtitle_policy,
        exclusions=[item.rstrip(".") for item in understanding.exclusions if item.strip()],
        camera_plan=camera_plan,
        spatial_rules=_spatial_rules(spec, subjects, understanding),
        continuity_rules=_continuity_rules(environment, subjects, understanding),
        opening_state=understanding.opening_state,
        end_state=understanding.end_state,
        scale_summary=_scale_summary(spec, subjects),
        user_request=spec.source_user_prompt,
        understanding_source=source,
    )
    _legacy_fields(intent, scene_beats)
    intent.timed_beats = _timed_beats(spec.duration_seconds, scene_beats)
    intent.action_text = synthesize_cinematic_action(intent)
    if fallback_reason:
        intent.understanding_source = f"{source}:{fallback_reason[:120]}"
    return intent
