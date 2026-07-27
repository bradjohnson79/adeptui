# M3.0c — Co-Director Intelligence and Authority Proof

## Authority and specialist output

`studio-api/app/codirector/intelligence/specialist_runner.py` contains the provider
payload unwrap path (`_unwrap_provider_payload`) and normalizes wrapped specialist
responses before schema validation. This is code-proven, including wrapper aliases and
field alias normalization.

The authority boundary remains explicit: specialist findings recommend and propose;
approval-bearing mutations require the relevant user approval route. Heuristic
`limited-analysis` output is labeled and is not represented as live model reasoning.

## Four-brief proof

The required live proof is four materially different briefs, each producing a distinct,
traceable specialist digest through the intended provider path. Existing tests prove
provider-vs-limited-analysis behavior and non-identical results for the covered mock
brief pair, but they do not constitute four live production briefs.

| Proof item | Status |
|---|---|
| B15 unwrap present in `specialist_runner` | **VERIFIED** by source and unit-test coverage |
| Provider output schema validation | **VERIFIED** by existing intelligence tests |
| Limited-analysis honesty label | **VERIFIED** by existing intelligence tests |
| Four materially different live briefs | **PENDING** |
| Production provider request IDs/artifacts retained | **PENDING** |

No claim is made that a live provider was available during this certification.
