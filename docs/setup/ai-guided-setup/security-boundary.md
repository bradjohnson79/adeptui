# Security Boundary

## Non-negotiable rule

Co-Director discovers and proposes. Trusted backend services execute.

## Allowed execution owners

- setup catalog/status/diagnostics
- Source Manager verification and source assignment
- Source Manager install jobs
- trusted runtime repair/reverify actions

## Forbidden behaviors

- no LLM shell installs
- no unreviewed scripts
- no silent file deletion
- no silent provider switching
- no uncertified-upstream auto update
- no secret echoing in UI or docs

## Practical result

AI-Guided Setup may summarize a plan or suggest a model. It may not bypass Source Manager or introduce an unreviewed install path.
