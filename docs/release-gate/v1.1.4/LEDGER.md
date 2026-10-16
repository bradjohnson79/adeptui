# Adept UI 1.1.4 evidence ledger

Phase: 1.1.4 is the live public release. 1.1.5 is building so the first launch records the installed version and checks the catalog.

## Passing

- Live 1.1.3 catalog signature: openssl, .NET, and launcher Python against adeptui.org.
- Public install of the 1.1.3 packages on Windows, Ubuntu, Fedora container, and macOS arm64.
- Reinstall and user-data marker on those install gates.

## Failing

- Windows launcher sibling. Published 1.1.3 places `Adept Launcher.exe` at `resources\Adept Launcher.exe`. Shortcuts stay on `Adept UI.exe`. The launcher cannot see its sibling.

## Root cause

Windows packaging used `extraResources`. That directory is `resources\`, not the install root. NSIS only retargets shortcuts when `$INSTDIR\Adept Launcher.exe` exists.

## Repair in this commit

- Windows launcher stays on `extraFiles`, beside `Adept UI.exe`.
- `build-windows.mjs` refuses a package that omits that sibling.
- Installer certification requires the sibling, a shortcut aimed at the launcher, and a visible window title.
- Product version is 1.1.4. v1.1.3 GitHub assets stay unchanged.

## Waiting

- Windows, macOS, and Linux 1.1.4 builds.
- Exact-byte catalog signing after those artifacts exist.
- GitHub release v1.1.4, adeptui.org deploy, and the public install gate.

## Blockers

- macOS notarization: EXTERNAL BLOCKER. No Apple credentials.
- Fedora physical desktop: the executable gate is a Fedora container, not a physical desktop.
- Visible Studio window: NOT VERIFIED until the Windows and macOS desktop jobs record one.

## Built

- Commit `8d836b25`. Windows, macOS, and Linux desktop jobs succeeded.
- Windows install certification: launcher beside Electron, shortcut targets `Adept Launcher.exe`, window title `Adept UI Studio`, boot GO, health 200, uninstall leaves the user-data marker.
- macOS arm64 smoke: window behavior PASS, dmg launch PASS, boot GO. Notarization remains PENDING CREDENTIALS.
- GitHub release `v1.1.4` at `8d836b25` with the four installers. Sizes match the signed catalog.
- Catalog SHA-256 is recorded after `verify_published_catalog.py --publishable --require-openssl` returned PASS.

## Public gate

Run `38847177899` completed success. Live catalog verification returned PASS before that run.

- Windows: installation, launcher beside Electron, shortcut `Adept Launcher.exe`, window title `Adept UI Studio`, reinstall and user data.
- Ubuntu: installation, Electron sibling `/opt/Adept UI/Adept UI.bin`, reinstall and user data. No physical display.
- Fedora container: installation, the same Electron sibling, reinstall and user data. Not a physical desktop.
- macOS: public install and reinstall. The desktop smoke of the same disk image showed the window. Notarization is an external blocker.

## Remaining

The published 1.1.4 launcher starts the app when no version is recorded, and it never writes that version. The catalog check therefore does not run. The repair records `resources/version.json` on first launch and then checks the catalog. That repair is 1.1.5 and is not in the live installer yet.

## Next

Build Windows, macOS, and Linux 1.1.5. Sign and publish only after those artifacts exist. Do not claim macOS notarization or a physical Fedora desktop.
