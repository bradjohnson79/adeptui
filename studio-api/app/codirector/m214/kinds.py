"""M2.14 Product section 50 capability IDs (honest registration)."""
from __future__ import annotations

# Product section 50 capability IDs — registered as partially_wired scaffolds.
CAPABILITY_IDS: tuple[tuple[str, str, str], ...] = (
    ("codirector.attachment.classify", "Classify attachment by content", "partially_wired"),
    ("codirector.attachment.interpret", "Interpret attachment proposal", "partially_wired"),
    ("codirector.attachment.confirm", "Confirm attachment interpretation", "partially_wired"),
    ("codirector.project.propose", "Propose project from idea/attachment", "partially_wired"),
    ("codirector.project.resume", "Resume unified session", "partially_wired"),
    ("codirector.media.list", "List media cards", "partially_wired"),
    ("codirector.media.select", "Select media item", "partially_wired"),
    ("codirector.media.compare", "Compare media items", "partially_wired"),
    ("codirector.media.review", "Review media item", "partially_wired"),
    ("codirector.media.approve", "Approve media item", "partially_wired"),
    ("codirector.media.reject", "Reject media item", "partially_wired"),
    ("codirector.media.request_revision", "Request media revision", "partially_wired"),
    ("storyteller.scene.analyze", "Storyteller scene analyze", "partially_wired"),
    ("storyteller.scene.identify_unknowns", "Identify scene unknowns", "partially_wired"),
    ("storyteller.scene.ask_questions", "Ask 2-4 high-impact questions", "partially_wired"),
    ("storyteller.scene.propose_direction", "Propose scene direction", "partially_wired"),
    ("storyteller.scene.generate_variations", "Generate scene variations", "partially_wired"),
    ("storyteller.scene.define_emotional_arc", "Define emotional arc", "partially_wired"),
    ("storyteller.scene.define_subtext", "Define subtext", "partially_wired"),
    ("storyteller.character.interpret", "Interpret character", "partially_wired"),
    ("storyteller.environment.interpret", "Interpret environment story", "partially_wired"),
    ("storyteller.media.review", "Storyteller media review", "partially_wired"),
    ("storyteller.handoff.create", "Create Storyteller production handoff", "partially_wired"),
    ("sound_producer.concept.create", "Create SonicConcept", "partially_wired"),
    ("sound_producer.score_brief.create", "Create score brief", "partially_wired"),
    ("sound_producer.ambience.plan", "Plan ambience", "partially_wired"),
    ("sound_producer.cue.plan", "Plan sound cues", "partially_wired"),
    ("sound_producer.dialogue.plan", "Plan dialogue treatment", "partially_wired"),
    ("sound_producer.mix_intent.create", "Create mix intent", "partially_wired"),
    ("production_team.message.send", "Send specialist message", "partially_wired"),
    ("production_team.message.respond", "Respond to specialist message", "partially_wired"),
    ("production_team.handoff.create", "Create department handoff", "partially_wired"),
    ("production_team.meeting.convene", "Convene production meeting", "partially_wired"),
    ("production_team.meeting.synthesize", "Synthesize meeting for user", "partially_wired"),
    ("production_team.conflict.detect", "Detect production conflicts", "partially_wired"),
    ("production_team.conflict.resolve", "Resolve/synthesize conflicts", "partially_wired"),
    ("production_team.decision.propagate", "Propagate decision impact", "partially_wired"),
    ("production_team.impact.calculate", "Calculate decision impact", "partially_wired"),
    ("production_team.state.revalidate", "Revalidate approvals after impact", "partially_wired"),
    ("production_team.brief.update", "Update UnifiedSceneBrief", "partially_wired"),
    ("production_team.readiness.evaluate", "Evaluate production readiness", "partially_wired"),
    ("production_team.final_review", "Final production review", "partially_wired"),
)

PROJECT_STAGES: tuple[str, ...] = (
    "idea",
    "discovery",
    "treatment",
    "screenplay",
    "previs",
    "production",
    "post",
    "delivery",
)

ATTACHMENT_KINDS: tuple[str, ...] = (
    "treatment",
    "screenplay",
    "storyboard",
    "sketch",
    "reference_image",
    "audio_reference",
    "video_reference",
    "notes",
    "unknown",
)

MEDIA_KINDS: tuple[str, ...] = (
    "image",
    "video",
    "audio",
    "storyboard",
    "environment_preview",
)

SPECIALIST_IDS: tuple[str, ...] = (
    "storyteller",
    "sound-producer",
)
