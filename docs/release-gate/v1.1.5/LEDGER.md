# Adept UI 1.1.5 four-platform certification ledger

Phase: executable installation and Studio checks have been run. Automatic upgrade from 1.1.3 and 1.1.4 remains NO-GO. macOS Gatekeeper remains an external blocker. Fedora was not run on a physical desktop. Lifecycle tests passed on https://github.com/bradjohnson79/adeptui/actions/runs/38858485654 at `83c48072`.

Runs:
- https://github.com/bradjohnson79/adeptui/actions/runs/38855953989
- https://github.com/bradjohnson79/adeptui/actions/runs/38857036264
Commit: `0658706e3d0eb924d784e47be1c7916bd7750545`
Live catalog: v1.1.5. Signed catalog job PASS. Release integrity page PASS. Failure recovery PASS.

| Platform | Environment | Installation | Studio | Upgrade | Recovery |
|---|---|---|---|---|---|
| Windows | GitHub windows-latest. Caption: Microsoft Windows Server 2025 Datacenter. Version 10.0.26100. AMD64. Graphical session. | GO | GO | NO-GO automatic. Migration PASS | covered by the shared recovery job |
| macOS arm64 | GitHub macos-14. macOS 14.8.9, build 23J631 | GO | EXTERNAL BLOCKER | NO-GO automatic. Migration PASS | covered by the shared recovery job |
| Ubuntu x64 | GitHub ubuntu-22.04. Ubuntu 22.04.5 LTS. Xvfb virtual display, not physical hardware | GO | GO | NO-GO automatic. Migration PASS | covered by the shared recovery job |
| Fedora x64 | fedora:41 container on an Ubuntu host, Xvfb. Not a physical desktop | GO | GO on the virtual display | NO-GO automatic. Migration PASS | covered by the shared recovery job |

macOS notarization: EXTERNAL BLOCKER. `spctl` reported `code has no resources but signature indicates they must be present`. The test did not remove quarantine or ad-hoc sign the application.

Windows evidence: shortcut target `Adept Launcher.exe`, window title `Adept UI Studio`, screenshot captured, no Adept terminal, update check `NO_UPDATE`, shutdown, restart, uninstall kept the project file, reinstall stayed 1.1.5. The launcher parent PID was not sampled before the launcher exited.

Ubuntu and Fedora evidence: desktop Exec resolves to `/opt/Adept UI/Adept UI`, Electron is the sibling `.bin`, and `xwininfo` showed a 1439x899 window named `Adept UI Studio`. The launcher log said the launcher ran. Parent PID was already 1 when sampled. Both completed shutdown, restart, user-data preservation, and reinstall. Ubuntu's update check was `NO_UPDATE`. Inside the Fedora container the launcher recorded `UPDATE_SERVICE_UNAVAILABLE` and still opened the installed 1.1.5 application. The container result is not a physical Fedora desktop.

Automatic upgrade from the published 1.1.3 and 1.1.4 installers stayed on those versions on Windows, Ubuntu, Fedora, and macOS. User data remained. Running the public 1.1.5 installer afterward left that data in place and installed 1.1.5. That is migration, not an automatic upgrade. The published launchers cannot apply an NSIS, DEB, RPM, or DMG artifact. Changing that is a new updater design and needs owner approval before a new public version.
