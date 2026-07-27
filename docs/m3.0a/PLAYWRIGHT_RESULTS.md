# M3.0a Phase 4 - Playwright Results

| Field | Value |
|-------|-------|
| Tip SHA | e2f3ae8a9750d44ec37b64361cbede6a95351d3c |
| Branch | `phase2/codirector-m2-9-production-suite` |
| Date | 2026-07-26 |
| Command | `npx playwright test` (full default suite, both projects) |
| Duration | 6.6 min |
| Stack | `scripts/e2e-start.mjs` - `STUDIO_E2E=1`, M2.8/M2.9 fixture modes on, mock Co-Director provider |
| Log | `artifacts-m30a-playwright-full.log` |

---

## 1. Headline

```
89 passed
 6 failed
 9 skipped
--------
104 tests, 34 spec files, 2 projects, 6.6 min
```

The full suite ran. Nothing was too heavy to execute and no subset was substituted for the
whole, so this section is a measurement rather than an estimate.

Of the 6 failures, **1 was caused by M3.0a and is fixed in this phase**; the other 5
reproduce independently of M3.0a and are analysed in section 4. Of the 9 skips, 8 are
feature flags that are off by default and 1 is the fal live gate.

## 2. Per-project

| Project | Test dir | Tests | Pass | Fail | Skip |
|---------|----------|------:|-----:|-----:|-----:|
| `chromium` | `tests/e2e` | 101 | 88 | 6 | 7 |
| `workspaces` | `studio-web/e2e` | 3 | 1 | 0 | 2 |

The `workspaces` project is new in this phase. Before it existed, those 3 tests were not
collected by a default run at all. Their first appearance in a suite total is here.

## 3. Per-layer

Layer definitions and the full per-spec breakdown are in `PLAYWRIGHT_TEST_PLAN.md`.

| Layer | Tests | Pass | Fail | Skip |
|-------|------:|-----:|-----:|-----:|
| 1. Shell and navigation | 7 | 7 | 0 | 0 |
| 2. Project and data lifecycle | 6 | 6 | 0 | 0 |
| 3. Setup, sources and capability gating | 18 | 18 | 0 | 0 |
| 4. Co-Director intelligence and approval loop | 31 | 25 | 6 | 0 |
| 5. Production platforms and workspaces | 36 | 28 | 0 | 8 |
| 6. Providers, credentials and cloud | 6 | 5 | 0 | 1 |

## 4. The six failures

Every failure was re-run in isolation after the Phase 3 remediations, in a focused subset
(`tests/e2e/m30a` plus the six failing specs; 26 tests, 3.7 min, log
`artifacts-m30a-playwright-subset.log`). Five reproduced identically, which rules out
test-ordering and shared-database contamination as the cause and makes them real, if
pre-existing, defects in the specs or the app.

### 4.1 Fixed in this phase

**`tools.spec.ts:283` - the tool catalog and availability are exposed for the open project**

```
Error: expect(received).toEqual(expected)
- Expected  -  0
+ Received  + 32
```

The spec asserts the Co-Director tool catalogue against a hard-coded allowlist. The comment
above the assertion explains why it is hard-coded: it is a security gate, designed to fail
the moment a tool appears in the registry without someone deliberately acknowledging it - and
in particular to make a shell, filesystem, SQL or arbitrary-execution tool impossible to add
quietly.

The allowlist had drifted **32 tools** behind: the whole of M2.3 through M2.14, plus M3.0a's
own `get_cloud_render_status`. A gate that fails on every single run is not a gate, because
nobody can tell the difference between the expected red and a real one.

The fix is the deliberate acknowledgement the assertion was asking for. The list was
regenerated from `codirector/tools/definitions.py` and each entry checked against its kind:

| Group | Count | Shape |
|-------|------:|-------|
| Read tools | 31 | Return state; no writes |
| Mutating tools | 20 | Every one a `create_*` / `propose_*` / `record_*` / `set_*` / `update_*` that produces an approval-gated proposal |
| Shell / filesystem / SQL / eval tools | **0** | - |
| Tools that enqueue a generation job | **0** | - |
| Tools that approve a proposal | **0** | - |

The spec passes with the refreshed list, and the gate is a gate again. This is the only spec
file modified in M3.0a.

### 4.2 Not caused by M3.0a

For each of the five, the attribution rests on the same test: does the failure touch any file
M3.0a changed? The complete M3.0a diff is 20 backend files, 4 frontend files,
`playwright.config.ts`, and 2 spec files. None of the five failures lands in that set.

**`intelligence-storyboard.spec.ts:47` - integrated planning and readiness flow keeps visual
validation pending**

```
Expected pattern: not /render completed|render finished|asset created/i
```

The assertion reads the entire page body and requires that none of those phrases appear
before approval. The phrase it now matches is the app's own honesty caveat, rendered inside
the storyboard proposal card:

> Does not claim a render completed - execution may be blocked when Comfy/packs are unavailable.

The string comes from `codirector/tools/handlers/storyboard.py`, which is committed and
unmodified. So the test fails *because* the product tells the truth in words that the test's
naive substring guard cannot distinguish from a lie. Recommended fix: scope the locator to
the status region, or exclude the caveat list before matching. Not attempted here - changing
an honesty assertion is not something to do casually at the end of an audit.

**`production-bible.spec.ts:90` - approving a Co-Director proposal creates a new Bible
version** and **`production-bible-m23.spec.ts:29` - production-ready character lifecycle**

```
Received string: "Couldn't approve that proposal: Applying this proposal to the Production Bible failed."
Locator: getByText(/Version 2 of/)  ->  element(s) not found
```

Both are the same defect seen from two angles: applying an approved Bible proposal fails, so
version 2 is never created. The API log carries the cause:

```
sqlite3.IntegrityError: FOREIGN KEY constraint failed
sqlalchemy.exc.IntegrityError: (sqlite3.IntegrityError) FOREIGN KEY constraint failed
```

The Bible apply path (`codirector/bible/*`) is not in the M3.0a diff. The most likely origin
is a foreign key introduced by the uncommitted M2.14 database work in the same working tree,
which would make this a live regression in that milestone rather than in this one. **It is
worth stating plainly that this is inference, not measurement**: no pre-M3.0a full-suite
baseline exists in the repository to diff against, and reconstructing one would mean running
the suite against a tree without the uncommitted M2.11-M2.14 work, which is most of the
application. Recommended: reproduce with SQLAlchemy echo on and name the constraint.

**`streaming-cancel.spec.ts:40` - reply streams incrementally and a Stop Generating control
is available while busy**

```
- Expected substring: [mock]
+ Received string: Director recommends proceeding with bounded Production Bible context. ...
```

The spec expects the `[mock]` prefix that `codirector/providers/mock.py` puts on its replies,
but the reply it received came from an E2E scenario configured through
`POST /api/e2e/codirector/scenario`, which does not carry the prefix. `providers/mock.py` is
committed and unmodified. Recommended fix: assert on the scenario's own text, or have the
scenario provider carry the same prefix.

**`vision-storyboard-validation.spec.ts:9` - validation workspace appears when flag on and
pending deep-link works**

```
Error: strict mode violation: getByRole('button', { name: /Co-Director/i }) resolved to 4 elements
```

Four buttons now match: the header button, two "Ask Co-Director" buttons on the validation
cover, and the floating action button. This is a stale locator against a page that grew more
entry points. M3.0a's only change to this workspace was the VIS-05 one-liner switching the
validation request from `provider: "mock"` to `provider: "local"`, which adds no buttons.
Recommended fix: `getByRole("banner").getByRole("button", { name: "Co-Director" })`.

## 5. The nine skips

| Spec | Skips | Reason |
|------|------:|--------|
| `production-suite-m29.spec.ts` | 3 | `codirector_production_suite_v1` off by default |
| `production-executive-m27.spec.ts` | 2 | One flag-off case, one restart-recovery case |
| `m214-unified-experience.spec.ts` | 2 | `codirector_unified_experience_v1` off by default |
| `capability-intelligence-m28.spec.ts` | 1 | Flag-gated case |
| `m30a-fal-ai-provider.spec.ts` | 1 | `ADEPT_M30A_FAL_LIVE` unset |

All nine are honest skips with a stated reason. None is a silent pass. The M2.9 and M2.14
skips are the ones worth revisiting before M3.0b, because between them they cover the newest
and least-exercised production UI in the repository.

## 6. Backend suite, for the same commit

Run alongside, `python -m pytest` over the five suites touched or relied on by M3.0a:

```
135 passed, 2 failed, 1 skipped   (56 s)
```

| Suite | Result |
|-------|--------|
| `tests/test_m213_virtual_environment_studio.py` | pass, including 4 new M3.0a refusal tests |
| `tests/test_m28_capability_intelligence.py` | pass, including 3 new M3.0a refusal tests |
| `tests/test_m29_production_suite.py` | pass, including 1 new M3.0a refusal test |
| `tests/test_fal_credentials.py` | pass |
| `tests/test_codirector_tools.py` | 2 failed |

The two failures are `test_capability_project_not_configured_without_project_id` and
`test_capability_bible_not_configured_before_bible_exists`, both asserting on
`CapabilityAdapter.state_for(...)`. `codirector/tools/capabilities.py` is unmodified, and
M3.0a's only edit anywhere in `tools/` is 51 added lines and zero deleted, all of them the
`get_cloud_render_status` definition, handler and binding. These failures cannot be caused by
an addition that the failing assertions never read.

## 7. Artifacts

| File | Contents |
|------|----------|
| `artifacts-m30a-playwright-full.log` | Full suite, 104 tests |
| `artifacts-m30a-playwright-subset.log` | Focused re-run, 26 tests |
| `artifacts-m30a-pytest-final.log` | Backend suites, 138 tests |
| `playwright-report/` | HTML report |
| `artifacts/functional-audit/test-output/` | Traces, screenshots and DOM snapshots for the 6 failures |

## Phase 4 closure addendum (2026-07-27)

The full root command `npx playwright test` completed in 4.8 minutes:
**108 passed, 0 failed, 9 skipped, 117 total**. `chromium`: 104/0/9 across
113 tests; `workspaces`: 4/0/0 across 4 tests. The four carried-forward failures
were closed by narrowing the intelligence honesty assertion, validating the B10
`appearanceSummary` mock payload, using a non-planning streaming prompt, and
scoping the vision flow to the unique Co-Director FAB. No failures remain.
