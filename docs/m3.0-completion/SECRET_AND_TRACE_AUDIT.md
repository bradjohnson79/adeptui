# M3.0 Completion - Phase 12: Secret and Trace Audit

**Verdict: CLEAN. No rotation required.** The operator's fal.ai key exists only in the
gitignored `.env` and in the encrypted secret store. It appears in no tracked file, no
untracked file in the working tree, no document, no artifact, no log, and nowhere in the
reachable git history of any ref.

| Field | Value |
|-------|-------|
| Date | 2026-07-27 |
| Branch | `phase2/codirector-m2-9-production-suite` |
| Tip SHA at audit time | `e2f3ae8a9750d44ec37b64361cbede6a95351d3c` |
| Audit script | `scripts/m30_secret_audit.py` |
| Machine-readable output | `artifacts/functional-audit/m30-secret-audit.json` (gitignored) |
| Secret values printed | **None.** Every finding below is redacted to first-4 / last-4 plus length. |
| Plan file | Not edited |
| Rotation required | **No** |

The audit script reads `.env` to learn *what to search for*, then reports only booleans,
paths, and redactions. It never writes a secret value to its own output file, and the JSON
it emits lands under `artifacts/`, which is gitignored.

---

## 1. Credentials found in the environment file

| Name | Redacted | Length | Class |
|------|----------|-------:|-------|
| `FAL_API_KEY` | `99cc...16e6` | 69 | fal.ai BYOK key |

That is the only entry in `.env` whose name matches
`KEY|SECRET|TOKEN|PASSWORD|CREDENTIAL` and whose value is long enough to be a credential.
The redaction above matches the one already recorded in `PHASE0_BASELINE_AUDIT.md`, so the
key has not changed during the milestone.

---

## 2. `.env` is gitignored and is not staged

| Check | Command | Result |
|-------|---------|--------|
| Ignored | `git check-ignore -v .env` | **Ignored** by `.gitignore:9:.env` |
| Tracked | `git ls-files -- .env */.env` | **No output** - not tracked anywhere in the tree |
| Staged | `git diff --cached --name-only` | **Index is empty** (0 staged paths at audit time); no `.env` present |

`.env` therefore cannot be committed by the Phase 13 staging step even accidentally, and
`git add -A` would not pick it up. Phase 13 still stages explicit paths rather than relying
on that.

---

## 3. Working-tree leakage scan

1,413 text files were read in full and searched for the literal key value. The scan covers
tracked *and* untracked files, including everything under `docs/`, `artifacts/`, `scripts/`,
`studio-api/`, `studio-web/`, and `tests/`. Binary-only directories and vendored trees
(`.git`, `node_modules`, `.venv`, `__pycache__`, `data`, `test-results`, `playwright-report`)
were skipped.

| Scan | Result |
|------|--------|
| Files scanned | 1,413 |
| Files containing the literal `FAL_API_KEY` value | **0** |

### Credential-shaped patterns (reported redacted, none real)

Three shapes were searched independently of the actual value, so that a *different* key
pasted by mistake would also be caught: an `Authorization: Key`/`Bearer` header with a
following non-space character, a `FAL_KEY`/`FAL_API_KEY` assignment with a following
alphanumeric, and the `uuid:hex` shape a fal key takes.

| Pattern | Hits | Hits containing a real secret |
|---------|-----:|------------------------------:|
| `Authorization: Key\|Bearer <value>` | 5 | **0** |
| `FAL_(API_)KEY = <value>` | 1 | **0** |
| `uuid:hex` fal key shape | 0 | **0** |

All six hits are documentation placeholders or test fixtures:

| Path | Line | Shape | Nature |
|------|-----:|-------|--------|
| `docs/audit/GITHUB_PACK_PROVIDER_COMPLETION.md` | 48 | `Authorization: Bearer <` | Literal `<token>` placeholder in prose |
| `docs/m3.0a/FAL_AI_CREDENTIAL_SECURITY.md` | 58 | `Authorization: Key <` | Placeholder describing the header fal expects |
| `docs/m3.0a/FAL_AI_INTEGRATION_AUDIT.md` | 42 | `Authorization: Key <` | Same placeholder |
| `studio-api/tests/test_codirector_provider.py` | 532, 543 | `Authorization: Bearer s` | Synthetic test token, not a real credential |
| `studio-api/tests/test_m30_fal_env_bridge.py` | 118 | `FAL_KEY='d` | Fake `.env` fixture written by the test into a tmp dir |

The bridge test fixture is deliberately a dummy string; `test_reports_and_verification_records_never_carry_the_key`
in the same file asserts that no report, verification record, or file in the secrets
directory ever contains it.

---

## 4. Git history

| Check | Result |
|-------|--------|
| `git log --all -S <key value> --oneline` | **No commits** on any ref have ever added or removed the key value |
| `git ls-files -- artifacts data` | **No output** - nothing under `artifacts/` or `data/` is tracked |
| `git ls-files -- *.zip *.webm *.mp4 *trace*` | Two matches, both benign: `docs/codirector/m2.7.1-storyboard-generate-trace.md` (a markdown write-up) and `studio-api/app/codirector/m211/traces.py` (source). **No Playwright trace zips, videos, or media binaries are tracked.** |

Because the pickaxe search over `--all` returns nothing, the key has never entered the
object database. No history rewrite and no key rotation is needed.

---

## 5. Artifacts, data, and test output are gitignored

| Path | Ignored | Rule |
|------|---------|------|
| `artifacts/` | Yes | `.gitignore:14:artifacts/` |
| `artifacts/m30a-fal/seedance_t2v_4s_480p.mp4` | Yes | `.gitignore:14:artifacts/` |
| `artifacts/m30a-fal/live_proof_summary.json` | Yes | `.gitignore:14:artifacts/` |
| `artifacts/functional-audit/logs/api.log` | Yes | `.gitignore:14:artifacts/` |
| `data/` | Yes | `.gitignore:6:data/` |
| `test-results/` | Yes | `.gitignore:16:test-results/` |
| `playwright-report/` | Yes | `.gitignore:17:playwright-report/` |

The paid fal MP4, its proof summary, the Playwright traces and screenshots under
`artifacts/functional-audit/test-output/`, the local Z-Image PNG under
`data/projects/.../assets/`, and `data/studio.db` are all unstageable by rule. The portable
evidence for those artifacts is their recorded sha256, which is what the proof documents
carry.

Note that this also means the encrypted secret store itself (`data/secrets/fal_api_key.enc`
and `data/secrets/master.key`) is gitignored. The encryption is real - Fernet, with the
master key held next to the ciphertext - but the reason it cannot be committed is the
ignore rule, and that is the guarantee being relied on here.

---

## 6. The API never returns the raw key

Four routes in `studio-api/app/routers/api.py` touch the fal credential, and every one of
them returns `FalKeyStatus`, which is built exclusively from
`secrets_store.secret_status("fal_api_key")`:

| Route | Returns |
|-------|---------|
| `GET /api/fal/key` | `FalKeyStatus` |
| `PUT /api/fal/key` | `FalKeyStatus` (after storing and probing) |
| `POST /api/fal/key/validate` | `FalKeyStatus` (after re-probing) |
| `DELETE /api/fal/key` | `FalKeyStatus` (after clearing) |

`FalKeyStatus` (`studio-api/app/schemas.py:351`) declares exactly seven fields -
`configured`, `hint`, `fingerprint`, `state`, `verified`, `verifiedAt`, `message` - and
Pydantic drops anything else. There is no field on the model that could carry the key.

| Field | Derivation | What a caller learns |
|-------|-----------|----------------------|
| `hint` | `secret_hint` - `f"{raw[:4]}••••{raw[-4:]}"`, or `••••••••` for values of 8 characters or fewer | 8 characters of a 69-character key |
| `fingerprint` | `secret_fingerprint` - first 12 hex characters of `sha256(key)` | A comparison handle, not a preimage |
| `state` | `missing` / `unverified` / `verified` / `invalid` | Probe outcome only |

`GET /api/fal/usage` calls `get_secret` internally to sign its own upstream request, but
returns `FalUsageOut`; the key is used, never echoed.

Two further guards were checked rather than assumed:

- `set_secret_verification` strips `key` and `api_key` from any `detail` dict before writing
  the verification record (`secrets_store.py:110`), so a probe response that happened to echo
  the credential could not be persisted into `data/secrets/*.verified.json`.
- The `.env`-to-secret-store bridge added in Phase 6 (`studio-api/app/fal_env_bridge.py`)
  returns a report that carries at most a fingerprint. Its regression test,
  `test_reports_and_verification_records_never_carry_the_key`, asserts the key string appears
  in no report, no verification record, and no file in the secrets directory.

`studio-api/tests/test_fal_credentials.py::test_status_never_returns_the_key` is the
standing regression test for the route contract itself.

---

## 7. Residual risks, stated plainly

1. **The key is on the operator's disk in plaintext** in `.env`, by design and by the
   milestone's own instruction to use a BYOK key from `.env`. Ignoring it is a repository
   guarantee, not a filesystem one.
2. **`data/secrets/master.key` sits beside the ciphertext it decrypts.** Anyone with
   read access to `data/` has both. That is the existing design; this audit did not change
   it and does not claim it is hardened storage.
3. **The audit is a point-in-time scan of the current working tree and current refs.** It
   does not prevent a future commit from adding a key; the ignore rules and the staging
   discipline in Phase 13 are what do that.
4. **`artifacts/functional-audit/logs/api.log` and friends were scanned and are clean**, but
   they are also gitignored, so they were never at risk of publication. The scan covered them
   anyway because a leak into a local log is still a leak.

---

## 8. Conclusion

| Question | Answer |
|----------|--------|
| Is `.env` gitignored? | Yes (`.gitignore:9`) |
| Is `.env` staged? | No - the index was empty at audit time |
| Does the key appear in any working-tree file? | No - 0 hits across 1,413 scanned files |
| Does the key appear in docs, artifacts, or logs? | No - the only credential-shaped strings found are placeholders and test fixtures |
| Are fal artifacts under `artifacts/` gitignored? | Yes (`.gitignore:14`) |
| Does the API ever return the raw key? | No - masked hint plus sha256 fingerprint only, with a regression test |
| Does the key appear in git history? | No - pickaxe search over `--all` returns nothing |
| **Is rotation required?** | **No** |
