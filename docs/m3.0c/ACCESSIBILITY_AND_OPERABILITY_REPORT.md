# Accessibility and Operability Report

Date: 2026-07-27

Status: **PENDING certification**.

## Available evidence

- The captured Playwright suite completed with 111 passed, 0 failed, and 6 intentional skips.
- Existing functional-audit evidence includes setup screenshots at 1024x768, 1280x720, 1440x900, and 1920x1080.
- The available E2E coverage demonstrates operability of the tested setup, project, Co-Director, media, timeline, render, export, and recovery journeys.

## Not yet certified

No dedicated accessibility audit was run for keyboard-only operation, focus order and visibility, semantic landmarks, accessible names and descriptions, contrast, reduced motion, screen-reader behavior, zoom/reflow, or automated WCAG checks. Functional Playwright success and screenshots are not sufficient evidence for an accessibility certification.

Required follow-up:

- Run the planned accessibility automation against the supported routes.
- Test keyboard-only completion of critical journeys.
- Check focus visibility, dialogs, form errors, tables/cards, and responsive reflow at supported viewport sizes.
- Record browser, viewport, tool versions, findings, and exit codes.
