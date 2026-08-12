# Co-Director Capability Matrix

**Branch:** `feature/ai-guided-setup`  
**Audit date:** 2026-08-02  
**Foundational contract:** Receive → perceive → understand → retrieve → assimilate → decide → respond → inquire → act → remember  
**Statuses:** `PASS` | `PARTIAL` | `FAIL` | `NOT IMPLEMENTED` | `NOT TESTED`

Do not mark PASS from code inspection alone when live testing is possible.

| Capability | Expected behavior | Current implementation | Live result | Gap | Priority | Test | Status |
|---|---|---|---|---|---|---|---|
| Receive short text | Complete text reaches intelligence layer | Composer → session → `/api/codirector/chat/stream` | Short turns persist and receive replies | None critical | P0 | Playwright foundational | PASS |
| Receive long-form / multi-paragraph | Full content preserved; truncation policy known | Message sanitize/limits in wiki path; chat stores full user content | Long Dreamweaver intro accepted | No explicit creator-facing truncation disclosure for extreme paste | P1 | Playwright foundational | PASS |
| Receive questions / corrections / approvals | Distinct handling; order preserved | Intent classifier + chat history persistence | Questions answered; corrections accepted | Multi-intent in one message still shallow | P1 | Playwright foundational | PARTIAL |
| Receive direct file attachments | Upload, associate with user message, persist | Composer file input + attachment tray + upload + `attachment_ids` on chat | Image attach + send works; ids reach backend enrichment | Content still also includes `[Attached: …]` text marker | P0 | Playwright media | PARTIAL |
| Receive Library assets | Select from project Library into composer | Large Library browser modal + `addLibraryAssets` | Large modal opens; filters work | Secondary taxonomy filters limited by payload honesty | P0 | Playwright library | PASS |
| Receive microphone / STT | Permission → record → transcript → edit → send | Browser `SpeechRecognition` via `useSpeechToText` | Mocked e2e path works; real device env-dependent | No backend STT; browser API only | P0 | Playwright mic | PARTIAL |
| Understand intent classes | Question ≠ fact; correction; action; continue | `classify_intent` + synthesis response types | Questions not written to Wiki after residue filter | Clarification / continue-explaining barely modeled | P0 | Wiki unit + foundational e2e | PARTIAL |
| Retrieve conversation history | Recent turns available to intelligence | Chat request sends full transcript messages to provider | Live chat turns include prior messages | Intelligence specialist path still compiles current user message primarily | P0 | Architecture audit | PARTIAL |
| Retrieve Wiki / Bible / plans | Relevant only; project-scoped | Bible excerpt + compact Wiki snapshot now injected into chat and intelligence context | Wiki snapshot enrichment present | Deep selective retrieval / corrections supersession still shallow | P0 | Unit + architecture | PARTIAL |
| Assimilate / synthesize | Connect facts; avoid duplicates; surface conflicts | Wiki derives proposed entries from user lore; decisions separate | Lore appears as proposed; residue filtered | Weak contradiction detection; append-style Wiki | P1 | Wiki unit + foundational e2e | PARTIAL |
| Decide response mode | Ack / ask / recommend / act — not one pattern | Synthesis chooses answer/clarification/warning/recommendation | Canned Next filler removed | Inquiry still underused | P1 | Synthesis unit | PARTIAL |
| Converse naturally | Project-specific; no scores/JSON/tools | Mock/heuristic providers still common in e2e | Defective `Continue with the recommended direction` removed from synthesis | Live quality depends on provider; confidence still internal | P0 | Playwright foundational | PARTIAL |
| Inquire intelligently | One useful question; skip when not needed | Clarification mostly empty-input / needsClarification flag | Often recommends without a targeted gap question | Intelligent inquiry policy missing | P0 | Conversation audit | FAIL |
| Recommend | Specific, stage-aware, no confidence leak | Specialist recommendations + synthesis | Generic canned storyboard package removed | Fallback recommendations still shallow under mock | P1 | Synthesis unit | PARTIAL |
| Act (tools) | Correct tool; persist before success | Tool registry + approval gates | Existing tool e2e coverage | Out of this audit’s deep retest | P1 | Existing tools specs | PARTIAL |
| Separate conversation from Wiki | No questions/commands/greetings as canon | `_is_conversation_residue` filter in `wiki.py` | Question excluded from Wiki JSON | Commands with long lore still enter (by design) | P0 | `test_codirector_wiki_residue.py` | PASS |
| Classify knowledge state | confirmed / proposed / unresolved / approved / rejected / superseded | Wiki entries use confirmed/proposed; decisions stored | Proposed for user lore; confirmed for project title/type | Missing rejected/superseded/reference-only lifecycle | P1 | Wiki inspection | PARTIAL |
| Project-scoped learning | Corrections reflected later; no cross-project leak | Project-bound conversation + Wiki | Temp projects isolated in e2e | Learning weak because history/Wiki not in retrieve | P0 | Playwright isolation via temp projects | PARTIAL |
| Continuity conflicts | Flag contradictions; ask when needed | Continuity specialist exists in priority chain | Not certified in this pass for rich conflicts | No strong creator-facing continuity UX | P2 | NOT TESTED deeply | PARTIAL |
| Vision cognition | Perceive image when available; honest unavailable | Separate vision stack; chat/intelligence get honest “perception not performed” metadata | Honesty path present; no ML perception in main chat | True vision cognition still unavailable | P0 | Playwright media (honesty) | PARTIAL |
| Audio cognition | Classify role; no false transcript claims | Attachable; metadata; no chat cognition | Association only | No speech/music analysis in chat | P1 | Playwright media | PARTIAL |
| Video cognition | Reference vs final; motion when supported | Attachable; no chat cognition | Association only | No frame/motion analysis in chat | P1 | Playwright media | PARTIAL |
| Honest activity | Only real steps | Activity labels exist in session/stream | Not fully audited against fabricated steps | Risk of over-claiming vision/Wiki steps | P1 | Media e2e | PARTIAL |
| Failure recovery | Truthful errors; no false success | Error cards + retry for provider failures | Existing reliability suite | Vision/STT/Wiki failure matrix incomplete | P1 | chat-reliability + mic denied | PARTIAL |
| Performance | Measure real latency; no fake delays | No fake delays added | Not fully instrumented in this audit | Need snapshot timings in report | P2 | Manual / future | NOT TESTED |
| Library browser UX | Large modal; All default; filters; a11y basics | Rewritten `CoDirectorAssetPicker` + CSS | Width ≥700; All/Images/Video/Audio/Documents | Characters/Locations/etc. omitted (honest) | P0 | Playwright library | PASS |
| Viewport lock | ~90vw/90vh, ~5% margins; page not scrolling | `app-shell-fixed` + framed fullscreen page | Framing asserted in foundational e2e | Ultrawide/4K screenshot matrix not fully captured | P0 | Playwright foundational | PASS |

## Critical blockers for full GO

1. Intelligent inquiry policy is effectively missing (Inquire FAIL).
2. True ML vision / audio / video cognition is not wired into main chat (honesty PARTIAL only).
3. Attachments still also flatten to `[Attached: …]` text markers (structured ids now also sent).
4. Continuity / supersession / knowledge-state lifecycle incomplete.

## Repairs completed in this audit wave

- Large Project Library browser modal (All / Images / Video / Audio / Documents).
- Co-Director viewport lock (`app-shell-fixed`, framed workspace).
- Synthesis: removed canned “Continue with the recommended direction” Next filler and hardcoded storyboard package.
- Wiki: filter questions/greetings/short commands from canon candidates.
- STT: richer states, cancel, creator-facing errors, elapsed listening indicator; audio accept on file input.
- Chat + intelligence enrichment: Project Wiki snapshot + honest attachment metadata via `attachment_ids`.
- Playwright suites + Wiki residue + attachment honesty unit tests authored.
- Live Beta Playwright: **7/7 passed** (`ADEPT_BETA_TARGET=1`).
