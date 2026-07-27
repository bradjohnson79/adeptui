"""Provider-specific prompt compiler with deterministic technical rules."""

from __future__ import annotations

import re
from typing import Any, Optional

from .registry import BINDINGS, binding_for_engine, binding_for_model
from .resolver import ResolveError, resolve_pack, try_resolve
from .schemas import (
    AppliedRule,
    AudioChannelPolicy,
    AudioIntent,
    AudioMode,
    CompileResult,
    ConfidenceLevel,
    NormalizedGenerationIntent,
    OverrideDisposition,
    ProvenanceClaim,
    ProductionReadiness,
)


_LAB_CONTAMINATION = re.compile(
    r"\b(laboratory|observation[- ]room|test[- ]film|sample[- ]project|"
    r"lab[- ]corridor|generic cinematic character)\b",
    re.IGNORECASE,
)


def normalize_audio_from_text(prompt: str, hint: Optional[AudioIntent] = None) -> AudioIntent:
    """Derive audio intent from filmmaker language when not explicitly provided."""
    base = hint or AudioIntent()
    text = (prompt or "").lower()
    music = base.music
    dialogue = base.dialogue
    ambience = base.ambience
    sfx = base.soundEffects
    mode = base.audioMode

    no_music = any(
        p in text
        for p in (
            "no background music",
            "no score",
            "no music",
            "without music",
            "silence",
            "silent",
            "no soundtrack",
            "preserve only intended dialogue",
        )
    )
    wants_music = any(
        p in text for p in ("background music", "score", "soundtrack", "with music")
    ) and not no_music
    no_audio = any(p in text for p in ("no audio", "no sound", "silent shot", "mute", "no generated audio"))
    dialogue_only = "dialogue only" in text or "dialogue-only" in text
    ambience_only = "ambience only" in text or "atmosphere only" in text
    sfx_only = "sound effects only" in text or "sfx only" in text

    if no_audio:
        return AudioIntent(
            audioMode=AudioMode.NONE,
            music=AudioChannelPolicy.PROHIBITED,
            dialogue=AudioChannelPolicy.PROHIBITED,
            ambience=AudioChannelPolicy.PROHIBITED,
            soundEffects=AudioChannelPolicy.PROHIBITED,
        )
    if no_music:
        music = AudioChannelPolicy.PROHIBITED
    if wants_music:
        music = AudioChannelPolicy.REQUIRED
        mode = AudioMode.MUSIC_ONLY if mode == AudioMode.NONE else mode
    if dialogue_only:
        mode = AudioMode.DIALOGUE_ONLY
        dialogue = AudioChannelPolicy.REQUIRED
        music = AudioChannelPolicy.PROHIBITED
        ambience = AudioChannelPolicy.PROHIBITED
        sfx = AudioChannelPolicy.PROHIBITED
    elif ambience_only:
        mode = AudioMode.AMBIENCE_ONLY
        ambience = AudioChannelPolicy.REQUIRED
        music = AudioChannelPolicy.PROHIBITED
        dialogue = AudioChannelPolicy.PROHIBITED
    elif sfx_only:
        mode = AudioMode.SOUND_EFFECTS_ONLY
        sfx = AudioChannelPolicy.REQUIRED
        music = AudioChannelPolicy.PROHIBITED
        dialogue = AudioChannelPolicy.PROHIBITED
    elif no_music and mode == AudioMode.NONE:
        mode = AudioMode.EXTERNAL_AUDIO_PIPELINE

    return AudioIntent(
        audioMode=mode,
        music=music,
        dialogue=dialogue,
        ambience=ambience,
        soundEffects=sfx,
    )


def _strip_contamination(text: str, examples: list[str]) -> tuple[str, list[str]]:
    warnings: list[str] = []
    out = text
    for ex in examples:
        for line in ex.splitlines():
            line = line.strip()
            if len(line) < 12:
                continue
            # Never leak example sentences into production prompts
            if line in out:
                out = out.replace(line, "")
                warnings.append("Removed knowledge-pack example content from prompt")
    if _LAB_CONTAMINATION.search(out):
        out = _LAB_CONTAMINATION.sub("", out)
        warnings.append("Removed lab/default scaffold language from prompt")
    return re.sub(r"\s{2,}", " ", out).strip(), warnings


def _rule(
    rule_id: str,
    description: str,
    *,
    confidence: float = 0.8,
    source: ConfidenceLevel = ConfidenceLevel.VERIFIED_INTERNAL,
) -> AppliedRule:
    return AppliedRule(
        ruleId=rule_id,
        description=description,
        provenance=ProvenanceClaim(
            sourceType=source,
            sourceReference=rule_id,
            confidence=confidence,
        ),
    )


def compile_intent(
    intent: NormalizedGenerationIntent,
    *,
    model_id: Optional[str] = None,
    engine_id: Optional[str] = None,
    runtime_model_version: Optional[str] = None,
    bible_package: Optional[dict[str, Any]] = None,
) -> CompileResult:
    """Compile normalized intent into model-specific prompt + parameters."""
    chosen_model = intent.forceModelId or model_id
    chosen_engine = engine_id
    if chosen_model and not chosen_engine:
        b = binding_for_model(chosen_model)
        chosen_engine = b.engineId if b else None

    pack, err = try_resolve(
        model_id=chosen_model,
        engine_id=chosen_engine,
        runtime_model_version=runtime_model_version,
        allow_non_active=False,
    )
    if pack is None:
        # Degraded mode — no fabricated expertise
        binding = binding_for_model(chosen_model or "") or binding_for_engine(chosen_engine or "")
        return CompileResult(
            modelId=(binding.modelId if binding else chosen_model) or "unknown",
            providerId=(binding.providerId if binding else "unknown"),
            engineId=(binding.engineId if binding else chosen_engine) or "unknown",
            compiledPrompt=intent.userPrompt if intent.preserveExactWording else (intent.userPrompt or ""),
            negativePrompt=intent.negativePromptHint or "",
            parameters={},
            warnings=[err or "MODEL_KNOWLEDGE_UNAVAILABLE"],
            confidence=0.0,
            status="MODEL_KNOWLEDGE_UNAVAILABLE",
            limitations=["Model-specific optimization unavailable"],
            audioPlanSummary="Unavailable — no active knowledge pack",
        )

    binding = pack["binding"]
    manifest = pack["manifest"]
    audio_behavior = pack.get("audio_behavior") or {}
    prompt_rules = pack.get("prompt_rules") or {}
    limitations = pack.get("limitations") or {}
    params_cfg = pack.get("parameters") or {}
    examples = list(pack.get("examples") or [])

    audio = intent.audioIntent
    if intent.userPrompt:
        audio = normalize_audio_from_text(intent.userPrompt, audio)

    applied: list[AppliedRule] = []
    warnings = list(pack.get("resolveWarnings") or [])
    excluded: list[str] = []
    parameters: dict[str, Any] = {}
    override_disp: dict[str, OverrideDisposition] = {}

    # Bible constraints — never overwrite canon
    bible_constraints: list[str] = []
    if bible_package:
        for key in ("styleConstraints", "continuityConstraints"):
            for item in bible_package.get(key) or []:
                bible_constraints.append(str(item))
        for item in bible_package.get("conflicts") or []:
            warnings.append(f"Production Bible conflict: {item}")
            applied.append(_rule("bible.conflict", f"Surfaced Bible conflict: {item}"))

    positive_parts: list[str] = []
    if intent.preserveExactWording:
        positive_parts.append(intent.userPrompt)
        applied.append(_rule("override.preserve_exact_wording", "Preserved user wording"))
        override_disp["preserveExactWording"] = OverrideDisposition.APPLIED
    else:
        if intent.userPrompt:
            positive_parts.append(intent.userPrompt.strip())
        # Deterministic positive appends from pack (structure only — no creative canon)
        for phrase in prompt_rules.get("positiveAppend") or []:
            if phrase and phrase not in (intent.userPrompt or ""):
                positive_parts.append(str(phrase))
                applied.append(_rule("prompt.positive_append", f"Appended structural phrase: {phrase}"))

    for c in bible_constraints[:8]:
        if c and c not in " ".join(positive_parts):
            positive_parts.append(c)
            applied.append(_rule("bible.constraint", f"Included Bible constraint: {c[:80]}"))

    for item in intent.mustInclude:
        if item:
            positive_parts.append(str(item))

    negative_parts: list[str] = []
    if intent.negativePromptHint:
        negative_parts.append(intent.negativePromptHint)
    for phrase in prompt_rules.get("negativeBase") or []:
        negative_parts.append(str(phrase))
        applied.append(_rule("prompt.negative_base", f"Negative base: {phrase}"))
    for item in intent.mustAvoid:
        negative_parts.append(str(item))

    # Audio deterministic policy
    supports_native = bool(audio_behavior.get("supportsNativeAudio"))
    generate_audio_param = audio_behavior.get("generateAudioParam")
    music_class = audio_behavior.get("musicSuppressionClassification") or "UNKNOWN"

    if audio.music == AudioChannelPolicy.PROHIBITED:
        for phrase in audio_behavior.get("musicProhibitedNegative") or [
            "background music",
            "musical score",
            "soundtrack",
        ]:
            negative_parts.append(str(phrase))
        for phrase in audio_behavior.get("musicProhibitedPositive") or []:
            positive_parts.append(str(phrase))
        applied.append(
            _rule(
                "audio.music_prohibited",
                f"Music prohibited; classification={music_class}",
                source=ConfidenceLevel.VERIFIED_INTERNAL,
            )
        )
        if supports_native and generate_audio_param:
            parameters[generate_audio_param] = False
            applied.append(
                _rule(
                    "audio.generate_audio_false",
                    f"Set {generate_audio_param}=false for music prohibition",
                    source=ConfidenceLevel.OFFICIAL
                    if audio_behavior.get("generateAudioOfficial")
                    else ConfidenceLevel.VERIFIED_INTERNAL,
                )
            )
        else:
            parameters["audioStrategy"] = "external_audio_pipeline"
            parameters["generate_audio"] = False
            warnings.append(
                limitations.get("musicSuppressionDisclosure")
                or "Model does not guarantee soundtrack suppression via a native toggle; "
                "using external audio pipeline / no embedded music request."
            )
            applied.append(
                _rule(
                    "audio.external_pipeline",
                    "No native soundtrack; external audio pipeline recommended",
                )
            )
    elif audio.music == AudioChannelPolicy.REQUIRED:
        if supports_native and generate_audio_param:
            parameters[generate_audio_param] = True
            applied.append(_rule("audio.music_required", f"Set {generate_audio_param}=true"))
        else:
            warnings.append("Model cannot generate native music; request score via external audio.")
            parameters["audioStrategy"] = "external_music_pipeline"
            applied.append(_rule("audio.music_external", "Music required but model has no native score"))

    if audio.audioMode == AudioMode.NONE:
        parameters["generate_audio"] = False
        if generate_audio_param:
            parameters[generate_audio_param] = False
        applied.append(_rule("audio.none", "No generated audio requested"))
        for phrase in ("dialogue", "speech", "music", "soundtrack"):
            negative_parts.append(phrase)

    if audio.dialogue == AudioChannelPolicy.PROHIBITED:
        negative_parts.extend(["dialogue", "talking", "speech", "lip sync"])
        applied.append(_rule("audio.no_dialogue", "Dialogue generation prohibited"))

    # Mode / input requirements
    if intent.mode in ("image_to_video", "i2v") and not intent.hasSourceImage:
        warnings.append("Image-to-video requires a source image")
        applied.append(_rule("mode.i2v_requires_image", "I2V source image missing — preflight will block"))

    # Duration clamp
    max_dur = params_cfg.get("maxDurationSec")
    if intent.durationSec is not None and max_dur is not None:
        if float(intent.durationSec) > float(max_dur):
            parameters["durationSec"] = float(max_dur)
            warnings.append(f"Duration clamped to model maximum {max_dur}s")
            applied.append(_rule("param.duration_clamp", f"Clamped duration to {max_dur}"))
            override_disp["durationSec"] = OverrideDisposition.ADJUSTED
        else:
            parameters["durationSec"] = float(intent.durationSec)

    # Version mismatch: withhold unsafe parameter injection
    if params_cfg.get("unsafeRulesWithheld"):
        for key in list(parameters.keys()):
            if key not in ("generate_audio", "audioStrategy", generate_audio_param):
                # keep audio safety knobs; drop speculative controls
                if key.startswith("experimental"):
                    parameters.pop(key, None)
                    excluded.append(key)
        warnings.append("Version mismatch: withheld unverified experimental parameters")

    # User overrides validation
    for key, value in (intent.userOverrides or {}).items():
        allowed = set(params_cfg.get("allowedOverrides") or [])
        if key not in allowed and key not in {"seed", "durationSec", "aspectRatio", "preserveExactWording"}:
            override_disp[key] = OverrideDisposition.REJECTED
            warnings.append(f"Unsupported override rejected: {key}")
            applied.append(_rule("override.rejected", f"Rejected unsupported override {key}"))
            continue
        parameters[key] = value
        override_disp[key] = OverrideDisposition.APPLIED
        applied.append(_rule("override.applied", f"Applied override {key}"))

    if "seed" in intent.userOverrides:
        parameters["seed"] = intent.userOverrides["seed"]

    compiled = ". ".join(p for p in positive_parts if p).strip()
    compiled, contam_warn = _strip_contamination(compiled, examples)
    warnings.extend(contam_warn)
    if contam_warn:
        applied.append(_rule("safety.no_example_leak", "Stripped example/lab contamination"))

    negative = ", ".join(dict.fromkeys(p for p in negative_parts if p))

    # Confidence
    overall = float((manifest.confidence or {}).get("overall") or 0.5)
    overall *= float(pack.get("confidenceScale") or 1.0)
    if warnings:
        overall = min(overall, 0.75)

    audio_summary_parts = [
        f"mode={audio.audioMode.value}",
        f"music={audio.music.value}",
        f"dialogue={audio.dialogue.value}",
    ]
    if music_class:
        audio_summary_parts.append(f"musicClass={music_class}")

    lim_list = list(limitations.get("items") or [])
    if manifest.runtimeStatus in (
        ProductionReadiness.NOT_PRODUCTION_READY,
        ProductionReadiness.EXPERIMENTAL,
        ProductionReadiness.PRODUCT_APPROVAL_REQUIRED,
    ):
        lim_list.append(f"runtimeStatus={manifest.runtimeStatus.value}")

    return CompileResult(
        modelId=binding.modelId,
        providerId=binding.providerId,
        engineId=binding.engineId,
        compiledPrompt=compiled,
        negativePrompt=negative,
        parameters=parameters,
        appliedRules=applied,
        excludedRules=excluded,
        warnings=warnings,
        confidence=round(overall, 3),
        fallbackRecommendations=list(prompt_rules.get("fallbacks") or []),
        knowledgePackVersion=manifest.knowledgePackVersion,
        modelVersion=manifest.modelVersion,
        audioPlanSummary="; ".join(audio_summary_parts),
        limitations=lim_list,
        status="ok",
        overrideDispositions=override_disp,
    )
