# READY FOR CREATOR CLICK-TEST — Timeline Publish + MAGI CTAs

**When:** 2026-09-13 ~19:40 PT  
**Verdict:** READY FOR CREATOR CLICK-TEST (backend publish real; MAGI queues real job; CTAs gated)

## Where to click
1. Open Adept at http://127.0.0.1:5173
2. Project: **Korri Anadriya**
3. Scene: **Venture Corridor Dialogue** (NOT Scene 12B / Quarters Interview)
4. Look at **Preview Monitor** top center chrome:
   - **PUBLISH** (teal) — registers Library Video Published Master from full stitch
   - **UPSCALE WITH MAGI** (indigo) — queues MAGI upscale on full stitch/published master only; does **not** auto-publish

## Expected
- Before Final Check PASS / accepted-issues: both buttons **hidden**
- This scene was seeded to `SCENE_FINISHED` (fixture for click-test only; FC code not rewritten) + existing stitch, with publish cleared so **PUBLISH** appears
- Click PUBLISH → badge becomes **Published**; Library asset tag `video_published_master`
- Click UPSCALE WITH MAGI → job queues; Timeline stays editable; no auto-publish
- After a re-stitch that changes stitch asset id → **Changes Pending** + **UPDATE PUBLISHED**

## Caveats
- Vite HMR should pick FE; if CTAs missing, hard-refresh browser (Ctrl+Shift+R)
- MAGI from this entry uses ffmpeg-scale by default (fast/honest); GPU Real-ESRGAN still available via Magi Editor
- Upscale returns a **queued job** (asset id appears when job finishes)
- Do **not** use Scene **12B** (Primary green keep_current media)
- GENERATE SCENE overlay idle-hide untouched (Primary-owned)
- Playwright A–E + full IMPLEMENT.md still in progress after this ping

## API smoke already proven
- Refuse before PASS: 400 NOT_PUBLISH_READY
- Publish after PASS: 200 + Video Published Master + honest provenance
- MAGI full-stitch entry: 200 ok, autoPublished=false
