# M3.0 Completion - Phase 2: B10, the Bible Proposal Actually Applies

**Verdict: FIXED.** Approving the deterministic provider's character proposal now produces Bible
version 2 with the new detail; rejecting it leaves version 1 untouched. Proven both at the API
level with pytest and from the browser with Playwright.

| Field | Value |
|-------|-------|
| Blocker | **B10** - "approving a Co-Director Bible proposal does not change the Bible" |
| Verdict | **Fixed** (5 pytest + 3 Playwright, all green) |
| Plan file | Not edited |
| Commit | None |

---

## 1. Root cause

The mock provider's `proposal_character_update` scenario emitted a character payload with a field
called `appearance`:

```json
"data": { "description": "...", "appearance": "Has a small scar above her left eyebrow" }
```

`CharacterData` (`studio-api/app/codirector/bible/domain/schemas.py`) has no such field and forbids
extras. Parsing the proposal succeeded - the fence is valid JSON and the mutation shape is right -
so the proposal was created, shown, and offered for approval. Validation only ran inside
`apply_mutation_set`, i.e. **after** the user clicked Approve. The failure therefore looked like
"approval does nothing" rather than "the provider proposed an invalid field".

That ordering is the reason the blocker was misread as a Bible-apply bug. The apply path was
correct; the payload was not.

---

## 2. Fix

`studio-api/app/codirector/providers/mock.py` - the scenario now proposes fields that
`CharacterData` actually defines:

| Before | After |
|--------|-------|
| `appearance` | `appearanceSummary` |
| - | `distinguishingFeatures` (added; the scar detail belongs there too) |
| `description` | unchanged |

A comment at the mutation records why the field names are not free-form, so a future rename fails
in review rather than silently at approval time.

No production code changed. The Bible apply path, the proposal lifecycle, and the schemas were all
already correct.

---

## 3. Backend proof - `studio-api/tests/test_m30_bible_mock_apply.py`

| Test | What it pins |
|------|--------------|
| `test_mock_character_proposal_payload_matches_character_data` | Pulls the ```proposal fence out of the mock reply, runs `validate_entity_data("character", ...)` - the exact call `apply_mutation_set` makes - and asserts every key is in `CharacterData.model_fields` and that `appearance` is gone |
| `test_mock_proposal_parses_into_a_bible_mutation_set` | `extract_proposal_block` returns a `BibleMutationSet` with no error and `entityKey == "ava"` |
| `test_approving_the_mock_proposal_creates_version_2` | Full HTTP lifecycle: chat -> proposal -> `POST .../proposals/{id}/approve` -> receipt `status: success`, `resultingVersionNumber: 2`, and `GET .../bible` shows Ava with "scar" in `appearanceSummary` |
| `test_rejecting_the_mock_proposal_leaves_the_bible_unchanged` | Reject -> `status: rejected`, Bible still at version 1, no Ava entity |
| `test_unknown_character_field_still_fails_loudly` | `validate_entity_data("character", {"appearance": ...})` still raises - the regression guard for this exact bug |

**Result: 5 passed** (part of the 20-test M3.0 Phase 1-3 batch).

The approve/reject pair matters together: a fix that made approval "work" by loosening validation
would also make rejection meaningless. Version 1 staying at version 1 is what proves the mutation
is gated on the decision.

---

## 4. Why the assertion is on the Bible, not the receipt

`POST .../approve` returns a receipt, and a receipt is easy to fake. Both lifecycle tests re-read
`GET /api/codirector/projects/{projectId}/bible` afterwards and assert on
`currentVersion.versionNumber` plus the entity's stored `data`. The version number is what other
surfaces (continuity checks, references, exports) read.

---

## 5. Browser proof - `tests/e2e/m30-completion/m30-completion-bible-apply.spec.ts`

Drives the Co-Director surface with `ADEPT_CODIRECTOR_MOCK_SCENARIO=proposal_character_update`, then
reads the Bible back over the API:

| Case | Assertion |
|------|-----------|
| Approve in the browser | Bible moves to version 2 and Ava's `appearanceSummary` contains the scar detail |
| Reject in the browser | Bible stays at version 1 |
| Payload shape | The proposal the UI displays uses only fields the Bible schema accepts - no `appearance` |

**Result: 3 passed** against the real E2E stack
(`npx playwright test tests/e2e/m30-completion/m30-completion-bible-apply.spec.ts --project=chromium`).
The API log shows the browser driving `POST /api/codirector/chat/stream`, then
`POST .../proposals/{id}/approve` 200 in the first case and `POST .../proposals/{id}/reject` 200 in
the second, with `GET .../bible` read back afterwards in both.

---

## 6. Honest limitations

1. **The proof uses the deterministic mock provider.** That is the provider the E2E stack runs, and
   it is the one that was broken - but a real LLM can still emit an invalid field, and it would fail
   the same way: at apply time, after the user approved. Moving validation forward to proposal
   *creation* would turn that into an immediate, honest rejection. Not done in this phase.
2. **Only `entityMutations` for characters are covered.** `factMutations` and other entity types
   share the same code path but have no equivalent scenario test here.
