# Setup Containment

## Rule

All install, repair, update, calibration, and certification flows must route through Setup and trusted Source Manager / install-job services. Creative surfaces may deep-link into Setup, but they must not become their own primary installer.

## Surface matrix

| Surface | Install / repair entry posture after this pass | Status |
| --- | --- | --- |
| Setup Wizard | Canonical lifecycle owner | PASS |
| AI-Guided Setup | Remains inside Setup; creator approves here before Source Manager executes | PASS |
| Production Dock | Uses `buildAiGuidedSetupPath()` and `InstallStatusChip` to open project Setup instead of a competing installer | PASS |
| Status Center / health strip | Uses `buildAiGuidedSetupPath()` to route missing local dependencies back to Setup | PASS |
| Home / workspace launch | Setup CTA still resolves into project Setup with `workspace=setup` | PASS |
| Off-project setup CTA fallback | Generic setup links now land on Home, which immediately forwards into a real project's AI-Guided Setup instead of dumping creators into `Source Manager` | PASS |
| Video Studio / Video Model Library | Visible install/repair buttons deep-link to Setup; verify/benchmark/remove remain secondary maintenance actions | PASS |
| Avatar Studio | Runtime install messaging points creators back to Setup for install and repair | PASS |
| Voice Studio | No competing installer surfaced in the workspace; setup-sensitive actions remain outside the creator flow | PASS |
| Image Studio | No competing installer surfaced in the workspace; provider/setup escalation remains outside the creator flow | PASS |
| Source Manager | Execution owner only; no longer the fallback destination for generic setup deep-links | PASS |

## Evidence

- Shared setup navigation helper: `studio-web/src/setup/navigation.ts`
- Home redirect to project Setup when no project context exists: `studio-web/src/pages/Home.tsx`
- AI-Guided setup panel no longer advertises a competing Source Manager CTA: `studio-web/src/setup/lifecycle/AiGuidedSetupPanel.tsx`
- Production Dock setup affordances: `studio-web/src/components/production-dock/ModelMenuDrawer.tsx`
- Status Center setup affordances: `studio-web/src/components/dashboard/SystemStatusStrip.tsx`
- Video Studio setup affordances: `studio-web/src/components/VideoModelLibrary.tsx`, `studio-web/src/components/Txt2VidPanel.tsx`
- Avatar Studio setup affordances: `studio-web/src/components/AvatarStudioWorkspace.tsx`

## Validation

- Playwright: `npm run test:e2e -- tests/e2e/setup/ai-guided-setup-lifecycle.spec.ts`
  - Result: `4 passed`
- The root AI-Guided redirect preserved `setupSource` and `setupComponent` while forwarding from `/` into `/project/:id?workspace=setup...`

## Finding

Phase 4 containment is now closed for the requested creator-facing deep-link rule.

Source Manager still exists as the trusted execution owner, but it is no longer the generic destination for install CTAs coming from Dock, Status, or studio entry points.
