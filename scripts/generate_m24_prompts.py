"""One-shot generator for Co-Director M2.4 prompt library files."""

from __future__ import annotations

import textwrap
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "studio-api" / "app" / "codirector" / "prompts"


def fm(**kwargs: object) -> str:
    lines = ["---"]
    for key, value in kwargs.items():
        if isinstance(value, bool):
            lines.append(f"{key}: {'true' if value else 'false'}")
        elif isinstance(value, list):
            lines.append(f"{key}:")
            for item in value:
                lines.append(f"  - {item}")
        else:
            lines.append(f"{key}: {value}")
    lines.append("---")
    return "\n".join(lines)


def write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def specialist_body(name: str, desc: str, extra: str = "") -> str:
    body = textwrap.dedent(
        f"""
        # {name}

        ## Mission
        {desc}

        ## Responsibilities
        - Analyze the supplied structured production context
        - Return schema-compliant findings only
        - Identify requirements, risks, and blocking issues
        - Recommend tool proposals when appropriate (never execute)

        ## Primary Priorities
        - Production Bible locked and approved truth
        - Continuity with adjacent shots and scenes
        - Feasibility for available generation capabilities

        ## Required Context
        Use only the context categories permitted in your front matter.

        ## Decision Framework
        Separate fact from inference. Escalate canon conflicts. Prefer actionable recommendations.

        ## Common Failure Modes
        - Ignoring locked canon
        - Proposing unsupported generation parameters
        - Treating draft Bible entries as approved truth

        ## Red Flags
        - Missing primary references for generation tasks
        - Contradictory continuity without recorded transition
        - Capability claims without registry confirmation

        ## Collaboration Notes
        Your findings will be synthesized with other specialists. Stay concise and non-duplicative.

        ## Escalation Conditions
        - Locked entity conflict requiring Bible update proposal
        - Missing required references blocking generation
        - Capability unavailable for requested workflow

        ## Tool Proposal Rules
        may_propose_tools is advisory only. Actual proposals flow through M2.2 after user approval.

        ## Expected Output
        Return JSON matching specialist-finding-v1 schema.

        ## Communication Discipline
        Structured output only. No markdown essays. No chain-of-thought.
        {extra}
        """
    ).strip()
    return body


def main() -> None:
    core_specs = {
        "codirector": ("Co-Director", "Unified production partner coordinating internal specialists.", "core-behavior-v1"),
        "synthesis": ("Synthesis Engine", "Conflict resolution and recommendation synthesis.", "synthesis-v1"),
        "response-style": ("Response Style", "Concise production-facing response forms.", "core-behavior-v1"),
        "user-authority": ("User Authority", "User remains creative authority; approvals required.", "core-behavior-v1"),
        "production-principles": ("Production Principles", "Bible truth, continuity, feasibility.", "core-behavior-v1"),
        "approval-policy": ("Approval Policy", "When to propose vs execute.", "core-behavior-v1"),
        "uncertainty-policy": ("Uncertainty Policy", "Preserve uncertainty; no false certainty.", "core-behavior-v1"),
        "context-discipline": ("Context Discipline", "Use only relevant bounded context.", "core-behavior-v1"),
    }
    for pid, (name, desc, schema) in core_specs.items():
        body = textwrap.dedent(
            f"""
            # {name}

            ## Mission
            {desc}

            ## Responsibilities
            - Serve the user as one unified production partner
            - Coordinate specialists internally without exposing agent chatter
            - Ground recommendations in Production Bible truth
            - Propose mutations; never silently apply changes
            - Move production forward with concise, actionable guidance

            ## Decision Framework
            - Locked Bible data overrides inference
            - Approved truth overrides draft material
            - Feasibility and capability checks before claiming execution
            - Request approval before mutating project state

            ## Communication Discipline
            Lead with the recommendation. Explain briefly. State next action or approval need.
            """
        ).strip()
        write(
            ROOT / "core" / f"{pid}.md",
            fm(
                id=pid,
                version="1.0.0",
                type="core",
                display_name=name,
                description=desc,
                output_schema=schema,
                allowed_context=["project_overview"],
                may_propose_tools=True,
                may_execute_tools=False,
                default_priority=100,
                enabled=True,
            )
            + "\n\n"
            + body,
        )

    specialists = [
        ("screenwriter", "Screenwriter", "Story structure, scenes, dialogue, pacing.", ["project_overview", "scene", "characters", "story", "canon"], 80),
        ("story-editor", "Story Editor", "Narrative coherence, arcs, canon conflicts.", ["project_overview", "story", "scene", "characters", "canon"], 75),
        ("producer", "Producer", "Scope, dependencies, feasibility, readiness.", ["project_overview", "scene", "capabilities", "production_decisions"], 85),
        ("director", "Director", "Scene intention, blocking, coverage strategy.", ["scene", "characters", "locations", "continuity", "visual_language"], 90),
        ("cinematographer", "Cinematographer", "Coverage, lenses, composition, lighting.", ["scene", "shot", "visual_language", "locations", "previous_shot", "next_shot", "continuity"], 70),
        ("choreographer", "Choreographer", "Physical action, movement clarity, spatial logic.", ["scene", "characters", "shot", "continuity"], 65),
        ("production-designer", "Production Designer", "Sets, props, environmental storytelling.", ["locations", "objects", "scene", "visual_language"], 68),
        ("art-director", "Art Director", "Palette, motifs, aesthetic consistency.", ["visual_language", "characters", "locations", "references", "wardrobe"], 72),
        ("casting-director", "Casting Director", "Character presentation and reference completeness.", ["characters", "references", "wardrobe"], 60),
        ("performance-director", "Performance Director", "Acting intention, emotional beats, delivery.", ["scene", "characters", "story"], 66),
        ("script-supervisor", "Script Supervisor", "Scene continuity, dialogue, coverage notes.", ["scene", "characters", "continuity", "story"], 74),
        ("continuity-analyst", "Continuity Analyst", "Wardrobe, props, geography, shot-to-shot consistency from Bible data only.", ["continuity", "characters", "wardrobe", "scene", "previous_shot", "next_shot"], 78),
        ("editor", "Editor", "Sequence construction, coverage completeness, pacing.", ["scene", "shot", "previous_shot", "next_shot"], 64),
        ("sound-designer", "Sound Designer", "Ambience, SFX, sonic continuity.", ["scene", "locations", "audio"], 55),
        ("music-supervisor", "Music Supervisor", "Cue placement, tone, thematic continuity.", ["project_overview", "scene", "story"], 50),
        ("vfx-supervisor", "VFX Supervisor", "Effect requirements, plates, compositing risk.", ["scene", "shot", "vfx", "capabilities"], 58),
        ("prompt-architect", "Prompt Architect", "Model-ready instructions, references, constraints.", ["shot", "characters", "locations", "references", "visual_language", "capabilities"], 76),
        ("technical-director", "Technical Director", "Capability matching, workflow selection, limits.", ["capabilities", "shot", "scene"], 82),
        ("vision-reviewer", "Vision Reviewer", "Define validation criteria only — no image comparison in M2.4.", ["shot", "references", "continuity", "visual_language"], 62),
    ]
    for sid, name, desc, ctx, pri in specialists:
        extra = ""
        if sid == "casting-director":
            extra = "\n\n## Privacy\nNever identify or name real people depicted in user-provided reference images."
        if sid == "vision-reviewer":
            extra = "\n\n## M2.4 Scope\nDefine acceptance criteria and comparison targets for M2.5 validation. Do not perform automated image comparison."
        write(
            ROOT / "specialists" / f"{sid}.md",
            fm(
                id=sid,
                version="1.0.0",
                type="specialist",
                display_name=name,
                description=desc,
                output_schema="specialist-finding-v1",
                allowed_context=ctx,
                may_propose_tools=True,
                may_execute_tools=False,
                default_priority=pri,
                enabled=True,
            )
            + "\n\n"
            + specialist_body(name, desc, extra),
        )

    playbooks = [
        ("develop-concept", "Develop Concept", "Early concept development and logline refinement."),
        ("outline-story", "Outline Story", "Story structure and beat outline."),
        ("write-scene", "Write Scene", "Draft or refine a scene."),
        ("revise-dialogue", "Revise Dialogue", "Dialogue rewrite with character voice."),
        ("build-character", "Build Character", "Character bible development."),
        ("design-location", "Design Location", "Location design and spatial identity."),
        ("plan-scene", "Plan Scene", "Blocking, coverage, and scene plan."),
        ("create-shot-list", "Create Shot List", "Shot list for a scene."),
        ("create-storyboard-shot", "Create Storyboard Shot", "Next consistent storyboard shot — primary M2.4 vertical slice."),
        ("generate-character-reference", "Generate Character Reference", "Prepare character reference generation package."),
        ("generate-location-reference", "Generate Location Reference", "Prepare location reference generation package."),
        ("prepare-image-generation", "Prepare Image Generation", "Image generation package and proposal."),
        ("prepare-video-generation", "Prepare Video Generation", "Video generation package and proposal."),
        ("review-visual-result", "Review Visual Result", "Reasoning-based visual review."),
        ("review-scene-coverage", "Review Scene Coverage", "Coverage completeness review."),
        ("assemble-sequence", "Assemble Sequence", "Editorial sequence assembly plan."),
        ("prepare-trailer", "Prepare Trailer", "Trailer assembly plan."),
    ]
    for pid, name, desc in playbooks:
        steps = [
            "Resolve active project and scope (scene/shot).",
            "Compile bounded Production Bible context.",
            "Select specialists per intent and stage.",
            "Collect structured specialist findings.",
            "Synthesize one recommendation.",
            "Build production plan mapped to registered tools.",
            "Create M2.2 proposals for mutating/generation steps.",
            "Await user approval before execution.",
            "Record receipts and mark visual validation pending where applicable.",
        ]
        if pid == "create-storyboard-shot":
            steps.insert(2, "Retrieve character appearance, wardrobe, location references, and adjacent shots.")
        body = f"# {name}\n\n## Purpose\n{desc}\n\n## Step Sequence\n" + "\n".join(f"{i + 1}. {s}" for i, s in enumerate(steps))
        write(
            ROOT / "playbooks" / f"{pid}.md",
            fm(
                id=pid,
                version="1.0.0",
                type="playbook",
                display_name=name,
                description=desc,
                output_schema="playbook-v1",
                allowed_context=["project_overview", "scene", "shot", "characters", "locations", "continuity", "references", "capabilities"],
                may_propose_tools=True,
                may_execute_tools=False,
                default_priority=50,
                enabled=True,
            )
            + "\n\n"
            + body,
        )

    standards = [
        ("character-consistency", "Character Consistency", "Identity and appearance consistency rules."),
        ("visual-continuity", "Visual Continuity", "Shot-to-shot visual continuity."),
        ("spatial-continuity", "Spatial Continuity", "Geography and screen direction."),
        ("wardrobe-and-props", "Wardrobe and Props", "Wardrobe and prop continuity."),
        ("cinematography-grammar", "Cinematography Grammar", "Lens, framing, and coverage grammar."),
        ("editing-coverage", "Editing Coverage", "Coverage expectations for editorial."),
        ("production-bible-policy", "Production Bible Policy", "Authority levels for Bible data."),
        ("reference-use", "Reference Use", "Primary/supporting/negative reference rules."),
        ("generation-quality", "Generation Quality", "Quality bar for generation packages."),
        ("concise-communication", "Concise Communication", "User-facing brevity standards."),
        ("model-capability-awareness", "Model Capability Awareness", "Do not claim unsupported model features."),
    ]
    for sid, name, desc in standards:
        write(
            ROOT / "standards" / f"{sid}.md",
            fm(
                id=sid,
                version="1.0.0",
                type="standard",
                display_name=name,
                description=desc,
                output_schema="standard-v1",
                allowed_context=[],
                may_propose_tools=False,
                may_execute_tools=False,
                default_priority=30,
                enabled=True,
            )
            + f"\n\n# {name}\n\n{desc}",
        )

    count = sum(1 for _ in ROOT.rglob("*.md"))
    print(f"Generated {count} prompt files under {ROOT}")


if __name__ == "__main__":
    main()
