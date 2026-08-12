# ERS Capability Matrix

| Capability | Status | Notes |
|---|---|---|
| Co-Director canonical draft creation | Available | `ers.create_sheet` |
| Spatial Map north lock | Available | `ers.attach_spatial_map` reuses project Spatial Map |
| Directional view planning | Available | `ers.generate_directional_views` creates Image Pipeline plans/groups |
| Explicit per-direction approval | Available | `ers.approve_direction` |
| Continuity validation | Available with limits | Metadata-based only in this pass |
| Truthful optional 3D label | Available | `ers.set_optional_three_d` |
| Sheet composition metadata | Available | `ers.compose_sheet` |
| Project registration | Available | `ers.register_project` updates/creates Production Bible location |
| PNG export | Available | Rendered with Pillow and registered as project asset |
| PDF export | Available | Derived from rendered PNG and registered as project asset |
| Offline HTML package | Available | Relative-media zip package, no network dependence |
| Creator review panel | Available | Read-only Co-Director panel in `Plans` |
| Autonomous Playwright certification | Not yet certified | Test scaffold added; full scenario A-L coverage still required |
