# E14 — Desktop certification

Measured on this Windows machine. macOS and Linux were not run here.

## Versions

- Desktop version owner: `electron/version.json` `1.1.0`
- App id: `app.adeptui.desktop`
- Display name: `Adept UI`
- Packager: electron-builder 26.15.3, Electron 35.7.5
- Installer: `electron/dist/Adept UI-Setup-1.1.0-win-x64.exe`
- Unpacked: `electron/dist/win-unpacked/Adept UI.exe`
- Signing: `Get-AuthenticodeSignature` status `NotSigned`
- `MACOS SIGNING: NOT CONFIGURED`
- `NOTARIZATION: PENDING CREDENTIALS`
- `WINDOWS CODE SIGNING: NOT CONFIGURED`
- Unsigned Windows SmartScreen warning is expected. It was not bypassed.

## Path ledger (isolated copy)

The unpacked app was copied to `%TEMP%\adept-ui-isolated-win` and launched with a fresh `--user-data-dir`.

| Use | Path |
| --- | --- |
| Renderer | `%TEMP%\adept-ui-isolated-win\resources\renderer` |
| Python | `%TEMP%\adept-ui-isolated-win\resources\python\python.exe` |
| API source | `%TEMP%\adept-ui-isolated-win\resources\studio-api` |
| Logs / temp / data | `%TEMP%\adept-ui-profile-fresh\` |
| Resources | `%TEMP%\adept-ui-isolated-win\resources` |

`VITE :5173 DEPENDENCY = 0` (renderer origin port `54557`, `viteContacted` false, HTTP 200)

`DEV .VENV DEPENDENCY = 0` (no packaged command line pointed at `studio-api\.venv`)

`DEV REPO PATH DEPENDENCY = 0`

## What passed

- Packaged renderer is loopback HTTP, not `file://` and not `:5173`. `GET /` returned 200.
- Google fonts are not in the built renderer. Fraunces and Manrope are bundled.
- Fresh profile `data\studio.db` was not created. The live `data\studio.db` hash stayed `600b561ad93285bb4f64a78d56479f15fde8c885cf3782e4f3727ce528dd3834` (97013760 bytes).
- Existing-profile check copied that database, the copy hash matched, and the second launch's `dataDir` was the disposable copy. The live file was not moved.
- Port collision: `:8758` stayed with PID 7540 (`uv` CPython, not the packaged interpreter). The shell reported the collision and did not stop it. `apiPidUnchanged` true.
- Comfy `:8188` stayed PID 31048. `COMFY RESTARTED?: NO`
- Studio API PID 7540 was still the listener after install, upgrade, uninstall, and the packaged launches.
- Package audit of the isolated `resources` tree: user `.env` 0, databases 0, model weights 0, Playwright report/trace directories 0, private keys 0. A filename search for `credential` also hits library modules such as `credentials.py` and certifi's public `cacert.pem`. Those are not user secrets.
- Same-profile second launch exited 0 while the first PID stayed up.
- Installer fixture A then the same 1.1.0 installer as fixture B: both exit 0, the disposable AppData marker was still present after the second install. A different version B was not built.
- Default uninstall: `deleteAppDataOnUninstall` is false and that string is not in the installer. The marker was still present when the uninstaller returned. The install directory was gone on the follow-up listing. The cert marker was then removed.
- Update selection tests: 5 passed. A newer win32 x64 artifact with a checksum is selected. An older remote is refused. A missing installed version fails closed. A Windows artifact is not selected for macOS or Linux. Application rollback remains `implemented: false`. `electron-updater` is not a dependency.

## What did not pass

Packaged Studio API did not become healthy. `:8758` was already owned by PID 7540. The shell did not kill that process, and it did not proxy the renderer at that foreign API, so the window does not look ready through the developer server. The packaged interpreter can import `app.main` (`app-import-ok` from `electron/build/python-win32-x64/python.exe`). That import is not the product listener.

API-death behavior was not observed, because no packaged API child was started.

## Platform verdicts

`WINDOWS: NO-GO — packaged API did not bind :8758 while PID 7540 held it`

`MACOS: PENDING NATIVE RUNNER`

`LINUX: PENDING NATIVE RUNNER`

Shared-architecture files are in the tree. That does not certify macOS or Linux, and it does not turn the Windows collision into a healthy packaged API.

## COMFY

`COMFY BEFORE: PID 31048`

`COMFY AFTER: PID 31048 / HTTP 200`

`COMFY RESTARTED?: NO`

The developer Studio API on PID 7540 was HTTP 200 after these runs. That is the foreign listener, not the packaged interpreter.
