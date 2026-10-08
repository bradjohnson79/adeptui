"""Adept v1.1 Production Readiness policy — single authority.

Status, Capability Registry, and Production Assurance must resolve readiness
from this module. Do not encode a second meaning in UI copy, score caps, or
per-file special cases.

VideoChat3 4B product contract (Closure 2)
-----------------------------------------
VideoChat3 is retired from current Adept UI. Timeline V2 and Co-Director
generation do not use it. The catalog id stays resolvable for leftover
callers and is not a Setup requirement.

Governing Temporal Continuity law: unavailable perception must not deadlock
generation; review-unavailable yields an explicit degraded packet.

Therefore:

* VideoChat3 is not a Setup requirement and is not listed in public Setup.
* InternVideo3 8B stays optional deep-review and must not cap studio
  readiness at 94.
* Classify ``codirector.video_intelligence.ready`` as
  ``advisory_review_degraded`` / ``continuity_review``.
* Do not score it as a production outage.
* Do not special-case the string ``videochat3`` in scoring — consumers use
  the capability id and this class.

Score meaning
-------------
The Production Assurance number is **Adept Platform Production Readiness**,
not infrastructure-only health. Creator-path checks are part of the score.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Iterable, Optional

POLICY_VERSION = "v1.1"
SCORE_SEMANTICS = "Adept Platform Production Readiness"

VIDEOCHAT3_CAPABILITY_ID = "codirector.video_intelligence.ready"
VIDEOCHAT3_COMPONENT_ID = "videochat3_4b"
VIDEOCHAT3_V11_ROLE = "continuity_review_only"


class ReadinessClass(str, Enum):
    PLATFORM_CRITICAL = "platform_critical"
    PRODUCTION_CRITICAL = "production_critical"
    WORKFLOW_DEGRADED = "workflow_degraded"
    ADVISORY_REVIEW_DEGRADED = "advisory_review_degraded"
    OPTIONAL = "optional"


class V11Requirement(str, Enum):
    REQUIRED = "required"
    CONTINUITY_REVIEW = "continuity_review"
    WORKFLOW = "workflow"
    ADVISORY = "advisory"
    OPTIONAL = "optional"
    DEFERRED = "deferred"


class Severity(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    STANDARD = "standard"
    ADVISORY = "advisory"
    OPTIONAL = "optional"


_CLASS_ORDER = (
    ReadinessClass.PLATFORM_CRITICAL,
    ReadinessClass.PRODUCTION_CRITICAL,
    ReadinessClass.WORKFLOW_DEGRADED,
    ReadinessClass.ADVISORY_REVIEW_DEGRADED,
    ReadinessClass.OPTIONAL,
)


@dataclass(frozen=True)
class ReadinessAssignment:
    readiness_class: ReadinessClass
    v11_requirement: V11Requirement
    workflow_scope: str
    production_effect: str
    severity: Severity

    def as_public(self) -> dict[str, str]:
        return {
            "readinessClass": self.readiness_class.value,
            "v11Requirement": self.v11_requirement.value,
            "workflowScope": self.workflow_scope,
            "severity": self.severity.value,
            "productionEffect": self.production_effect,
        }


def _assign(
    readiness_class: ReadinessClass,
    v11_requirement: V11Requirement,
    workflow_scope: str,
    production_effect: str,
    severity: Severity,
) -> ReadinessAssignment:
    return ReadinessAssignment(
        readiness_class=readiness_class,
        v11_requirement=v11_requirement,
        workflow_scope=workflow_scope,
        production_effect=production_effect,
        severity=severity,
    )


PLATFORM = lambda scope, effect: _assign(
    ReadinessClass.PLATFORM_CRITICAL, V11Requirement.REQUIRED, scope, effect, Severity.CRITICAL
)
PRODUCTION = lambda scope, effect: _assign(
    ReadinessClass.PRODUCTION_CRITICAL, V11Requirement.REQUIRED, scope, effect, Severity.HIGH
)
WORKFLOW = lambda scope, effect: _assign(
    ReadinessClass.WORKFLOW_DEGRADED, V11Requirement.WORKFLOW, scope, effect, Severity.STANDARD
)
ADVISORY = lambda scope, effect: _assign(
    ReadinessClass.ADVISORY_REVIEW_DEGRADED, V11Requirement.ADVISORY, scope, effect, Severity.ADVISORY
)
CONTINUITY = lambda scope, effect: _assign(
    ReadinessClass.ADVISORY_REVIEW_DEGRADED,
    V11Requirement.CONTINUITY_REVIEW,
    scope,
    effect,
    Severity.ADVISORY,
)
OPTIONAL = lambda scope, effect: _assign(
    ReadinessClass.OPTIONAL, V11Requirement.OPTIONAL, scope, effect, Severity.OPTIONAL
)
DEFERRED = lambda scope, effect: _assign(
    ReadinessClass.OPTIONAL, V11Requirement.DEFERRED, scope, effect, Severity.OPTIONAL
)

#: Capability-id assignments. Prefer these over prefix/subsystem inference.
CAPABILITY_POLICY: dict[str, ReadinessAssignment] = {
    "storage.project_data": PLATFORM("platform.storage", "The studio cannot persist project files."),
    "storage.database": PLATFORM("platform.storage", "The studio cannot persist project records."),
    "project.create": PRODUCTION("create.path", "Creators cannot open a new project."),
    "project.list": PRODUCTION("create.path", "Creators cannot see their projects."),
    "project.read": PRODUCTION("create.path", "Creators cannot open an existing project."),
    "project.update": WORKFLOW("create.path", "Project settings cannot be saved."),
    "project.delete": OPTIONAL("create.path", "Archive/delete is unavailable; production can continue."),
    "project.duplicate": OPTIONAL("create.path", "Duplicate is unavailable; production can continue."),
    "project.archive": OPTIONAL("create.path", "Archive is unavailable; production can continue."),
    "project.scenes.read": PRODUCTION("timeline.context", "Scenes cannot be loaded."),
    "project.scenes.create": PRODUCTION("create.path", "A project cannot receive its first scene."),
    "project.scenes.update": WORKFLOW("timeline.context", "Scene edits cannot be saved."),
    "project.scenes.delete": OPTIONAL("timeline.context", "Scene delete is unavailable."),
    "project.scenes.reorder": OPTIONAL("timeline.context", "Scene reorder is unavailable."),
    "project.scenes.active": WORKFLOW("timeline.context", "Active scene binding is incomplete."),
    # Legacy Generate Timeline panel propose (menu-hidden workspace in v1.1).
    # Consumer audit 2026-09-14: the only caller is studio-web GenerateTimelinePanel
    # under the menu-hidden legacy "generate" workspace. Co-Director chat/tools and
    # Timeline H3 generate never call POST /api/projects/{projectId}/timeline/propose.
    # The endpoint stays honestly DEGRADED (Ollama-or-heuristic) but must not own
    # Status warningChecks.
    "project.timeline.propose": OPTIONAL(
        "timeline.context",
        "Legacy Generate Timeline propose is menu-hidden in v1.1; Co-Director production does not consume it.",
    ),
    "project.timeline.apply": WORKFLOW("timeline.context", "Timeline apply is unavailable."),
    "comfyui.health": PRODUCTION("local.runtime", "Local picture/video runtime is unreachable."),
    "comfyui.queue": PRODUCTION("local.runtime", "Local generation cannot be queued."),
    "comfyui.cancel": WORKFLOW("local.runtime", "In-flight local jobs cannot be cancelled from Adept."),
    "comfyui.outputs": WORKFLOW("local.runtime", "Local outputs cannot be read back."),
    "models.image.ready": PRODUCTION("image.generate", "Required local still-image weights are missing."),
    "models.image.krea2.ready": OPTIONAL("image.krea2", "Krea 2 is an optional still stack."),
    "models.video.ready": PRODUCTION(
        "video.generate",
        "Required local video weights are missing (LTX 2.5 and/or MiniMax H3). Retired WAN / Hunyuan Video / LTX 2.3 are not this gate.",
    ),
    "workflows.discover": WORKFLOW("local.runtime", "Workflow discovery is incomplete."),
    "workflows.validate": WORKFLOW("local.runtime", "Workflow validation is incomplete."),
    "workflows.ready": PRODUCTION("local.runtime", "Registered workflows are not ready."),
    "workflows.image.ready": PRODUCTION("image.generate", "Image workflows are not ready."),
    "workflows.video.ready": PRODUCTION("video.generate", "Video workflows are not ready."),
    "extensions.comfyui.ready": PRODUCTION("local.runtime", "Required Comfy nodes are missing."),
    "generation.image.queue": PRODUCTION("image.generate", "Image generation cannot be queued."),
    "generation.video.queue": PRODUCTION("video.generate", "Video generation cannot be queued."),
    "generation.lipsync.queue": WORKFLOW("voice.lipsync", "Lip sync cannot be queued."),
    "generation.jobs.read": WORKFLOW("jobs", "Job status cannot be read."),
    "image.generate": PRODUCTION("image.generate", "Image generation is not callable."),
    "video.generate": PRODUCTION("video.generate", "Video generation is not callable."),
    "director.timeline.read": PRODUCTION("timeline.context", "Timeline cannot be loaded."),
    "director.timeline.update": PRODUCTION("timeline.context", "Timeline cannot be saved."),
    "references.timeline_bindings": PRODUCTION("timeline.context", "Timeline context bindings are not ready."),
    # Gated LTX 2.3 Ingredients IC-LoRA — optional still/video path, not MiniMax H3 Timeline.
    # Missing weights stay honestly NOT_CONFIGURED; they must not cap studio readiness at 84.
    "references.ic_lora.ready": OPTIONAL(
        "references.ic_lora",
        "Ingredients IC-LoRA is an optional LTX 2.3 path. Timeline generation does not require it.",
    ),
    "codirector.chat": PRODUCTION("codirector.routing", "Co-Director chat is not callable."),
    "codirector.provider": PRODUCTION("codirector.routing", "Co-Director has no usable model."),
    "codirector.video_intelligence.ready": CONTINUITY(
        "codirector.temporal_continuity",
        "When VideoChat3 is unavailable, Temporal Continuity review is degraded. Timeline generation still works.",
    ),
    "codirector.media_intelligence.qwen_omni.ready": ADVISORY(
        "codirector.media_intelligence",
        "Media Intelligence (Qwen2.5-Omni) is not installed. Core Adept stays usable; Co-Director media perception is reduced.",
    ),
    "codirector.vision.validate": ADVISORY("codirector.review", "Vision validation assistance is reduced."),
    "codirector.vision.review": ADVISORY("codirector.review", "Vision review assistance is reduced."),
    "codirector.tools": WORKFLOW("codirector.routing", "Co-Director tools are not fully wired."),
    "source_manager.read": OPTIONAL("setup", "Source Manager overview is informational."),
    "source_manager.refresh": OPTIONAL("setup", "Source refresh is informational."),
    "source_manager.install": OPTIONAL("setup", "Install is a setup action, not a live production outage."),
    "source_manager.repair": OPTIONAL("setup", "Repair is a setup action."),
    "downloads.read": OPTIONAL("setup", "Download list is informational."),
    "downloads.queue": OPTIONAL("setup", "Download queue is informational."),
    "setup.read": OPTIONAL("setup", "Setup status is informational."),
    "setup.prepare": OPTIONAL("setup", "Setup prepare is informational."),
    "health.read": PLATFORM("platform.api", "Studio health cannot be read."),
    "capabilities.read": PLATFORM("platform.api", "Capability Registry cannot be read."),
}

_PREFIX_POLICY: tuple[tuple[str, ReadinessAssignment], ...] = (
    ("3d.", DEFERRED("deferred.3d", "Native 3D is deferred from v1.1.")),
    ("m28.", OPTIONAL("optional.sandbox", "Sandbox/recipe surfaces are optional.")),
    ("storyteller.", ADVISORY("codirector.review", "Storyteller assistance is reduced.")),
    ("production_team.", ADVISORY("codirector.review", "Production-team assistance is reduced.")),
    ("sound_producer.", ADVISORY("codirector.review", "Sound-producer assistance is reduced.")),
    ("codirector.attachment.", ADVISORY("codirector.review", "Attachment interpretation is reduced.")),
    ("codirector.media.", ADVISORY("codirector.review", "Media review assistance is reduced.")),
    ("codirector.bible.", WORKFLOW("codirector.bible", "Production Bible workflow is incomplete.")),
    ("codirector.project.", WORKFLOW("codirector.routing", "Co-Director project tools are incomplete.")),
    ("ve.", WORKFLOW("virtual_environment", "Virtual Environment workflow is incomplete.")),
    ("virtual_stage.", WORKFLOW("virtual_environment", "Virtual Stage workflow is incomplete.")),
    ("audio.", WORKFLOW("audio.studio", "Audio workflow is incomplete.")),
    ("lipsync.", WORKFLOW("voice.lipsync", "Lip sync workflow is incomplete.")),
    ("mouth.", WORKFLOW("voice.lipsync", "Mouth-track workflow is incomplete.")),
    ("character.", WORKFLOW("character.creator", "Character workflow is incomplete.")),
    ("frame.", WORKFLOW("timeline.frames", "Frame workflow is incomplete.")),
    ("storyboard.", WORKFLOW("storyboard", "Storyboard workflow is incomplete.")),
    ("references.", WORKFLOW("references", "Reference workflow is incomplete.")),
    ("assets.", WORKFLOW("library", "Library asset workflow is incomplete.")),
    ("image.", WORKFLOW("image.generate", "An image-studio path is incomplete.")),
    ("video.", WORKFLOW("video.generate", "A video path is incomplete.")),
    ("editor.", WORKFLOW("editor", "Editor sequences are incomplete.")),
    ("spatial.", WORKFLOW("spatial_map", "Spatial Map workflow is incomplete.")),
    ("scene.", WORKFLOW("scene.creator", "Scene render workflow is incomplete.")),
    ("timeline.", WORKFLOW("timeline.context", "Timeline workflow is incomplete.")),
)

_SUBSYSTEM_POLICY: dict[str, ReadinessAssignment] = {
    "storage": PLATFORM("platform.storage", "Platform storage is not ready."),
    "project": PRODUCTION("create.path", "Project workflow is not ready."),
    "comfyui": PRODUCTION("local.runtime", "Local runtime is not ready."),
    "models": PRODUCTION("local.runtime", "Required models are not ready."),
    "generation": PRODUCTION("generation", "Generation cannot run."),
}

#: Production Assurance check ids (not capability ids).
STATUS_CHECK_POLICY: dict[str, ReadinessAssignment] = {
    "api.health": PLATFORM("platform.api", "Studio API is not operational."),
    "session.binding": PRODUCTION("create.path", "No project is bound."),
    "codirector.provider": PRODUCTION("codirector.routing", "Co-Director has no usable model."),
    "tools.registry": PRODUCTION("codirector.routing", "Co-Director tools are unavailable."),
    "proposal.service": WORKFLOW("codirector.bible", "Proposal service is degraded."),
    "comfy.health": PRODUCTION("local.runtime", "Local picture/video runtime is unreachable."),
    "gpu.stats": OPTIONAL("platform.gpu", "GPU stats are informational."),
    "source_manager.overview": OPTIONAL("setup", "Source Manager is informational."),
    "install_jobs.status": OPTIONAL("setup", "Install jobs are informational."),
    "production_control.status": PRODUCTION("generation", "No local or hosted runtime path is available."),
    "production_control.queue": OPTIONAL("jobs", "Queue depth is informational."),
    "image_runtime.readiness": PRODUCTION("image.generate", "Image runtime is not ready."),
    "video_runtime.readiness": PRODUCTION("video.generate", "Video runtime is not ready."),
    "voice_runtime.readiness": WORKFLOW("voice", "Voice runtime is not ready."),
    "voice_environment.runtime": WORKFLOW("voice", "Voice Environment is not ready."),
    "magi.readiness": OPTIONAL("magi", "MAGI is optional."),
    "library.preflight": PRODUCTION("library", "Project library cannot persist."),
    "bible.versions": ADVISORY("codirector.bible", "Production Bible is informational."),
    "scriptwriter.documents": WORKFLOW("scriptwriter", "Scriptwriter documents are missing."),
    "timeline.preflight": WORKFLOW("timeline.context", "Bound-scene timeline preflight found issues."),
    "create.path": PRODUCTION("create.path", "CREATE path is not usable."),
    "timeline.generator_truth": PRODUCTION("timeline.generators", "Timeline generator catalog is dishonest or empty."),
    "timeline.context_binding": PRODUCTION("timeline.context", "Timeline cannot bind project/scene context."),
    "posecraft.identity_nav": OPTIONAL("posecraft", "Dormant v1.2 staging probe. Not a v1.1 readiness requirement."),
    "codirector.grounded_routing": WORKFLOW(
        "codirector.routing",
        "Co-Director knowledge/routing foundation is not landed.",
    ),
    "runtime.authority": OPTIONAL("runtime.supervisor", "Leftover scheduled-task names are informational."),
    # Bound-scene Temporal Continuity handoff packet (probe owned by the temporal
    # lane). Advisory continuity: it must warn when the bound scene's latest
    # production handoff packet is unavailable, it must never Block 35, and missing
    # InternVideo3 (optional deep-review) is not this check's concern.
    "codirector.temporal_continuity.packet": CONTINUITY(
        "codirector.temporal_continuity",
        "The bound scene's latest Temporal Continuity handoff packet is unavailable. Timeline generation still works.",
    ),
    "codirector.temporal_continuity": CONTINUITY(
        "codirector.temporal_continuity",
        "Temporal Continuity review is degraded. Timeline generation still works.",
    ),
    # Fallback only. The live probe overwrites this with the snapshot class.
    # A registry timeout must not infer WORKFLOW_DEGRADED from criticality=high.
    "capabilities.registry": ADVISORY(
        "capability.registry",
        "Capability Registry gaps are classified per row. A probe timeout is not a production outage.",
    ),
}

_DEFAULT_OPTIONAL = OPTIONAL("unclassified", "This row is not a v1.1 production gate.")


def classify_capability(
    capability_id: str,
    *,
    subsystem: str = "",
    component_ids: Iterable[str] = (),
) -> ReadinessAssignment:
    """Resolve v1.1 readiness for one capability id.

    Component ids are not scoring keys. ``videochat3_4b`` is classified only
    because its capability id is in ``CAPABILITY_POLICY``.
    """
    token = str(capability_id or "").strip()
    if token in CAPABILITY_POLICY:
        return CAPABILITY_POLICY[token]
    for prefix, assignment in _PREFIX_POLICY:
        if token.startswith(prefix):
            return assignment
    if subsystem in _SUBSYSTEM_POLICY:
        return _SUBSYSTEM_POLICY[subsystem]
    _ = tuple(component_ids)
    return _DEFAULT_OPTIONAL


def classify_status_check(check_id: str) -> Optional[ReadinessAssignment]:
    token = str(check_id or "").strip()
    return STATUS_CHECK_POLICY.get(token)


def infer_from_criticality(criticality: str) -> ReadinessClass:
    key = str(criticality or "").strip().lower()
    if key == "critical":
        return ReadinessClass.PRODUCTION_CRITICAL
    if key == "high":
        return ReadinessClass.WORKFLOW_DEGRADED
    if key == "optional":
        return ReadinessClass.OPTIONAL
    return ReadinessClass.ADVISORY_REVIEW_DEGRADED


def worst_class(classes: Iterable[ReadinessClass | str]) -> Optional[ReadinessClass]:
    found: list[ReadinessClass] = []
    for item in classes:
        if isinstance(item, ReadinessClass):
            found.append(item)
            continue
        try:
            found.append(ReadinessClass(str(item)))
        except ValueError:
            continue
    if not found:
        return None
    return min(found, key=lambda item: _CLASS_ORDER.index(item))


def class_affects_production(readiness_class: ReadinessClass | str) -> bool:
    token = ReadinessClass(str(readiness_class))
    return token in {ReadinessClass.PLATFORM_CRITICAL, ReadinessClass.PRODUCTION_CRITICAL}


def class_is_advisory(readiness_class: ReadinessClass | str) -> bool:
    token = ReadinessClass(str(readiness_class))
    return token in {ReadinessClass.ADVISORY_REVIEW_DEGRADED, ReadinessClass.OPTIONAL}


def videochat3_v11_decision() -> dict[str, str]:
    assignment = classify_capability(VIDEOCHAT3_CAPABILITY_ID)
    return {
        "capabilityId": VIDEOCHAT3_CAPABILITY_ID,
        "componentId": VIDEOCHAT3_COMPONENT_ID,
        "role": VIDEOCHAT3_V11_ROLE,
        "catalogRequiredRemains": "false",
        "reason": (
            "VideoChat3 is not part of current Adept UI. Timeline and Co-Director "
            "generation do not require it."
        ),
        **assignment.as_public(),
    }
