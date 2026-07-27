# M3.0c — Production Bible Full-Stack Certification

## B10 evidence

The deterministic/mock Bible lifecycle is **VERIFIED** for the bounded cases covered by
`studio-api/tests/test_m30_bible_mock_apply.py`: a valid proposal can be approved and
applied, and a proposal can be rejected without changing the Bible. The browser approve
and reject flow was also recorded in the M3.0 completion evidence.

This does not certify every Bible schema, provider, or browser viewport.

## Cases matrix

| Case | Status | Evidence / remaining proof |
|---|---|---|
| Bible import preview | **VERIFIED** | Existing API/test lifecycle. |
| Bible import confirm | **VERIFIED** | Existing API/test lifecycle. |
| Mock character proposal schema | **VERIFIED** | B10 test validates against `CharacterData`. |
| Browser approve valid proposal | **VERIFIED** | M3.0 completion browser evidence and B10 test. |
| Browser reject proposal | **VERIFIED** | M3.0 completion browser evidence and B10 test. |
| Bible version increments after approval | **VERIFIED** | B10 test asserts resulting version. |
| Rejected proposal leaves Bible unchanged | **VERIFIED** | B10 test asserts unchanged version/entity state. |
| Provider-generated proposal across all entity types | **PENDING** | No complete live provider matrix recorded. |
| Invalid/unknown fields fail before approval | **VERIFIED** | B10 validator guard test. |
| Concurrent edits/conflict resolution | **PENDING** | No full-stack proof recorded. |
| Import/export fidelity for all entity classes | **PENDING** | Broader matrix still owed. |

## Certification conclusion

The approve/reject authority boundary is certified for the tested B10 workflow. Full-stack
coverage beyond those cases remains **PENDING** and must not be inferred from the mock
provider path.
