# M42 Subagent Ownership Matrix

**Binding:** Only one active implementation owner per file tree at a time.  
**Peer reviewer:** Issues `PASS` or `RETURN FOR CORRECTION` only; no edits unless reassigned.  
**Primary agent:** Sole integrator and certifier.

| Area | Active owner | Peer reviewer | Forbidden for owner |
|---|---|---|---|
| Character Creator / visual sheet / Korri identity | KorriPipelineSubagent | IntegrationReviewer | Voice UI redesign, cert gate rewrites |
| ComfyUI / `zimage.*` workflow builders + registry fingerprints | ComfyWorkflowSubagent | KorriPipelineSubagent | UI chrome, voice APIs |
| HelpTip / (?) captions | HelpSystemSubagent | AccessibilityReviewer | Provider/queue/DB |
| One-project library policy / cert project reuse | LibraryScopeSubagent | IntegrationReviewer | Unrelated UI |
| Voice Creator UI | VoiceCreatorUISubagent | UxReviewer | Provider adapters, queue, Character Creator generation |
| Voice Performance UI | VoicePerformanceUISubagent | UxReviewer | Provider adapters, queue, Character Creator generation |
| Playwright M42 voice/character specs | TestSubagent | Primary agent | Product feature code except testids |
| Certification reports | DocsSubagent | Primary agent | Implementation code |

## File-tree ownership (active sprint)

| Path glob | Owner |
|---|---|
| `studio-api/app/character_identity/visual_sheet.py` | KorriPipelineSubagent |
| `studio-api/app/character_identity/api.py` (character/visual-sheet routes) | KorriPipelineSubagent |
| `studio-web/src/components/CharacterProfileWorkspace.tsx` | KorriPipelineSubagent |
| `studio-web/src/components/TimelineCharacterCreatorPanel.tsx` | KorriPipelineSubagent |
| `studio-api/app/workflows/image_tools.py` (`zimage.*`) | ComfyWorkflowSubagent |
| `config/image-workflows/certified-registry.json` | ComfyWorkflowSubagent |
| `studio-web/src/components/HelpTip.tsx` | HelpSystemSubagent |
| `studio-web/src/styles.css` (`.help-tip*`) | HelpSystemSubagent |
| `scripts/m42_w43_korri_visual_sheet_cert.py` | LibraryScopeSubagent |
| `scripts/m33j_korri_create_from_brief.py` | LibraryScopeSubagent |
| `.cursor/rules/creator-first-ui.mdc` (one-project clause) | LibraryScopeSubagent |
| `studio-web/src/components/VoiceCreatorWorkspace.tsx` | VoiceCreatorUISubagent |
| `studio-web/src/components/VoicePerformanceWorkspace.tsx` | VoicePerformanceUISubagent |
| `studio-web/src/styles.css` (`.voice-studio-*`) | VoiceCreatorUISubagent / VoicePerformanceUISubagent (coordinate) |
| `tests/e2e/m42/m42-w43-korri-voice-creator.spec.ts` | TestSubagent |
| `tests/e2e/m42/m42-w44-voice-performance.spec.ts` | TestSubagent |
| `docs/release-gate/m42/M42_SUBAGENT_*.md` | DocsSubagent / Primary agent |

## Conflict rule

If two assignments need the same file, the primary agent serializes ownership. The second agent waits or receives a narrowed contract.

---

## Qwen-Image-2512 sprint (ACTIVE HARD STOP)

| Area | Active owner (GPT-5.4) | Peer reviewer | Forbidden for owner |
|---|---|---|---|
| Model install + ComfyUI qwen-2512 workflows + registry | Qwen2512RuntimeIntegration | Independent Engineering Review | Prompt Package, Style Registry, Character Creator UX, final GO |
| Qwen prompt compiler / identity locks / corrections | Qwen2512PromptIntelligence | Consistency reviewer | Comfy runtime, Style profile content, final GO |
| Reference roles / recipes / deviation contracts | Qwen2512ConsistencyArchitecture | Character Creator reviewer | Model install, Style profiles, final GO |
| Style Intelligence profiles | Qwen2512StyleIntelligence | Visual continuity reviewer | Canonical identity, Comfy runtime, final GO |
| Character Creator UI defaults + sheet handoff | Qwen2512CharacterCreatorUI | UX reviewer | Prompt compiler internals, Style package, final GO |
| Asset / identity / VersionGraph / persistence | Qwen2512AssetPersistence | Integration reviewer | Prompting, styles, final GO |
| Tests / Playwright / failure recovery | Qwen2512TestSubagent | Primary agent | Production logic unless reassigned |
| Independent Korri visual review (RO) | Qwen2512VisualReview | — | Any edits / certification |
| Independent engineering review (RO) | Qwen2512EngineeringReview | — | Any edits / certification |
| Architecture / integration / real E2E / GO | **Primary agent** | — | — |

### File-tree ownership (Qwen-2512 sprint)

| Path glob | Owner |
|---|---|
| `studio-api/app/workflows/qwen_image_2512.py` | Qwen2512RuntimeIntegration |
| `comfyui/workflows/qwen-image-2512/**` | Qwen2512RuntimeIntegration |
| `config/image-workflows/certified-registry.json` (qwen-image-2512 keys) | Qwen2512RuntimeIntegration |
| `studio-api/app/image_prompting/**` | Qwen2512PromptIntelligence |
| `studio-api/app/character_consistency/**` | Qwen2512ConsistencyArchitecture |
| `studio-api/app/style_intelligence/**` | Qwen2512StyleIntelligence |
| `studio-web/src/components/CharacterProfileWorkspace.tsx` | Qwen2512CharacterCreatorUI |
| `studio-api/app/character_identity/visual_sheet.py` | Primary agent (serial after runtime+prompt ready) |
| `tests/e2e/m42/m42-qwen-2512-*.spec.ts` | Qwen2512TestSubagent |
| `artifacts/m42/w43-qwen-2512/**` | Shared evidence (owners write their folders) |
| Final certification reports / gate verdict | Primary agent only |
