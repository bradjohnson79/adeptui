# Adept UI 1.1 Electron — Phase 2 macOS

The packaged-dependency contract in this report is historical. `pywin32==312` is now a Windows-only marker in `electron/packaged-requirements.txt`. The Mac staging job is described in `electron/E20_MACOS_RUNTIME_ENABLEMENT.md`. This Phase 2 verdict is unchanged.

Verdict: **ADEPT UI 1.1 ELECTRON — MACOS NO-GO**

Native runtime status: **PENDING**. No Apple Silicon machine ran `Adept UI.app` in this mission. A Windows configuration and an unexecuted GitHub job are not a Mac certification.

Public distribution remains separate: signing is not configured, and notarization is waiting on credentials.

## A. Phase 1 entry state

| Item | Value |
| --- | --- |
| Phase 1 verdict | `ADEPT UI 1.1 ELECTRON — WINDOWS FULL GO` in `electron/E17_WINDOWS_FINAL_CERTIFICATION.md` |
| Branch | `feat/character-creator-final-closure` |
| HEAD | `007479e5561e641c7e03e18748873c5349d0ddd5` |
| Electron | 35.7.5 |
| electron-builder | 26.15.3 |
| Desktop version | 1.1.0 |
| App id | `app.adeptui.desktop` |
| Product | Adept UI |

Windows artifacts present on this machine:

| Artifact | SHA-256 |
| --- | --- |
| `electron/dist/win-unpacked/Adept UI.exe` | `3befc5907cc5743ea87c6540cebd15c007dd3a032ae2b680368498a4527cadb1` |
| `electron/dist/Adept UI-Setup-1.1.0-win-x64.exe` | `cb3e1b163ffb6fa348bffe93b4b35db68bd3b96d81975f6c15724d7aa25d14fa` |

The unpacked executable hash matches the Phase 1 record. The installer hash does not. Phase 1 recorded `8cea04a17c755f0624751ee2c595f9cc2f5cebc109f9dcc6407d4ef315021364`. The installer on disk was rebuilt later for the startup-screen change. Windows behavior was not recertified in this mission and was not modified for Mac.

## B. macOS census

This workstation is Windows. `electron-builder` cannot produce a runnable `.app` or `.dmg` here.

`electron/builder.config.cjs` already declares a Mac target:

- `dmg` and `dir`
- arch `arm64` only
- icon `electron/icons/icon.png` (no `.icns` file is built)
- `identity: null`
- `notarize: false`
- artifact name `Adept UI-1.1.0-mac-arm64.dmg`

x64 is not configured. It is not certified.

`.github/workflows/electron-desktop.yml` has a `macos-arm64` job on `macos-latest`. That job only runs a Vite build and `electron-builder --mac --arm64`. It does not stage Studio API, does not stage a macOS Python, and does not launch the app. It was not executed in this mission.

## C. Platform adapters

Shared shell, already present:

- `electron/main.cjs`
- `electron/preload.cjs`
- `electron/endpoint.cjs` — packaged mode is `127.0.0.1:8760` for every OS
- `electron/platform/paths.cjs` — user data comes from `app.getPath("userData")`; packaged Python is `python.exe` on Windows and `bin/python` elsewhere
- `electron/platform/process.cjs` — `netstat`/`powershell` on Windows, `lsof`/`ps` elsewhere
- `electron/platform/menu.cjs` — Mac application menu, About, and Command+Q

Windows-only, left untouched:

- `electron/scripts/build-windows.mjs`
- `electron/scripts/stage-packaged-runtime.mjs` (embeddable Windows Python 3.11.9)
- `electron/scripts/certify-windows.mjs`
- `electron/scripts/certify-installer.mjs`

Mac adapter still required before a runner can produce a working app:

- stage an arm64 CPython and the Studio API inside the Mac build
- omit Windows-only Python pins from that install
- build `icon.icns`
- launch and certify the packaged `.app` on that Mac

## D. Python runtime

`electron/packaged-requirements.txt` is the desktop pin file. It does not include Torch. The Windows staging script installs it into a Windows embeddable Python. That interpreter must not be copied to a Mac.

PyPI lookup for the pins that contain native code:

| Pin | macOS arm64 |
| --- | --- |
| numpy, pillow, pydantic_core, cryptography, psycopg-binary, mediapipe, opencv wheels, tiktoken, watchfiles, and the other native pins checked | wheel or universal2 wheel exists |
| greenlet 3.5.4 | `macosx_11_0_universal2`, which includes arm64 |
| pyinjector 1.3.0 | universal2 wheel exists for CPython 3.11 |
| pywin32 312 | Windows wheels only. No macOS wheel and no portable source build |

`pywin32` is not imported by `studio-api/app`. It is still a hard pin in the shared requirements file, so `pip install -r electron/packaged-requirements.txt` on macOS arm64 fails. That is a backend dependency blocker for the file as it is used today. The Windows pin file was not edited.

`PACKAGED PYTHON ARCH` was not produced. `DEV VENV DEPENDENCY` and `DEV REPO PATH DEPENDENCY` were not measured on a Mac bundle because no bundle exists.

## E. Local AI capability

Not opened on macOS. The packaged pin file has no CUDA and no Torch. Comfy and local model readiness on a Mac remain unclassified at runtime. No CUDA-ready claim is made.

## F. Comfy

Not launched on macOS. The Windows Comfy installation was not packaged. A fresh Mac profile would need Setup to configure a Mac Comfy. That behavior was not executed.

## G–T. Runtime gates

Not run. There is no `Adept UI.app` and no `.dmg`.

## U. Windows regression check

No shared Electron source was changed in this mission, so the Windows suite was not rerun.

## V. Final matrix

| Check | Result |
| --- | --- |
| MACOS NATIVE RUNNER | FAIL |
| MACOS ARM64 BUILD | FAIL |
| Adept UI.app | FAIL |
| DMG | FAIL |
| PACKAGED RENDERER | NOT RUN |
| PACKAGED API :8760 | NOT RUN |
| DEV VITE DEPENDENCY | NOT RUN |
| DEV VENV DEPENDENCY | NOT RUN |
| DEV REPO DEPENDENCY | NOT RUN |
| FRESH PROFILE PROJECT COUNT | NOT RUN |
| FIRST PROJECT PERSISTENCE | NOT RUN |
| BOOT MANAGER | NOT RUN |
| CO-DIRECTOR STREAM | NOT RUN |
| MAJOR PRODUCT SURFACE SMOKE | NOT RUN |
| LOCAL CAPABILITY TRUTHFULNESS | NOT RUN |
| COMFY SUPPORT CLASSIFICATION | NOT RUN |
| SINGLE INSTANCE | NOT RUN |
| CLEAN SHUTDOWN | NOT RUN |
| EXTERNAL LINKS | NOT RUN |
| OFFLINE FONTS | NOT RUN |
| MAC UPDATE ARTIFACT SELECTION | NOT RUN |
| UPDATE USER DATA LOSS | NOT RUN |
| USER PROJECTS BUNDLED | NOT RUN |
| MODEL WEIGHTS BUNDLED | NOT RUN |
| WINDOWS BINARIES BUNDLED | NOT RUN |
| SECRETS BUNDLED | NOT RUN |
| MACOS E2E | FAIL |
| WINDOWS SHARED REGRESSIONS | 0 |
| MACOS SIGNING | NOT CONFIGURED |
| NOTARIZATION | PENDING CREDENTIALS |

## W. Final verdict

**MACOS BACKEND DEPENDENCY BLOCKER:** `pywin32==312` is pinned in `electron/packaged-requirements.txt` and has no macOS wheel. A Mac staging install of that file cannot succeed until a Mac requirements adapter omits it. The Windows pin file stays as it is.

**MACOS NATIVE RUNNER:** this session ran on Windows. The GitHub `macos-arm64` job was not dispatched, and that job does not yet stage Python or the Studio API or launch the app.

Linux was not modified. Linux remains pending Phase 3.

ADEPT UI 1.1 ELECTRON — MACOS NO-GO
