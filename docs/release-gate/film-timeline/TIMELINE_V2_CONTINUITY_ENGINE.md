# Timeline V2 continuity engine

Date: 2026-09-27  
Branch: `feat/character-creator-final-closure`  
HEAD at backup: `ca8f3c0cc25cf09e665047363cfb4ebecc2bb89b`  
Backup: `backups/timeline-continuity/2026-09-27-ca8f3c0c/RESTORE.md`

FilmTimeline remains the Timeline owner. ShotState remains the shot authority. The continuity packet lives on `segment.generationMetadata["continuity"]`.

## What shipped

- `studio-api/app/film_timeline/continuity.py` extracts the last frame, a short tail, and a head still with `extract_frame_png`, caches them by asset id and packet version, and clears that segment plus the next seam after a retake.
- The orchestrator prepares the previous packet before Continue or the next planned piece, and records the new packet when a segment completes. A seam warning stays on the existing status line. There is no paid retry.
- Local MiniMax stays Reference-to-Video (`minimax-h3-i2v-local`, `generationMode="reference"`).
- LTX Continue uses the installed one-image `LTXVImgToVideo` path. The builder's extra end-image batch is not connected to that node, so it is not treated as a live first/last-frame path.
- The duration menu is 3–20 seconds. `plan_duration` still refuses lengths that are not a legal combination. LTX 17 seconds is refused. MiniMax 20 seconds is planned as 15 then 5.
- Qwen2.5-Omni is registered for full continuity review. Generate and Continue still run when it is absent, and the packet records review unavailable.
- Preview height uses the existing Timeline preview-height preference. The left panel collapses with an icon, and the last width and tab stay in workspace preferences.

## Open-source classification

Baseline is native provider context, ShotState, the previous video or the verified LTX start image, the last frame, tail frames, and Omni when it is installed. No candidate below showed a measured gain over that baseline, so none was installed.

| Candidate | Class | Decision |
| --- | --- | --- |
| ffmpeg frame extract and signal stats | REQUIRED | Already in the product. Used. |
| Existing shot stitch | REQUIRED | Already in the product. Used. |
| Qwen2.5-Omni 7B | REQUIRED for full review only | Registered. Not a generation dependency. Model not present, so review is unavailable. |
| ComfyUI-H3-Motion-Context / OBVPM | USEFUL OPTIONAL | Not installed. License not cleared. No measured long-form gain. Left out. |
| LTX first/last-frame batch in `ltx_25_builder` | NOT NEEDED as a live path | `LTXVImgToVideo` consumes one start image. The end-image batch is not wired to it. |
| ComfyUI-VDN-H3 | NOT NEEDED | Not in the live MiniMax graph. |
| comfyui-speed-minimaxH3 | DUPLICATE FUNCTION | Live EasyCache comes from Comfy extras. |
| Optical-flow, interpolation, and extra stitch packs | NOT NEEDED | Would add a second stitcher. No measured seam gain. |
| WAN wrapper | NOT NEEDED | Retired. Not a Timeline owner. |

## Licenses already in use

- ComfyUI and KJNodes: GPL-3.0.
- LTX community license, including the commercial-revenue threshold and Attachment A item 20.
- ffmpeg: gyan.dev full build.
- comfyui-speed-minimaxH3 is GPL-3.0 and is not the live EasyCache node.
- ComfyUI-VDN-H3 1.4.0 is Apache-2.0 and is not required by the live graph.

## Tests

`studio-api/tests/test_film_timeline_continuity.py` covers packet cache, retake invalidation, duration 3–20, the LTX 17 second refusal, MiniMax remaining reference-video only, Omni note reuse, the Timed Prompt beating an Omni camera note, and a real ffmpeg still extract.

Paid Kling, Seedance, and Veo runs: NOT RUN.

Disposable MiniMax and LTX 40–60 second Continue runs: NOT RUN. No generation was submitted.

## Verdict

`NO-GO — TIMELINE V2 CONTINUITY`

The service, wiring, duration rule, review registration, and workspace controls are in place. Full-review Omni is YELLOW because the model is not installed, and that does not block generation. The live disposable MiniMax and LTX continuity runs were not executed, so the continuity chain is not fully verified.
