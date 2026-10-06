# Adept video systems — T2V / I2V / R2V

Governing journey for binding MiniMax and LTX 2.5 to the creator system that owns each mode.

## Product law

| System | Mode | Local engines |
|---|---|---|
| Text to Video | Text-to-video (words only) | LTX 2.5 empty-latent · MiniMax Route A T2VA |
| 1 Frame / 3 Frame | Image-to-video (pictures) | LTX 2.5 I2V · MiniMax I2VA |
| Timeline | Reference-to-video | MiniMax H3 Ref2V · LTX 2.5 start-frame + prompt references |

Do not run T2V on Timeline. Do not run R2V on Text to Video. Do not silently swap families.

## Runtime

- LTX 2.5 T2V/I2V: canonical Comfy `:8188`. Do not restart it.
- MiniMax T2V/I2V: Route A `:8192`, prepare-on-Generate.
- MiniMax Timeline R2V: Comfy `:8188` `MiniMaxH3ReferenceToVideo`.

## Project

Korri Anadriya `beffd3d8-791d-4adf-9c4d-681ec9d4efb0`. No disposable projects.
