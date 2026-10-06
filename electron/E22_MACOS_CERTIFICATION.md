# Adept UI 1.1 Electron — macOS certification

**ADEPT UI 1.1 ELECTRON — MACOS FULL GO**

`electron/E20_MACOS_RUNTIME_ENABLEMENT.md` is historical. It described enablement before an Apple Silicon package had been built or launched.

Certified commit: `ebb70a92c8e026e0e707203325f29fc42c45bde6`
Run: https://github.com/bradjohnson79/adeptui/actions/runs/37548457402
Runner: GitHub `macos-14`, `uname -m` = `arm64`, macOS 14.8.9 (23J631).
Python staged in the package: CPython 3.11.14, `arm64`, platform `macOS`.
Windows and Linux jobs on this dispatch: skipped. The push that published this commit skipped Linux packaging. The Windows installer was not rebuilt.

## Packages that executed

| Artifact | Path on the runner | Bytes | SHA-256 |
| --- | --- | ---: | --- |
| `Adept UI.app` | `electron/dist/mac-arm64/Adept UI.app` | 982309268 | `58efc1d0f3b1d0032956bad555f938095b1526a4571970ab86a4e2ca350de842` |
| `Adept UI-1.1.0-mac-arm64.dmg` | `electron/dist/Adept UI-1.1.0-mac-arm64.dmg` | 395748020 | `550b981a706b3af82a98029f4eb9021b0837f7d0de7aace785442329f42ddffa` |

The `.app` hash is the bundle contents. The `.dmg` hash is the file bytes.

## Observed gates

Native runner, arm64 Python, Studio API `:8760` healthy, Background Services `:8759` healthy, owner count 1, duplicate managers 0, Boot `GO`, failed required checks 0, fresh profile 0, project persisted after relaunch, 15 surfaces passed, single instance, both port collisions passed, foreign listeners left alive, API loss detected, DMG copy launched into the same user-data root, package audit clean, x86_64-only required binaries 0.

Co-Director stream wiring `PASS`. Model execution `UNAVAILABLE`. CUDA `NO`. Comfy `OPTIONAL/SETUP REQUIRED`. False ready states 0.

`codesign --force --deep --sign -` was a CI launch accommodation. It is not distribution signing.

## Separate from the functional verdict

- `MACOS SIGNING — NOT CONFIGURED`
- `NOTARIZATION — PENDING CREDENTIALS`
- `CHECKSUM BYTE VALIDATION — NOT IMPLEMENTED`
- `SIGNATURE VALIDATION — NOT IMPLEMENTED`
- `APPLICATION ROLLBACK — NOT IMPLEMENTED`
- `X64 SUPPORT — NOT TARGETED`

## Limitation

The surface walk attempted one `fonts.googleapis.com` stylesheet request. Electron cancelled it. No Google font file finished loading. `GOOGLE FONT NETWORK DEPENDENCY = 0`. Fraunces and Manrope in the package are the bundled faces.

## Local regression before the native run

Electron node tests: 19 passed. Boot and supervisor pytest, after the Darwin `lsof`/`ps` owner lookup: 64 passed. Those lookups do not replace the Windows or Linux paths.
