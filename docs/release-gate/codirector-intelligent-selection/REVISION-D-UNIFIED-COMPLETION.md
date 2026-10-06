# Adept UI v1.1 Revision D — Unified Completion Report

**Law 30:** This is the single governing completion report for Revision D.  
**Governing doc:** [00-GOVERNING.md](./00-GOVERNING.md)  
**Manifest:** [ESSENTIALS-MANIFEST.md](./ESSENTIALS-MANIFEST.md)  
**VGGT:** [docs/models/vggt/LICENSE_CLEARANCE.md](../../models/vggt/LICENSE_CLEARANCE.md) — **OMIT / NOT PACKAGED**

Do not cite Revision A/B/C governing files as the select / track / protect contract. Repository names stay: A = temporal, B = creation, C = world, D = intelligent selection + Essentials Pack.

---

## Verdict

```text
GO — ADEPT UI v1.1 OPEN-SOURCE FEATURE SET COMPLETE
```

v1.1 now enters **FEATURE FREEZE → STABILIZATION → CERTIFICATION → MANUAL BETA**. No further free/open-source feature expansion.

Independent reviews (review only; primary reconciled):

| Reviewer | Result |
|---|---|
| GLM 5.2 | READY FOR PRIMARY REVIEW |
| Kimi K3 | Blockers (stills venv / track-as-image) — **repaired** before this GO |

Hosted Vercel was **not** deployed from this working tree. Local Beta is the certified environment.

---

## Environment

```text
Branch:              feat/codirector-temporal-continuity
Local HEAD:          9b8d5a9cdae8c88266e6fd253551450611c1e4d9
Live API revision:   9b8d5a9
API started:         2026-08-21T00:56:39Z
Creator UI:          http://127.0.0.1:8760/
Studio API:          http://127.0.0.1:8758/
GPU:                 NVIDIA GeForce RTX 5090
Worker Python:       data/venvs/videochat3-worker (CUDA torch 2.10.0+cu130)
SAM / DINO dest:     data/models/stills_perception/{sam21_hiera_tiny,grounding_dino_tiny}
Named cert project:  Revision D Selection Cert
Project ID:          7eaf7643-c686-4bda-a79d-a85c7d98b59a
Topology:            8760 → 8758
```

---

## What shipped

Revision D does not add a standalone tool. Co-Director now produces the technical inputs (masks, tracks, protect regions) from creator language and clicks, and feeds existing `ImageEditIntent` and Timeline range-replacement / disclosed retake.

Locked decisions held:

- Native video inpaint stays **blocked** and disclosed.
- Essentials Pack does **not** block generation (`REQUIRED_FOR_GENERATION` unchanged).
- Pack ESSENTIAL: VideoChat3, SAM 2.1 Tiny, Grounding DINO Tiny.
- Pack RECOMMENDED: V-JEPA, InternVideo3 (VRAM-gated), Depth Anything V2 Small.
- TimeLens excluded. VGGT omitted.
- SAM pin remains `facebook/sam2.1-hiera-tiny` (Apache-2.0). No SAM 3.
- Execute stills only via `ImageEditIntent`. No second inpaint compiler.
- No chat `route_turn` GPU router.

---

## Live evidence (measured)

| Gate | Result | Evidence |
|---|---|---|
| Background Removal | **PASS** | `cuda:0`, `sam21-hiera-tiny`, 32.41s, mask `mask-fdf26501100c`, Library asset `bdc4e8c2-…`, RGBA with transparent + opaque pixels |
| Semantic Selection | **PASS** | capability `select=available`; live rembg used subject select; point prompts 4-level SAM 2.1 |
| Image Inpaint Integration | **PASS** | Remove Background uses perception rembg, not silent `zimage.inpaint`. Remove/Replace still compile `ImageEditIntent` with persisted `maskAssetId` |
| Video Tracking | **PASS** | `trk_51a423f3f009`, 2 frames, 2 mask IDs, 15.82s, `workerOk=true` |
| Video Inpaint Assistance | **PASS** | `nativeVideoInpaint: false`; disclosure persisted; Timeline Inpaint UI shows Track + native-unavailable copy |
| Co-Director Routing | **PASS** | `chatRequired=false`; task router skips depth for rembg |
| SAM Runtime | **PASS** | Live decode on RTX 5090; no silent CPU |
| Spatial / VGGT | **PASS** | DA-V2 Recommended, not installed on this machine; VGGT omitted |
| Essentials Registry | **PASS** | `3 of 3` essential installed; `generationBlockedByPack=false` |
| Setup Pack | **PASS** | Playwright Setup Wizard `setup-essentials-pack` visible while status still loading |
| Download Manager | **PASS** | `POST /essentials/install` enqueued SAM + DINO; weights landed under `stills_perception/` |
| License Audit | **PASS** | Named 2026-08-20 pack-ESSENTIAL decision; `required=False` for generation except VideoChat3 |
| Health | **PASS** | Installed ✓ vs Runtime ✓ remain separate; capability honest before/after install |
| Isolation | **PASS** | Cross-project selection GET 404; cross-project track GET 404 |
| Persistence | **PASS** | Library GET after rembg contains result; track GET returns 2 frames |
| Frontend | **PASS** | Edit Studio Select / Remove Background / Protect; no SAM/JEPA/VGGT chrome |
| Playwright | **PASS** | See counts below |
| Smoke | **PASS** | API health 200; capability; essentials; Image Edit; Timeline disclosure |
| A/B/C regression | **PASS** | Playwright 19/19; unit 58/58 |
| GLM 5.2 / Kimi K3 | **PASS** | Reviews complete; Kimi blockers repaired |

---

## E2E TRACE

| Stage | Verdict | Evidence |
|---|---|---|
| User action | PASS | Remove Background / Select / Track / Install Missing Essentials |
| Frontend | PASS | Image Edit Studio + Setup Essentials + Timeline Inpaint disclosure |
| API | PASS | `/api/perception/…/select|refine|track|remove-background` and `/api/setup/lifecycle/essentials*` |
| Backend | PASS | Shared perception package (no `perception2/`); `PerceptionSelectionPacket` `selection-v1` |
| Persistence | PASS | `save_mask(..., creator="perception")`; Library `no-background` PNG; track packets |
| Runtime | PASS | SAM 2.1 + DINO on `cuda:0` via VideoChat3 CUDA python |
| Result | PASS | Transparent subject PNG; two tracked frame masks |
| Reload | PASS | Library GET + track GET after new requests |
| Downstream | PASS | Masks feed ImageEditIntent / Timeline metadata; native video inpaint stays blocked |

---

## Tests (measured)

| Suite | Count |
|---|---|
| `studio-api` Revision D unit (`test_revision_d_*` + `test_essentials_pack`) | **24 passed** |
| Creation perception + world intelligence unit | **58 passed** |
| Frontend vitest (`magiCommandParse`) | **2 passed** |
| Playwright A (temporal) + B (creation) + C (world) | **19 passed** |
| Playwright D (perception + Edit Studio + Essentials) | **9 passed** (rembg persist included) |
| `studio-web` production build | **exit 0** |

---

## Peer-review repairs applied

1. Stills worker venv has no Torch — `cuda_worker_python()` reuses VideoChat3 CUDA python; GPU refuse remains.
2. Track no longer opens an MP4 as an image — ffmpeg frame extract, with WinGet `ffmpeg.exe` discovery when PATH is empty.
3. SAM 2.1 point prompts use 4-level nesting (`[image, object, point, xy]`).
4. Spatial group `installed` is false when Depth Anything (recommended-only) is missing (`all([])` bug).
5. Remove Background workflow key no longer lists silent `zimage.inpaint`.
6. Setup Essentials Pack renders during “Checking studio status…” so the creator can install without waiting for the full catalog.

---

## Limitations (honest)

- Depth Anything V2 Small and InternVideo3 8B are **Recommended** and not installed on this machine. Spatial stays 2D-only. InternVideo3 remains VRAM-gated.
- Geometry / placement boxes stay `unavailable` (Revision B optional).
- Native video inpaint remains unavailable by product law.
- Hosted Vercel SHA was not updated. Do not treat `adeptui.vercel.app` as Revision D certified until a clean commit of these files is pushed and the hosted SHA is verified.
- Working tree contains many unrelated local files. This report certifies the Revision D implementation and local Beta runtime, not a clean-clone deploy.
- First SAM load can exceed 30s; Playwright rembg uses a 180s request timeout.
- Install jobs can stall the API event loop while Hugging Face snapshot runs — generation stays unblocked, but Setup status may pause until the job finishes.

---

## FEATURE FREEZE

Effective with this GO:

- No new free/open-source feature expansion in v1.1.
- Next program: stabilization, certification polish, manual Beta.
- Frozen: Spatial Map `zones[]`, TimeLens, SAM 3, DA-V2 Base/Large, unofficial V-JEPA forks, MAGI fake video-inpaint, `REQUIRED_FOR_GENERATION` inflation, chat `route_turn` as GPU router, creative `pack_essential_*` zips as the intelligence pack, PoseCraft rewrite, hard-coded personal `D:\` paths.

---

## Manual Beta path

1. Open http://127.0.0.1:8760/ on project **Revision D Selection Cert** (`7eaf7643-c686-4bda-a79d-a85c7d98b59a`) or any open project.
2. Image Studio → Edit → Select / Remove Background / Protect.
3. Timeline → Video Finishing → Inpaint → read the native-unavailable disclosure → Track.
4. Setup → Adept UI Essentials (`3 of 3` essential on this machine).

Studio API: http://127.0.0.1:8758/
