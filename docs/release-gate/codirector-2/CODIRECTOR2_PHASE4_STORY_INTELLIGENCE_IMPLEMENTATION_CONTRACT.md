# CO-DIRECTOR 2.0 — PHASE 4 STORY INTELLIGENCE IMPLEMENTATION CONTRACT (FREEZE)

| Field | Value |
|---|---|
| Phase | 4 (implementation) |
| Date | 2026-08-08 |
| Status | **FROZEN** — governing contract for Phase 4 source edits. |
| Dependency | `GO — CO-DIRECTOR 2.0 PHASE 3 INTENT + STAGE ROUTER CERTIFIED` |
| Governing evidence | Phase 1 `CODIRECTOR2_STORY_INTELLIGENCE_AUDIT.md`, `CODIRECTOR2_SCRIPTWRITER_WIKI_AUDIT.md` |

---

## 1. Current defect model (verified against live source)

| Defect | Source | Evidence citation |
|---|---|---|
| Logline = generic freeform text | Deterministic `compile_story_summary` uses `narrative[0]` truncated to 220 | `story_compiler.py:40-43` |
| Short/Long summary = concatenated records | `first 2 texts` / `first 6 + episode summary`, no editorial synthesis | `story_compiler.py:44-47` |
| AI-derived text persisted without proposal | `editor._persist` writes directly to `compiledWiki`; `approval_required=False` | `editor.py:254-269`; `intelligence/contracts.py:366` |
| Instruction text enters story fields | `extract_documentation` has no instruction/content split; instruction verbs absent from `_SUBSTANTIVE` | `discovery/documentation.py:16-20`; instruction verbs at `documentation.py:39` |
| Creator corrections appear as summary evidence | `correction/apply.py:161-185` stores instruction verbatim as confirmed knowledge entry; `evidence.py:100-106` treats it as fact | `correction/apply.py:161-185`; `evidence.py:100-106` |
| Unsupported facts enter derived artifacts | `check_grounding` is alias/token heuristic, not semantic; no per-sentence citation check | `laws.py:119-142` (documented gap) |
| No acceptance UI or approval flow for story fields | Summary is written to `compiledWiki["storySummary"]` directly — no `CoDirectorProposal` row, no receipt | `editor.py:254-269`; `page_compiler.py:207` |
| Creator rejection not treated as final | No reject flow exists for story fields — they are overwritten on each compile | `page_compiler.py:207` runs on every turn |

---

## 2. Existing architecture reused

| Component | Location | Decision | What changes |
|---|---|---|---|
| LLM editorial editor | `compiled/story_summary_editor/editor.py:138` | ADAPT | Add proposal emit before `_persist`; keep LLM core, 45s timeout, provider resolution |
| Evidence classifier | `compiled/story_summary_editor/evidence.py:77` | KEEP + ADAPT | Add LivingProjectBrief + partnership story template fields as evidence inputs; keep provenance hierarchy |
| 10 laws validator | `compiled/story_summary_editor/laws.py:241` | KEEP + EXTEND | Add law #11: `NO_INSTRUCTION_CONTAMINATION_IN_SUMMARIES`; add per-sentence grounding check |
| Conservative fallback | `compiled/story_summary_editor/fallback.py:30` | KEEP | Safe deterministic result for no-provider mode |
| Readiness gates | `compiled/story_summary_editor/readiness.py:24-68` | KEEP | Per-section coverage MINIMAL→MATURE; gates whether proposal is warranted |
| ProposalService | `bible/proposals.py:128-585` | ADAPT | Add story-field proposal type (analogous to `BibleMutationSet`) |
| Knowledge supersede | `conversation/knowledge.py:52-93` | ADAPT | Reuse supersede/reject lifecycle for story-field revisions |
| Creator correction | `correction/` (apply.py, memory.py, classify.py, undo.py) | KEEP | Unchanged; correction entries feed evidence as creator-authoritative |
| Phase 2 invalidation | `production_state/invalidation.py` | REUSE | After story mutation → invalidate cache section `"story_intelligence"` |
| Page compiler | `compiled/page_compiler.py:49` | ADAPT | Wire async/LLM path as default instead of deterministic concatenation |
| Phase 3 router | `routing/orchestrator.py` | MODIFY_KNOWLEDGE | Routes through Story Intelligence compiler, not direct LLM text |

---

## 3. Authoritative source map

| Evidence domain | Store | Read path | Authority class | Consumed today? |
|---|---|---|---|---|
| Script content (Fountain elements) | `script_documents_v2` | `scriptwriter/store.py:135-163` | Creator-authored | No |
| Production Bible (overview, characters, relationships) | `production_bible_entities` + `bible/domain/schemas.py` | `bible/domain_service.py` + `bible/read` tools | Creator-approved | No |
| Approved Wiki fields | `knowledgeEntries` (settings_json) | `snapshot.py` + `wiki.py` | Creator-approved | Yes (via evidence.py) |
| Creator-stated production facts | Phase 2 Production State | `production_state/projection.py` | Creator-stated | No |
| Character Identity | `character_profiles` + `character_identity/models.py` | `character_identity/service.py` | Creator-stated/approved | Partial (character roles) |
| Scene records | `scenes` table | `scene_service.py` + `scenes` model | Creator-approved summaries | No |
| Approved decisions | `m211_decision_records` + `codirector_approvals` | `m211/decisions.py` | Creator-approved | No |
| Creator corrections | `correction/memory.py` + confirmed knowledge entries | `correction/memory.py:77-102` | Creator-authoritative | Yes (via evidence.py) |
| LivingProjectBrief | `discovery/brief.py` `LivingProjectBrief.fields` | `discovery/brief.py:42-58` | Ai-inferred → creator-approved | No |
| Partnership story template | `partnership/story_template.py` `build_story_template` | `partnership/story_template.py:18` | Ai-inferred | No |

**Excluded sources:** raw assistant chatter, unapproved AI speculation, stale rejected proposals, arbitrary conversation memory, unrelated project fields.

---

## 4. Canonical Story Evidence Model

**File:** `app/codirector/story_intelligence/story_model.py` — projection-only (Law 7), no writable store.

```python
@dataclass
class StoryFact:
    value: str
    source: str  # "script_writer" | "production_bible" | "wiki" | "creator_stated" | "character_identity" | "scene_records" | "approved_decision" | "correction" | "living_brief"
    sourceRef: str
    provenance: str  # Phase 2 ProvenanceTaxonomy
    confidence: float = 1.0
    updated_at: Optional[datetime] = None

class StoryEvidenceModel(BaseModel):
    project_id: str
    format: Optional[StoryFact] = None
    title: Optional[StoryFact] = None
    protagonist: Optional[StoryFact] = None
    primary_characters: list[StoryFact] = []
    setting: Optional[StoryFact] = None
    premise: Optional[StoryFact] = None
    objective: Optional[StoryFact] = None
    conflict: Optional[StoryFact] = None
    stakes: Optional[StoryFact] = None
    tone: Optional[StoryFact] = None
    genre: Optional[StoryFact] = None
    relationships: list[StoryFact] = []
    story_beats: list[StoryFact] = []
    ending: Optional[StoryFact] = None
    themes: list[StoryFact] = []
    unresolved_questions: list[StoryFact] = []
    source_refs: list[str] = []  # all evidence source ids aggregated
```

Function `build_story_evidence(db, project_id) -> StoryEvidenceModel` — composes from the authoritative sources above. Must NOT write to any store. Must handle missing projects gracefully.

---

## 5. Instruction/content separation

**File:** `app/codirector/story_intelligence/sanitize.py`

### Layer 1 — Deterministic (runs first, high confidence):
```python
_INSTRUCTION_PREFIX_RE = re.compile(
    r"^\s*(?:place|put|add|set|save|write|update|change|make|turn|use this as|enter this as)\b"
    r".*\b(?:in(?:to)? (?:the )?(?:short |long )?summary"
    r"|as (?:the )?logline"
    r"|to (?:the )?wiki"
    r"|as canon|as a fact|in the bible"
    r")\s*[:\-–—]?\s*(.+)",
    re.I | re.DOTALL,
)
```
If matched → content = capture group 1, instruction = full match minus capture group.
If not matched → fall through to semantic.

### Layer 2 — Semantic/model fallback:
For ambiguous patterns where deterministic can't cleanly split. If uncertain, keep the full text as content (safe).

### Integration:
- Hook into `extract_documentation` (discovery/documentation.py:39) — strip instruction before candidate extraction
- Add instruction token filter to `wiki_intelligence/classification.py:46` `is_user_preference_not_canon` (generalize to also reject instruction tokens)
- Add law #11 to `laws.py` — `NO_INSTRUCTION_CONTAMINATION_IN_SUMMARIES` checked as post-condition over all three output fields

---

## 6. Compiler contracts

### 6.1 Logline compiler (`compilers/logline.py`)

| Requirement | Rule |
|---|---|
| Length | One sentence, ≤300 chars |
| Content | Central premise; protagonist if supported; conflict/objective/stakes if evidence supports |
| Prohibited | Meta commentary, instruction text, unsupported invention, assistant praise |
| Format-aware | Commercial/sketch/music video ≠ traditional high-stakes structure |
| Validation | Non-empty, one sentence, no bullet/list, no contamination, no unsupported names |

### 6.2 Short Summary compiler (`compilers/short_summary.py`)

| Requirement | Rule |
|---|---|
| Length | ~50–100 words |
| Content | Central setup, major beat(s), conclusion if known |
| Prohibited | Instructions, assistant commentary, analysis, production advice, field labels, unsupported facts |
| Format-aware | 20-sec commercial → appropriately short |

### 6.3 Long Summary compiler (`compilers/long_summary.py`)

| Requirement | Rule |
|---|---|
| Length | ~150–400 words narrative; shorter for commercials |
| Content | setup → development → conflict → resolution → character movement (only where evidence exists) |
| Prohibited | No padding, no unsupported facts, no instruction text |
| Format-aware | 20-sec commercial → relatively short; feature → fuller synthesis |

All compilers produce a **proposed artifact text** that goes through validation before proposal. If validation fails → return structured failure (no proposal created).

---

## 7. Proposal/approval integration

### 7.1 New proposal type

Add to `bible/proposals.py` or a dedicated `story_intelligence/proposal.py`:

```python
@dataclass
class StoryFieldProposal:
    artifact_type: Literal["logline", "short_summary", "long_summary"]
    current_value: Optional[str]  # current compiled value (may be None)
    proposed_value: str
    compiler_version: str
    evidence_hash: str
```

### 7.2 Flow

```
Compiler → proposed artifact text
    ↓
Validator (deterministic → fail fast)
    ↓
ProposalService.create_proposal(project_id, proposal_type="story_field", payload=StoryFieldProposal)
    ↓ durable CoDirectorProposal row created
    ↓
Frontend shows CURRENT vs PROPOSED (reuse existing proposal preview)
    ↓
Creator approves → ProposalService.approve(project_id, proposal_id)
    ↓ applies exactly the proposed_value (argument pinned at creation)
    ↓ writes to compiledWiki["storySummary"][artifact_type]
    ↓
Creator rejects → ProposalService.reject(project_id, proposal_id)
    ↓ current artifact untouched (byte-identical preservation)
    ↓ no automatic re-proposal loop
```

### 7.3 Argument pinning

The `proposed_value` is captured at proposal creation time. Approval applies it verbatim. No hidden recomputation at approval time. The current approval machinery already supports this (execution receipts).

### 7.4 Creator direct edits

If creator manually edits a story field → saved with `provenance="CREATOR_STATED"` → becomes authoritative. AI may later propose refinement but cannot overwrite automatically. Creator rejection ("No, keep my wording") → REJECT → byte-identical preservation asserted in tests.

### 7.5 Story freshness

After story mutation (script updated, character corrected, approved Wiki field changed, correction applied) → `invalidate_cache_sections(db, project_id, ["story_intelligence"])` — Phase 2 invalidation reuse.

---

## 8. Test requirements

### 8.1 Schnick Coffee fixture (contract § canonical test)

Seed: title="Schnick Coffee", format="commercial", primary character="Korri", script with the fountain text from the contract.

**Logline assertions:** one sentence, Korri + coffee/product + gag/fourth-wall reversal, no invented stakes, no unrelated characters, no meta text.

**Short Summary assertions:** coffee shop, Korri promoting, green/stinky product, she breaks character, narrator confirms gag. No instruction text, assistant praise, production recommendations.

**Long Summary assertions:** fuller but short; do not pad.

### 8.2 Contamination adversarial cases (4 cases)

1. Instruction prefix → content-only extraction
2. "Make this shorter" → instruction excluded, content compiled
3. "Short summary should say exactly:" → direct creator edit, preserved verbatim
4. "Improve this summary" → AI transformation allowed, MUST go through proposal

### 8.3 Negative assertions

- Rejected proposal does NOT persist
- Direct creator edit survives AI rejection
- Instruction phrases absent from artifacts
- Unsupported character names blocked
- Unsupported plot events blocked
- Stale rejected proposal never becomes evidence
- Project isolation: Project A evidence never enters Project B
- Empty project does not hallucinate summary (returns INSUFFICIENT_EVIDENCE)
- AI-inferred tone does not become creator-approved canon
- Direct script text remains unmodified

---

## 9. Subagent sequencing

1. **Agent A** — writes this contract doc + source map
2. **Agent B** — `story_model.py` (StoryEvidenceModel + `build_story_evidence`)
3. **Agent C** — `sanitize.py` (instruction/content separation)
4. **Agent D** — `compilers/logline.py` (logline compiler + validator)
5. **Agent E** — `compilers/short_summary.py` + `compilers/long_summary.py` + shared validators
6. **Agent F** — `proposal.py` + integration into ProposalService + creator authority
7. **Agent G** — Schnick Coffee fixture tests + adversarial cases + regression
8. **Agent H** — independent verifier + certification report

---

*This contract is frozen as of 2026-08-08. No Phase 4 source edit precedes this document.*
