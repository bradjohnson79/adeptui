# Hosted API Provider Setup — Report

## Verdict (implementer)

```text
IMPLEMENTER PASS — awaiting independent Composer 2.5 API gates
```

## Scope

- Existing kie / wavespeed / fal BYOK
- New OpenAI-compatible endpoints: `/api/hosted-providers/openai-compatible`
- Secrets via Fernet `secrets_store` (masked; never echoed)
- Capability discovery from `/v1/models` (LLM when detected)
- `budgetPreference` wired into hosted resolver
- Dock picker groups: NATIVE / OLLAMA / CUSTOM / DOCKER / HOSTED API

## Evidence

- Playwright: `tests/e2e/setup/hosted-api-provider-setup.spec.ts` → PASS
- Unit resolver budgetPreference covered in `test_provider_usage.py`
