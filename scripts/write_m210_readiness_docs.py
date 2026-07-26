#!/usr/bin/env python3
"""Write M2.9->M2.10 readiness documentation as UTF-8."""
from __future__ import annotations

import hashlib
import json
import platform
import subprocess
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TODAY = date.today().isoformat()


def utf8_write(path: Path, text: str) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    data = text.replace("\r\n", "\n")
    if not data.endswith("\n"):
        data += "\n"
    raw = data.encode("utf-8")
    path.write_bytes(raw)
    return hashlib.sha256(raw).hexdigest()


def git(*args: str) -> str:
    try:
        return subprocess.check_output(
            ["git", *args], cwd=ROOT, text=True, stderr=subprocess.DEVNULL
        ).strip()
    except Exception:
        return "UNKNOWN"


def main() -> None:
    branch = git("branch", "--show-current") or "UNKNOWN"
    sha = git("rev-parse", "HEAD") or "UNKNOWN"
    baseline_path = ROOT / "config/capabilities/adept-ui-v1.0-native.json"
    baseline = json.loads(baseline_path.read_text(encoding="utf-8"))
    baseline_hash = (
        ROOT / "config/capabilities/adept-ui-v1.0-native.sha256"
    ).read_text(encoding="utf-8").strip()

    node = subprocess.getoutput("node -v") or "UNKNOWN"
    npm = subprocess.getoutput("npm -v") or "UNKNOWN"
    py = sys.version.split()[0]

    env_md = f"""# M2.10 Native Environment Baseline

**Status:** Readiness artifact only -- does not authorize M2.10 discovery.  
**Audit date:** {TODAY}  
**Branch:** `{branch}`  
**Commit SHA:** `{sha}`  

This baseline describes the production environment M2.10 must not mutate without approval.
Fields that cannot be verified in this readiness pass are marked **UNKNOWN**.

## Host

| Field | Value |
| --- | --- |
| Operating system | {platform.system()} {platform.release()} |
| GPU | UNKNOWN |
| VRAM | UNKNOWN |
| RAM | UNKNOWN |
| Storage expectations | UNKNOWN |

## Toolchain

| Field | Value |
| --- | --- |
| Python version | {py} |
| Node version | {node} |
| npm version | {npm} |
| Package manager (JS) | npm |
| CUDA version | UNKNOWN |
| PyTorch version | UNKNOWN |

## ComfyUI / local generation

| Field | Value |
| --- | --- |
| ComfyUI installation path | UNKNOWN (machine-local; not committed) |
| ComfyUI commit or version | UNKNOWN |
| Approved custom nodes | UNKNOWN (see live Comfy install; not inventoried in this pass) |
| Approved model files | Z-Image Turbo path used in M2.7.1 acceptance (`z_image_turbo_bf16.safetensors`) -- absolute machine paths not recorded here |
| Model hashes | UNKNOWN |

## Native adapters

| Field | Value |
| --- | --- |
| Workflow adapters | See `config/capabilities/adept-ui-v1.0-native.json` `workflowAdaptersNative` |
| Provider adapters | `comfy.local`, `vision.local`; optional `fal.api` |
| Active ports (typical) | API UNKNOWN; Comfy often `8188`; web Vite UNKNOWN |
| Environment variables (names only) | `STUDIO_FEATURE_*`, `ADEPT_MOCK_IMAGEGEN` (must remain unset for production acceptance), Comfy URL vars as configured locally |
| Feature flags | `unified_generate`, `story`, `scene_sheets`, `jobs`, `resources`, `future_rollout`, `codirector_intelligence_v2`, `vision_validation_v1`, `timeline_references_v1`, `production_executive_v1` (all default off) |

## Schema versions

| Field | Value |
| --- | --- |
| Database migration head | `M011` (`production_contexts`; registry skips unused `M009`) |
| Production Job schema | M008 executive tables + M011 production context |
| Validation schema | M006 vision |
| Asset schema | `assets` + `asset_versions` / `asset_edges` |
| Timeline schema | Director scene JSON + M007 timeline reference bindings |
| Native capability baseline hash | `{baseline_hash}` |

## Secrets policy

- Secret **values** are not recorded in this baseline.
- Credential files, API keys, and private production assets must not be committed.
"""

    contracts_md = f"""# M2.10 Add-on Integration Contract Readiness

**Status:** Architecture readiness note -- **no add-ons discovered or installed**.  
**Audit date:** {TODAY}  
**Commit SHA:** `{sha}`  

This document records whether Adept UI has clear contracts for future M2.10 integrations.
Missing contracts are listed as **M2.10 prerequisites**, not implemented here.

## Categories

| Category | Registration | Lifecycle | M2.7 jobs | Config | Health | Capability declaration | Validation | Approval | Uninstall/rollback | Audit | UI | Feature flag |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Provider | PARTIAL (`providers/contracts.py` Protocols) | MISSING registry | PARTIAL (executive image adapter only) | PARTIAL | PARTIAL | VIA capability registry | PARTIAL | YES (Bible/proposal) | MISSING | PARTIAL | PARTIAL | YES (env flags) |
| Workflow adapter | YES (`workflows/registry.py`) | PARTIAL | PARTIAL | YES | VIA readiness caps | YES | PARTIAL | YES | MISSING | PARTIAL | PARTIAL | PARTIAL |
| Deterministic processor | MISSING generic | MISSING | MISSING | MISSING | MISSING | MISSING | MISSING | YES (required) | MISSING | MISSING | MISSING | MISSING |
| Validator | YES (M2.5 vision engine) | YES | YES (`validate`) | PARTIAL | PARTIAL | YES | YES (owns pending) | N/A | N/A | YES | YES | `VISION_VALIDATION_V1` |
| Co-Director intelligence source | PARTIAL (tools/intelligence) | PARTIAL | PARTIAL | PARTIAL | PARTIAL | PARTIAL | PARTIAL | YES (no silent approve) | MISSING | PARTIAL | YES | `CODIRECTOR_INTELLIGENCE_V2` |
| Timeline utility | PARTIAL (director/editor APIs) | PARTIAL | MISSING executive | YES | PARTIAL | PARTIAL | PARTIAL | WEAK (direct apply) | PARTIAL | PARTIAL | YES | `TIMELINE_REFERENCES_V1` |
| Asset processor | PARTIAL (`asset_graph`) | PARTIAL | PARTIAL | PARTIAL | PARTIAL | PARTIAL | PARTIAL | YES | PARTIAL | PARTIAL | PARTIAL | PARTIAL |
| Model package | PARTIAL (setup packs / source manager) | PARTIAL | setup ops not M2.7 | YES packs | YES probes | readiness caps | N/A | install gated in source manager | PARTIAL | PARTIAL | YES Source Manager | PARTIAL |
| Custom node package | PARTIAL (setup/source manager) | PARTIAL | setup ops | PARTIAL | PARTIAL | extensions ready | N/A | install gated | PARTIAL | PARTIAL | YES | PARTIAL |

## Security boundaries observed

- Discovery metadata must not execute repository code (M2.8/M2.10 requirement; discovery not started).
- Source URLs treated as untrusted input (required; not exercised by M2.10 discovery yet).
- No install / sandbox / production promotion without explicit approval (M2.7.1 Bible path proven; add-on promotion path not Accepted -- M2.8 sandbox not Accepted).
- No write outside approved sandbox paths -- **BLOCKED/MISSING** until M2.8 sandbox Accepted.
- Secrets must not appear in logs/manifests -- policy documented; continuous enforcement UNKNOWN.
- No automatic license acceptance -- required prerequisite.
- No silent custom-node / model / workflow / provider-priority replacement -- required prerequisite.
- No Production Bible mutation from discovery -- discovery not present; Bible mutations remain proposal/approval-gated.
- No add-on may mark its own output approved or clear M2.5 `visualValidationPending` -- M2.5 ownership remains authoritative for vision.

## M2.10 prerequisites (contracts)

1. Formal add-on registration schema distinct from native baseline (`source: addon` vs `native`).
2. Human-gated sandbox install/execute/promote lifecycle (depends on **Accepted M2.8**).
3. Uninstall/rollback contract with inventory diffs against this checkpoint.
4. Explicit prohibition of add-on override of accepted native capability IDs without proposal.
5. Deterministic processor registration + M2.7 job handler binding.
6. License/trust/maintenance fields on candidate records (analysis only until approved).
"""

    closure_md = f"""# M2.9 Closure and M2.10 Readiness

**Audit date:** {TODAY}  
**Branch:** `{branch}`  
**Commit SHA:** `{sha}`  

## Executive summary

This readiness pass audited the repository against the M2.9 Complete Production Suite planning requirements and the requested M2.9 -> M2.10 transition.

**Honest milestone state:**

| Milestone | Status |
| --- | --- |
| M2.7 / M2.7.1 Production Executive | **Accepted** |
| M2.8 Capability Intelligence Foundation | **Planning only -- not Accepted** |
| M2.9 Complete Native Production Suite | **Planning only -- not Accepted** |
| M2.10 Add-on Discovery / v1.1 Integration | **Not started** |
| M3.0 Full Playwright Qualification | **Not started** |

Because READY FOR M2.10 requires M2.9 Accepted (and M2.8 Accepted as prerequisite to M2.9), the verdict of this pass is **NOT READY FOR M2.10**.

Roadmap principle recorded:

```text
M2.9 completes the native suite.
M2.10 selectively expands and freezes Adept UI v1.1.
M3.0 proves the frozen v1.1 system works end to end.
```

Current chain:

```text
M2.7.1 Accepted -> M2.8 (not Accepted) -> M2.9 (not Accepted) -> M2.10 (not started) -> M3.0 (not started)
```

## Architecture audit -- section status

| Section | Classification | Notes |
| --- | --- | --- |
| Image Production | CONNECTED | M2.7 closed-loop + Comfy/Z-Image; M2.9 prompt extras (inpaint/outpaint/upscale) incomplete |
| Frame Production | PARTIALLY CONNECTED | Frame UI + render queue; no `frame.*` capabilities / M2.7 handlers |
| Text-to-Video / Image-to-Video | PARTIALLY CONNECTED | UI + queue/fal/local workflows; not executive-orchestrated |
| Director Timeline Generation | PARTIALLY CONNECTED | Propose/apply + director APIs; not full M2.9 suite |
| Lip Sync Timeline | PARTIALLY CONNECTED | Tracks + LatentSync queue; no M2.7 lipsync job |
| Mouth Rectangle Control | PARTIALLY CONNECTED | Manual ROI/track UI; `mouth.*` caps missing |
| Audio Production | UI ONLY | Upload/handoff stub; generation missing |
| Editing and Post-Production | PARTIALLY CONNECTED | Editor sequences persist; export depth incomplete |
| SFX | UI ONLY | Placement tracks only; generation missing |
| Music | UI ONLY | Placement tracks only; generation missing |
| Rendering | PARTIALLY CONNECTED | Render/export jobs exist; not M2.7 executive |
| Co-Director Production Control | CONNECTED | Flag-gated Accepted image closed-loop only |

## Counts

| Metric | Count |
| --- | --- |
| Native capability baseline records | {baseline["counts"]["capabilities"]} |
| Accepted (baseline) | {baseline["counts"]["accepted"]} |
| Conditional | {baseline["counts"]["conditional"]} |
| Unavailable | {baseline["counts"]["unavailable"]} |
| Runtime registry IDs exported | {baseline["counts"]["registryIdsExported"]} |
| Provider kinds (built-in local) | 2 (`comfy.local`, `vision.local`) |
| Optional external API | 1 (`fal.api`) |
| Workflow adapters (native list) | {len(baseline["workflowAdaptersNative"])} |
| M2.7 executive job handlers | {len(baseline["executiveJobHandlers"])} |

## Coverage statements

| Area | Finding |
| --- | --- |
| Validation ownership | M2.5 owns `visualValidationPending` clearing (with `planId`) |
| Approval / Bible | `ProposalService.approve` gates canon; executive does not self-approve |
| Asset versioning | `asset_versions` / Bible versions exist; suite-wide M2.9 version model incomplete |
| Timeline coverage | Partial; reference bindings M007 present |
| Production Bible coverage | Connected for M2.7.1 image closed-loop |
| Restart persistence | Proven for M2.7 executive jobs in M2.7.1; not proven for full M2.9 suite |
| Mock-only accepted sections | None claimed Accepted beyond M2.7.1 evidence; Audio/SFX/Music remain UI ONLY |
| Duplicate execution architecture | Legacy `queue_worker` coexists with M2.7 executive -- residual risk for M2.9 |

## Mock-only / gaps / blockers

### Blockers for READY FOR M2.10

1. M2.8 not Accepted (sandbox, routing, Virtual Stage, Location Spin, Model Radar).
2. M2.9 not Accepted (native suite incomplete vs planning prompt).
3. No M2.9 section Playwright suite (`*m29*` specs absent).
4. Multiple departments UI ONLY or PARTIALLY CONNECTED.
5. M2.9 feature flags not implemented per section.

### Unresolved gaps

- No unified M2.7 job types for video, lipsync, audio, music, sfx, render.
- Timeline apply bypasses Bible proposal bus.
- Virtual Stage declared capability unavailable.
- Add-on registration/uninstall contracts incomplete (see add-on contracts doc).

## Security and approval findings

- Bible mutation remains approval-gated (Accepted M2.7.1 path).
- Vision pending clear remains M2.5-owned.
- Add-on discovery/install/promote paths are **not** Accepted; M2.8 sandbox required first.
- Do not weaken security to pass readiness.

## Tests

See completion summary in the final commit notes / Phase I output. Exact pass/fail/skip counts are recorded when the readiness test command is run.

## Verdict

# NOT READY FOR M2.10

Reasons: M2.9 is not Accepted; M2.8 is not Accepted; native suite audit shows multiple non-CONNECTED departments; readiness artifacts are produced for baseline/comparison only.

**This task does not start M2.10 discovery.**  
**This task does not claim Adept UI v1.1 exists.**  
**This task does not begin M3.0.**

## Related artifacts

- `config/capabilities/adept-ui-v1.0-native.json`
- `docs/codirector/m2.10-native-environment-baseline.md`
- `docs/codirector/m2.10-preflight-checkpoint.md`
- `docs/codirector/m2.10-addon-integration-contracts.md`
- `docs/codirector/m2.10-prompt.md`
- `docs/codirector/m2.9-prompt.md` (handoff retargeted to M2.10)
"""

    checkpoint_md = f"""# M2.10 Preflight Checkpoint

**Purpose:** Rollback / diff anchor before any authorized M2.10 work.  
**Created:** {TODAY}  
**Does not authorize discovery.**

## Identity

| Field | Value |
| --- | --- |
| Branch | `{branch}` |
| Commit SHA | `{sha}` |
| Database migration head | `M011` |
| Native capability baseline hash | `{baseline_hash}` |
| Environment baseline path | `docs/codirector/m2.10-native-environment-baseline.md` |
| Closure report | `docs/codirector/m2.9-closure-and-m2.10-readiness.md` |
| Verdict at checkpoint | NOT READY FOR M2.10 |

## Inventories (references, not binaries)

| Inventory | Location / note |
| --- | --- |
| Native capabilities | `config/capabilities/adept-ui-v1.0-native.json` |
| Workflow adapters | baseline `workflowAdaptersNative` + `studio-api/app/workflows/registry.py` |
| Provider adapters | baseline `providerKinds` + `studio-api/app/providers/contracts.py` |
| Approved models | Machine-local; M2.7.1 used Z-Image Turbo -- hashes UNKNOWN here |
| Approved custom nodes | UNKNOWN / machine-local |
| Feature-flag state | Defaults off in `studio-api/app/feature_flags.py` |
| Known accepted limitations | M2.7.1 gaps listed in `M2.7.1_ACCEPTANCE_REPORT.md` |

## Rules

- Do not copy secrets or large model binaries into the repository.
- Any M2.10 change must be diffable against this checkpoint.
- Product must authorize M2.10 before discovery begins.
"""

    m210_prompt = f"""# Co-Director M2.10 -- Add-on Discovery and Adept UI v1.1 Integration

**Status:** Planning prompt only -- **not started**.  
**Do not begin discovery, GitHub/HF scanning, downloads, installs, sandbox execution, integration, or promotion until product explicitly authorizes M2.10.**

## Prerequisites

- M2.7 / M2.7.1 remains **Accepted**
- M2.8 Capability Intelligence Foundation is **Accepted**
- M2.9 Complete Native Production Suite is **Accepted**
- Native capability baseline exists: `config/capabilities/adept-ui-v1.0-native.json`
- Preflight checkpoint recorded: `docs/codirector/m2.10-preflight-checkpoint.md`
- Current readiness verdict as of {TODAY}: **NOT READY FOR M2.10** (see closure report)

## Roadmap position

```text
M2.7.1 Accepted Production Executive
M2.8 Capability Intelligence Foundation (Accepted required)
M2.9 Complete Native Production Suite (Accepted required)
M2.10 Add-on Discovery and Adept UI v1.1 Integration  <-- this milestone
M3.0 Full Playwright Production Qualification
```

Principle:

```text
M2.9 completes the native suite.
M2.10 selectively expands and freezes Adept UI v1.1.
M3.0 proves the frozen v1.1 system works end to end.
```

## Scope (when authorized)

- GitHub and Hugging Face discovery (metadata only until approved)
- Candidate review
- Compatibility, trust, maintenance, and license analysis
- Human-approved sandbox evaluation (via Accepted M2.8)
- Selected end-to-end integration
- v1.1 promotion
- Feature freeze

## Hard constraints

- M2.10 must use M2.8 discovery/compatibility/sandbox/approval/routing/promotion architecture.
- M2.10 must not become an unlimited add-on collection phase.
- No repository, model, node, workflow, processor, or provider may be downloaded, installed, executed, integrated, or promoted without the appropriate human approval stage.
- Native baseline capabilities must not be silently overridden by add-ons.
- Production Bible mutations remain proposal/approval-gated.
- M2.5 retains visual validation lifecycle ownership.

## M3.0 must not begin until

- M2.10 is Accepted
- Adept UI v1.1 capability registry is locked
- Provider and workflow versions are frozen
- Database schema is frozen except qualification fixes
- Rollback checkpoint is recorded
- Product explicitly authorizes M3.0

## Related docs

- [m2.9-closure-and-m2.10-readiness.md](./m2.9-closure-and-m2.10-readiness.md)
- [m2.10-preflight-checkpoint.md](./m2.10-preflight-checkpoint.md)
- [m2.10-native-environment-baseline.md](./m2.10-native-environment-baseline.md)
- [m2.10-addon-integration-contracts.md](./m2.10-addon-integration-contracts.md)
- [m2.9-prompt.md](./m2.9-prompt.md)
- [m2.8-prompt.md](./m2.8-prompt.md)
"""

    # Write new docs
    hashes = {}
    hashes["env"] = utf8_write(
        ROOT / "docs/codirector/m2.10-native-environment-baseline.md", env_md
    )
    hashes["contracts"] = utf8_write(
        ROOT / "docs/codirector/m2.10-addon-integration-contracts.md", contracts_md
    )
    hashes["closure"] = utf8_write(
        ROOT / "docs/codirector/m2.9-closure-and-m2.10-readiness.md", closure_md
    )
    hashes["checkpoint"] = utf8_write(
        ROOT / "docs/codirector/m2.10-preflight-checkpoint.md", checkpoint_md
    )
    hashes["m210"] = utf8_write(ROOT / "docs/codirector/m2.10-prompt.md", m210_prompt)

    # Retarget m2.9-prompt handoff language
    p = ROOT / "docs/codirector/m2.9-prompt.md"
    text = p.read_text(encoding="utf-8")
    replacements = [
        (
            "M3.0 must not begin until M2.9 is Accepted",
            "M2.10 must not begin until M2.9 is Accepted; M3.0 must not begin until M2.10 is Accepted",
        ),
        (
            "M3.0 is the **full Playwright production qualification** milestone.",
            "M2.10 is the **add-on discovery and Adept UI v1.1 integration** milestone.\n"
            "- M3.0 is the **full Playwright production qualification** milestone.",
        ),
        (
            "M2.7.1 Accepted -> M2.8 Accepted -> M2.9 Implement suite -> M3.0 Full Playwright qualify",
            "M2.7.1 Accepted -> M2.8 Accepted -> M2.9 Implement suite -> M2.10 Add-on Discovery / v1.1 freeze -> M3.0 Full Playwright qualify",
        ),
        (
            "M2.9 = finish the production platform\nM3.0 = prove the production platform",
            "M2.9 = finish the native production platform\n"
            "M2.10 = selectively expand and freeze Adept UI v1.1\n"
            "M3.0 = prove the frozen v1.1 production platform",
        ),
        (
            "- [ ] M3.0 has not started",
            "- [ ] M2.10 has not started during M2.9\n- [ ] M3.0 has not started",
        ),
        (
            "# 14. M3.0 handoff\n\n"
            "After M2.9 is accepted, prepare the M3.0 qualification plan.\n\n"
            "M3.0 must not become another feature-development milestone.\n\n"
            "Its purpose is:\n\n"
            "```text\n"
            "Full Playwright Production Qualification\n"
            "Cross-system verification\n"
            "Failure injection\n"
            "Recovery testing\n"
            "Migration testing\n"
            "Permission testing\n"
            "Performance testing\n"
            "Stress testing\n"
            "Complete scene production\n"
            "Final release-readiness verdict\n"
            "```\n\n"
            "No large feature should be introduced during M3.0 unless required to repair a qualification failure.\n\n"
            "Do not create an M3.0 planning file until product authorizes the M2.9 -> M3.0 transition.",
            "# 14. M2.10 handoff\n\n"
            "After M2.9 is accepted, product may authorize **M2.10 Add-on Discovery and Adept UI v1.1 Integration**.\n\n"
            "M2.10 must use the discovery, compatibility, sandboxing, approval, routing, and promotion architecture established in M2.8.\n\n"
            "M2.10 must not become an unlimited add-on collection phase.\n\n"
            "No repository, model, node, workflow, processor, or provider may be downloaded, installed, executed, integrated, or promoted without the appropriate human approval stage.\n\n"
            "M3.0 must not begin until:\n\n"
            "- M2.10 is accepted\n"
            "- Adept UI v1.1 capability registry is locked\n"
            "- provider and workflow versions are frozen\n"
            "- database schema is frozen except qualification fixes\n"
            "- rollback checkpoint is recorded\n"
            "- product explicitly authorizes M3.0\n\n"
            "Do not create M2.10 discovery results or M3.0 qualification results during M2.9 implementation.\n\n"
            "See [m2.10-prompt.md](./m2.10-prompt.md).",
        ),
        (
            "Do not begin M3.0 until the complete M2.9 acceptance checklist has been satisfied and product has explicitly authorized the transition.",
            "Do not begin M2.10 until the complete M2.9 acceptance checklist has been satisfied and product has explicitly authorized M2.10.\n"
            "Do not begin M3.0 until M2.10 is Accepted and product has explicitly authorized M3.0.",
        ),
    ]
    for old, new in replacements:
        if old not in text:
            print("WARN missing replacement anchor:", old[:80])
        else:
            text = text.replace(old, new, 1)

    # Related docs footer
    if "m2.10-prompt.md" not in text:
        text = text.rstrip() + (
            "\n- [m2.10-prompt.md](./m2.10-prompt.md) -- next milestone after M2.9 Accepted "
            "(planning only; discovery not started)\n"
            "- [m2.9-closure-and-m2.10-readiness.md](./m2.9-closure-and-m2.10-readiness.md)\n"
        )

    hashes["m29"] = utf8_write(p, text)

    # Cross-link m2.8 and acceptance report
    for rel in [
        "docs/codirector/m2.8-prompt.md",
        "docs/codirector/M2.7.1_ACCEPTANCE_REPORT.md",
    ]:
        path = ROOT / rel
        body = path.read_text(encoding="utf-8")
        if "m2.10-prompt.md" not in body:
            body = body.rstrip() + (
                "\n- [m2.10-prompt.md](./m2.10-prompt.md) -- M2.10 planning prompt "
                "(not started; blocked until M2.8+M2.9 Accepted)\n"
                "- [m2.9-closure-and-m2.10-readiness.md](./m2.9-closure-and-m2.10-readiness.md) "
                "-- readiness verdict\n"
            )
            utf8_write(path, body)
            print("updated", rel)

    print(json.dumps(hashes, indent=2))


if __name__ == "__main__":
    main()
