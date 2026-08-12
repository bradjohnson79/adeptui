# M42 — Dual HunyuanVideo Model Library Report

**Stamped:** 2026-08-01T18:06:47.225911+00:00  
**Playwright:** True (exit 0 — 4/4 passed against Beta)

## Final provider strategy

| Provider | Status |
|---|---|
| LTX Video | Default |
| HunyuanVideo 1.5 | Installed Optional (when weights verified) |
| HunyuanVideo 13B | Installed Advanced (when weights verified) |
| WAN 2.2 | Optional (unchanged) |
| MiniMax H3 | Coming Soon / reserved |

## Hard constraints honored

- LTX default unchanged; no project migration
- Official Tencent HF sources only
- Independent install queue jobs (never forced dual download)
- Isolated storage paths under `data/models/video/<providerId>/`
- True local T2V gated per-provider certification stamps
- WAN remains available

## Code verification

```json
{
  "provider15": true,
  "provider13": true,
  "engineMap15": true,
  "engineMap13": true,
  "component15": true,
  "component13": true,
  "workflowT2v15": true,
  "workflowI2v15": true,
  "workflowT2v13": true,
  "workflowI2v13": true,
  "ltxDefault": true,
  "wanPresent": true,
  "minimaxComingSoon": true,
  "isolatedDirs": true,
  "uiLibrary": true,
  "playwrightSpec": true
}
```
