# Co-Director Intelligence Remediation + Frontend E2E — Certification

## CURRENT

```text
GO — CODIRECTOR INTENT FIDELITY + ACTION-FIRST INTELLIGENCE + FRONTEND E2E CERTIFIED
```

Governing document for this milestone. Baseline audit remains historical:
`docs/release-gate/codirector-reasoning/01-INTELLIGENCE_LAYER_MAP.md`
(`READY FOR CODIRECTOR INTELLIGENCE REMEDIATION`).

Preserved (do not treat as reopened):
`GO — CODIRECTOR FULL-STACK MULTIMODAL VISION CERTIFIED`
(`docs/release-gate/codirector/CODIRECTOR_FULLSTACK_VISION_CERTIFICATION.md`).

Live target: local Beta `http://127.0.0.1:8760/` + Studio API `http://127.0.0.1:8758/`.
Project: Schnick Coffee `2347bf46-3762-4763-86c5-4a6032522278`.
Character: Korri `c49371ed-ba6b-4c16-ba98-a8b28b72118b`.

Branch: `feat/voice-studio-identity-and-global-ux`
HEAD: `959be5ad4196b55f5c9a3fd87c5a7fe9516deaaf`
API cert process: `apiStartedAt` `2026-08-20T00:11:02Z` (`apiRevision` `959be5a`)

Law 27: specialized subagents requested `gpt-5.4-medium`; that slug is not on the Task tool list. Subagents E and F used `inherit`.

---

## Verdict

**GO — CODIRECTOR INTENT FIDELITY + ACTION-FIRST INTELLIGENCE + FRONTEND E2E CERTIFIED**

Law observed on live Beta:

```text
COMMAND + SUFFICIENT CONTEXT = ACT
```

Critical smoke (`Create Korri's CRS.`):

```text
speech_act=COMMAND
context_sufficient=true
clarification_required=false
resolved_action=create_character_reference_sheet
capability=character.generate_visual_sheet
job_started=true
PASS — CODIRECTOR INTELLIGENCE REMEDIATION SMOKE
```

Playwright A–I on `ADEPT_BETA_TARGET=1`: **9 passed (5.4m)**; screenshot re-run **9 passed (6.0m)**.

---

## Before / after

| Failure | Before | After |
| --- | --- | --- |
| “Create Korri's CRS.” | Often `UNKNOWN` / questionnaire (“which direction?”, Cyber-Grunge) | `COMMAND` → existing `character_creator.propose_visual_sheet` → job starts. UI: “Creating Korri's character reference sheet now.” |
| “Should we create Korri's CRS?” | Could become an action | `QUESTION` — execute forbidden |
| “Do you have vision?” | Prose / project advice | Deterministic answer from `runtime_capabilities` (no Korri / Schnick) |
| Optional palette / historical art | Blocked or asked branding forks | Not material — ACT with CRS precedence |
| Missing character bind | `VISION_UNAVAILABLE` or silent Korri | ASK: “Which character should I make the reference sheet for?” |
| Next-best-action | Chips during production commands | Suppressed while `speech_act=COMMAND` |
| Retry | Could inherit rejected assistant fork | Resends user text + current attachments / character bind |

---

## Implementation (additive control layer)

No second routing stack. `UnifiedIntent` field names stay frozen.

New modules:

| File | Role |
| --- | --- |
| `studio-api/app/codirector/conversation/foundation/speech_act.py` | `COMMAND \| QUESTION \| CAPABILITY_QUESTION \| DISCUSSION \| CREATIVE_IDEATION` from current user text only. Interrogative `Should we` / `Can you` is not COMMAND. |
| `studio-api/app/codirector/conversation/foundation/runtime_capabilities.py` | Per-turn object: provider, model, `vision_supported`, `vision_active`, `vision_state`, attachments, `degraded` / `degraded_reason`. |
| `studio-api/app/codirector/conversation/foundation/sufficiency.py` | Ask only if required field missing, not resolvable, no safe default, material. Optional aesthetic conflict ignored. |
| `studio-api/app/codirector/conversation/foundation/asset_authority.py` | `ATTACHED_THIS_TURN > APPROVED/ACTIVE CRS > hero_identity > CURRENT profile > CANDIDATE/HISTORICAL/ARCHIVED` |

Wired into existing turns:

- `intent.py` — COMMAND → `REQUEST_GENERATION` / `REQUEST_ACTION`, `should_ask_question=False`, `should_use_tools=True`. EXPLAIN_PROJECT / workflow hold run before speech-act QUESTION/COMMAND so listening turns stay listening. Bare “Create shots.” is not COMMAND (frozen corpus).
- `dialogue_policy.py` — COMMAND + sufficient → `question_budget=0`, EXECUTE, no questionnaires / “Would you like” / branding forks.
- `unified_intent.py` + `capabilities/registry.py` — `character.generate_visual_sheet` (alias `create_character_reference_sheet`) → `character_creator.propose_visual_sheet` / `advance_visual_sheet`. CRS patterns before generic `image.generate`.
- `service.py` / `orchestrate.py` — inject structured turn-control; CAPABILITY_QUESTION short-circuit; COMMAND + missing → deterministic clarification; COMMAND + sufficient + CRS → existing tool with `pre_approved=True`; suppress NBA / `conversation_actions` / next-step options; SSE `speech_act`, `runtime_capabilities`, `context_sufficient`, `vision_active`.
- `vision_input.py` — CRS COMMAND is not a visual-inspection turn (`character reference` removed from inspection lexicon). Vision unit tests not weakened; added negatives for create-CRS phrases.
- Frontend — consume SSE on activity (not creator chrome). Hide action / next-step chips on COMMAND. Retry = `retryLastSend()` (user text only). SSE types added in `api.ts`.

Canonical mutating tool reused: `character_creator.propose_visual_sheet`. Shared visual resolver reused: `studio-api/app/character_identity/visual_context.py`. Character Creator architecture not rebuilt.

---

## Files changed (this milestone)

| Path | Change |
| --- | --- |
| `studio-api/app/codirector/conversation/foundation/speech_act.py` | New |
| `studio-api/app/codirector/conversation/foundation/runtime_capabilities.py` | New |
| `studio-api/app/codirector/conversation/foundation/sufficiency.py` | New |
| `studio-api/app/codirector/conversation/foundation/asset_authority.py` | New |
| `studio-api/app/codirector/conversation/foundation/intent.py` | Speech-act mapping; CRS imperatives; listen-before-question |
| `studio-api/app/codirector/conversation/foundation/dialogue_policy.py` | COMMAND / capability / ideation postures |
| `studio-api/app/codirector/conversation/foundation/schemas.py` | Additive intent fields |
| `studio-api/app/codirector/routing/unified_intent.py` | CRS capability + speech-act gate |
| `studio-api/app/codirector/routing/orchestrator.py` | Sufficiency before classify |
| `studio-api/app/codirector/capabilities/registry.py` | `character.generate_visual_sheet` |
| `studio-api/app/codirector/conversation/orchestrate.py` | Context inject + NBA suppress + SSE |
| `studio-api/app/codirector/service.py` | Caps, short-circuits, CRS dispatch, NBA strip |
| `studio-api/app/codirector/vision_input.py` | CRS command ≠ visual inspection |
| `studio-web/src/api.ts` | New SSE event types |
| `studio-web/src/components/CoDirector/types.ts` | Activity fields (not chrome) |
| `studio-web/src/components/CoDirector/CoDirectorSession.tsx` | SSE consume, NBA ignore, retry |
| `studio-web/src/components/CoDirector/CoDirectorConversation.tsx` | Hide chips on COMMAND; user Retry |
| `studio-api/tests/test_codirector_intelligence_remediation.py` | New |
| `studio-api/tests/fixtures/codirector_reasoning_corpus.json` | New |
| `studio-api/tests/test_codirector_multimodal_vision.py` | CRS-not-inspection negatives |
| `scripts/codirector_intelligence_smoke.py` | New |
| `tests/e2e/codirector/codirector-intelligence-remediation.spec.ts` | New A–I |

---

## Tests (measured)

| Gate | Result |
| --- | --- |
| Intelligence unit + corpus | **13 passed** (`test_codirector_intelligence_remediation.py`) |
| Vision unit regression | **16 passed** (`test_codirector_multimodal_vision.py`) — not weakened |
| Combined intel + vision re-run | **29 passed** |
| Foundational AI + complete companion + ownership corpus | **25 passed** + `test_foundation_agrees_with_unified_on_execution_over_corpus` **1 passed** |
| Earlier combined intel/vision/foundational/companion/ownership | **54 passed** (then EXPLAIN_PROJECT order confirmed) |
| Live smoke | **PASS — CODIRECTOR INTELLIGENCE REMEDIATION SMOKE** (`intel-smoke-ae042509b4`, 48.23s) |
| Playwright A–I | **9 passed (5.4m)**; evidence re-run **9 passed (6.0m)** |
| Beta | Web `http://127.0.0.1:8760/` **200**; `__beta_web_health` **200**; API `http://127.0.0.1:8758/api/health` **200** |

### Playwright matrix

| ID | Case | Result |
| --- | --- | --- |
| A | Capability Q from runtime state | PASS (11.2s / 38.1s) |
| B | Narrow visual Q stays on the image | PASS |
| C | Korri CRS command, no questionnaire | PASS |
| D | CRS result / progress visible | PASS |
| E | Required clarification only (library, no bind) | PASS (after fill-first send + vision-gate + ask short-circuit) |
| F | Optional ambiguity still acts | PASS |
| G | Retry resends user command | PASS |
| H | NBA suppressed on COMMAND | PASS |
| I | Reload + 1920 / 1440 / 1024 / 768 shots | PASS |

---

## E2E TRACE — Korri CRS command

| Stage | Verdict | Evidence |
| --- | --- | --- |
| User action | PASS | “Create Korri's CRS.” + Send |
| Frontend | PASS | `codirector-send-button` → `/api/codirector/chat/stream` |
| API | PASS | SSE `speech_act=COMMAND` |
| Backend | PASS | `character.generate_visual_sheet` / `propose_visual_sheet` |
| Persistence | PASS | Assistant completion persisted; I reload still shows CRS text |
| Runtime | PASS | `execution_status` / job_started |
| Result | PASS | “Creating Korri's character reference sheet now.” + Working card |
| Reload | PASS | Playwright I |
| Downstream | PASS | Character Creator still shows approved Korri CRS (revision 2); no new project spawned |

Saved: `docs/release-gate/codirector-reasoning/evidence/korri-crs-11-step-trace.json`

---

## Frontend evidence

| File | What it shows |
| --- | --- |
| `evidence/intel-A-capability.png` | Vision supported, not active; Visual context · Korri; no speech-act enum chrome |
| `evidence/intel-B-visual-q.png` | Narrow visual question |
| `evidence/intel-C-korri-crs-command.png` | Action-first + `generate_visual_sheet` Working |
| `evidence/intel-D-crs-progress.png` | Progress / result |
| `evidence/intel-E-required-clarification.png` | Library, no bind → which character |
| `evidence/intel-F-optional-ambiguity.png` | Cooler palette still acts |
| `evidence/intel-G-retry.png` | Retry on user bubble |
| `evidence/intel-H-nba-suppressed.png` | No conversation-action chips |
| `evidence/intel-I-responsive-1920.png` | 1920×1080 |
| `evidence/intel-I-responsive-1440.png` | 1440×900 |
| `evidence/intel-I-responsive-1024.png` | 1024×768 |
| `evidence/intel-I-responsive-768.png` | 768×1024 |

---

## Subagents

| ID | Scope | Return |
| --- | --- | --- |
| A–D | Intent / capability / sufficiency / NBA (implementation from isolated root causes) | Completed in control layer |
| E | Live UI / CSS / wiring | `READY FOR PRIMARY REVIEW` — in-IDE browser could not open Character workspace; primary verified shots A–I instead |
| F | Independent final | `READY FOR PRIMARY CERTIFICATION` |

Primary double-check: re-ran intel + vision (29), foundational/companion/ownership (26), smoke file, Playwright 9/9, live health, screenshots A–I, 11-step trace.

---

## Limitations (honest)

- Execution card can still show raw `childjobstatus.completed` (polish; not a questionnaire hijack).
- Header Degraded/Ready chip follows provider health, not SSE `runtime_capabilities.degraded`. Capability answers still use the structured object.
- If the CRS dispatcher throws, the turn can fall through to the LLM path; COMMAND still strips NBA / questionnaires.
- Playwright G clicks Retry only when the control is visible.
- This cert is **local Beta**, not hosted Vercel.
- Working tree contains unrelated dirty files; this report certifies only the intelligence-remediation files above.
- Repeated cert CRS commands start real jobs (`candidateCount` default 1 on propose). They stay in Schnick Coffee / Korri — no disposable project spam.

---

## Manual review

1. Open `http://127.0.0.1:8760/` → Schnick Coffee → Korri.
2. Ask “Do you have vision?” — runtime answer, no branding.
3. Send “Create Korri's CRS.” — one-liner + tool/job; no Cyber-Grunge fork.
4. Library workspace, no character: “Create a character reference sheet.” — asks which character only.
5. Refresh — last CRS turn remains.

Beta left running: `http://127.0.0.1:8760/` (UI), `http://127.0.0.1:8758/` (API).

---

## Final language

```text
GO — CODIRECTOR INTENT FIDELITY + ACTION-FIRST INTELLIGENCE + FRONTEND E2E CERTIFIED
```
