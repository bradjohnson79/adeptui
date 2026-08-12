# PoseCraft — Independent Scrollable Panes

## CURRENT AUTHORITATIVE STATUS

```text
GO — POSECRAFT INDEPENDENT PANEL SCROLLING READY
```

## Behavior

| Column | Scroll |
| --- | --- |
| Left panel (`.posecraft-pane-scroll` / `posecraft-left-scroll`) | Independent `overflow-y: auto` |
| Center viewport (`posecraft-viewport-panel`) | Fixed — `overflow: hidden`; camera only |
| Right panel (`posecraft-right-scroll`) | Independent `overflow-y: auto` |
| Page (`.page.posecraft-workspace`) | `overflow: hidden` — not the scroll container |
| Shell (`posecraft-shell`) | `overflow: hidden` |

Expanding accordions increases pane scroll height only; viewport width/height is not displaced.

## Evidence

- Spec: `tests/e2e/posecraft/posecraft-independent-panel-scroll.spec.ts` — **1 passed**
- Artifacts: `docs/release-gate/posecraft/artifacts/independent-panel-scroll/`
- Beta: http://127.0.0.1:8760/

## Verdict

```text
GO — POSECRAFT INDEPENDENT PANEL SCROLLING READY
```
