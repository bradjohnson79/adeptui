# Testing

Unit:

```bash
studio-api/.venv/Scripts/python.exe -m pytest studio-api/tests/codirector/prompt_intelligence -q
```

Playwright:

```bash
PLAYWRIGHT_BASE_URL=http://127.0.0.1:8760 npx playwright test tests/e2e/m42/m42-codirector-prompt-intelligence.spec.ts --project=chromium
```
