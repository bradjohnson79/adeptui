# NVDA Manual Certification Checklist (A11Y-SR-01..12)

NVDA launch is **not** NVDA certification. Keep these results separate:

| Gate | Result |
|------|--------|
| NVDA installed | PASS / FAIL |
| NVDA launch preflight | PASS / FAIL |
| NVDA A11Y-SR-01..12 manual session | PENDING / PASS / FAIL |

Installed path (known): `C:\Program Files\NVDA\nvda.exe`

## Session prep

1. Launch NVDA.
2. Open Adept UI Studio in Chrome.
3. Confirm speech is audible before scoring any item.
4. Record PASS/FAIL/NOTES per row. Do not mark Manual Beta GREEN from launch alone.

## Checklist

| ID | Surface | Announcement expectation | Result | Notes |
|----|---------|--------------------------|--------|-------|
| A11Y-SR-01 | App shell / landmark | Main region / page title announced on load | PENDING | |
| A11Y-SR-02 | Primary nav / workspace menu | Menu button name + expanded/collapsed | PENDING | |
| A11Y-SR-03 | Project Home | Heading and primary CTA announced | PENDING | |
| A11Y-SR-04 | ImageGen | Prompt/negative labels announced with fields | PENDING | |
| A11Y-SR-05 | Txt2Vid | Prompt + engine controls labeled; LOCAL-16 dialog title/actions announced | PENDING | |
| A11Y-SR-06 | Paid fal dialog | Dialog role, title, preferred local action, cancel | PENDING | |
| A11Y-SR-07 | Director | Scene list / clip selection announced | PENDING | |
| A11Y-SR-08 | Editor | Timeline / clip actions announced | PENDING | |
| A11Y-SR-09 | Settings / Integrations | fal key and billing controls labeled (no secret leakage) | PENDING | |
| A11Y-SR-10 | Job status | Status/progress changes announced or polite live region | PENDING | |
| A11Y-SR-11 | Error / blocker | LOCAL_START_FRAME_REQUIRED / failure message announced | PENDING | |
| A11Y-SR-12 | Focus order | Tab order logical; no keyboard trap in dialogs | PENDING | |

## Verdict rules

- Launch preflight PASS ≠ manual session PASS.
- Incomplete manual session ⇒ Manual Beta Entry **NO**, even if M3.0h is YES.
- Accessibility does **not** retroactively fail a GREEN local filmmaker path.
