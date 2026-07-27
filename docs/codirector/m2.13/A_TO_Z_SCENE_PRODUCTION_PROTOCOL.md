# A–Z Scene Production Protocol

`SceneProductionPlan` stages:

| Stage | Name | Approval gate |
| --- | --- | --- |
| A | Source Intake | |
| B | Asset Validation | |
| C | Route Decision | |
| D | Environment Construction | |
| E | Environment Approval | environment |
| F | Theme Recommendation | |
| G | Theme Preview | |
| H | Theme Approval | theme |
| I | Blocking Draft | |
| J | Blocking Refine | |
| K | Blocking Approval | blocking |
| L | Camera State | |
| M | Lighting State | |
| N | Camera/Lighting Approval | camera_lighting |
| O | Shot Package Build | |
| P | Shot Package Approval | shot_package |
| Q | Concept Draft | |
| R | Concept Production | |
| S | Concept Approval | concept |
| T | Draft Stitch | |
| U | Timeline Publish | |
| V | Selective Regenerate | |
| W | Final Candidate | |
| X | Bible / Continuity Bind | |
| Y | Readiness Checkpoint | |
| Z | Final Delivery | |

Advances require an explicit API call. Leaving an approval stage without a persisted approval records a blocker and sets readiness `NO-GO`.
