# Stability Cull — Read-only Comfy workflow audit handoff

**Kind:** handoff, not a second rewrite program.  
**Date:** 2026-08-23  
**Cull SHA:** `0dd6edf6a94b63b4bcd74e8f06bc888e4fd9ac1c` (includes `2a83a49`)  
**Sources:** committed `config/image-workflows/certified-registry.json` and `config/video-workflows/certified-registry.json` at that SHA; CRS routing in `visual_sheet.py` (working tree, includes uncommitted CC keys); live `GET http://127.0.0.1:8188/object_info` (200, 2007 nodes); `GET http://127.0.0.1:8192/object_info` failed (H3 isolated adapter down).  
**Not done:** no Comfy installs, no graph edits, no Schnick/Korri writes, no queue submits.

Uncommitted dirty `certified-registry.json` adds SenseNova + Qwen Edit 2509 rows. Those keys are **not** in the cull SHA registry. Callers in dirty `visual_sheet.py` still mention them.

## Color key

| Color | Meaning |
|---|---|
| GREEN | Committed Certified (or equivalent) + live nodes that can run the family + product route exists |
| YELLOW | Certified/Built but fingerprint, honesty, or node-name gap; usable with care |
| ORANGE | Draft / experimental / isolated runtime missing; do not default |
| RED | Blocked, remapped, or claimed-ready without a live path |
| BLACK | Absent from committed registry and no live isolated runtime |

## Matrix

| Family | Committed registry | Live `:8188` nodes | Product route | Color | Next repair only |
|---|---|---|---|---|---|
| Qwen 2512 txt2img | `qwen2512.txt2img` Certified | Qwen loaders + `TextEncodeQwenImageEdit*` present | CRS AUTO fallback; Character Sheet | GREEN | Keep family-specific readiness (`qwen_image_2512_models`). Do not remap to Z-Image. |
| Qwen 2512 ref | `qwen2512.ref` Certified | Same Qwen encode nodes | ERS I2I / ref path; CRS must not default this | YELLOW | Confirm ref graph still binds `qwen2512.ref` not `zimage.ref_edit`. |
| FLUX / Kontext txt2img | `flux.txt2img` Certified | 30 Flux-named nodes; **Nunchaku = 0** | CRS AUTO primary when certified/executable | YELLOW | Prove which Flux loader the committed builder uses (no Nunchaku). Do not default if weights missing. |
| FLUX img2img | `flux.img2img` Certified | Flux + Inpaint/VAEEncode present | CRS AUTO when identity crop | YELLOW | Same loader honesty as txt2img. |
| FLUX Kontext edit / fill / in/outpaint | Draft (`flux.kontext_edit`, `flux.edit`, `flux.fill`, `flux.inpaint`, `flux.outpaint`) | Flux nodes present | Edit surfaces; never-default | ORANGE | Leave Draft until a certified graphHash exists. |
| Illustrious | `illustrious.txt2img` Certified | **No Illustrious-named nodes** (generic UNET/CLIP/KSampler) | Anime / Character local | YELLOW | Certified + null `graphHash` is a known cull honesty gap. Do not demote without routing-test repair. |
| Z-Image txt2img / ref / in / out | All four Certified | `TextEncodeZImageOmni` + standard SD stack | Ref-locked CRS still `zimage.ref_edit` | GREEN | Keep Z-Image aliases only for Z-Image keys. |
| Qwen Edit 2509 | **Not in cull SHA registry** (dirty tree only) | `TextEncodeQwenImageEditPlus` present | Dirty CC picker / `qwen_edit_2509.*` | ORANGE | Next CC closure: commit registry rows only with family readiness + never-default. |
| CRS (product) | Uses Flux / Qwen2512 / Z-Image / (dirty) SenseNova / 2509 keys | Family nodes as above | `visual_sheet.py` AUTO Flux→Qwen2512; no silent Z-Image for other families after cull | YELLOW | Unify start payload remains `CRS_GENERATION` / `four_view` / `candidateCount` product=4, cert E2E=1. |
| ERS | `sensenova.ers` not in cull SHA; Qwen ref Certified | Qwen + SenseNova U1 local nodes on `:8188` | Scene / Spatial ERS callers | YELLOW | Audit Spatial→Scene against `qwen2512.ref` vs SenseNova; do not treat SenseNova disk-complete as GPU-ready. |
| Scene | Director `director.scene_render` Certified (video orch.) | LTX/WAN nodes present | Scene Creator + 30s fail-close | YELLOW | Confirm still-image scene path vs video director key. No silent family swap. |
| Spatial → Scene | Not a registry key | Openpose + ControlNet present | `scene_creator_mini.py` + ERS package | YELLOW | Next: one live Spatial camera → Scene still on cert project only. |
| Edit / inpaint | Z-Image inpaint Certified; Flux inpaint Draft | Inpaint + RemBG nodes | Image Edit + CIS | YELLOW | Prefer Certified Z-Image inpaint; keep Flux inpaint Draft. |
| Revision D tracking | Selection/rembg evidence is prior milestone | `RemBGSession+`, `easy imageRemBg` | Intelligent selection | YELLOW | Tracking only; no new rembg architecture. |
| Background remove | `image.background_remove` Deferred | RemBG nodes present | Revision D / utility | ORANGE | Registry Deferred vs live nodes — label honesty, not a rebuild. |
| Timeline I2V | `ltx.simple_i2v`, `ltx.scene` Certified; `video.extend` Certified | 113 LTX nodes | Timeline | GREEN | Keep LTX 2.3 Certified path. |
| LTX 2.5 | `ltx_25.t2v` / `ltx_25.i2v` **Built** at cull SHA | LTX2* nodes present | Dock label capped to Testing by cull | ORANGE | Do not advertise Built as Certified. Promote only after executable+fingerprint. |
| WAN | `wan.first_last_frame`, `wan.three_frame` Certified | 168 Wan nodes | Timeline / first-last | GREEN | Keep family key; no fal silent swap. |
| MiniMax H3 | Not an image-registry row; adapter `:8192` | H3 nodes **also on `:8188`**; `:8192` down | Owner-only, never-default | ORANGE | Isolated adapter is down. Nodes on production Comfy are a containment risk — do not start `:8192` from this audit. Next: confirm H3 never defaults and never shares `:8188` jobs. |
| Upscale | `image.upscale` Certified; `video.upscale` Deferred | ImageUpscaleWithModel + many upscalers | Utility / Timeline | YELLOW | Image GREEN-adjacent; video remains Deferred. |
| MAGI | No Comfy MAGI sampler in object_info (`CreateMagicMask` only) | Not a generation family here | Magi editor is product, not Comfy txt2img | BLACK | Out of this Comfy matrix. |
| Audio-if-Comfy | LTX audio VAE loaders present | `LTXVAudioVAELoader` etc. | LTX A/V, not a standalone Adept audio engine | ORANGE | Do not treat audio VAE nodes as a certified Adept audio product. |
| fal * | Blocked | Cloud, not Comfy | Picker Unavailable (cull dock cap) | RED | Keep Blocked/Unavailable. |
| Imagen | Blocked | N/A | Hidden/unavailable | RED | Keep Blocked. |
| SenseNova U15 | **Not in cull SHA registry**; dirty tree has five keys | 10 SenseNova U1 Local nodes on `:8188` | Dirty CC + committed `sensenova_u15.py` builder | ORANGE | `runtimeReady` must stay false until GPU path is proven. Installed ≠ ready. |

## Priority repairs (recommend only)

1. **H3 containment** — `:8192` down; H3-named nodes exist on production `:8188`. Next owner decision: isolate or document as residual install. Do not default H3.
2. **Commit or drop dirty registry rows** — SenseNova + Qwen Edit 2509 exist in the working-tree registry and in `visual_sheet.py` but not in the cull SHA. That split will break clean-clone Character Creator.
3. **FLUX loader honesty** — Certified Flux without Nunchaku. Next: record which loader/weights the live builder actually uses.
4. **Illustrious fingerprint** — Certified + null graphHash remains a known gap.
5. **LTX 2.5** — keep Testing/Built until executable certification.
6. **Background remove label** — Deferred in registry, nodes live. Honesty pass only.

No implementation in this handoff.
