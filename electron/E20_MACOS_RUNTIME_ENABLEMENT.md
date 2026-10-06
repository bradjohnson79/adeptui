# Adept UI 1.1 Electron — macOS runtime enablement

Verdict: **ADEPT UI 1.1 MACOS RUNTIME ENABLEMENT — NO-GO**

Phase 2 certification was not rerun. It remains **ADEPT UI 1.1 ELECTRON — MACOS NO-GO**.

This machine is Windows. The new Mac job was not dispatched, because that would require publishing this change. No `Adept UI.app` was built or launched here.

## What changed

`electron/packaged-requirements.txt` remains the only maintained pin list. `pywin32==312` now carries `sys_platform == "win32"`. macOS staging generates its install file from that list and does not pass `pywin32` to pip. Linux selection of the same list also drops it. There is no second hand-written requirements file.

The Mac job in `.github/workflows/electron-desktop.yml` now runs on `macos-14` and, on that runner only:

1. refuses anything other than Apple Silicon
2. downloads relocatable CPython 3.11.14 arm64 (`python-build-standalone` 20260127)
3. installs the generated Mac requirements with that Python
4. stages Studio API source beside it
5. builds `Adept UI.app` and the arm64 dmg
6. copies the app outside the checkout, ad-hoc signs it so the runner can launch it, and waits for `http://127.0.0.1:8760/api/healthz` plus `GET /api/boot/certification`

That ad-hoc signature is not Developer ID signing. Public signing stays **NOT CONFIGURED**. Notarization stays **PENDING CREDENTIALS**.

The Windows package script was not edited and the Windows installer was not rebuilt. `pywin32` is still on disk in `electron/dist/win-unpacked/resources/python`.

## Measured here

| Check | Result |
| --- | --- |
| WINDOWS PYWIN32 PRESENT | YES |
| MACOS PYWIN32 INSTALL ATTEMPT | 0 (marker selection; pip did not run on a Mac) |
| LINUX PYWIN32 INSTALL ATTEMPT | 0 (marker selection; the Linux job does not pip-install) |
| WINDOWS SHARED REGRESSIONS | 0 (`node --test` 12 passed, 0 failed) |
| MACOS NATIVE RUNNER | NOT RUN |
| PACKAGED PYTHON ARM64 | NOT RUN |
| STUDIO API STAGED | NOT RUN |
| Adept UI.app BUILT | NOT RUN |
| Adept UI.app LAUNCHED | NOT RUN |
| STUDIO API :8760 | NOT RUN |
| BOOT MANAGER REACHABLE | NOT RUN |
| VITE DEPENDENCY | NOT RUN |
| DEV VENV DEPENDENCY | NOT RUN |
| DEV REPO DEPENDENCY | NOT RUN |
| WINDOWS BINARIES IN MAC PACKAGE | NOT RUN |
| PYWIN32 IN MAC PACKAGE | NOT RUN |

On this Windows machine, `node electron/scripts/build-macos.mjs` and the Mac staging script both exit 1 with `MACOS NATIVE RUNNER = FAIL`.

## Remaining blocker

A native Apple Silicon runner has not executed the upgraded job. Compilation of the workflow file is not a Mac launch. Phase 2 resumes only after that runner reports Studio API HTTP 200 on `127.0.0.1:8760`.
