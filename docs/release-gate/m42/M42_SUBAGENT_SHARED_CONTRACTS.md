# M42 Subagent Shared Contracts (Frozen)

**Freeze date:** 2026-07-31  
**Change policy:** Change request → impact analysis → primary-agent approval → update this file → notify affected owners.  
**Rule:** Subagents must not invent new shapes or silently rename identifiers.

This document freezes the contracts used by the current Korri / Voice governance sprint. It **references** existing consumer/resolver contracts rather than rewriting them:

| Prior contract | Path |
|---|---|
| W2 Consumer | `docs/release-gate/m42/M42_W2_CONSUMER_CONTRACT.md` |
| W2 Resolver | `docs/release-gate/m42/M42_W2_RESOLVER_CONTRACT.md` |
| W4 Consumer | `docs/release-gate/m42/M42_W4_CONSUMER_CONTRACT.md` |
| W4B Consumer | `docs/release-gate/m42/M42_W4B_CONSUMER_CONTRACT.md` |

---

## 1. Project & library scoping

| Rule | Value |
|---|---|
| Generation scope | Always the open `projectId` |
| Character assets | Stay in that project’s Library |
| Cert project name (stable) | `Korri Character Production` |
| Env overrides | `ADEPT_PROJECT_ID`, `ADEPT_KORRI_PROJECT_NAME` |
| Forbidden | New disposable project per image / sheet / cert run |

---

## 2. Character Creator / visual sheet API

Base: Studio API (beta default `http://127.0.0.1:8758`).

| Method | Path | Purpose |
|---|---|---|
| POST | `/api/projects/{project_id}/characters/seed-korri` | Create/refresh Korri from canon |
| POST | `/api/projects/{project_id}/characters/{character_id}/visual-sheet/generate` | Start pack (`includeDetails`, `includePerformance`) |
| POST | `/api/projects/{project_id}/characters/{character_id}/visual-sheet/advance` | Advance queue/phases |
| GET | `/api/projects/{project_id}/characters/{character_id}/visual-sheet` | Read pack status + `roleAssets` |
| POST | `/api/projects/{project_id}/characters/{character_id}/visual-sheet/owner-approve` | Owner approval |
| GET | `/api/projects/{project_id}/characters/{character_id}/references` | Role-tagged references |

Pack statuses of record include: generating phases → ready for approval → `OWNER_APPROVED`.

Evidence fields expected in cert JSON: `mock: false`, `comfyOk`, `roleAssets` (15 roles for full Korri pack), `ownerApproved`.

---

## 3. Certified image workflows

| Workflow id | Role in Character Creator |
|---|---|
| `zimage.txt2img` | Hero + coverage (text) |
| `zimage.ref_edit` | Details / performance from hero (`sourceAssetId`) |
| `character_sheet` | Sheet assembly where applicable |

Registry of truth: `config/image-workflows/certified-registry.json`.

Fingerprint / builder changes require ComfyWorkflowSubagent ownership + primary approval + registry update. No placeholder graphs on the Character Creator path.

---

## 4. Voice Creator API (W43)

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/projects/{project_id}/characters/{character_id}/voice` | Workspace state |
| POST | `.../voice/design/preview` | Preview design |
| POST | `.../voice/design/generate` | Generate candidates |
| GET | `.../voice/candidates` | List Voice Versions |
| POST | `.../voice/candidates/{id}/{action}` | shortlist / reject / refine |
| POST | `.../voice/approve` | Approve voice |
| POST | `.../voice-profiles/validate-reference` | Clone reference validation |
| POST | `.../voice/clone/generate` | Clone generation |
| GET | `.../voice/provenance` | History (backend `mock` is authoritative) |

UI creative labels (`Voice Versions`, `Pass`, `Approve`, `History`) are presentation-only; API identifiers remain as above.

Co-Director UI actions (frozen names):

* `open_voice_creator`
* `open_voice_performance`

---

## 5. Voice Performance API (W44)

Mounted under voice-performance router (project-scoped in product clients):

| Surface | Path fragment | Purpose |
|---|---|---|
| Gate | `/gate/wave44` | Readiness |
| Parse / validate | `/parse`, `/validate` | Markup |
| Plans | `/plans`, `/plans/{id}/compile`, `/generate` | Performance plan |
| Segments | `/plans/{id}/segments`, retry/approve/reject | Voice Clips |
| Assemble / timeline | `/assemble`, `/place-on-timeline` | Listen → Timeline |
| Character readiness | `/characters/{character_id}/readiness` | Integration flags |

Readiness flags of record: `approvedVoice`, `emotionProfileAttached`, `promptPackageAttached`, `readyForPerformance`.

---

## 6. Asset types & identity roles

Visual-sheet roles (full Korri pack):

`hero_portrait`, `full_body_front`, `full_body_side_left`, `full_body_back`, `closeup_front`, `closeup_side_left`, `closeup_back`, `skin_closeup`, `hair_front`, `hair_side`, `hair_back`, `wardrobe_reference`, `accessory_reference`, `expression_sheet`, `pose_sheet`

Assets must carry `project_id` and link into Character Profile references by `reference_role`.

---

## 7. Feature flags & gate names

| Gate / flag | Notes |
|---|---|
| Character Identity v1 | `STUDIO_FEATURE_CHARACTER_IDENTITY_V1` |
| W43 Character Creator / Voice Creator | Phase reports under `M42_W43_*` |
| W44 Voice Performance | `/gate/wave44` + `M42_W44_*` |
| ADEPT_UI_BETA_RUNTIME | Local beta supervisor |

---

## 8. Error & honesty contracts

* No silent provider switch.
* Production certification evidence requires backend `mock: false` (ignore client-hardcoded mock badges).
* Capability honesty: unavailable providers must surface honestly.
* Failures escalate; do not fake progress bars or mock assets for cert.

---

## 9. Evidence roots

```text
artifacts/m42/governance/korri-e2e/
artifacts/m42/governance/voice-ux/
artifacts/m42/w43/
artifacts/m42/character-creator/
docs/release-gate/m42/subagent-handoffs/
```
