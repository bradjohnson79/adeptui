# -*- coding: utf-8 -*-
"""Wire M2.14 into flags, migrations, routers, health, DAG, contracts, frontend."""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def write(path: Path, text: str) -> None:
    if not text.endswith("\n"):
        text += "\n"
    path.write_text(text, encoding="utf-8", newline="\n")
    print("patched", path.relative_to(ROOT))


def patch_feature_flags() -> None:
    path = ROOT / "studio-api" / "app" / "feature_flags.py"
    text = read(path)
    if "codirector_unified_experience_v1" in text:
        print("feature_flags already patched")
        return
    text = text.replace(
        '* ``STUDIO_FEATURE_VIRTUAL_ENVIRONMENT_STUDIO_V1`` (M2.13)\n"""',
        '* ``STUDIO_FEATURE_VIRTUAL_ENVIRONMENT_STUDIO_V1`` (M2.13)\n'
        '* ``STUDIO_FEATURE_CODIRECTOR_UNIFIED_EXPERIENCE_V1`` (M2.14)\n"""',
    )
    text = text.replace(
        "    virtual_environment_studio_v1: bool = False\n",
        "    virtual_environment_studio_v1: bool = False\n"
        "    codirector_unified_experience_v1: bool = False\n",
    )
    write(path, text)


def patch_migrations_init() -> None:
    path = ROOT / "studio-api" / "app" / "migrations" / "__init__.py"
    text = read(path)
    if "m017_codirector_unified_experience" in text:
        print("migrations already patched")
        return
    text = text.replace(
        "from .m016_virtual_environment_studio import MIGRATION as M016\n",
        "from .m016_virtual_environment_studio import MIGRATION as M016\n"
        "from .m017_codirector_unified_experience import MIGRATION as M017\n",
    )
    text = text.replace(
        "DEFAULT_REGISTRY = MigrationRegistry((M001, M002, M003, M004, M005, M006, M007, M008, M010, M011, M012, M013, M014, M015, M016))",
        "DEFAULT_REGISTRY = MigrationRegistry((M001, M002, M003, M004, M005, M006, M007, M008, M010, M011, M012, M013, M014, M015, M016, M017))",
    )
    text = text.replace(
        '    "M016",\n    "Migration",',
        '    "M016",\n    "M017",\n    "Migration",',
    )
    write(path, text)


def patch_codirector_router() -> None:
    path = ROOT / "studio-api" / "app" / "routers" / "codirector.py"
    text = read(path)
    if "m214_router" in text:
        print("codirector router already patched")
        return
    text = text.replace(
        "from ..codirector.m213.api import router as m213_router\n",
        "from ..codirector.m213.api import router as m213_router\n"
        "from ..codirector.m214.api import router as m214_router\n",
    )
    text = text.replace(
        "router.include_router(m213_router)\n",
        "router.include_router(m213_router)\nrouter.include_router(m214_router)\n",
    )
    write(path, text)


def patch_main() -> None:
    path = ROOT / "studio-api" / "app" / "main.py"
    text = read(path)
    if "ensure_m214_tables" in text:
        print("main already patched")
        return
    text = text.replace(
        """    try:
        from .codirector.m213.db import ensure_m213_tables

        ensure_m213_tables()
    except Exception:
        logger.exception("M2.13 table ensure failed")
""",
        """    try:
        from .codirector.m213.db import ensure_m213_tables

        ensure_m213_tables()
    except Exception:
        logger.exception("M2.13 table ensure failed")
    try:
        from .codirector.m214.db import ensure_m214_tables

        ensure_m214_tables()
    except Exception:
        logger.exception("M2.14 table ensure failed")
""",
    )
    write(path, text)


def patch_health_api() -> None:
    path = ROOT / "studio-api" / "app" / "routers" / "api.py"
    text = read(path)
    if "unifiedExperienceEnabled" in text:
        print("health api already patched")
        return
    text = text.replace(
        '"virtualEnvironmentStudioEnabled": bool(feature_flags.virtual_environment_studio_v1),',
        '"virtualEnvironmentStudioEnabled": bool(feature_flags.virtual_environment_studio_v1),\n'
        '        "unifiedExperienceEnabled": bool(feature_flags.codirector_unified_experience_v1),',
    )
    write(path, text)


def patch_registry() -> None:
    path = ROOT / "studio-api" / "app" / "capabilities" / "registry.py"
    text = read(path)
    if "codirector.attachment.classify" in text:
        print("registry already patched")
        return
    # Insert M2.14 caps before storage section (read kinds.py; do not import app)
    caps = []
    kinds_path = ROOT / "studio-api" / "app" / "codirector" / "m214" / "kinds.py"
    kinds_src = read(kinds_path)
    ids = re.findall(r'\("([^"]+)",\s*"([^"]+)",\s*"([^"]+)"\)', kinds_src)
    for cid, display, status in ids:
        baseline = "S.PARTIALLY_WIRED" if status == "partially_wired" else "S.NOT_IMPLEMENTED"
        subsystem = (
            "storyteller"
            if cid.startswith("storyteller.")
            else "sound_producer"
            if cid.startswith("sound_producer.")
            else "production_team"
            if cid.startswith("production_team.")
            else "codirector_unified"
        )
        caps.append(
            f"""    _d(
        id="{cid}",
        display_name="{display}",
        subsystem="{subsystem}",
        baseline_status={baseline},
        summary="M2.14 Product §50: {display}.",
        read_only={str(cid.endswith(".list") or cid.endswith(".evaluate")).lower()},
        http_ref="/api/codirector/m214/",
    ),"""
        )
    block = (
        "\n    # ---------------------------------------------------------------- M2.14 unified experience (Product §50)\n"
        + "\n".join(caps)
        + "\n"
    )
    text = text.replace(
        "    # ---------------------------------------------------------------- storage\n",
        block + "    # ---------------------------------------------------------------- storage\n",
    )
    write(path, text)


def patch_contracts() -> None:
    path = ROOT / "studio-api" / "app" / "codirector" / "intelligence" / "contracts.py"
    text = read(path)
    if '"storyteller"' in text and "Storyteller" in text:
        print("contracts already patched")
        return
    # Append after VPC contract block — find last SpecialistContract closing before PRODUCT_ROLE or ROLE map
    insert = '''
    "storyteller": SpecialistContract(
        specialist_id="storyteller",
        product_role="Storyteller",
        responsibilities=(
            "Idea-first discovery with 2-4 high-impact questions",
            "EmotionalSceneProfile (arc, subtext, tone, stakes)",
            "Approval-aware StorytellerProductionHandoff",
            "Format guidance and progressive depth by stage",
        ),
        input_keys=("idea", "attachmentInterpretation", "scene", "mode"),
        output_keys=("emotionalSceneProfile", "questions", "handoff", "formatGuidance", "honestyNotes"),
        may_execute_tools=False,
        aliases=("story_teller", "emotional-storyteller"),
    ),
    "sound-producer": SpecialistContract(
        specialist_id="sound-producer",
        product_role="Sound Producer",
        responsibilities=(
            "SonicConcept and score/ambience/cue/dialogue/mix intent",
            "Coordinate Music Supervisor and Sound Designer (no new providers)",
            "Guided / Creative / Variation sonic modes",
            "Required exchanges with Storyteller, Camera, Editor, VPC, Continuity",
        ),
        input_keys=("emotionalSceneProfile", "unifiedSceneBrief", "mode"),
        output_keys=("sonicConcept", "scoreBrief", "ambience", "cues", "mixIntent", "honestyNotes"),
        may_execute_tools=False,
        aliases=("sound_producer", "sonic-producer"),
    ),
'''
    # Insert before closing of SPECIALIST_CONTRACTS dict — look for virtual-production-coordinator block end
    marker = '"virtual-production-coordinator": SpecialistContract('
    idx = text.find(marker)
    if idx < 0:
        raise SystemExit("VPC contract not found")
    # Find the end of that contract entry: next "    ),\n" after aliases for vpc then likely closing
    # Simpler: insert before ROLE_ALIASES or PRODUCT_ROLE_TO_ID if present
    for anchor in ("PRODUCT_ROLE_TO_SPECIALIST", "ROLE_TO_SPECIALIST", "PRODUCT_ROLE_MAP", "def resolve_specialist"):
        aidx = text.find(anchor)
        if aidx > 0:
            # walk back to previous newline that starts a dict close or next entry
            # Insert before the last `}` of SPECIALIST_CONTRACTS — find `}\n\n` after vpc
            close = text.rfind("}", 0, aidx)
            # find the SPECIALIST_CONTRACTS closing brace more carefully
            break
    # Append contracts before the closing of the contracts dict that contains vpc
    # Find pattern after vpc contract
    m = re.search(
        r'("virtual-production-coordinator": SpecialistContract\([\s\S]*?aliases=\([^)]*\),\n    \),\n)',
        text,
    )
    if not m:
        # try without trailing comma variants
        m = re.search(
            r'("virtual-production-coordinator": SpecialistContract\([\s\S]*?\n    \),\n)',
            text,
        )
    if not m:
        raise SystemExit("Could not locate VPC contract end for insert")
    text = text[: m.end()] + insert + text[m.end() :]
    # Also add product role aliases if map exists
    if "Story Analyst" in text and '"Storyteller"' not in text:
        text = text.replace(
            '"Story Analyst": "story-analyst",',
            '"Story Analyst": "story-analyst",\n    "Storyteller": "storyteller",\n    "Sound Producer": "sound-producer",',
        )
    write(path, text)


def patch_selector() -> None:
    path = ROOT / "studio-api" / "app" / "codirector" / "intelligence" / "specialist_selector.py"
    text = read(path)
    if '"unified_experience"' in text or '"storyteller_discovery"' in text:
        print("selector already patched")
        return
    text = text.rstrip() + """

_INTENT_SPECIALISTS.update(
    {
        "storyteller_discovery": (
            "storyteller",
            "sound-producer",
            "director",
            "cinematographer",
            "continuity-analyst",
        ),
        "sound_production": (
            "sound-producer",
            "music-supervisor",
            "sound-designer",
            "storyteller",
            "editor",
        ),
        "unified_experience": (
            "storyteller",
            "sound-producer",
            "cinematographer",
            "editor",
            "virtual-production-coordinator",
            "continuity-analyst",
            "director",
        ),
    }
)
_CONTINUITY_INTENTS = frozenset(set(_CONTINUITY_INTENTS) | {"storyteller_discovery", "unified_experience", "sound_production"})
"""
    write(path, text)


def patch_dag() -> None:
    path = ROOT / "studio-api" / "app" / "codirector" / "m211" / "dag.py"
    text = read(path)
    if "storyteller" in text and "sound-producer" in text:
        print("dag already patched")
        return
    # Replace story-analyst node with storyteller first, keep story-analyst optional? Plan says first-class Storyteller.
    # Extend pipeline: insert storyteller early and sound-producer before sound-designer
    text = text.replace(
        'DagNode("story", "story-analyst", "Story Analyst"),',
        'DagNode("storyteller", "storyteller", "Storyteller"),\n'
        '    DagNode("story", "story-analyst", "Story Analyst", optional=True),',
    )
    text = text.replace(
        'DagNode("sound", "sound-designer", "Sound Supervisor"),',
        'DagNode("sound_producer", "sound-producer", "Sound Producer"),\n'
        '    DagNode("sound", "sound-designer", "Sound Supervisor"),',
    )
    write(path, text)


def patch_web_api() -> None:
    path = ROOT / "studio-web" / "src" / "api.ts"
    text = read(path)
    if "m214Status" in text:
        print("web api already patched")
        return
    # health type
    text = text.replace(
        "virtualEnvironmentStudioEnabled?: boolean;",
        "virtualEnvironmentStudioEnabled?: boolean;\n      unifiedExperienceEnabled?: boolean;",
    )
    # methods near m213Status
    if "m213Status:" in text:
        text = text.replace(
            "m213Status: () => req<Record<string, unknown>>(\"/api/codirector/m213/status\"),",
            """m213Status: () => req<Record<string, unknown>>("/api/codirector/m213/status"),
  m214Status: () => req<Record<string, unknown>>("/api/codirector/m214/status"),
  m214Idea: (body: { projectId: string; idea: string; preferredFormat?: string }) =>
    req<Record<string, any>>("/api/codirector/m214/idea", { method: "POST", body: JSON.stringify(body) }),
  m214Stage: (body: { projectId: string; stage: string }) =>
    req<Record<string, any>>("/api/codirector/m214/stage", { method: "POST", body: JSON.stringify(body) }),
  m214Media: (projectId: string) =>
    req<{ items: any[]; groups: Record<string, any[]> }>(`/api/codirector/m214/media/${projectId}`),
  m214HitchhikerSmoke: (body: { projectId: string }) =>
    req<{ cards: any[] }>("/api/codirector/m214/hitchhiker/smoke", { method: "POST", body: JSON.stringify(body) }),
  m214Approvals: (body: { projectId: string; pending?: Record<string, unknown> }) =>
    req<Record<string, any>>("/api/codirector/m214/approvals", { method: "POST", body: JSON.stringify(body) }),
  m214Plan: (projectId: string) => req<Record<string, any>>(`/api/codirector/m214/plan/${projectId}`),
  m214Session: (projectId: string) => req<Record<string, any>>(`/api/codirector/m214/session/${projectId}`),""",
        )
    write(path, text)


def patch_types() -> None:
    path = ROOT / "studio-web" / "src" / "types.ts"
    text = read(path)
    if "unifiedExperienceEnabled" in text:
        print("types already patched")
        return
    text = text.replace(
        "virtualEnvironmentStudioEnabled?: boolean;",
        "virtualEnvironmentStudioEnabled?: boolean;\n    unifiedExperienceEnabled?: boolean;",
    )
    write(path, text)


def patch_session() -> None:
    path = ROOT / "studio-web" / "src" / "components" / "CoDirector" / "CoDirectorSession.tsx"
    text = read(path)
    if "unifiedExperienceEnabled" in text:
        print("session already patched")
        return
    text = text.replace(
        "  productionIntelligenceEnabled: boolean;\n",
        "  productionIntelligenceEnabled: boolean;\n  unifiedExperienceEnabled: boolean;\n",
    )
    text = text.replace(
        "      productionIntelligenceEnabled: Boolean(providerHealth?.productionIntelligenceEnabled),\n",
        "      productionIntelligenceEnabled: Boolean(providerHealth?.productionIntelligenceEnabled),\n"
        "      unifiedExperienceEnabled: Boolean(providerHealth?.unifiedExperienceEnabled),\n",
    )
    write(path, text)


def patch_shell() -> None:
    path = ROOT / "studio-web" / "src" / "components" / "CoDirector" / "CoDirectorShell.tsx"
    text = read(path)
    if "UnifiedExperienceWorkspace" in text:
        print("shell already patched")
        return
    text = text.replace(
        'import type { CoDirectorDisplayMode } from "./types";\n',
        'import type { CoDirectorDisplayMode } from "./types";\n'
        'import { UnifiedExperienceWorkspace } from "./UnifiedExperienceWorkspace";\n'
        'import "./m214-unified.css";\n',
    )
    text = text.replace(
        "  const { contextPanelOpen, uiContext, plan, attachments } = useCoDirectorSession();\n",
        "  const { contextPanelOpen, uiContext, plan, attachments, unifiedExperienceEnabled } = useCoDirectorSession();\n",
    )
    text = text.replace(
        '        <div className="codirector-main">\n          <CoDirectorConversation compactWelcome={mode === "popup"} />\n          <CoDirectorComposer />\n        </div>\n',
        '        <div className="codirector-main">\n'
        "          {unifiedExperienceEnabled ? (\n"
        "            <UnifiedExperienceWorkspace\n"
        '              projectId={uiContext.projectId || uiContext.projectName || "default"}\n'
        "              enabled={Boolean(unifiedExperienceEnabled)}\n"
        "            />\n"
        "          ) : (\n"
        "            <>\n"
        '              <CoDirectorConversation compactWelcome={mode === "popup"} />\n'
        "              <CoDirectorComposer />\n"
        "            </>\n"
        "          )}\n"
        "        </div>\n",
    )
    write(path, text)


def patch_chrome() -> None:
    path = ROOT / "studio-web" / "src" / "components" / "dashboard" / "StudioChrome.tsx"
    text = read(path)
    if "unifiedExperienceEnabled" in text:
        print("chrome already patched")
        return
    text = text.replace(
        "    virtualEnvironmentStudioEnabled?: boolean;\n",
        "    virtualEnvironmentStudioEnabled?: boolean;\n    unifiedExperienceEnabled?: boolean;\n",
    )
    write(path, text)


def main() -> None:
    patch_feature_flags()
    patch_migrations_init()
    patch_codirector_router()
    patch_main()
    patch_health_api()
    patch_registry()
    patch_contracts()
    patch_selector()
    patch_dag()
    patch_web_api()
    patch_types()
    patch_session()
    patch_shell()
    patch_chrome()
    print("wiring complete")


if __name__ == "__main__":
    main()
