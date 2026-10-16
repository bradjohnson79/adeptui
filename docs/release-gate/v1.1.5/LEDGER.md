# Adept UI 1.1.5 four-platform certification ledger

Phase: certification workflow is in the repository. Platform results are recorded from the GitHub Actions run, not from package inspection.

Published release: v1.1.5. Catalog commit `d663ddd06eb59a066438d76c8a235640038f5cd8`. Installer commit `45a564e48f85f9e3825f51cc573e02eafd489a8d`.

| Platform | Environment | Installation | Studio | Upgrade | Recovery |
|---|---|---|---|---|---|
| Windows 11 x64 | GitHub windows-latest desktop session | waiting for the certification run | waiting | waiting | waiting |
| macOS arm64 | GitHub macos-14 | waiting | waiting | waiting | waiting |
| Ubuntu x64 | GitHub ubuntu-22.04 with Xvfb | waiting | waiting | waiting | waiting |
| Fedora x64 | fedora:41 container with Xvfb, not a physical desktop | waiting | waiting | waiting | waiting |

macOS notarization: EXTERNAL BLOCKER until Apple credentials are available. The certification does not bypass Gatekeeper.

Automatic upgrade from the immutable 1.1.3 and 1.1.4 binaries is expected to stay NO-GO. Those launchers do not apply a later installer. A public reinstall that keeps the user-data directory is recorded as migration, not as an automatic upgrade.

The launcher update worker copies a non-zip catalog artifact into its lifecycle directory. It does not run the NSIS, DEB, RPM, or DMG installer. Changing that behavior is a new updater design and is not part of this release.
