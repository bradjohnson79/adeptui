# Certified Image Catalog

## Local image setup components

Primary first-class setup entries added:

- `flux1_dev_local`
- `flux1_schnell_local`
- `flux1_kontext_dev_local`
- `qwen_image_2512_models`
- `zimage_models`
- `sana_15_local`
- `sdxl_local`
- `sd35_large_local`

Additional experimental catalog entries added:

- `cogview4_local`
- `hidream_local`
- `lumina_image_2_local`
- `pixart_sigma_local`
- `kolors_local`
- `omnigen_local`
- `janus_pro_local`
- `hunyuan_image_local`

## Card metadata

Lifecycle metadata now supports:

- Ready / Not Installed / Repair Recommended posture
- certified version/date
- parameter count
- download size
- disk usage
- VRAM recommendation
- typical generation speed
- supported resolutions
- strengths
- weaknesses
- best-for notes
- capability badges

## Cloud providers

Image cloud providers stay in a separate `Cloud Providers` section. The registry now includes:

- fal.ai
- Replicate
- OpenAI Images
- Google Imagen
- Ideogram
- Recraft
- Leonardo
- Runware
- Together AI

## Recommendations

Current creator-facing recommendation rules:

- photoreal character -> `FLUX.1 Kontext Dev`
- anime/stylized -> `Sana 1.5`, `Qwen-Image-2512`, `Z-Image Turbo`
- fast preview -> `FLUX.1 Schnell`

## Production Dock wiring

Production Dock model IDs now map back to setup component IDs for the expanded image catalog, so install/certification posture can surface under Image Generation without workspace-specific wiring.
