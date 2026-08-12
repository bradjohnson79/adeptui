# M42 Wave 4 — Reference Workflows

zimage.ref_edit remains the certified reference-edit path, revalidated through ImageEditIntent.

Role-aware multi-reference is modeled on EditLayer / ReferenceAsset; certified multi-ref keys are empty until additional dual-stage cert.

## FLUX Kontext interface (R7)

KontextEditSession + API stubs:

- POST /api/image-product/projects/{id}/kontext/session
- POST .../kontext/session/{sessionId}/turn

Status is honest **Blocked** until lux.kontext_edit is live dual-stage Certified. Turns are recorded; no pixel manipulation; no fake execute.

Artifact: kontext_interface_results.json, 
eference_edit_results.json.
