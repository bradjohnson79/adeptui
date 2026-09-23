## MiniMax H3 Three-Frame Runtime Truth

**Updated:** 2026-09-09 (PT) — Adept CREATE 3 Frame integrate

### Proven local CREATE path (authority)

Local MiniMax H3 on Route A:

- **First + Last (empty middle):** `MiniMaxH3ImageToVideo(first_frame, last_frame)` — **no** `MiniMaxH3AddGuide`, **no** third `LoadImage`.
- **First + Middle + Last:** same base + `MiniMaxH3AddGuide(image=middle, frame_idx=length//2)`; guider consumes AddGuide; sampler latent stays on I2V.
- **Forbidden:** duplicate first/last as fake middle; partner Hailuo FLF for middle; Ref2V-as-middle; Timeline/CRS/Co-Director for this surface.

Proofs: `theme_walk/h3_3frame/PROOF_A_LOCAL_2FRAME_GRAPH.json`, `PROOF_B_LOCAL_3FRAME_GRAPH.json`.

### Honesty

- `threeFrameNative=True` for the local AddGuide path only.
- Default CREATE strategy: `middle-guidance-b` (optional middle).
- Legacy `segmented-a` remains in code for historical plans but is **not** the CREATE execute path.
- Partner `MinimaxHailuo03FirstLastFrameNode` has **no** middle socket and is **not** used for Adept 3 Frame.

### UI

- Generate enabled when First + Last present (Middle optional).
- Preview Monitor uses the same Route A poll + preview_bus path as 1 Frame.
