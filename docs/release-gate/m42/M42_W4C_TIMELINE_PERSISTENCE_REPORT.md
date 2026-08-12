# M42 Wave 4C — Persistence Compatibility

| Key | Behavior |
|---|---|
| `adept_ui_last_workspace` | Read via `resolveWorkspace` (director→timeline); write canonical `timeline` |
| Layout / Magi keys | Unrelated; unchanged |
| Rollback | Legacy query `workspace=director` still resolves |

**Verdict:** **GO**
