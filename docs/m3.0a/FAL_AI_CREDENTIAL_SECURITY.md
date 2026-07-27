# M3.0a — fal.ai Credential Security

How the user's fal.ai API key is stored, transmitted, exposed, and revoked. BYOK: the key
belongs to the user, Adept holds it only to render on their behalf.

| Field | Value |
|-------|-------|
| Secret name | `fal_api_key` |
| Store | `studio-api/app/secrets_store.py` |
| Date | 2026-07-26 |

---

## 1. At rest

| Property | Detail |
|----------|--------|
| Location | `{STUDIO_DATA_DIR}/secrets/fal_api_key.enc` |
| Encryption | Fernet (AES-128-CBC + HMAC-SHA256) |
| Master key | `{STUDIO_DATA_DIR}/secrets/master.key`, generated on first use, `chmod 0600` |
| File mode | `0600` where the platform supports it |
| Database | Never — the key is not in any table, migration, or backup of the SQLite file |
| Logs | Never — no code path logs the key, and `run_fal_model` errors carry status codes and fal's message, not the credential |

The master key sits beside the encrypted secret. That protects against a leaked backup of the
secret file alone, and against casual inspection; it is not protection against an attacker who
already has read access to the whole data directory. This is the same threat model as every
other credential in the studio and is stated here so it is not mistaken for something stronger.

## 2. Verification metadata

`{STUDIO_DATA_DIR}/secrets/fal_api_key.verified.json` records the outcome of the last probe:

```json
{
  "verified": true,
  "message": "Key accepted by fal.ai.",
  "checkedAt": "2026-07-26T00:00:00Z",
  "fingerprint": "<sha256 prefix of the key>",
  "detail": {"httpStatus": 404, "probeEndpoint": "fal-ai/veo3.1"}
}
```

The fingerprint is a SHA-256-derived identifier already used to distinguish keys in the UI; it
is not reversible to the key. `set_secret_verification` strips any `key`/`api_key` entry from
`detail` before writing, so a future caller cannot accidentally persist the secret through the
metadata path.

If the stored key changes, the fingerprint stops matching and `get_secret_verification`
returns nothing — the status degrades to `unverified` rather than describing a key that is no
longer present.

## 3. In transit

| Hop | Protection |
|-----|-----------|
| Browser → API | The key appears exactly once, in the body of `PUT /api/fal/key`, over the local loopback interface |
| API → fal.ai | HTTPS, `Authorization: Key <key>` header — never a query string, so it cannot land in an access log or proxy history |
| API → Browser | Never. No endpoint returns the key or any usable prefix of it |

The E2E suite asserts the header-not-URL property directly
(`test_status_never_returns_the_key`) so a future refactor that moves the key into a URL
fails the build.

## 4. What the UI and the model can see

| Consumer | Sees | Does not see |
|----------|------|--------------|
| `GET /api/fal/key` | `configured`, masked `hint`, `fingerprint`, `state`, `verified`, `verifiedAt`, `message` | the key |
| Project Settings panel | The same status, plus fal's message | the key (the input is write-only and cleared on success) |
| Co-Director `get_cloud_render_status` | `credentialState`, `cloudRenderUsable`, `verifiedAt`, engines, guidance text | the key, the hint, and the fingerprint |
| Setup diagnostics | Verified / Key Rejected / Not Verified / Not Configured | the key |

The Co-Director tool is deliberately the most restricted of these: model output can be echoed
into a chat transcript, so it receives no credential material at all — not even the mask.

## 5. Lifecycle

| Action | Effect |
|--------|--------|
| Save (`PUT /api/fal/key`) | Probe first. Rejected → HTTP 400, nothing written. Accepted → encrypt, store, record `verified`. Unreachable → store, record `unverified` |
| Re-verify (`POST /api/fal/key/validate`) | Re-probe the stored key, overwrite the record. A revoked key downgrades to `invalid` |
| Clear (`DELETE /api/fal/key`) | Deletes both the encrypted secret and the verification record |
| Replace | Old verification record no longer matches the fingerprint and is ignored |
| Revoked at fal | Reads `verified` until the next probe or the next failing render, which raises `FalAuthError` |

## 6. Probe cost

Validation issues one authenticated `GET` against a fal queue-status URL with a random,
non-existent request id. No job is submitted and no credits are consumed. The billing
endpoint is deliberately **not** used for validation: it requires an admin-scoped key, so a
perfectly good render-only key would be reported as invalid.

## 7. Residual risks

| Risk | Status |
|------|--------|
| Read access to `STUDIO_DATA_DIR` yields the key | Accepted — master key is co-located, same as other studio credentials |
| Key valid at save, revoked later | Detected at next probe or first failing render; "Re-verify" is one click |
| Render-only key cannot read usage | Expected; usage is optional and its absence never affects credential state |
| Key shared across projects | By design — one installation, one fal account |
