# M43 Voice Studio UX Rebuild — Certification Report

## Verdict

IMPLEMENTATION GO  
MANUAL UX CERTIFICATION PENDING

Final milestone certification remains open until
`voiceStudioBeginnerFlowPassed = PASS`.

This is not a runtime NO-GO. Implementation, APIs, persistence, Playwright, and architecture are passed. Final UX certification has not yet been issued.

Live Playwright `tests/e2e/m43/m43-voice-studio.spec.ts` **3/3 passed** against beta (`PLAYWRIGHT_BASE_URL=http://127.0.0.1:8760`) with Qwen Voice Design ready.

## Final milestone rule

```text
voiceStudioFinalGo =
  implementationPassed
  ∧ playwrightPassed
  ∧ voiceStudioBeginnerFlowPassed
```

| Flag | Current |
|---|---|
| implementationPassed | true |
| playwrightPassed | true |
| voiceStudioBeginnerFlowPassed | false |
| voiceStudioFinalGo | false |

## Summary

Character **Voice** and **Voice Performance** are merged into one creator-facing **Voice Studio** tab on Character Creator. Production APIs remain (design → candidates → approve → performance plan → generate → assemble → timeline). UX adds structured prompt building, persisted candidate batches, Use-vs-Approve separation, upload semantics, wizard resume, and Co-Director chips.

Especially strong decisions: Select for Testing vs Approve Voice, persisted batches, resumable wizard state, partial candidate retry, and prompt-clause synchronization.

## Creator journey

```text
Choose method
→ Create or select voice
→ Generate 3 candidates
→ Select for testing
→ Perform dialogue
→ Generate 3 takes
→ Approve
→ Add to Timeline
```

## Gate flags

| Flag | Status |
|---|---|
| voiceStudioUnifiedOperational | PASS (single Voice Studio tab; legacy redirects) |
| voiceStudioThreeVoiceGenerationOperational | PASS (default candidateCount=3 + gallery) |
| voiceStudioPerformanceOperational | PASS (in-page wizard) |
| voiceStudioCandidateSelectionOperational | PASS (Select for Testing) |
| voiceStudioTimelineOperational | PASS (assemble/place after approve) |
| voiceStudioCoDirectorOperational | PASS (persistent chips) |
| voiceStudioAdvancedPreserved | PASS (Advanced drawer) |
| voiceStudioHelpOperational | PASS (HelpTips on key fields) |
| voiceStudioNoNestedScrollbars | PASS (creator path; CSS + e2e check) |
| voiceStudioNoMockData | PASS (mock:false preserved) |
| voiceStudioCreatorExperienceOperational | PASS |
| voiceStudioPlaywrightPassed | PASS (3/3) |
| voiceStudioCandidateBatchesPersisted | PASS (`candidateBatches` on lineage + workspace GET) |
| voiceStudioUseVersusApprovalSeparated | PASS (`/voice/select-testing` ≠ approve) |
| voiceStudioPromptSynchronizationOperational | PASS (`VoicePromptDocument` clause sync) |
| voiceStudioCharacterProfilePrefillOperational | PASS (prefill banner + brief hydrate) |
| voiceStudioGenerateSimilarPreservesIdentity | PASS (similar panel + method=similar batch) |
| voiceStudioPartialBatchFailureRecoveryOperational | PASS (failed slot + `/retry`) |
| voiceStudioWizardResumeOperational | PASS (`voiceStudioDraft` on continuity_json) |
| voiceStudioUploadSemanticsOperational | PASS (upload kinds + register API) |
| voiceStudioBeginnerFlowPassed | PENDING — manual beginner pass required |

## NO-GO checks

| NO-GO | Mitigated |
|---|---|
| Batches disappear after reload | Server `candidateBatches` |
| Use Voice silently approves | `select-testing` only |
| Dropdown wipe of custom prompt | Clause + `userAdditions` model |
| Generate Similar unrelated | Keep checkboxes + parentCandidateId |
| Dialogue upload → identity | Upload kinds; only reusable+consent |
| Resume loses draft | `PUT .../voice/studio-draft` |
| One failure kills batch | Per-candidate failed + retry |
| Beginner needs Advanced | Default path never opens Advanced |

## Primary files

- `studio-web/src/components/VoiceStudioWorkspace.tsx`
- `studio-web/src/components/voiceStudio/*`
- `studio-web/src/components/CharacterProfileWorkspace.tsx`
- `studio-api/app/character_identity/voice_creator.py`
- `studio-api/app/character_identity/api.py`
- `studio-api/app/voice_performance/service.py` (testing voice generate)
- `tests/e2e/m43/m43-voice-studio.spec.ts`

## Beginner usability evidence (manual)

Run with a first-time-user mindset on **Korri Character Production** against the real beta. Do **not** open Advanced.

### Procedure

1. Open Korri Character Profile
2. Open Voice Studio
3. Select Create New Voice
4. Confirm or adjust the character details
5. Generate 3 Voices
6. Listen to all three
7. Select one for testing
8. Enter a dialogue line
9. Select mood and delivery
10. Generate 3 Performances
11. Select one take
12. Approve and save the voice
13. Approve the performance
14. Add the performance to Timeline
15. Reload and confirm persistence

### Pass rule

```text
voiceStudioBeginnerFlowPassed =
  workflowCompleted
  ∧ advancedNotRequired
  ∧ noBlockingErrors
  ∧ noDeveloperKnowledgeRequired
  ∧ voicePersisted
  ∧ performancePersisted
  ∧ timelinePlacementPersisted
```

### Usability targets

| Target | Goal |
|---|---|
| Completion time | under 5 minutes |
| Blocking moments | 0 |
| Advanced required | No |
| Unexplained technical terms | 0 |

Misclicks are observational evidence, not an automatic failure, unless they reveal unclear controls.

### Metrics

| Metric | Result |
|---|---|
| Completion time | Pending manual pass |
| Misclicks | Pending manual pass |
| Blocked moments | Pending manual pass |
| Terms requiring explanation | Pending manual pass |
| Advanced opened | No required |

### Checklist

- [ ] Generate three real voice candidates
- [ ] Listen to all three candidates
- [ ] Select one voice for testing
- [ ] Generate three real performance takes
- [ ] Listen to all three takes
- [ ] Select and approve one take
- [ ] Approve and save the character voice
- [ ] Add the approved performance to Timeline
- [ ] Reload and confirm voice persistence
- [ ] Reload and confirm performance persistence
- [ ] Reload and confirm Timeline placement
- [ ] Complete the workflow without opening Advanced

### After the manual pass

When the checklist and metrics are complete:

```text
voiceStudioBeginnerFlowPassed = true
voiceStudioFinalGo = true
```

Then replace the verdict with:

> GO — M43 Voice Studio UX Rebuild is complete. Voice creation and Voice Performance are unified into one creator-first workflow. Real candidate batches and performance takes are generated, persisted, selected, approved, and placed on Timeline. Advanced controls remain available without burdening the beginner path, and both automated and manual usability certification pass.

Also record: _Manual beginner flow completed without opening Advanced. Voice selection, performance approval, Timeline placement, and reload persistence were verified against the real beta._

## Playwright

```bash
# against live beta (repo root)
$env:PLAYWRIGHT_BASE_URL="http://127.0.0.1:8760"
npx playwright test tests/e2e/m43/m43-voice-studio.spec.ts
```
