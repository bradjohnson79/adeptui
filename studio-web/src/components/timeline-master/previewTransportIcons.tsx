/** Playback marks shared by Full Screen and the Timeline preview bar. */

import type { ReactNode } from "react";

function Mark({ children }: { children: ReactNode }) {
  return (
    <svg className="preview-transport-icon" viewBox="0 0 24 24" width="18" height="18" aria-hidden="true">
      {children}
    </svg>
  );
}

export function TransportPlayIcon() {
  return (
    <Mark>
      <path d="M8 5.5v13l11-6.5-11-6.5z" fill="currentColor" />
    </Mark>
  );
}

export function TransportPauseIcon() {
  return (
    <Mark>
      <rect x="6" y="5" width="4" height="14" rx="1" fill="currentColor" />
      <rect x="14" y="5" width="4" height="14" rx="1" fill="currentColor" />
    </Mark>
  );
}

export function TransportSceneStartIcon() {
  return (
    <Mark>
      <rect x="4" y="5" width="2" height="14" rx="0.5" fill="currentColor" />
      <path d="M19 6 12 12l7 6V6z" fill="currentColor" />
      <path d="M13 6 6 12l7 6V6z" fill="currentColor" />
    </Mark>
  );
}

export function TransportSceneEndIcon() {
  return (
    <Mark>
      <path d="M5 6v12l7-6-7-6z" fill="currentColor" />
      <path d="M11 6v12l7-6-7-6z" fill="currentColor" />
      <rect x="18" y="5" width="2" height="14" rx="0.5" fill="currentColor" />
    </Mark>
  );
}

export function TransportBatchStartIcon() {
  return (
    <Mark>
      <rect x="5" y="5" width="2" height="14" rx="0.5" fill="currentColor" />
      <path d="M19 6 9 12l10 6V6z" fill="currentColor" />
    </Mark>
  );
}

function SkipMark({ forward }: { forward: boolean }) {
  return (
    <Mark>
      <g transform={forward ? "translate(24 0) scale(-1 1)" : undefined}>
        <path
          d="M13.2 6.1a6.1 6.1 0 1 0 1.35 4.55"
          fill="none"
          stroke="currentColor"
          strokeWidth="1.7"
          strokeLinecap="round"
        />
        <path d="M13.4 3.2 9.2 6.35l4.35 2.15V3.2z" fill="currentColor" />
      </g>
      <text
        x="12"
        y="15.4"
        textAnchor="middle"
        fontSize="6.4"
        fontWeight="700"
        fill="currentColor"
        fontFamily="inherit"
      >
        5
      </text>
    </Mark>
  );
}

export function TransportRewind5Icon() {
  return <SkipMark forward={false} />;
}

export function TransportForward5Icon() {
  return <SkipMark forward={true} />;
}

export function TransportBatchEndIcon() {
  return (
    <Mark>
      <path d="M5 6v12l10-6L5 6z" fill="currentColor" />
      <rect x="17" y="5" width="2" height="14" rx="0.5" fill="currentColor" />
    </Mark>
  );
}
