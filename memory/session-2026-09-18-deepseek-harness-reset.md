# Session Memory: 2026-09-18 — Deepseek Harness Clean Reset

Harness-only mission. No Adept product systems (Timeline, Co-Director, Comfy, creators) were modified.

## Discovery map (before reset)

| Path | Class | Notes |
|---|---|---|
| `C:\AdeptFilmWorks\AIVideoStudio\deepseek-harness` | INSTALL | Local npm wrapper; only `package.json` + lock + `node_modules`. Dep: `@deepseek-ai/dsh@0.1.0-rc.6` (`dsh` CLI). Not a global install. |
| `C:\Users\bradj\.dsh` | WORKSPACE STATE (root) | Official single-root home (`$DSH_HOME` else `~/.dsh`). **This is why prior reinstalls failed.** |
| `~\.dsh\sessions\` | CONVERSATION STATE | **173 MB / 231 `.zstd` session logs.** Workspaces `--C-AdeptFilmWorks-AIVideoStudio--` (~230) and `--C-AdeptFilmWorks-AIVideoStudio-deepseek-harness--` (1). Each dir is `session.jsonl.zstd`. |
| `~\.dsh\storages\workspace.json` | CONVERSATION STATE | Workspace `ad520d49-1dcb-4f58-8670-c053306af1fe` bound to `C:\AdeptFilmWorks\AIVideoStudio` with **13 live session IDs** + 2 archived. Reloaded on every `dsh web` from this repo. |
| `~\.dsh\storages\session_projcache*` | CACHE | Projection cache of those sessions (~814 KB + dir). |
| `~\.dsh\attachments\v1\objects\` | CONVERSATION STATE | 44 hashed attachment objects (~31 MB). |
| `~\.dsh\settings.yaml` | CONFIG | Models/providers/theme. Safe to restore. Default model at discovery: `openrouter` / `z-ai/glm-5.3-flash`. Deepseek V4 Flash/Pro listed. |
| `~\.dsh\.credentials.yaml` | CREDENTIAL + SESSION | `refs` = provider key names (`DEEPSEEK_API_KEY`, `OPENROUTER_API_KEY`, `OLLAMA_API_KEY`). `records.client-connection/browser-session` = persisted browser grant — **session restoration, do not restore.** |
| `~\.dsh\.anonymous-user-id` | WORKSPACE STATE | 37-byte identity token. Do not restore. |
| `~\.dsh\profiles\web` | CONFIG | Auto-init web profile. Safe to let first boot recreate. |
| `~\.dsh\settings.yaml.pre-visual-review-*.bak` | CONFIG | Old settings backup. Archive only. |
| Adept `studio-web` / `studio-api` | SHARED — DO NOT DELETE | **No Deepseek Harness wiring found.** Journey 11 = N/A (standalone `dsh web` on `:3080`). |
| Comfy `:8188`, Studio API `:8758`, MiniMax `:8192`, project JSON | SHARED — DO NOT DELETE | Untouched. |

No Harness Windows service, scheduled task, or Run-key autostart. No `DSH_HOME` env override. Default web bind: `127.0.0.1:3080`.

## Stale-state root cause (proven)

`@deepseek-ai/dsh` keeps **all user data under `~/.dsh`**, not under the npm install.

`workspace.json` reattaches the Adept repo workspace and its session ID list. Session bodies live as `session.jsonl.zstd`. A browser-session grant in `.credentials.yaml` can re-auth the old UI session.

Uninstalling / reinstalling `deepseek-harness/node_modules` never deletes `~/.dsh`. Next launch looks like a continuation of August 2026 chats.

## Reset protocol

1. Forensic **move** of entire `~\.dsh` to `C:\Users\bradj\.dsh-forensic-20260918` (outside the repo; contains secrets — never commit).
2. Restore into a **new** `~\.dsh` only: `settings.yaml` + sanitized `.credentials.yaml` (`refs` only, no `records`).
3. Fresh `npm install` of `@deepseek-ai/dsh` in `deepseek-harness\`.
4. Boot `dsh web`, certify a brand-new conversation, then persistence isolation.

## Old session IDs that must be absent after reset

From `workspace.json` at discovery: `session-4ea21ee4-…`, `session-0ec4a333-…`, `session-04ba72ed-…`, `session-f9b4016c-…`, `session-ebea631f-…`, `session-6372f2a3-…`, `session-f3379c79-…`, `session-8b93c583-…`, `session-0b1f6630-…`, `session-35fbb77d-…`, `session-3013b9a5-…`, `session-7993dec6-…`, `session-297d2a0a-…`. Workspace id `ad520d49-1dcb-4f58-8670-c053306af1fe`.
