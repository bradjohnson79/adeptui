# Co-Director — Product-Owner Human Experience Review

**Owner-owned.** Do not prefill scores. Agents may prepare scenarios and capture technical evidence only.

**Beta UI:** http://127.0.0.1:8760/  
**Studio API:** http://127.0.0.1:8758/  
**Primary fixture:** The Dreamweaver (or `ADEPT_PROJECT_ID`)  
**Governing report:** [`CO_DIRECTOR_CREATIVE_OPERATING_INTELLIGENCE_COMPLETION_REPORT.md`](./CO_DIRECTOR_CREATIVE_OPERATING_INTELLIGENCE_COMPLETION_REPORT.md)

**Passing threshold (do not lower):**

```text
No score below 4
Overall average at least 4.25
All mandatory Yes/No checks = Yes
```

Until you complete and confirm this scorecard:

```text
PRODUCT-OWNER HUMAN REVIEW: PENDING
FINAL PRODUCT ACCEPTANCE: HOLD
```

---

## 1. Setup

1. Confirm Beta is up (links above).
2. Open **The Dreamweaver** → Co-Director (full workspace).
3. Open **More → Options** and locate **Partnership style** (initiative dial).
4. Keep a notepad or paste evidence below (transcript excerpts, screenshots optional under `artifacts/human-review/`).
5. Prefer natural conversation — do not force engineer workflows.

Optional support: after setup, agents may run  
`npx playwright test tests/e2e/codirector/codirector-creative-operating-human-gate-support.spec.ts` with `ADEPT_BETA_TARGET=1` — this **supports** review; it does **not** replace your scores.

---

## 2. Review scenarios

### A. Quiet Partner (listening)

1. Set initiative to **Quiet Partner**.
2. Paste a flowing story beat (several sentences). Explicitly say you want Co-Director to keep listening / not ask questions yet.
3. Send 2–3 turns of narration without asking for help.

**Expected:** Specific acknowledgement; no interrogation; no “five things next” / treatment push; Project Bible may update quietly; **0 questions** unless clarification is essential.

**Evidence (owner):**

| Field | Notes |
|-------|-------|
| Transcript excerpt | |
| Questions asked (count) | |
| Failure examples observed? | |

**Question quality check (if any question appeared):**

| Prompt | Answer |
|--------|--------|
| Did the question deepen the project? | |
| Was the timing natural? | |
| Would the conversation have been better without it? | |

---

### B. Collaborative Partner

1. Set **Collaborative Partner**.
2. Pause after establishing a character or location; invite light partnership (“what do you notice?”).

**Expected:** Conversational; one or two useful options at natural pauses; high-value question only when it deepens material; not over-directing.

**Evidence:**

| Field | Notes |
|-------|-------|
| Options offered | |
| Felt over-directed? | |

---

### C. Proactive Producer

1. Set **Proactive Producer**.
2. Ask for help developing a missing motivation / structural gap.

**Expected:** One strong missing element; why it matters now; useful next step or preview; one step ahead — not a full production checklist or distant seasons.

**Evidence:**

| Field | Notes |
|-------|-------|
| Missing element named | |
| Overwhelmed / checklist-y? | |

---

### D. Hands-On Co-Creator

1. Set **Hands-On Co-Creator**.
2. Ask for a short draft or preview of a scene / treatment beat.

**Expected:** Concrete proposed/exploratory contribution; authorship or ownership asked before major writing; collaborative, not controlling.

**Evidence:**

| Field | Notes |
|-------|-------|
| Authorship / permission asked? | |
| Contribution marked proposed/exploratory? | |

---

### E. Creative temperature (same project material)

Reuse the same core beat and observe posture across stages (Emerging → Structuring → Refining → Locking → Producing as the project naturally progresses, or by requesting critique / production help).

| Stage | Expected emphasis | Observed |
|-------|-------------------|----------|
| Emerging | Protect momentum; intrigue; few/no questions; no production pressure | |
| Structuring | Treatment/outline/map ok with readiness reason + small preview | |
| Refining | Constructive critique; preserve strengths | |
| Locking | Protect approved canon; warn before foundational changes | |
| Producing | Scenes, assets, prompts, continuity, dependencies | |

---

### F. Project-specific interest

Flag any generic praise (“unique and compelling”, empty “great idea”) without a project-specific observation.

| Turn | Specific observation present? | Generic praise only? |
|------|-------------------------------|----------------------|
| 1 | | |
| 2 | | |
| 3 | | |

---

### G. One-step-ahead

| Format context | Appropriate example | Inappropriate leap | Observed |
|----------------|---------------------|--------------------|----------|
| Episodic (if applicable) | What Ep 2 withholds vs Ep 1 | Episodes 2–10 + season schedule | |
| Film | Next act/sequence turn | Full sequel trilogy | |
| Documentary | Missing disagreeing perspective | Episode logic | |

---

### H. Project Bible Steward

Inspect Wiki / Project Bible after conversation.

| Check | Pass? | Notes |
|-------|------:|-------|
| Merged repeated facts | | |
| Clean headings | | |
| Clean character identities | | |
| Metadata not dumped into Characters | | |
| Fact / interpretation / possibility distinct | | |
| Speculative forward clearly exploratory | | |
| No raw transcript blocks | | |
| No technical processing labels | | |
| Open questions meaningful, not excessive | | |

**Why It Matters** (spot-check Character / Location / Prop if present):

| Record | Story Importance grounded? | Production Importance grounded (no invention)? |
|--------|----------------------------|------------------------------------------------|
| | | |
| | | |

---

### I. Curiosity threads

| Check | Pass? | Notes |
|-------|------:|-------|
| Grounded in project material | | |
| Resurfaces when relevant (not every message) | | |
| Updates when partially answered | | |
| Closes when resolved | | |
| Separate from canon | | |

---

### J. Specialist cohesion & disagreement

Provoke a reveal vs continuity vs overload tension (or use Correct / develop dialogue).

**Expected synthesis shape:** one natural recommendation (e.g. foreshadow now, pay off later) — no “The Producer says…” leakage unless you asked for departmental views.

| Check | Pass? | Notes |
|-------|------:|-------|
| One Co-Director voice | | |
| Conflict addressed (not ignored) | | |
| No raw specialist debate | | |

---

### K. Correction intelligence

Use **Correct with Co-Director** (or equivalent) on a structural identity error  
(e.g. title vs person: “Special Agent” is not a separate character).

| Check | Pass? | Notes |
|-------|------:|-------|
| Correction preview | | |
| Records merge / aliases preserved | | |
| Scene/timeline / TOC update | | |
| Provenance remains | | |
| Undo works | | |
| Locked canon respected | | |
| Not display-only label change | | |

---

### L. Script intelligence

Attach or paste a known episode/project script and identify it as such.

| Expected area | Present & grounded in source? | Notes |
|---------------|-------------------------------|-------|
| Installment overview | | |
| Scene breakdown | | |
| Characters / Locations / Props / Wardrobe | | |
| Story beats / Continuity | | |
| Visual / Audio notes | | |
| Open questions | | |
| Source script reference | | |

Reject generic summaries or fabricated scenes.

---

### M. Cross-format spot-check (minimum two non-series)

| Fixture | Checks | Pass? | Notes |
|---------|--------|------:|-------|
| Standalone film | Act/sequence logic; no Episode 2; one-step structural suggestion | | |
| Documentary | Subjects/interviews/research/archives; no false character-arc; interview/research gap ok | | |
| Optional: game / music video / commercial | Format-appropriate | | |

---

### N. Response naturalness

Run consecutive turns; note structural variety.

| Check | Pass? | Notes |
|-------|------:|-------|
| Warm, specific, interested, clear | | |
| Non-sycophantic / non-technical / non-formulaic | | |
| Not same rigid template every turn | | |

---

### O. Performance (owner feel + any measurements)

Targets: Warm P50 TTFT &lt; 8s; Warm P95 &lt; 20s; no ordinary turn &gt; 30s; Project Bible background-first.

| Metric | Observed | Notes |
|--------|----------|-------|
| Decision-layer (if shown in support artifacts) | | Not full TTFT |
| Perceived first response | | |
| Full response completion | | |
| Background Steward / Bible | | |
| Ordinary turn &gt; 30s? | | |

---

## 3. Scorecard (blank — owner fills)

| Dimension | Score 1–5 | Notes |
| --------- | --------: | ----- |
| Feels like one coherent partner | | |
| Understands the project specifically | | |
| Warmth and genuine interest | | |
| Quiet Partner respects creative flow | | |
| Collaborative Partner feels balanced | | |
| Proactive Producer adds useful initiative | | |
| Hands-On Co-Creator respects authorship | | |
| Questions are meaningful and well timed | | |
| One-step-ahead suggestions are useful | | |
| Project Bible stays clean and organized | | |
| Story and production importance are useful | | |
| Canon and speculation stay distinct | | |
| Curiosity threads feel natural | | |
| Specialist expertise appears without leakage | | |
| Corrections update the wider knowledge structure | | |
| Script intelligence is useful | | |
| Cross-format behavior is appropriate | | |
| Responses remain natural and non-formulaic | | |
| Perceived speed | | |
| Desire to continue working with Co-Director | | |

**Average score:** ________  
**Any score below 4?** ________  

---

## 4. Mandatory Yes/No (all must be Yes)

| # | Question | Yes / No |
|---|----------|----------|
| 1 | Does Co-Director feel like one partner rather than several systems? | |
| 2 | Does it show specific interest instead of generic praise? | |
| 3 | Does Quiet Partner avoid unnecessary questions and suggestions? | |
| 4 | Does Proactive Producer remain bounded and useful? | |
| 5 | Does Hands-On Co-Creator preserve creator authority? | |
| 6 | Does Co-Director stay one meaningful step ahead rather than overplanning? | |
| 7 | Does the Project Bible remain clean rather than becoming a transcript dump? | |
| 8 | Are facts, interpretations, and possibilities clearly distinct? | |
| 9 | Are open questions meaningful and non-repetitive? | |
| 10 | Do corrections update all affected records? | |
| 11 | Does script analysis reflect the source material? | |
| 12 | Do specialists remain invisible beneath one voice? | |
| 13 | Does the system behave appropriately across different project formats? | |
| 14 | Does normal conversation remain fast enough? | |
| 15 | Would the product owner trust Co-Director through a full production? | |

---

## 5. Final approval (owner only)

```text
Reviewer name: _______________________
Date: _______________________
Average score: _______________________
All mandatory Yes: _______________________
Refinement verifier (VERIFIED required): _______________________
```

**Owner product verdict (choose one):**

```text
GO — CO-DIRECTOR CREATIVE OPERATING INTELLIGENCE AND PROJECT BIBLE STEWARDSHIP VERIFIED
```

```text
NO-GO — CO-DIRECTOR CREATIVE OPERATING INTELLIGENCE OR PROJECT BIBLE STEWARDSHIP REMAINS INCOMPLETE
```

```text
HOLD — PRODUCT-OWNER HUMAN EXPERIENCE REVIEW PENDING
```

After a passing review, update the governing completion report **Final Product Verdict** and Program Status human-review lines only.
