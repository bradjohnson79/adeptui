# Co-Director Knowledge Foundation — Operational Convergence

**PREDECESSOR — not current 100% authority.** Current 100% certification lives in `docs/release-gate/codirector/CODIRECTOR_100_OPERATIONAL_CONVERGENCE.md`.

**Historical governing document for Co-Director 84 → Operational Knowledge Convergence.**

The remaining score-94 Temporal Continuity / InternVideo3 advisory is owned by the successor:

`docs/release-gate/codirector/CODIRECTOR_VIDEO_INTELLIGENCE_OPERATIONAL_CONVERGENCE.md`

Older knowledge-foundation GO (`CODIRECTOR_ADEPT_SYSTEM_GENERATOR_KNOWLEDGE_FOUNDATION_CERTIFICATION.md`) is **historical for this score**. It certified the corpus; it did not prove routed/landed Status or close the Capability Registry workflow caps.

---

## Identity

| Field | Value |
| --- | --- |
| Project | Korri Anadriya `beffd3d8-791d-4adf-9c4d-681ec9d4efb0` |
| Scene | `d774a22f-2b02-4eb2-b5ab-a98af9ff8f85` — 12B — Quarters Interview |
| Branch | `feat/character-creator-final-closure` |
| HEAD (committed) | `99665cf7` |
| Review URLs | Creator UI `http://127.0.0.1:5173/` · Studio API `http://127.0.0.1:8758/` |
| Co-Director | `http://127.0.0.1:5173/project/beffd3d8-791d-4adf-9c4d-681ec9d4efb0?workspace=codirector&sceneId=d774a22f-2b02-4eb2-b5ab-a98af9ff8f85` |
| Evidence | `.runtime/_cd84_before.json` · `.runtime/_cd84_after.json` |

---

## INITIAL SCORE / STATUS (BEFORE)

| Field | Live value |
| --- | --- |
| Indicator | Degraded |
| Score | **84** |
| Band | Fair |
| Checks | 15 healthy / **2 warning** / 0 blocked |
| Warning 1 | `codirector.grounded_routing` — `routed=false`, `landed=false`, `wanContentNotReimplemented=true` (hardcoded) |
| Warning 2 | `capabilities.registry` — **2 workflow** gaps: `references.ic_lora.ready` (`NOT_CONFIGURED` / `MODEL_MISSING`) and cascaded `references.weighting` |
| Chat | `POST /api/codirector/chat` “What is WAN?” → **HTTP 500** (`_maybe_platform_knowledge_reply` missing) |

---

## What was repaired (reconnect, not rebuild)

### Capability Registry (workflow caps)

- `references.ic_lora.ready` is **OPTIONAL** in `CAPABILITY_POLICY`. Live eval stays `NOT_CONFIGURED` when the LTX 2.3 Ingredients file is missing. **Not** marked `locally_verified`.
- `references.weighting` no longer hard-depends on IC-LoRA. Influence storage is independent of that optional model.
- Registry Status `workflowBlockers` / `workflowBlockerDetails` are **empty** after repair.

### Knowledge routing / landing

- Restored `_maybe_platform_knowledge_reply`, `_is_project_content_question`, and `stream_for_project` from `service.py.delib_bak` without replacing the current chat/grounding path.
- Removed illegal `story_script_context_block` / `inspect_turn_grounding` kwargs that were swallowed as TypeError.
- Shared routing receipt (`knowledgebase/routing_receipt.py`): query, retrieved ids, consumer, timestamp. Written only after a real `knowledge_reply`.
- Status probe **executes** the hook on “What is WAN?”. `routed` / `landed` are measured. `wanContentNotReimplemented` is derived (False when the production spoken card works).

### Project + scene reachability

- Existing Timeline snapshot join now includes Scene Prompt, scene summary, playhead Timed Prompt (bounded), and current take.
- `inspect_turn_grounding` attaches the snapshot whenever a scene is bound (not only `workspace=timeline`).
- Deterministic `grounding_reply` answers scene / characters / environment / generator / what happens / current take from that join.

### Sync chat 500 on content questions

- Restored `_foundation_llm_turn` did not accept `allow_direct_answer` (merge artifact). Call site aligned. “What happens in this scene?” is now answered from the snapshot without a 500.

---

## AFTER — live measured

| Field | Live value |
| --- | --- |
| Indicator | Operational |
| Score | **94** |
| Band | Operational |
| Checks | 16 healthy / **1 warning** / 0 blocked |
| `codirector.grounded_routing` | **healthy** — `routed=true`, `landed=true`, `replyable=true`, `wanSpokenCard=true`, `wanContentNotReimplemented=false` |
| Receipt | consumer `codirector.status.probe`, retrieved `wan-2.2`, spoken card “WAN in Adept is First and Last Frame video…” |
| `capabilities.registry` | **advisory** — `workflowBlockers=[]`. Remaining: `codirector.video_intelligence.ready` (`internvideo3_8b` missing). Designed 94 cap in `weighting.py` (`advisory_issues` → `min(max(score, 85), 94)`). **Bands not weakened.** |

### Chat (HTTP 200, same project + scene)

| Question | Reply |
| --- | --- |
| What is WAN? | WAN in Adept is First and Last Frame video. You need both pictures. It is not text-to-video. |
| What scene are we working on? | We are working on 12B — Quarters Interview. |
| Who are the characters? | Anadriya, Korri, Addex, Cami Briggs, and character_sheet. |
| What environment is assigned? | Anadriya's Quarters. |
| What generator is this scene using? | minimax-h3. |
| What happens in this scene? | Scene 12B summary + `@Anadriya @Korri #AnadriyasQuarters`. 2 MiniMax H3 R2V batches. |
| What is the current take? | `take_ab85f21f7a33` on Batch 1 — Interview through top billing. |

### Stream

`POST /api/codirector/chat/stream` HTTP 200. Assistant event: same WAN spoken card. Not Wide Area Network.

### Production inspect (read-only)

- `GET /api/codirector/projects/{id}/context` — story / script / characters / foundation (Story Complete source `story_entries`, 5 characters).
- `GET /api/codirector/projects/{id}/timeline-context/{sceneId}` — same `sceneId` `d774a22f-…`.
- Scene row engine `minimax-h3` matches chat generator answer.

### Replay

- Conversation `GET` HTTP 200; events persist.
- Receipt files survive API recycle: `data/codirector/knowledge_routing_receipt.json` and project-scoped copy.

### Browser

Vite `:5173` Korri Anadriya Co-Director workspace opened. Chat composer (`Ask Co-Director…`) present. Status chip: Studio API Online, ComfyUI Ready. Browser send of “What is WAN?” was not posted from the automation host; the same turn was proven on live `/chat` and `/chat/stream`.

---

## Tests

`58 passed` — `test_v11_readiness_policy.py`, `test_codirector_platform_knowledge.py`, `test_codirector_story_script_access.py`, `test_active_timeline_scene_snapshot.py`, `test_production_assurance_truth.py`.

---

## Independent review

[Independent review](0dd80f39-989c-44aa-87c8-34d8e5843b2b) returned **READY FOR PRIMARY REVIEW**. Primary re-verified live Status, chat, stream, and production inspect.

---

## R2V / Comfy

R2V law files were **not edited** by this mission. Scene 12B published master was **not** updated.

**COMFY BEFORE:** PID 45624 / health 200  
**COMFY AFTER:** PID 45624 / health 200  
**COMFY RESTARTED?:** NO  
**WHY?:** Knowledge + registry + snapshot only. Studio API recycled via `scripts/restart_studio_api_only.py` (`comfyPidUnchanged=True`).

---

## E2E TRACE

| Stage | Result |
| --- | --- |
| User action | PASS — Co-Director on Korri Anadriya / 12B |
| Frontend | PASS — composer + Status on `:5173` |
| API | PASS — `/chat`, `/chat/stream`, `/status/check` |
| Backend | PASS — hook + `knowledge_reply` + snapshot join |
| Persistence | PASS — conversation events + routing receipt files |
| Runtime | PASS — Comfy untouched; API recycled only |
| Result | PASS — WAN spoken card; scene/cast/env/generator/take |
| Reload | PASS — receipt + Status still routed/landed |
| Downstream | PASS — timeline-context package + project context share sceneId / generator |

---

## Limitations

- Score **94** is the designed ceiling while Temporal Continuity (`internvideo3_8b`) remains an advisory registry gap. Reaching **95 Excellent** requires that review row to be honestly healthy — do not hide it and do not lower the 95 band.
- `project.timeline.propose` remains `DEGRADED` by design (heuristic fallback). It is usable and is not a workflow Status cap.
- Ingredients IC-LoRA remains honestly `NOT_CONFIGURED` / optional.
- Character list includes a `character_sheet` record that exists on the project.
- Working tree is dirty with unrelated Timeline/MAGI/R2V work. This mission’s files are uncommitted.

---

## FINAL VERDICT

**NO-GO** — remaining live check id: `capabilities.registry` (advisory `codirector.video_intelligence.ready` / `internvideo3_8b`). Live score **94 Operational**, below the required **>=95**.

Knowledge routing/landing is proven. The two workflow caps that held the studio at 84 are closed. The 84/95 bands were not weakened.
