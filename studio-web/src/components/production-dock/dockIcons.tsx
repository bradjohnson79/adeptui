/** Inline SVGs for Production Dock collapse / launcher controls. */

export function DockCollapseArrowIcon({ className }: { className?: string }) {
  return (
    <svg
      className={className}
      width="22"
      height="22"
      viewBox="0 0 24 24"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      aria-hidden="true"
      focusable="false"
    >
      <path
        d="M6 9.5L12 15.5L18 9.5"
        stroke="currentColor"
        strokeWidth="2.25"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

/** Circular launcher mark — dock / production console glyph. */
export function DockLauncherIcon({ className }: { className?: string }) {
  return (
    <svg
      className={className}
      width="26"
      height="26"
      viewBox="0 0 24 24"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      aria-hidden="true"
      focusable="false"
    >
      <rect
        x="3.5"
        y="14"
        width="17"
        height="5.5"
        rx="2.75"
        stroke="currentColor"
        strokeWidth="1.75"
      />
      <path
        d="M7 14V11.5C7 10.12 8.12 9 9.5 9H14.5C15.88 9 17 10.12 17 11.5V14"
        stroke="currentColor"
        strokeWidth="1.75"
        strokeLinecap="round"
      />
      <circle cx="12" cy="6.25" r="2.25" stroke="currentColor" strokeWidth="1.75" />
      <path
        d="M8.5 16.75H15.5"
        stroke="currentColor"
        strokeWidth="1.5"
        strokeLinecap="round"
      />
    </svg>
  );
}
