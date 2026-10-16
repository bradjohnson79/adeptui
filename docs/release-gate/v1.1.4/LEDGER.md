# Adept UI 1.1.4 evidence ledger

Phase: v1.1.4 artifacts are built and the GitHub release exists. Production catalog deploy and the public install gate are next.

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

## Next

Deploy adeptui.org, then let `release-catalog-gate` install from the public commands.
