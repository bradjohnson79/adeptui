# Adept UI 1.1 Electron — Windows Final Certification

Date: 2026-10-06

Verdict: **ADEPT UI 1.1 ELECTRON — WINDOWS FULL GO**

The earlier byte-hash failure is closed in section AH. The live project count, project folders, and logical database contents are preserved. Unexpected semantic mutations measured in the recertification are 0.

Checksum validation, package signature validation, and application rollback are **NOT IMPLEMENTED**. They are deferred distribution-hardening items. They are not recorded as PASS.

MACOS: PENDING NATIVE RUNNER
LINUX: PENDING NATIVE RUNNER

## A. Baseline

| Item | Measured |
| --- | --- |
| Branch | `feat/character-creator-final-closure` |
| HEAD | `007479e5561e641c7e03e18748873c5349d0ddd5` |
| Electron | 35.7.5 (builder 26.15.3) |
| Product version | 1.1.0, win32 x64, `app.adeptui.desktop` |
| Live DB | `C:\AdeptFilmWorks\AIVideoStudio\data\studio.db` |
| Live DB bytes | 97,013,760 |
| Live DB SHA-256 | `6822090c91d329a1bb67bed6d409e0f2cfc509dfa3a13015ef3ea465faf05b42` |
| Live projects | 152 |
| Project folders | 69 |
| Asset folders | 52 |
| Vite :5173 | PID 7884 |
| Studio API :8758 | PID 7540 |
| Background Services :8759 | PIDs 16496, 46676, 10940, 41924 |
| Desktop API :8760 | no listener |
| Comfy :8188 | PID 31048, HTTP 200 |
| Installer Authenticode | Status 2, SignerCertificate null (NotSigned) |

No source file was edited in this certification. The artifacts under test were not rebuilt.

## B. Artifact identity

| Artifact | Bytes | SHA-256 |
| --- | --- | --- |
| `electron/dist/win-unpacked/Adept UI.exe` | 201,233,408 | `3befc5907cc5743ea87c6540cebd15c007dd3a032ae2b680368498a4527cadb1` |
| `electron/dist/Adept UI-Setup-1.1.0-win-x64.exe` | 290,610,156 | `2aaa7da6a8629d7678d3a5df0e1b99e2d89226d351e44e9d0b06ccb47c82ce6b` |

These hashes were recomputed after the disposable 1.1.1 fixture build and matched the baseline. The 1.1.1 fixture was written only to `%TEMP%\adept-upgrade-dist`.

Unpacked tree: 891,213,768 bytes, 20,142 files.
Packaged Python: 484,685,685 bytes, 17,032 files.
Renderer: 83,398,971 bytes, 752 files.
API source: 25,167,706 bytes, 2,284 files.

SIGNED = NO
CERTIFICATE = NONE
SMARTSCREEN BYPASS USED = NO
WINDOWS CODE SIGNING = NOT CONFIGURED

## C. Unpacked EXE

Launch copy, outside the repository: `%TEMP%\adept-ui-isolated-win\Adept UI.exe` (same bytes as the dist executable).

- Window and packaged renderer loaded.
- Health `http://127.0.0.1:8760/api/healthz` = 200.
- API command: `%TEMP%\adept-ui-isolated-win\resources\python\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8760`
- `viteContacted` false. `devRepoPathDependency` 0. The command does not use a developer `.venv` or a PATH Python.

UNPACKED EXE LAUNCH = PASS
PACKAGED API PROCESS IDENTITY = PASS
STUDIO API HEALTH = PASS
VITE :5173 DEPENDENCY = 0
DEV .VENV DEPENDENCY = 0
DEV REPO PATH DEPENDENCY = 0
PACKAGED API = 8760

## D. Packaged renderer

Renderer origin during the unpacked run: `http://127.0.0.1:64994`.
Proxy after surface navigation: api 528, media 1, targetPort 8760.
CDP requests to :8758 or :5173: none.
CDP HTTP 5xx: none.
One startup console error, `ApiError: Bad Gateway`, occurred while the packaged API was still coming up. The API log for that run had no HTTP 5xx, and later navigation recorded no 5xx and no exceptions.

PACKAGED RENDERER = PASS
PACKAGED REQUESTS TO :8758 = 0
PACKAGED REQUESTS TO :5173 = 0

## E. Studio API

Packaged mode resolves to `127.0.0.1:8760` through `electron/endpoint.cjs`. The listening process was the packaged `python.exe` with cwd and source under the packaged `resources\studio-api`. Development API PID 7540 stayed on 8758.

PACKAGED STUDIO API :8760 = PASS

## F. Boot Manager

`GET /api/boot/certification` on the packaged API:

- verdict GO
- studioApi `127.0.0.1:8760`
- runtimeMode `electron-packaged`
- failed required checks: 0

Vite is not a required check in packaged mode.

BOOT MANAGER = PASS
FAILED REQUIRED BOOT CHECKS = 0
VITE REQUIRED IN PACKAGED MODE = NO

## G. Product surface smoke

Unpacked Electron, disposable project `Windows Cert Disposable` (`3a18bf09-2a72-4b0c-a6bb-9b880b9c39ef`). Each route rendered with a title of Adept UI Studio and was not an unknown workspace.

Homepage, project home, Co-Director, Character, Prop, Environment, Voice, Image Generator, Storyboard, Timeline, MAGI, Library, Script Writer, Setup, Update Manager, Comfy Manager.

MAJOR PRODUCT SURFACE SMOKE = PASS

## H. Co-Director

A chat stream with no project id returns the SSE error `A project is required`. The certification request included the disposable project id and asked for the single word ready, with no tools and no media generation.

Measured on a later packaged launch (`http://127.0.0.1:60024` proxying to 8760):

- HTTP 200
- `content-type: text/event-stream`
- events: `request_started`, token `ready`, `completed` content `ready`
- model `qwen3.6:35b-a3b`, provider `ollama`
- proxy targetPort 8760

CO-DIRECTOR STREAM = PASS

## I. Comfy Manager

Unpacked and installed `/setup/comfy` both showed Healthy, `127.0.0.1:8188`, PID 31048, Running 0, Queued 0, GPU cuda:0 NVIDIA GeForce RTX 5090.

COMFY MANAGER = PASS
COMFY PORT = 8188
COMFY RESTARTED = NO

## J. Fresh-user profile

Profile: `%TEMP%\adept-ui-final-fresh`. It was an empty directory before launch.

Before the disposable project was created:

- project count 0
- no developer model path in the profile files
- the fresh database file did not contain port 8758 or 8760
- profile files were limited to the new app database, setup state, and empty runtime registries

Boot reached GO.

FRESH PROFILE PROJECT COUNT = 0
FRESH PROFILE USER LIBRARY ASSETS = 0

## K. First-project persistence

Created through the packaged UI: `Windows Cert Disposable` (`3a18bf09-2a72-4b0c-a6bb-9b880b9c39ef`). The create control returned success. The project id was read from `GET /api/projects`. After a normal close and relaunch of the same profile: health 200, project count 1, same name, new packaged API PID 53252.

FIRST PROJECT PERSISTENCE = PASS

## L. Existing-user preservation

A disposable copy of the live database was made while the live hash was still the baseline hash. Copy hash matched before the test. Electron was launched against that copy only.

- project count 152
- sample project `PRODUCTION_FLOW_SMOKE_20261005_151736` (`9ba87fb5-89b5-4f9d-8815-e53d6097ce11`) returned HTTP 200
- relaunch count 152, sample still present
- live hash immediately after this test was still `6822090c91d329a1bb67bed6d409e0f2cfc509dfa3a13015ef3ea465faf05b42`

EXISTING PROFILE PRESERVATION = PASS
EXISTING PROFILE RELAUNCH = PASS

The later file-hash change is recorded in section Z. It happened after this test had already matched the baseline hash.

## M. Single-instance and window behavior

Second launch against the same profile exited. The first process stayed alive. Listeners on 8760 remained 1. The second process exit code was not captured because the watcher attached after it had already exited.

Off-screen bounds `{x:-30000,y:-30000,width:900,height:700}` were discarded. The relaunch window rect was `240,66,1680,966`, and the saved bounds file was rewritten to `{x:240,y:66,width:1440,height:900}`.

`window.open('https://example.com')` from the installed renderer left a single Electron page target. `setWindowOpenHandler` sends public http(s) through `shell.openExternal` and denies a new Electron window. Loopback renderer URLs stay in the app. Packaged navigation to Vite :5173 is denied.

SINGLE INSTANCE = PASS
DUPLICATE API = 0
WINDOW STATE = PASS
EXTERNAL LINK HANDLING = PASS

## N. Electron security

Production BrowserWindow: `contextIsolation` true, `nodeIntegration` false, `sandbox` true, `webSecurity` true, `allowRunningInsecureContent` false.

Runtime in the packaged page: `process` undefined, `require` undefined. Preload keys: `getInfo`, `getStatus`, `openExternal`, `selectUpdateArtifact`. IPC allowlist is those four channels. Packaged `index.html` does not reference Google Fonts. CDP font resource count for Google Fonts was 0. Fraunces and Manrope are bundled through `@fontsource`.

ELECTRON SECURITY = PASS
OFFLINE FONT/UI = PASS

## O. Shutdown and packaged API loss

Normal close of the unpacked window: Electron process gone, packaged API listener gone, development API PID 7540 still listening, Comfy PID 31048 still listening.

Killing only the packaged `python.exe` whose command contained the isolated resources path: renderer `/api/healthz` returned 503, `apiOwned` false, `apiExited` true. The body uses the shared port-collision sentence. The health endpoint did not stay at 200.

OWNED PROCESS CLEANUP = PASS
UNOWNED PROCESS KILLED = NO
PACKAGED API LOSS DETECTED = PASS
FALSE HEALTHY STATE = NO

## P. Port collision

A disposable Node listener owned 8760. Packaged Electron reported the collision, did not take ownership of an API process, and did not kill the holder. The holder was still alive after Electron stopped. The disposable listener was then closed. 8760 was empty afterward.

8760 COLLISION HANDLING = PASS
WRONG PROCESS KILLED = NO

## Q. Installer

`Adept UI-Setup-1.1.0-win-x64.exe /S /D=%TEMP%\adept-install-final` exited 0. `Adept UI.exe` was present. Start Menu shortcut `Adept UI.lnk` was created. After uninstall that shortcut was gone.

Installed process command: `%TEMP%\adept-install-final\resources\python\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8760`

Health 200. Boot GO. Failed required checks 0. Fresh project count on the isolated install profile 0. `devRepoPathDependency` 0. `viteContacted` false.

INSTALLER = PASS
INSTALLED APP LAUNCH = PASS

## R. Installed application smoke

Isolated profile `%TEMP%\adept-ui-installed-profile`. Disposable project `Installed Cert Disposable` (`054beefa-83c9-4060-b664-0b5397026f46`).

| Surface | Result |
| --- | --- |
| Homepage | Mounted. Project name present in the page text. |
| Projects | Same homepage library. Project count from the packaged API was 1. |
| Co-Director | Co-Director chrome mounted. |
| Image Generator | Cinematic Image Generator mounted in the disposable project. |
| Storyboard | First 3.5s sample was still `Loading project…`. A second launch waited until the page read Storyboard Studio. |
| Timeline | Scene 1 and MiniMax H3 mounted. |
| MAGI | MAGI Editor mounted. |
| Library | Project Library mounted. |
| Setup | Adept Setup mounted. |
| Comfy Manager | Healthy, 127.0.0.1:8188, PID 31048. |

Proxy targetPort 8760, api count 311. CDP 5xx and exceptions: none. Requests to :8758 or :5173: none.

INSTALLED APP SMOKE = PASS

## S. Reinstall and upgrade

Same 1.1.0 installer run again over the isolated directory: exit 0, health 200, project count 1, name `Installed Cert Disposable`.

Disposable 1.1.1 installer, built with electron-builder `extraMetadata.version` 1.1.1 into `%TEMP%\adept-upgrade-dist` only: install exit 0, health 200, boot GO, studioApi port 8760, project count 1, same name, packaged python command still on 8760.

SAME-VERSION REINSTALL = PASS
UPGRADE PRESERVATION = PASS
POST-UPGRADE API :8760 = PASS
POST-UPGRADE BOOT = PASS

## T. Update Manager bridge

`selectDesktopArtifact` accepts a newer artifact only when platform and architecture match the request. A Windows artifact is not selected for macOS or Linux. A missing installed version fails closed. Older remotes are refused. The selected record carries checksum or signature metadata through to Setup. It does not verify file bytes. `restartApi` for packaged mode is port 8760. `rollback.implemented` is false.

Node tests covering this bridge passed (section AC).

UPDATE WINDOWS ARTIFACT SELECTION = PASS
WRONG PLATFORM ARTIFACT REJECTED = PASS
WRONG ARCH ARTIFACT REJECTED = PASS

## U. Update integrity, signing, rollback

CHECKSUM VALIDATION = NOT IMPLEMENTED
SIGNATURE VALIDATION = NOT IMPLEMENTED
APPLICATION ROLLBACK = NOT IMPLEMENTED

The bridge requires a checksum or signature field to be present before it will select an artifact. It does not hash the file and it does not check a signature. Rollback is explicitly unimplemented.

These three are deferred distribution-hardening items for a later mission. They are not PASS. They are not waived. This certification did not add a second updater.

WINDOWS CODE SIGNING = NOT CONFIGURED
SIGNED = NO
CERTIFICATE = NONE
SMARTSCREEN BYPASS USED = NO

## V. Uninstall

`deleteAppDataOnUninstall` is false. Silent uninstall of the isolated install exited 0. `Adept UI.exe` was absent afterward. The isolated profile database was still present. The live database hash did not change during install, reinstall, upgrade, or uninstall.

DEFAULT UNINSTALL PRESERVES USER DATA = PASS

## W. Package-content audit

Scan root: `electron/dist/win-unpacked/resources`.

| Check | Count |
| --- | --- |
| `.env` files | 0 |
| `.db` / sqlite files | 0 |
| model weights over 5 MB (safetensors, ckpt, gguf, onnx, pt, pth, bin) | 0 |
| playwright directories | 0 |
| backup directories | 0 |
| `node_modules` | 0 |
| developer `.venv` | 0 |

One directory named `venv` exists at `python\Lib\site-packages\venv`. That is the Python standard-library `venv` module, required by voice install. It is not a developer virtualenv.

USER PROJECTS BUNDLED = 0
USER LIBRARY ASSETS BUNDLED = 0
MODEL WEIGHTS BUNDLED = 0
BACKUPS BUNDLED = 0
PLAYWRIGHT ARTIFACTS BUNDLED = 0
DEV .ENV SECRETS BUNDLED = 0
DEV .VENV BUNDLED = 0

## X. Secret audit

2,845 non-site-packages text files were scanned for credential shapes: AWS access-key shape, private-key blocks, `sk-` tokens of 20 or more characters, `fal_` tokens of 20 or more characters, Slack tokens, GitHub tokens, and Google API-key shape.

Matches: 0.

Two `.pem` files are certifi CA bundles (`certifi\cacert.pem` and `pip\_vendor\certifi\cacert.pem`). Short substrings such as `fal_` in provider module names and `sk-` inside minified identifiers are not credentials.

PACKAGED SECRETS = 0

## Y. Package sizes

| Piece | Bytes |
| --- | --- |
| Installer | 290,610,156 |
| Unpacked `Adept UI.exe` | 201,233,408 |
| Unpacked tree | 891,213,768 |
| Packaged Python | 484,685,685 |
| Renderer | 83,398,971 |
| API source | 25,167,706 |

Largest packaged files are runtime libraries: `cv2.pyd` (112,898,048), OpenCV ffmpeg DLL, MediaPipe DLL, NumPy OpenBLAS, cryptography, `hf_xet`, Pillow AVIF, `ProjectEditor` renderer chunk (6,777,809), `python311.dll`. No model-weight files were in that set.

## Z. Live-data preservation

| | Baseline | Final |
| --- | --- | --- |
| Path | `data\studio.db` | same |
| SHA-256 | `6822090c91d329a1bb67bed6d409e0f2cfc509dfa3a13015ef3ea465faf05b42` | `7428f6bcade69567c096e76ca7f7306ec9aaa500e34fb788d6bc8f12d64b4d53` |
| Bytes | 97,013,760 | 97,013,760 |
| Projects | 152 | 152 |
| Project folders | 69 | 69 |
| Asset folders | 52 | 52 |

The hash still matched the baseline at the end of the unpacked existing-profile test (`devAfter` in the unpacked evidence). The live file mtime is 2026-10-06T16:28:29Z, which is the development-regression window before the installer run. From the installer run onward, including installed smoke and the storyboard recheck, the hash stayed `7428f6bc…`.

Row comparison against the disposable copy taken at the baseline hash:

- 159 of 160 tables are identical
- project count 152 on both, no project ids added or removed
- assets 1481, scenes 356, jobs 697 on both
- the only differing table is `scenes`, and the difference is two `updatedAt` values inside one scene JSON (`Cade at Schnick Coffee Shop`)
- those newer stamps (`2026-10-06T16:26:36Z`) are on the disposable copy, written when the isolated existing profile was opened
- the live row still has `2026-10-06T05:01:49Z`

The live file bytes changed during the morning run. Section AH is the closure: that difference is the SQLite header change counter plus an `updatedAt` write that landed on the disposable profile copy, not on the live project rows. The live project inventory did not lose a project or a project folder.

LIVE PROJECT DB MUTATED = NO
LIVE PROJECTS LOST = 0
LIVE PROJECT FOLDERS LOST = 0

## AA. Development regression

After the Electron runs:

- `http://127.0.0.1:5173/` HTTP 200
- `http://127.0.0.1:8758/api/healthz` HTTP 200
- Vite PID 7884, API PID 7540, both unchanged from baseline
- Earlier browser pass on the dev UI rendered the homepage, reported 152 productions, boot headline ADEPT UI READY — GO, and opened project `CD Timeline Recert Browser` (`31ae66b5-47c8-40d5-83a4-f37ae50b309c`)

WEB DEVELOPMENT REGRESSIONS = 0

## AB. Comfy preservation

COMFY BEFORE: PID 31048, HTTP 200
COMFY AFTER: PID 31048, HTTP 200
COMFY RESTARTED BY ELECTRON = NO

## AC. Automated tests

| Suite | Pass | Fail | Skipped | Duration |
| --- | --- | --- | --- | --- |
| `node --test electron/endpoint.test.mjs electron/update/bridge.test.mjs` | 8 | 0 | 0 | 63.9 ms |
| `pytest studio-api/tests/test_boot_certification.py` | 14 | 0 | 0 | 0.38 s |

Covered: endpoint 8758 for web and electron development, 8760 for packaged mode, Comfy port left at 8188, Windows artifact selection, wrong platform and wrong architecture rejection, navigation policy, boot certification for packaged 8760 with Vite not required.

## AD. Windows artifact paths and hashes

Version 1.1.0, architecture win-x64, signing NotSigned.

- Unpacked: `C:\AdeptFilmWorks\AIVideoStudio\electron\dist\win-unpacked\Adept UI.exe`
  - 201,233,408 bytes
  - SHA-256 `3befc5907cc5743ea87c6540cebd15c007dd3a032ae2b680368498a4527cadb1`
- Installer: `C:\AdeptFilmWorks\AIVideoStudio\electron\dist\Adept UI-Setup-1.1.0-win-x64.exe`
  - 290,610,258 bytes
  - SHA-256 `8cea04a17c755f0624751ee2c595f9cc2f5cebc109f9dcc6407d4ef315021364`

The installer hash changed when the Studio API reconcile fix was rebuilt. The unpacked executable hash did not. Section AH is the recertification of these artifacts.

## AE. macOS and Linux

MACOS: PENDING NATIVE RUNNER
LINUX: PENDING NATIVE RUNNER
MACOS SIGNING: NOT CONFIGURED
NOTARIZATION: PENDING CREDENTIALS

This Windows run does not certify either platform.

## AF. Final matrix

```text
UNPACKED EXE LAUNCH = PASS
PACKAGED RENDERER = PASS
PACKAGED STUDIO API :8760 = PASS
PACKAGED API PROCESS IDENTITY = PASS
STUDIO API HEALTH = PASS
BOOT MANAGER = PASS
FAILED REQUIRED BOOT CHECKS = 0
VITE :5173 DEPENDENCY = 0
DEV .VENV DEPENDENCY = 0
DEV REPO PATH DEPENDENCY = 0
PACKAGED REQUESTS TO :8758 = 0
PACKAGED REQUESTS TO :5173 = 0
MAJOR PRODUCT SURFACE SMOKE = PASS
CO-DIRECTOR STREAM = PASS
COMFY MANAGER = PASS
FRESH PROFILE PROJECT COUNT = 0
FRESH PROFILE USER LIBRARY ASSETS = 0
FIRST PROJECT PERSISTENCE = PASS
EXISTING PROFILE PRESERVATION = PASS
EXISTING PROFILE RELAUNCH = PASS
LIVE PROJECT DB MUTATED = NO
PROJECT COUNT PRESERVED = PASS
PROJECT FOLDERS PRESERVED = PASS
UNEXPECTED SEMANTIC DB MUTATIONS = 0
LIVE DB PRESERVATION = PASS
PACKAGED ELECTRON LIVE DB ACCESS = 0
LIVE PROJECTS LOST = 0
SINGLE INSTANCE = PASS
DUPLICATE API = 0
WINDOW STATE = PASS
EXTERNAL LINK HANDLING = PASS
ELECTRON SECURITY = PASS
OFFLINE FONT/UI = PASS
OWNED PROCESS CLEANUP = PASS
UNOWNED PROCESS KILLED = NO
PACKAGED API LOSS DETECTION = PASS
FALSE HEALTHY STATE = NO
8760 COLLISION HANDLING = PASS
INSTALLER = PASS
INSTALLED APP LAUNCH = PASS
INSTALLED APP SMOKE = PASS
SAME-VERSION REINSTALL = PASS
UPGRADE PRESERVATION = PASS
POST-UPGRADE API :8760 = PASS
POST-UPGRADE BOOT = PASS
UPDATE WINDOWS ARTIFACT SELECTION = PASS
WRONG PLATFORM ARTIFACT REJECTED = PASS
WRONG ARCH ARTIFACT REJECTED = PASS
CHECKSUM VALIDATION = NOT IMPLEMENTED
SIGNATURE VALIDATION = NOT IMPLEMENTED
APPLICATION ROLLBACK = NOT IMPLEMENTED
WINDOWS CODE SIGNING = NOT CONFIGURED
SMARTSCREEN BYPASS USED = NO
DEFAULT UNINSTALL PRESERVES USER DATA = PASS
USER PROJECTS BUNDLED = 0
USER LIBRARY ASSETS BUNDLED = 0
MODEL WEIGHTS BUNDLED = 0
BACKUPS BUNDLED = 0
PLAYWRIGHT ARTIFACTS BUNDLED = 0
DEV .ENV SECRETS BUNDLED = 0
PACKAGED SECRETS = 0
WEB DEVELOPMENT REGRESSIONS = 0
COMFY RESTARTED BY ELECTRON = NO
```

## AG. Final verdict

ADEPT UI 1.1 ELECTRON — WINDOWS FULL GO

The packaged Windows application launched, installed, served the renderer, ran Studio API on 127.0.0.1:8760, reached Boot Manager GO, and uninstalled without deleting user data. Comfy PID 31048 stayed up. The development stack on 5173 and 8758 stayed up. Section AH records why the earlier file-hash difference is not a loss of project data.

Checksum validation, signature validation, and application rollback remain NOT IMPLEMENTED. They are distribution-hardening items for a public downloadable release. They are not recorded as PASS.

MACOS: PENDING NATIVE RUNNER
LINUX: PENDING NATIVE RUNNER

## AH. Live database forensic closure

The morning gate `LIVE PROJECT DB MUTATED = YES` compared SHA-256 of `data\studio.db`. The file size stayed 97,013,760. Project count stayed 152. Project folders stayed 69. Asset folders stayed 52.

A raw page comparison of the live file against a byte copy taken before that window (`%TEMP%\adept-ui-profile-existing\data\studio.db`, 23,685 pages of 4,096 bytes) found 3 differing pages:

- Page 0 differs in 4 bytes: the SQLite file change counter, its version-valid-for copy, and the library version stamp.
- Pages 21452 and 21464 differ only because that disposable copy's scene `Cade at Schnick Coffee Shop` (`9df33d43-e091-4782-ac59-043bf110115b`) has two `timelineMaster.batchBlocks[].updatedAt` values of `2026-10-06T15:57:13Z`. The live row is still `2026-10-06T05:01:49Z`.

No other table differs. No text column in the live database contains a `2026-10-06T16` or `2026-10-06T17` timestamp. The newest application timestamp column is `2026-10-06 04:38:52` on `storyboard_panels`, earlier than the live file mtime `2026-10-06T17:25:17Z`. The live header sqlite version is `3053001` (3.53.1, the development API). Packaged Python writes `3045001` (3.45.1) and that stamp is not on the live file.

Writer of the disposable `updatedAt` change:

- PROCESS: Studio API started by packaged Electron
- OWNER: existing-profile certification copy, not `data\studio.db`
- ACTION: process startup
- CODE PATH: `reconcile_all_open_timeline_jobs` → `reconcile_batch_from_job` → `save_master` with the default `touch_batches=True`
- CHANGE: only those two `updatedAt` stamps
- WHY: a startup reconcile saved a master whose batch status did not change, and the default save refreshed every batch timestamp

That call now passes `touch_batches=False`. Replaying startup reconcile on a raw copy of the live database left the file hash unchanged. A packaged existing-profile launch after the rebuild left the disposable copy byte-identical to the live file (`275953ec5e485d8f50967b9c7522a55a75073a0a862c0230ae01ded429ba4326`).

The 13 read actions (no-op, health, boot, homepage, projects page, project list, project open, CD Timeline Recert Browser open, timeline mount, and the combined regression) were each run on a fresh disposable copy. None changed the file hash. Packaged Electron was launched with a temporary profile: health 200, boot 200, live hash unchanged, `dataDir` was the temporary profile. `PACKAGED ELECTRON LIVE DB ACCESS = 0`.

The preservation gate now compares a logical digest of every application table, the project count, and the change counter. A header-only counter change is recorded as physical and does not fail the gate. A row change fails it. `electron/scripts/db-preservation.mjs` is what `certify-windows.mjs` and `certify-installer.mjs` use.

Recertification after the rebuild, same machine, Comfy PID 31048 HTTP 200 before and after, development API PID 7540 unchanged:

| Check | Result |
| --- | --- |
| Unpacked renderer | HTTP 200 |
| Packaged API health | HTTP 200 |
| Vite contacted | 0 |
| Dev repo path dependency | 0 |
| Existing-profile copy after launch | byte-identical to the live database |
| Live logical digest | `19445605731875396bae1074a1f0a8333b1ea183adfdf1a6cd6373e9c532e9ad` before and after |
| Projects | 152 before and after |
| Installer install / reinstall | exit 0 / exit 0 |
| Installed boot | GO, Studio API `127.0.0.1:8760` |
| Installed fresh project count | 0 |
| Uninstall removes the exe | yes |
| Upgrade marker preserved | yes |
| Live DB preservation | PASS, semantic mutations 0 |

The unpacked `Adept UI.exe` hash is unchanged because executable signing and resource editing are off. The installer payload changed because the Studio API source changed.

| Artifact | Bytes | SHA-256 |
| --- | --- | --- |
| `electron\dist\win-unpacked\Adept UI.exe` | 201,233,408 | `3befc5907cc5743ea87c6540cebd15c007dd3a032ae2b680368498a4527cadb1` |
| `electron\dist\Adept UI-Setup-1.1.0-win-x64.exe` | 290,610,258 | `8cea04a17c755f0624751ee2c595f9cc2f5cebc109f9dcc6407d4ef315021364` |

```text
PROJECT COUNT PRESERVED = PASS
PROJECT FOLDERS PRESERVED = PASS
UNEXPECTED SEMANTIC DB MUTATIONS = 0
LIVE DB PRESERVATION = PASS
PACKAGED ELECTRON LIVE DB ACCESS = 0
```

COMFY BEFORE: PID 31048, HTTP 200
COMFY AFTER: PID 31048, HTTP 200
COMFY RESTARTED?: NO

