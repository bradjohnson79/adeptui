# M42 W6P — Release Readiness

## Notes
- Product name: Timeline (Preview Monitor wording)
- Scene Reference Binding is canonical attachment authority
- `director_references` retained as Timeline ReferenceSet compatibility

## Limitations
- Performance metrics intentionally `not_measured` (honest)

## Migration / rollback
- Forward: m024 scene_reference_bindings (+ m023 continuity)
- Rollback: drop scene_reference_* tables; Timeline ReferenceSets unaffected

## API index
- `/api/projects/:projectId/references*`
- `/api/m42-product/gate/wave6p`
- `/api/m42-product/gate/wave6p/scene-references`

| **Verdict** | **GO** |
