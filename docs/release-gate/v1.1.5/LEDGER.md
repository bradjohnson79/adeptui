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

Automatic upgrade from the published 1.1.3 and 1.1.4 installers stayed on those versions on Windows, Ubuntu, Fedora, and macOS. User data remained. Running the public 1.1.5 installer afterward left that data in place and installed 1.1.5. That is migration, not an automatic upgrade. The published launchers cannot apply an NSIS, DEB, RPM, or DMG artifact.

## Terminal installation (owner correction, 2026-10-16)

The 1.1.6 and 1.1.7 package-updater work is discontinued. The public version stays 1.1.5. New archives use unique filenames and are not replacements for the published exe, deb, rpm, or dmg.

Status: the live catalog points at the corrected r2 archives. Public installation and update passed on the four runners. Windows showed the Studio window. Ubuntu, Fedora, and macOS graphical windows were not verified in this gate. Fedora was a container. macOS notarization remains an external blocker.

Corrected archives, added beside the first terminal archives and the original packages:

| File | Bytes | SHA-256 |
|---|---:|---|
| Adept.UI-1.1.5-terminal-r2-win-x64.zip | 370904892 | d9dcbf2ed7a986c7e8290238c5ad5a913f81faffe55c7cf31c336caa2d430b04 |
| Adept.UI-1.1.5-terminal-r2-linux-x64.zip | 577928766 | c5c1301f4335c45981921489be28715ebe6b52d3e772bf268be80d647b35dc1a |
| Adept.UI-1.1.5-terminal-r2-mac-arm64.zip | 500505267 | c61a9279141e22e431462f1b5fbbb1c1505f81a52d2bd2005648040baabeb97c |

The GitHub download of each r2 archive matched those hashes. Catalog SHA-256 `f1d9df8af9df84d29368d0b839eb720014c97b47dc4fd984ef2d32b8e195a146`. Signature SHA-256 `09500ed46c4d5358eb67070507b6a91ee7b851a5aa928a5dbe408e262188eaae`.

Public gate https://github.com/bradjohnson79/adeptui/actions/runs/38879554190 at `d44794a4` succeeded. Windows, Ubuntu, Fedora, and macOS each reported installation, reinstall with the project file kept, `UPDATE: PASS`, and `PREVIOUS_VERSION_PRESERVED: PASS`. Windows also reported shortcut `C:\Users\runneradmin\.adept-ui\bin\Adept Launcher.exe` and `STUDIO_WINDOW: PASS Adept UI Studio`. macOS reported `NOTARIZATION: EXTERNAL_BLOCKER`. The earlier failed update left the recorded version at 1.1.4, so a failed update did not replace the installed application.

Public install gate https://github.com/bradjohnson79/adeptui/actions/runs/38872577737 at `d28c60cc` succeeded:

- Windows: installation, uninstall, reinstall, user-data file kept, shortcut `C:\Users\runneradmin\.adept-ui\bin\Adept Launcher.exe`, window title `Adept UI Studio`.
- Ubuntu and Fedora: the same archive installed, uninstalled, and reinstalled with the project file kept. Fedora ran in a fedora:41 container, not on a physical desktop.
- macOS: the archive installed under `~/.adept-ui/app/Adept UI.app`, uninstalled, and reinstalled with the project file kept. Notarization remains an external blocker. The graphical window was not verified.

The following update gate failed on Windows, Ubuntu, Fedora, and macOS with `INSTALL_INTERRUPTED`. The frozen launcher tried to copy `adept_lifecycle` from a PyInstaller temporary directory that does not exist. A local Windows run of the corrected launcher applied the published Windows archive: exit 0, `Adept UI.exe` present, registry `1.1.5`, previous version `1.1.4`. That local run is not a substitute for the public four-platform gate. New archives use the `r2` filename and are building from `d9081767`.

Published terminal archives, added to the existing v1.1.5 release without replacing the original exe, deb, rpm, or dmg:

| File | Bytes | SHA-256 |
|---|---:|---|
| Adept.UI-1.1.5-terminal-win-x64.zip | 370904367 | c485535f982f3eac50b546743ec721f1f35cd29e2ef3e4e75354cf557d3cc20b |
| Adept.UI-1.1.5-terminal-linux-x64.zip | 577937390 | 3f6fc48d26f516d784aaa3b72fcbfc2292bd24b2be8f6f4d00a59a23b7a42269 |
| Adept.UI-1.1.5-terminal-mac-arm64.zip | 500516104 | d04ca60751a8f1b6f2ffd9435ed995a8d23b04fb724661e2c9d74b349cbbcf5b |

The GitHub download of each archive matched those hashes. Original v1.1.5 package sizes were unchanged: exe 291928877, deb 403729200, rpm 358651569, dmg 409234403.

Archive builds: Linux https://github.com/bradjohnson79/adeptui/actions/runs/38867950022, Windows https://github.com/bradjohnson79/adeptui/actions/runs/38867952750, macOS https://github.com/bradjohnson79/adeptui/actions/runs/38867955516. Build commit `0f53d5fc`. Linux and Windows jobs succeeded. macOS job succeeded. Fedora in that workflow installed the RPM in a container; that is not the terminal archive certification.

- Install scripts prefer a zip and fall back to the existing package only while the live catalog is still the 1.1.6 package catalog.
- A zip installs into the user directory `~/.adept-ui` without administrator privileges. The launcher is copied to `~/.adept-ui/bin`. The desktop shortcut is named Adept UI.
- Ordinary launcher updates apply a zip and restore the previous application if activation fails. They do not run NSIS, DMG, DEB, or RPM.
- `ADEPT_UNINSTALL=1` removes `~/.adept-ui` and the Adept UI shortcut. It does not delete personal projects.
- Another 1.1.5 revision does not replace an installation whose registry already says 1.1.5. Update certification has to start from an older recorded version.
- macOS notarization remains an external blocker. The installer does not remove quarantine or disable Gatekeeper.

Build commit for the archives: `0f53d5fc`. Runs:

- Linux: https://github.com/bradjohnson79/adeptui/actions/runs/38867950022
- Windows: https://github.com/bradjohnson79/adeptui/actions/runs/38867952750
- macOS: https://github.com/bradjohnson79/adeptui/actions/runs/38867955516

## Terminal-only installation (2026-10-16, revision 1)

Package installers are no longer the installation path. The public command installs one signed zip. Visible version remains 1.1.5. This section records internal revision 1. It is not the current archive.

Current archives:

| File | Bytes | SHA-256 |
|---|---:|---|
| Adept.UI-1.1.5-terminal-r3-win-x64.zip | 370844291 | 977e6de6ec6c4b0a86a09ac5aa29a0910afa460f9f20af7d56db668ea50b9def |
| Adept.UI-1.1.5-terminal-r3-linux-x64.zip | 577927019 | 9261c7d7cb7bf40be7fdaa3b56f081faa34388d9af92446a79f4cde6659d871d |
| Adept.UI-1.1.5-terminal-r4-mac-arm64.zip | 430838506 | ec6758a3c26e02509c504fe1ec049778ae73c5b922d2c5921dc96ef2268a2ea8 |

Catalog SHA-256 `ba2c59b6bc1cd70547f47f09d707daa4ebd97d6bfda66dec2c57e48f254599ca`. Signature SHA-256 `ab35e844ec7f7fb7669ed26b49c57e859f524433b82515223d477b9d22cbf419`.

Public gate https://github.com/bradjohnson79/adeptui/actions/runs/38938192171 at `886e3de3` succeeded. Windows reported `STUDIO_WINDOW: PASS Adept UI Studio`, `UPDATE: PASS`, `PREVIOUS_VERSION_PRESERVED: PASS`, and `SAME_VERSION_REVISION: PASS 1`. Ubuntu, Fedora, and macOS reported installation, reinstall with the project file kept, and update. Fedora ran in a container.

macOS bundle check `SIGNATURE_STRUCTURE: PASS`. `spctl` remains `NOT_ACCEPTED`. A screenshot from https://github.com/bradjohnson79/adeptui/actions/runs/38938192203 shows the window titled Adept UI Studio and the setup choices. The System Events title probe did not read that title. Notarization remains an external blocker.

Ubuntu and Fedora virtual displays for revision 1 started the application and showed an Error window, not Adept UI Studio. That is not a physical-desktop pass.

## Universal Terminal Installer — OWNER-LOCK READY (2026-10-16)

Visible version remains 1.1.5. Internal revision is 3. The public catalog points at new archives and does not replace the revision 1 files above.

| File | Bytes | SHA-256 |
|---|---:|---|
| Adept.UI-1.1.5-terminal-r6-win-x64.zip | 370940940 | 8acab679869e3742afd3f0ae10bbcae9e76225c114baff36bafa5f9fd96a04e8 |
| Adept.UI-1.1.5-terminal-r6-linux-x64.zip | 578096251 | e6fe2d1997028511478802e8f33bc30d2f531b09ee752074299eab335003744b |
| Adept.UI-1.1.5-terminal-r6-mac-arm64.zip | 430838384 | 6af1c85f9f5efce69e365ecc8feb50d934e7d42596136573a9f5cfa9cd1a0bc2 |

Catalog SHA-256 `d742bf531b88b6c7cead962b4f1aa05e33790d5557efa74fc92f9522c8c01fe2`. Signature SHA-256 `063fe09301553d2384b1c09ead7aa0f182c0dec4ab3bbba3a5e2714c7078b8b8`. Catalog deployment `dpl_DRvfMsySJNzxf6pZrMk2mxWSzpB1`. Current production deployment `dpl_J69LQqt6BLvp8c4ZWYoJhv8AQYvy`.

Linux Studio was failing because the packaged Python runtime was extracted without its executable bit. The main process then showed “A JavaScript error occurred in the main process” (`spawn .../python EACCES`). Startup now marks that runtime executable. The terminal installer was not changed.

Public installation gate https://github.com/bradjohnson79/adeptui/actions/runs/38951351797 at `1c8fafdf` succeeded. Windows reported `INSTALLATION: PASS`, `SHORTCUT: PASS`, `STUDIO_WINDOW: PASS Adept UI Studio`, `UPDATE: PASS`, `PREVIOUS_VERSION_PRESERVED: PASS`, and `SAME_VERSION_REVISION: PASS 3`.

Studio certification https://github.com/bradjohnson79/adeptui/actions/runs/38951351688 succeeded. Ubuntu on Xvfb reported `STUDIO_WINDOW_first: PASS`, `SETUP_WIZARD: PASS`, `RESTART: PASS`, and `UNINSTALL_PRESERVES_USER_DATA: PASS`, labeled `DISPLAY: VIRTUAL_XVFB`. Fedora in a container on Xvfb reported the same window, restart, and user-data results, with `SETUP_WIZARD: NOT_VERIFIED`. Neither Linux result is a physical-desktop verification.

macOS reported `INSTALLATION: PASS`, `SIGNATURE_STRUCTURE: PASS`, `SHUTDOWN: PASS`, `RESTART: PASS`, and `UNINSTALL_PRESERVES_USER_DATA: PASS`. `GATEKEEPER: NOT_ACCEPTED`. `NOTARIZATION: EXTERNAL_BLOCKER`. The System Events title probe printed `STUDIO_WINDOW: PROCESS_STARTED title not confirmed`.

The desktop update selector calls the existing Universal Launcher. It does not contain a second updater. The launcher checks the signed catalog, verifies the archive, and applies the update after Studio exits.

Do not modify this architecture without explicit owner authorization.

## Revision 4 — unified Setup Wizard (2026-10-16)

Visible version remains 1.1.5. Internal revision is 4. The public catalog points at new archives and does not replace the revision 3 files above. The terminal installer commands are unchanged.

Build commit `812b15ca`.

| File | Bytes | SHA-256 |
|---|---:|---|
| Adept.UI-1.1.5-terminal-r7-win-x64.zip | 370936676 | 368892fa4bf396f8e1589b58e4183a7f039cd1dd5ca773d47ed6d8e9d6fa30a4 |
| Adept.UI-1.1.5-terminal-r7-linux-x64.zip | 578097608 | 02a0e306d52ca06934c6791d5e7572615992cf4c9c7a37e6e36cd91167d18128 |
| Adept.UI-1.1.5-terminal-r7-mac-arm64.zip | 430843015 | 01d021c8217d65955f9723b52637e31f3f9ca0618905067f637b16d6e0e8ce77 |

Windows build https://github.com/bradjohnson79/adeptui/actions/runs/38967067975. Linux build https://github.com/bradjohnson79/adeptui/actions/runs/38967052588. macOS build https://github.com/bradjohnson79/adeptui/actions/runs/38967071578.

Catalog SHA-256 `f5337ac2871e15486aaca2524c308b828b1b204471a5a180c4551f4b12ffa11c`. Signature SHA-256 `954df2866685ee7eaa4a025869d696d86d8f6a3cc52db282f6b2b9d0cd633059`.

The packaged renderer contains Install ComfyUI, the `pip install comfy-cli` command, and Copy command. It does not contain Prepare My Studio, the capability-blocker text, or Official ComfyUI Download.

Production deployment `dpl_DXnxBwxasrhg9VZjiU1JkJz2wxJv` on adeptui.org. Catalog commit `7744114f`. Ledger commit follows this section.

Public installation gate https://github.com/bradjohnson79/adeptui/actions/runs/38968955081 succeeded against the live catalog. Windows reported `INSTALLATION: PASS`, `SHORTCUT: PASS`, `STUDIO_WINDOW: PASS Adept UI Studio`, `UPDATE: PASS`, `PREVIOUS_VERSION_PRESERVED: PASS`, and `SAME_VERSION_REVISION: PASS 4`. Ubuntu, Fedora, and macOS reported `INSTALLATION: PASS`, `UPDATE: PASS`, and `PREVIOUS_VERSION_PRESERVED: PASS`. Those Linux and macOS jobs do not open the Studio window (`GRAPHICAL_STARTUP: NOT_VERIFIED`).

Studio certification https://github.com/bradjohnson79/adeptui/actions/runs/38969153085 installed from adeptui.org. Ubuntu on Xvfb reported `SETUP_WIZARD: PASS`, `STUDIO_WINDOW_first: PASS`, `RESTART: PASS`, and `UNINSTALL_PRESERVES_USER_DATA: PASS`. The first-run screenshot shows only Full Local Installation, Hybrid Installation — Local + API, and Full API Installation. It does not show System Status, a capability-blocker list, or Prepare My Studio. Fedora in a container reported the Studio window title, restart, and user-data preservation, with `SETUP_WIZARD: NOT_VERIFIED` and a blank virtual-display frame. Neither Linux result is a physical desktop. Windows reported the Studio window, shortcut, restart, and user-data preservation. The Windows frame captured the startup gauge while services were still starting. macOS reported `SIGNATURE_STRUCTURE: PASS`, `GATEKEEPER: NOT_ACCEPTED`, `NOTARIZATION: EXTERNAL_BLOCKER`, and `STUDIO_WINDOW: PROCESS_STARTED title not confirmed`. The macOS screenshot of that same run shows the three Setup Wizard choices.

Prepared for owner approval. The existing Setup Wizard lock stays as written. This revision does not add a new lock. After the owner approves, the lock record can name this certified behavior: three choices only, no System Status, no capability-blocker dashboard, no Prepare My Studio, ComfyUI terminal instructions only when a local profile needs ComfyUI, and a completed API installation stays complete.

## Revision 5 — unified Setup Manager (2026-10-16)

Visible version remains 1.1.5. Internal revision is 5. The public catalog points at new archives and does not replace the revision 4 files above. The terminal installer commands are unchanged. Owner certification of the Setup Manager is not granted by this record.

Product commit `e83477128131407a565fb3416a4799aaa6625257`. Catalog commit `641aa649670e79f537c2be1042a8e6741dc6fa74`.

| File | Bytes | SHA-256 |
|---|---:|---|
| Adept.UI-1.1.5-terminal-r9-win-x64.zip | 370906600 | ed9232d3b2cf408bd78af63d58464afbc34de877b7a17eba5c1928146e827d56 |
| Adept.UI-1.1.5-terminal-r9-linux-x64.zip | 578060874 | 05e82aa4f4959da3e0daccacf895e1db15afabc285e62e519889d68b5117fc65 |
| Adept.UI-1.1.5-terminal-r9-mac-arm64.zip | 430808440 | afbcd18b9f88a223388776153020c8852df2a5eac6873cb36588df720d808339 |

The unpublished r8 archives are not in the catalog. Linux build https://github.com/bradjohnson79/adeptui/actions/runs/38977990264. Windows build https://github.com/bradjohnson79/adeptui/actions/runs/38978008508. macOS build https://github.com/bradjohnson79/adeptui/actions/runs/38978011224. Build commit `e8347712`.

Catalog SHA-256 `e08e2b23470f367271fe3c3636ca5b873d36f1ed7200cf6b42e370b9a6ea8e3a`. Signature SHA-256 `9dd371b58b63ca54b7e185b46468dca5c4e7f8e851dd5d0b2db3c2676a675837`. Catalog deployment `dpl_DUnvJuEMmLBHqUvXQ3Xjw2BxFJE3`. Current production deployment `dpl_9tvb97A7ZEJXvQQFGNLbCPCeE9rm` on adeptui.org.

Public installation gate https://github.com/bradjohnson79/adeptui/actions/runs/38979729580 succeeded against the live catalog. Windows reported `INSTALLATION: PASS`, `SHORTCUT: PASS`, `STUDIO_WINDOW: PASS Adept UI Studio`, `UPDATE: PASS`, `PREVIOUS_VERSION_PRESERVED: PASS`, and `SAME_VERSION_REVISION: PASS 5`. Ubuntu and Fedora reported `INSTALLATION: PASS`, `REINSTALL_AND_USER_DATA: PASS`, `UPDATE: PASS`, and `PREVIOUS_VERSION_PRESERVED: PASS`. Fedora ran in a fedora:41 container. macOS reported `INSTALLATION: PASS`, `REINSTALL_AND_USER_DATA: PASS`, `UPDATE: PASS`, `GRAPHICAL_STARTUP: NOT_VERIFIED`, and `NOTARIZATION: EXTERNAL_BLOCKER`. Those Linux and macOS jobs do not open the Studio window. The same-version check started from recorded revision 0 and finished at published revision 5. It is the launcher revision path, not a separate test that began on a revision 4 installation.

The Setup menu on the local Windows Studio opens the three-choice manager. Inline provider keys are on that page. Legacy setup sections are not mounted. That local window is the owner's machine. It is not a substitute for the virtual-display or container Studio checks.

Studio certification https://github.com/bradjohnson79/adeptui/actions/runs/38980530835 installed from adeptui.org. Windows reported the Studio window, shortcut, restart, and user-data preservation. The Windows frame shows the startup gauge while services are still starting. Ubuntu on Xvfb reported `SETUP_WIZARD: PASS`, `STUDIO_WINDOW_first: PASS`, `RESTART: PASS`, and `UNINSTALL_PRESERVES_USER_DATA: PASS`, labeled `DISPLAY: VIRTUAL_XVFB`. The Ubuntu frame shows Full Local Installation, Hybrid Installation — Local + API, and Full API Installation, with Full API selected. Fedora in a fedora:41 container reported the Studio window title, restart, and user-data preservation, with `SETUP_WIZARD: NOT_VERIFIED`. The Fedora frame is blank. Neither Linux result is a physical desktop. macOS reported `SIGNATURE_STRUCTURE: PASS`, `GATEKEEPER: NOT_ACCEPTED`, `NOTARIZATION: EXTERNAL_BLOCKER`, and `STUDIO_WINDOW: PROCESS_STARTED title not confirmed`. The macOS screenshot of that same run shows the three installation choices and the window title Adept UI Studio. Gatekeeper approval is not claimed.

The publication pin still expected revision 4 archive names, so the failure-recovery job failed while the install and Studio jobs passed. The pin now expects revision 5 and the r9 archive names. Owner certification of the Setup Manager is not granted.
