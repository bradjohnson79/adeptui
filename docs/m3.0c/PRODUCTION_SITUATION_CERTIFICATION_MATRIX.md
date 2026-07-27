# M3.0c Production Situation Certification Matrix

Phase 18 was executed against the live local API with fixtures disabled. The
already-paid fal Seedance motion proof was reused after queue certification; no
new fal job was submitted. Each situation has a real local ComfyUI still, a
real imported PCM WAV (S07 is represented on the SFX track), and a reused
motion asset. Image approval/publication, timeline approval, and handoff
evidence are recorded in `artifacts/m30-situations/situation-finish.json`.

The final export validation is in
`artifacts/m30-situations/phase18-final-validation.json`: all 12 export jobs
finished, every pack exists, every `project.json` contains `director_json`,
and every pack contains non-empty PNG, WAV, and MP4 media. Read-only SQLite
durability evidence is in `artifacts/m30-situations/persistence-check.json`.
Generative audio remained provider-unavailable; imported audio is disclosed and
was used for the production timeline.

| Situation | Production case | Real media and completion evidence | Result |
|---|---|---|---|
| S01 | Live-action dramatic | Still, imported music WAV, reused Seedance MP4; approvals, handoffs, timeline, persistence, export pack validated | EXECUTED |
| S02 | Suspense/thriller | Still, imported ambience WAV, reused Seedance MP4; approvals, handoffs, timeline, persistence, export pack validated | EXECUTED |
| S03 | Music video | Still, imported music WAV, reused Seedance MP4; approvals, handoffs, timeline, persistence, export pack validated | EXECUTED |
| S04 | Animated | Still, imported music WAV, reused Seedance MP4; approvals, handoffs, timeline, persistence, export pack validated | EXECUTED |
| S05 | Commercial | Still, imported music WAV, reused Seedance MP4; approvals, handoffs, timeline, persistence, export pack validated | EXECUTED |
| S06 | Dialogue-heavy two-person | Still, imported dialogue-bed WAV, reused Seedance MP4; approvals, handoffs, timeline, persistence, export pack validated | EXECUTED |
| S07 | Action/chase | Still, imported SFX WAV on SFX track, reused Seedance MP4; approvals, handoffs, timeline, persistence, export pack validated | EXECUTED |
| S08 | Fantasy/sci-fi | Still, imported ambience WAV, reused Seedance MP4; approvals, handoffs, timeline, persistence, export pack validated | EXECUTED |
| S09 | Documentary/interview | Still, imported room-tone WAV, reused Seedance MP4; approvals, handoffs, timeline, persistence, export pack validated | EXECUTED |
| S10 | Stylized 2D/anime | Still, imported music WAV, reused Seedance MP4; approvals, handoffs, timeline, persistence, export pack validated | EXECUTED |
| S11 | Product/location reconstruction | Still, imported room-tone WAV, reused Seedance MP4; approvals, handoffs, timeline, persistence, export pack validated | EXECUTED |
| S12 | Full short-form capstone | Still, imported music WAV, reused Seedance MP4; approvals, handoffs, timeline, persistence, export pack validated | EXECUTED |
