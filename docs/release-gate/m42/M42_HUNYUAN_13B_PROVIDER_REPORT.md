# M42 — HunyuanVideo 13B Provider Report

**Provider ID:** `hunyuan-video-13b-local`  
**Stamped:** 2026-08-01T18:05:58.818357+00:00  
**Installed/healthy (this host):** False

## Scope

Independent install, remove, repair, verify, health, benchmark, and workflow keys for `hunyuan-video-13b-local`.
Official Tencent Hugging Face source only. Does not overwrite the sibling Hunyuan provider.
LTX remains the default Adept video engine.

## Evidence

- `artifacts/m42/hunyuan/hunyuan-video-13b-local/`
- Workflow keys under `hunyuan15.*` or `hunyuan13b.*`
- True local T2V requires `t2v_certified.json` for this provider only

## Code checks

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
