# M41 Phase 4.1A — Test Report

| Field | Value |
|---|---|
| **Phase** | 4.1A — Video Runtime & Generation Infrastructure |
| **Date** | 2026-07-29 |
| **Suite** | `studio-api/tests/test_m41_41a_video_runtime.py` |
| **Live cert** | **Outstanding** — see checklist below |

---

## Automated coverage (unit / mocked)

| Area | Tests | Proves |
|---|---|---|
| Compatibility registry + WAN middle frame | catalog / validate_inputs | Registry contracts |
| LatentSync node aliases | missing_nodes | Alias groups |
| VRAM safety states + safe config | estimate_vram (mocked free VRAM) | State machine logic |
| Canonical job contract | roundtrip | Serialization |
| Failure classification | classify_exception | Typed errors |
| Output gate | missing / nonzero file | Gate checks without ffprobe |
| Deep halt + confirm stopped | halt_prompt mocks | Interrupt/delete/confirm *API usage* |
| Halt not confirmed | active prompt persists | `COMFY_CANCEL_NOT_CONFIRMED` |
| Cancel mid-wait | wait_for_prompt cancel_check | Waiter aborts |
| Deferred preflight | video.upscale | Honesty |
| Diagnostics payload | build_diagnostics | Shape |

**These do not prove live ComfyUI stop, VRAM release, or playback.**

---

## Live cancellation evidence checklist (required for full GO)

### LTX

- [ ] Start long generation; record `prompt_id`  
- [ ] Cancel during sampling  
- [ ] Confirm `/interrupt` received  
- [ ] Confirm prompt absent from active execution  
- [ ] Confirm absent from pending queue  
- [ ] Confirm no completed asset registered  
- [ ] Confirm VRAM drops toward post-load/idle or below safe threshold  
- [ ] Confirm next queued generation starts normally  
- [ ] Confirm Studio status path: `cancelling` → `cancelled` (not immediate `cancelled`)  
- [ ] Negative: if Comfy keeps running past timeout → `cancel_failed_runtime_active` / `COMFY_CANCEL_NOT_CONFIRMED`  

### WAN

- [ ] Repeat full LTX procedure on WAN FLF  

### LatentSync

- [ ] Cancel during processing  
- [ ] Verify ffmpeg / decoding / child processes do not continue after `cancelled`  

### Playback / output gate (live)

- [ ] Real render passes output gate  
- [ ] Browser-compatible playback (proxy if needed)  
- [ ] Poster/proxy optional path observed when ffmpeg present  

### free_memory honesty

- [ ] Document observed VRAM after cancel (active generation released vs full idle)  
- [ ] Do not claim full model unload unless measured  

---

## Manual / operator checklist (non-cancel)

- [ ] Preflight blocked when nodes/models missing  
- [ ] Safe VRAM config consent shown when tight/high-risk/insufficient  
- [ ] `/diagnostics/video-runtime` reflects live Comfy + GPU  
- [ ] fal path still requires paid fallback approval  

---

## Gate status implied by this report

| Unlock | Status |
|---|---|
| Wave 6 wiring | Allowed under CONDITIONAL GO |
| Wave 6 production activation | **Blocked** until live checklist above is filled |
