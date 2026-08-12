# Project Password Protection — Certification Report

| Field | Value |
|---|---|
| **Recorded** | 2026-07-31T03:49:39.406873+00:00 |
| **projectPasswordProtectionGo** | `true` |
| **Binary only** | Yes |
| **mock** | `false` |

## Completion statement

GO — Adept UI Project Password Protection is fully wired through the Project Library, project APIs,
Timeline/MAGI/asset routes (middleware), Co-Director lock refusal, exports (honest encrypted deferral),
authorization via unlock grants, audit logging, and secure unlock sessions, with no plaintext storage,
no route bypasses, and automated unit certification.

## Flags

```json
{
  "projectPasswordMenuOperational": true,
  "projectPasswordSetupOperational": true,
  "projectPasswordHashingOperational": true,
  "projectPasswordPlaintextStorageZero": true,
  "projectUnlockOperational": true,
  "projectUnlockGrantOperational": true,
  "projectLockNowOperational": true,
  "projectPasswordChangeOperational": true,
  "projectPasswordDisableOperational": true,
  "projectPasswordResetOperational": true,
  "projectProtectedRoutesOperational": true,
  "projectDirectRouteBypassZero": true,
  "projectCoDirectorLockEnforced": true,
  "projectBruteForceProtectionOperational": true,
  "projectSecurityAuditOperational": true,
  "projectDuplicateProtectionOperational": true,
  "projectExportProtectionHonest": true,
  "projectCrossProjectGrantDenied": true,
  "projectPasswordPlaywrightPassed": true,
  "projectPasswordNoMockData": true,
  "projectPasswordReportsComplete": true,
  "projectPasswordArtifactsComplete": true
}
```

## Security model

- Hash: Argon2id (preferred) or PBKDF2-SHA256 fallback
- Unlock: short-lived grant token (cookie + `X-Adept-Project-Unlock` header)
- Never store/transmit password hash to the browser
- Co-Director refuses locked projects without inventing data

Artifacts: `artifacts/project-security/`
