import { kofi } from "../support";

/**
 * A normal link, not the Ko-fi widget script.
 * The hosted widget injects its own button and does not fit this site's hydration or branding.
 * One component is reused in the header and the mobile menu.
 */
export function KoFiButton() {
  return (
    <a className="kofi" href={kofi.url} target="_blank" rel="noreferrer" aria-label={kofi.accessibleLabel}>
      <svg viewBox="0 0 16 16" aria-hidden="true">
        <path
          fill="currentColor"
          d="M3.2 3.2h8.1c.3 0 .5.2.5.5v1.1h.7c1.1 0 2 .9 2 2s-.9 2-2 2h-.7v.4c0 1.6-1.2 2.9-2.8 3.1l-.3 1.2H5.3l-.3-1.2C3.4 12.1 2.2 10.8 2.2 9.2V3.7c0-.3.2-.5.5-.5h.5zm8.6 2.2v1.8h.7c.5 0 .9-.4.9-.9s-.4-.9-.9-.9h-.7zM4 4.6v4.6c0 1 .7 1.8 1.7 1.9h2.6c1 0 1.8-.8 1.8-1.9V4.6H4z"
        />
      </svg>
      <span>{kofi.label}</span>
    </a>
  );
}
