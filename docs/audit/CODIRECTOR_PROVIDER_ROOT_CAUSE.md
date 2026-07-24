# Co-Director Provider — Root Cause

**Date:** 2026-07-24  
**Branch:** `phase1b/codirector-provider-reliability`

## Exact failing request

**User-visible string** (only construction site):

`studio-web/src/components/CoDirector/CoDirectorSession.tsx` → `send()` catch:

```text
I couldn't reach the local model. ${err.message}
```

When the Adept API / Vite proxy is unreachable, `err.message` is the browser `TypeError` **`Failed to fetch`**, producing:

```text
I couldn't reach the local model. Failed to fetch.
```

When Adept is up but Ollama is down, Adept returns HTTP 503 and the suffix is typically:

```text
Ollama is not reachable at http://127.0.0.1:11434
```

## Current request path

```text
Browser CoDirectorSession.send
  → fetch("/api/assistant/chat")          [api.ts]
  → Vite proxy → Adept API :8742
  → assistant_chat()                      [routers/api.py]
  → ollama_reachable() / chat_ollama()    [assistant.py]
  → httpx → http://127.0.0.1:11434/api/*
```

**The browser does not call Ollama directly.** CORS to :11434 is not the failure mode for this string.

## Root cause (composite)

1. **Fragile UX:** Any transport/`ApiError` is string-interpolated into a chat bubble with no structured code, Retry, or Settings action.
2. **No preflight:** Chat submits even when health already reports Ollama offline / no models.
3. **No E2E mock:** Critical suite never exercises chat against a deterministic provider; real Ollama absence surfaces as opaque failures in manual use.
4. **Hardcoded default model** (`gemma4:12b`) with no FE model discovery/selection on the chat path.
5. **502/503 detail** is a bare string — FE cannot classify CONNECTION_REFUSED vs MODEL_NOT_FOUND vs BACKEND_UNAVAILABLE.

## Affected files

- `studio-web/src/components/CoDirector/CoDirectorSession.tsx`
- `studio-web/src/api.ts` (`assistantChat`, `assistantHealth`, `ApiError`)
- `studio-api/app/routers/api.py` (`assistant_chat`, `assistant_health`)
- `studio-api/app/assistant.py` (`chat_ollama`, `ollama_reachable`)
- `studio-api/app/config.py` (`ollama_url`, `ollama_model`)

## Proposed architecture

Provider-neutral Adept gateway under `/api/codirector/*`:

- Browser ↔ Adept only  
- Adept ↔ Ollama (or Mock in `STUDIO_E2E`)  
- Structured error codes + recommended actions  
- Model discovery + selected model persistence  
- Health/preflight before send  
- Preserve user message + Retry  

Legacy `/api/assistant/*` remains as thin aliases.
