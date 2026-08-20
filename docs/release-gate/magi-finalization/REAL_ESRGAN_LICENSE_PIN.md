# Real-ESRGAN-ncnn-Vulkan — License and Artifact Pin

Measured 2026-08-20. Commercial-use clearance is download-on-install only.
Binaries and models are **not** vendored in the Adept git tree.

## Engine

| Field | Pin |
|---|---|
| Repository | https://github.com/xinntao/Real-ESRGAN-ncnn-vulkan |
| License | MIT (Xintao Wang 2021) plus MIT for nihui/realsr-ncnn-vulkan (2019) |
| Windows binary source | Parent portable package below (includes the ncnn Vulkan exe) |
| Commercial use | Yes, with copyright notice retention |

## Models

| Field | Pin |
|---|---|
| Repository | https://github.com/xinntao/Real-ESRGAN |
| License | BSD 3-Clause (Xintao Wang 2021) |
| Commercial use | Yes, with copyright + disclaimer reproduction in documentation/distribution materials |
| Usable artifacts | ncnn `.bin` / `.param` only. PyTorch `.pth` files are **not** used. |
| Excluded | GFPGAN / face-restore extras (not in this package; not shipped) |

## Pinned Windows install package

One official portable zip contains the engine **and** ncnn models:

| Field | Value |
|---|---|
| URL | https://github.com/xinntao/Real-ESRGAN/releases/download/v0.2.5.0/realesrgan-ncnn-vulkan-20220424-windows.zip |
| Release tag | `v0.2.5.0` |
| Filename | `realesrgan-ncnn-vulkan-20220424-windows.zip` |
| Size (bytes) | `45474481` |
| SHA-256 | `ABC02804E17982A3BE33675E4D471E91EA374E65B70167ABC09E31ACB412802D` |
| Measured | 2026-08-20, SHA256 via Get-FileHash |

### Package contents (inspected)

- `realesrgan-ncnn-vulkan.exe`
- `vcomp140.dll`, `vcomp140d.dll`
- `models/realesr-animevideov3-x2.bin` + `.param`
- `models/realesr-animevideov3-x3.bin` + `.param`
- `models/realesr-animevideov3-x4.bin` + `.param`
- `models/realesrgan-x4plus.bin` + `.param`
- `models/realesrgan-x4plus-anime.bin` + `.param`
- `README_windows.md`

Not present in this zip (do not advertise): `realesrgan-x2plus`, `realesrnet-x4plus`.

## Redistribution strategy

Adept UI downloads this zip during Setup install into:

`settings.data_dir / "runtimes" / "realesrgan-ncnn-vulkan"`

Attribution notices (MIT + BSD 3-Clause) are written beside the install.
Second Setup click reuses a valid install; it does not download another tree.

## Windows compatibility

Official portable Windows build for Intel / AMD / NVIDIA Vulkan GPUs.
Ready requires: binary launches + required models exist + Vulkan inference probe.
