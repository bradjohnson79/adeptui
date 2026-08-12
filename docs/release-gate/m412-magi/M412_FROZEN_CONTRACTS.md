# M4.12 MAGI — Frozen Contracts

Branch: `feature/m4-12-magi-editor-post-production`

## Sequence document

`studio-web/src/magiSequence/types.ts` — `MagiSequenceDocument`, `MagiClip`, `MagiTrack`, edit command kinds.

## Focus / keyboard

`studio-web/src/magiSequence/focus.ts` + `MagiFocusContext.tsx` + `useMagiKeyboard.ts`

- Regions: `timeline | viewer | media_bin | inspector | text_input | modal | none`
- Delete/Backspace only when `timeline` owns focus and target is not a typing surface
- Space / JKL / arrows only for `timeline` or `viewer`
- Cmd/Ctrl+C/V/Z native in text fields; MAGI stack when timeline owns focus

## API

- `GET /api/magi/projects/{projectId}/sequence`
- `PUT /api/magi/projects/{projectId}/sequence`

Store: `studio-api/app/magi/sequence/store.py`
