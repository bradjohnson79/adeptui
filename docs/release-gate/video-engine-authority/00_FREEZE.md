# Video Engine Authority — Frozen Contracts

**Date:** 2026-09-05  
**Branch:** `feat/character-creator-final-closure`  
**HEAD:** `b6156455` (working tree dirty; this freeze is not a commit)  
**Project:** Korri Anadriya `beffd3d8-791d-4adf-9c4d-681ec9d4efb0`  
**Surfaces:** Vite `http://127.0.0.1:5173/` · Studio API `http://127.0.0.1:8758/`  
**Governing:** this file. Supersedes Sept 4 local-video “no local T2V / LTX 2.3 is the live LTX path” for family set and T2V. Supersedes `seedance-2.0.md` line “Adept does not expose Seedance 2.5.”

CRT workstream IDs (not in-repo before this freeze):

- **CRT-A / CRT-B** — certified leaves, Wave6 consumer fields, `/api/engines`, CREATE picker authority
- **CRT-C / CRT-G** — setup/config filenames, extra model paths, Ollama defaults
- **CRT-D** — live Comfy graph contracts (MCP-only)

## COMFY BEFORE (read-only)

- Port `:8188` HTTP 200 `system_stats`
- PID **69108**
- Comfy `0.32.0` · torch `2.10.0+cu130` · GPU RTX 5090
- Route A `:8192` also listening (PID **15272**) — do not start/stop
- **COMFY RESTARTED?: NO**
- Comfy MCP: no Cursor namespace. `comfy-mcp.exe` not found under `data/venvs`. **Workflow-level cert = E2E BLOCKED until MCP attaches.**

## Live walk (measured 2026-09-05)

`GET /api/healthz` → `{"status":"ok"}`  
`GET /api/engines` is still `fal_catalog.list_engines_for_ui()` — **second catalog**:

| id | label | group |
|---|---|---|
| auto | Auto Select (recommend) | auto |
| minimax-h3 | MiniMax H3 (Default · local) | local |
| ltx | LTX Video (local ComfyUI) | local |
| hunyuan15 | HunyuanVideo 1.5 (local optional) | local |
| hunyuan13b | HunyuanVideo 13B (local advanced) | local |
| wan | WAN 2.2 (local optional) | wan |
| fal_seedance | Seedance 2.0 (fal.ai) | fal |
| fal_kling | Kling 2.5 Turbo Pro (fal.ai) | fal |
| fal_veo | Veo 3.1 (fal.ai) | fal |
| fal_runway | Runway Gen-3 Turbo (fal.ai) | fal |

Missing from `/api/engines`: `ltx-2.5` / `ltx-2.5-distilled`, `seedance-2.0`, `seedance-2.5`. Retired locals advertised as first-class. Only one Seedance row (labeled 2.0).

`GET /api/director-timeline/generators` join (16 rows). Evidence: `evidence/LIVE_TIMELINE_GENERATORS.json`.

| id | label | readiness | executable | adapter | t2v / i2v / r2v |
|---|---|---|---|---|---|
| ltx-local | LTX 2.3 (Local) | Requires Setup | no | ltx-local | none / ltx.simple_i2v / ltx.scene |
| ltx-2.5-full | LTX 2.5 Full | Testing | no | **ltx-local** | ltx_25.t2v Ready / ltx_25.i2v Ready / ltx_25.i2v |
| ltx-2.5-distilled | LTX 2.5 | Testing | no | **ltx-local** | same |
| ltx-2.5-comfy | LTX 2.5 Comfy INT8 | Testing | no | **ltx-local** | same |
| wan-local | WAN 2.2 First/Last Frame | Requires Setup | no | wan-local | none |
| hunyuan-video-1.5-local | HunyuanVideo 1.5 | Requires Setup | no | hunyuan-video-1.5-local | none |
| hunyuan-video-13b-local | HunyuanVideo 13B | Requires Setup | no | hunyuan-video-13b-local | none |
| minimax-h3 | MiniMax H3 | Ready | yes | minimax-h3-t2v-local | route_a.t2va / route_a.i2va / h3.ref2v |
| minimax-h3-i2v-local | MiniMax H3 Image-to-Video | Ready | yes | minimax-h3-i2v-local | none / route_a.i2va / none |
| seedance-fal | Seedance (fal.ai) | Ready | yes | seedance-api | no per-surface records |
| seedance-kie | Seedance (Kie) | Unsupported | no | none | none |
| kling-fal / kling-kie / veo-* | hosted | Testing | no | stubs | — |

**Confirmed defects to repair (not re-decide):**

1. Dual catalog: `/api/engines` ≠ Timeline join.
2. LTX 2.5 execution bind is `ltx-local` (2.3 adapter). Silent 2.3 fallback.
3. Seedance collapsed to `seedance-fal` / generic “Seedance (fal.ai)”. No `seedance-2.5` product.
4. CREATE picker hardcodes `ALL_ENGINES` including retired locals.
5. Capability registry still blocks queue video on **LTX 2.3** `ltx_checkpoint`.
6. Home `?project=&workspace=` does not open CREATE; editor path is `/project/{id}?workspace=txt2vid`.

## Frozen authorities

### 1. Active v1.1 local video families

**Only:**

- `ltx-2.5-distilled` (creator token `ltx-2.5` / label **LTX 2.5**) — Comfy `:8188` `ltx_25.*`
- `minimax-h3` (label **MiniMax H3**) — CREATE Route A; Timeline `h3.ref2v` on `:8188`

`ltx-2.5-full` and `ltx-2.5-comfy` remain **Testing**, not CREATE defaults.

**Retired / compatibility locals (not Auto Select, not CREATE defaults):**

- `ltx-local` (LTX 2.3)
- `wan-local` (WAN 2.2)
- `hunyuan-video-1.5-local`, `hunyuan-video-13b-local`

Saved Timeline batches that already name those IDs still resolve in place.

### 2. Hosted Seedance family (distinct API models)

| Product ID | Label | Provider | Adept model IDs (do not invent more) | Locality |
|---|---|---|---|---|
| `seedance-2.0` | Seedance 2.0 | fal | `bytedance/seedance-2.0/text-to-video`, `.../image-to-video`, `.../reference-to-video` | HOSTED / API |
| `seedance-2.5` | Seedance 2.5 | fal | `bytedance/seedance-2.5/text-to-video`, `.../image-to-video`, `.../reference-to-video` | HOSTED / API |

Each has its own readiness, workflow modes, duration/resolution truth **as Adept implements**, paid/approval flag, capability metadata.

**Never** classify either as local Ready. One version Ready must not paint the other Ready.

**Legacy aliases (not creator-facing product rows):**

- `seedance-fal`, `seedance-api`, `fal_seedance` → migrate to `seedance-2.0` only when metadata proves 2.0 (current live adapter notes + fal_catalog IDs prove 2.0). Otherwise **legacy / ambiguous**.
- `seedance-kie` stays a separate unsupported product. Not fal 2.0 or 2.5.

**No silent remap** 2.5 ↔ 2.0.

Kling / Veo / Runway remain honest Testing / Requires Setup. Discovery “Seedance 1 Pro” / `fal-ai/bytedance/seedance/v1/pro` is a third-identity leak — do not revive it as a product.

### 3. Per-surface workflow eligibility

Eligibility = surface + model + actual workflow. Timeline R2V flags never decide CREATE.

- **T2V:** LTX 2.5 `ltx_25.t2v`; MiniMax `route_a.t2va`; Seedance 2.0 T2V; Seedance 2.5 T2V (when adapter sends 2.5 T2V). Kling/Veo/Runway honest. Hide LTX 2.3 / WAN / Hunyuan from Auto Select.
- **1 Frame:** LTX 2.5 `ltx_25.i2v`; MiniMax `route_a.i2va`; Seedance 2.0 I2V; Seedance 2.5 I2V when wired. WAN disabled (needs last frame).
- **3 Frame:** local LTX 2.5 `ltx_25.i2v` only (H3 has no `multiFrame`). Hosted Seedance versions only if that adapter truly accepts three stills — otherwise hide (do not silent-drop to I2V). WAN FLF is not a CREATE default.
- **Timeline:** LTX 2.5 one-cond R2V `ltx_25.i2v`; MiniMax `h3.ref2v` on `:8188`. Seedance 2.0 / 2.5 R2V as separate rows only when video-ref R2V is wired for that version.

### 4. Auto Select

Local-first, surface-aware. Prefers MiniMax H3 / LTX 2.5. Never fal. Never retired local. Never pick Seedance 2.0 or 2.5 because a local is on-demand or preparing. If no local workflow is executable, stay on Auto Select with a creator-language reason.

### 5. Hosted / local classification

- LTX 2.5 / MiniMax H3 = local.
- Seedance 2.0 / 2.5 / Kling / Veo / Runway = hosted/API.
- Wave6 consumer fields are **not** CREATE picker authority.

### 6. Persistence + lineage

Jobs/assets persist: `requestedEngineId`, `resolvedEngineId`, `provider`, `modelVersion`. A 2.5 generation must never later appear as generic Seedance or 2.0.

### 7. Execution binds (no silent 2.3 / 2.0 collapse)

- `ltx-2.5-*` must **not** bind Timeline adapter `ltx-local`. Own adapter queues `ltx_25.*`.
- `seedance-2.5` must **not** bind `seedance-api` 2.0 submit.
- `/api/engines` is a **view of the join**, not `list_engines_for_ui()`.
- Frontend picker consumes the join. `engineSurfacePolicy` is a presenter over `workflowCapabilities`.
- Recommend / VRAM / MIL resolve only to frozen **local** families + `auto`.

## Seedance Adept-implemented capability (do not invent)

**2.0 (already wired, version the product):** T2V / I2V / R2V (R2V only with video ref). Adept durations 4–12s, 480p/720p, max 4 images + 1 video, no audio refs. Paid fal approval required.

**2.5 (identity in scope; modes only if adapter sends them):** Same three fal endpoint names. Until Adept implements 2.5 submit, readiness is **Testing** or **Requires Setup**, never Ready-via-2.0. Do not claim 30s / 50 refs / 1080p in Adept until the adapter actually sends those params.

## Parallel work may begin

This file is the team-release gate. Subagents extend this join. No new registries.
