# Adept UI 1.1.6 launcher update ledger

Phase: the signed catalog and GitHub release exist. Four-platform installation, Studio, and automatic-update certification has not been recorded yet.

Release: https://github.com/bradjohnson79/adeptui/releases/tag/v1.1.6
Target: `ee26304ba0544bcf35ced80e4854b849cfa8e18a`
Desktop build: https://github.com/bradjohnson79/adeptui/actions/runs/38860054364
Windows, macOS arm64, Linux DEB/RPM, Ubuntu smoke, and Fedora RPM jobs completed success.

Published asset SHA-256, measured from the GitHub release URLs:

| File | Bytes | SHA-256 |
|---|---:|---|
| Adept.UI-Setup-1.1.6-win-x64.exe | 291932729 | 46b5f7d95125d4c5c11ec4dfd26eaa2306efc23709e9f8afb30f280de1d6dcf1 |
| Adept.UI-1.1.6-linux-x64.deb | 403735340 | dfcd7e088fc10ed35ae8f2addb3185530dfba1e13f5fa41c13fa99c2123f97f6 |
| Adept.UI-1.1.6-linux-x64.rpm | 358666733 | ac192203d47791b556db55e70edd6b2ce23e4f955befcc2e0fbfbb4f2765c03e |
| Adept.UI-1.1.6-mac-arm64.dmg | 411520074 | b0b9d2440ed05a179a13d9cfe224290786b81ead7155586ee84dfa2ac06302f9 |

Catalog SHA-256 `aeb9eecc32dddf0f993ca3373ba5af10bd79dd081d976c25b9b1ff9783905506` (1453 bytes). Signature SHA-256 `01e713033204a7282a9c84d35e56e9dd60c2c6bd324a74aa029d6c90b024da6f` (512 bytes). OpenSSL verified those exact catalog bytes with the pinned public key. v1.1.3, v1.1.4, and v1.1.5 assets were not replaced. v1.1.5 Windows installer remains 291928877 bytes.

The 1.1.6 launcher installs a newer signed NSIS, DEB, RPM, or DMG with the platform installer. Frozen 1.1.3, 1.1.4, and 1.1.5 launchers cannot do that and need one public installer run. macOS notarization remains an external blocker. The packaging step re-signs the bundle ad hoc so the executable and resources agree. Gatekeeper is not bypassed.

Launcher and lifecycle tests before this release: 35 passed. Website download tests: 6 passed.
