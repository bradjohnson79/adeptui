# Certification

## Record type

`ProviderCertificationRecord` persists:

- component id/name
- certified flag
- certified version/date
- recipe id
- latest verification summary
- calibration profile
- monitor findings
- lifecycle status

## Persistence

Records are stored under the setup lifecycle data directory in the local data root. Certification is additive to live verification; it never bypasses the current verifier.

## Flow

1. Install or link component.
2. Verify component health.
3. Record calibration defaults and machine profile.
4. Persist certification against the trusted recipe/version.

## Archive

Archiving marks the record archived without silently deleting files or removing install history.
