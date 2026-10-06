# Co-Director Chat Vision + Attachment Reference — Certification

## CURRENT

```text
GO — CODIRECTOR MULTIMODAL VISION + ATTACHMENT REFERENCE + GENERATION HANDOFF E2E CERTIFIED
```

Governing document for this repair. The 2026-08-19 Ollama `images[]` cert remains historical.

Project: Korri Anadriya `beffd3d8-791d-4adf-9c4d-681ec9d4efb0`  
Asset: `Venture Corridor scene.png` `b98585a0-8829-48cc-8c7b-63b9687955bb`  
Vision provider: fal.ai `fal-ai/any-llm/vision` + `google/gemini-2.5-flash-lite`  
Local UI: `http://127.0.0.1:5173/`  
Studio API: `http://127.0.0.1:8758/` (recycled only; new PID 11788)

---

## Classification

**EXISTS + DISCONNECTED → RESTORED**

The approved fal `chat_vision` stack was never removed. Chat was not calling it. `_prepare_chat_request` injected metadata-only attachment text that told the model vision was not run. The filename label `[Attached: Venture Corridor scene.png]` was treated as if it were pixels.

---

## Live proof

- Direct vision: corridor, LQ-05 doors, scuffed metal, Earth in windows. No upload-denial.
- Live utterance through GPT Image 2: vision then `image.generate`. Hosted fallback applied (GPT Image 2 not executable → local). No lighting/style interview.
- Two-image compare: Image 1 darker/more industrial (pipes, grated floor, CREW QUARTERS) vs cleaner Image 2.
- Same visual reference with no new attachment: `image.generate` after API recycle.
- Wrong project id: `PROJECT_NOT_FOUND`. Cross-project asset load: `VisionLoadError`.
- Playwright: 2 passed.

Evidence: `docs/architecture/codirector/evidence/chat-vision/`
