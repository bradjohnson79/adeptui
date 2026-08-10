import type { ReactNode } from "react";
import { IconButton } from "./Button";
import "./menu.css";

export type ToolbarAction = {
  id: string;
  label: string;
  icon: ReactNode;
  disabled?: boolean;
  onClick?: () => void;
};

export function Toolbar({
  actions,
  onSearchClick,
  trailing,
}: {
  actions: ToolbarAction[];
  onSearchClick?: () => void;
  trailing?: ReactNode;
}) {
  return (
    <div className="ds-toolbar" role="toolbar" aria-label="Workspace toolbar" data-testid="ds-toolbar">
      <div className="ds-toolbar__group">
        {actions.map((action, index) => (
          <span key={action.id} style={{ display: "contents" }}>
            {index === 5 ? <span className="ds-toolbar__sep" aria-hidden /> : null}
            <IconButton
              aria-label={action.label}
              title={action.label}
              disabled={action.disabled}
              onClick={action.onClick}
              data-testid={`toolbar-${action.id}`}
            >
              {action.icon}
            </IconButton>
          </span>
        ))}
      </div>
      <button type="button" className="ds-toolbar__search" onClick={onSearchClick} data-testid="toolbar-search">
        <span aria-hidden>⌕</span>
        <span>Search…</span>
        <span className="ds-toolbar__kbd">Ctrl+K</span>
      </button>
      {trailing}
    </div>
  );
}

export const ToolbarIcons = {
  new: (
    <svg width="18" height="18" viewBox="0 0 18 18" fill="none" aria-hidden>
      <path d="M9 3v12M3 9h12" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />
    </svg>
  ),
  open: (
    <svg width="18" height="18" viewBox="0 0 18 18" fill="none" aria-hidden>
      <path d="M3 5h5l1.5 2H15v8H3V5z" stroke="currentColor" strokeWidth="1.4" />
    </svg>
  ),
  save: (
    <svg width="18" height="18" viewBox="0 0 18 18" fill="none" aria-hidden>
      <path d="M4 3h8l3 3v9H4V3z" stroke="currentColor" strokeWidth="1.4" />
      <path d="M6 3v5h6V3" stroke="currentColor" strokeWidth="1.4" />
    </svg>
  ),
  undo: (
    <svg width="18" height="18" viewBox="0 0 18 18" fill="none" aria-hidden>
      <path d="M6 7H3V4" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" />
      <path d="M3 7a6 6 0 1 1 2 5" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" />
    </svg>
  ),
  redo: (
    <svg width="18" height="18" viewBox="0 0 18 18" fill="none" aria-hidden>
      <path d="M12 7h3V4" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" />
      <path d="M15 7a6 6 0 1 0-2 5" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" />
    </svg>
  ),
  generate: (
    <svg width="18" height="18" viewBox="0 0 18 18" fill="none" aria-hidden>
      <path d="M9 2l1.2 4.2L14.5 7.5l-4.3 1.3L9 13l-1.2-4.2L3.5 7.5l4.3-1.3L9 2z" stroke="currentColor" strokeWidth="1.2" />
    </svg>
  ),
  render: (
    <svg width="18" height="18" viewBox="0 0 18 18" fill="none" aria-hidden>
      <rect x="3" y="4" width="12" height="10" rx="2" stroke="currentColor" strokeWidth="1.4" />
      <path d="M7 8l4 2-4 2V8z" fill="currentColor" />
    </svg>
  ),
  codirector: (
    <svg width="18" height="18" viewBox="0 0 18 18" fill="none" aria-hidden>
      <circle cx="9" cy="8" r="3.2" stroke="currentColor" strokeWidth="1.4" />
      <path d="M4 15c1.2-2.4 3-3.5 5-3.5s3.8 1.1 5 3.5" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" />
    </svg>
  ),
  character: (
    <svg width="18" height="18" viewBox="0 0 18 18" fill="none" aria-hidden>
      <circle cx="9" cy="6" r="2.5" stroke="currentColor" strokeWidth="1.4" />
      <path d="M4.5 15c.8-3 2.4-4.5 4.5-4.5s3.7 1.5 4.5 4.5" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" />
    </svg>
  ),
  bible: (
    <svg width="18" height="18" viewBox="0 0 18 18" fill="none" aria-hidden>
      <path d="M4 3.5h8.5A1.5 1.5 0 0 1 14 5v10H5.5A1.5 1.5 0 0 0 4 16.5V3.5z" stroke="currentColor" strokeWidth="1.4" />
      <path d="M7 7h4M7 10h3" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round" />
    </svg>
  ),
  library: (
    <svg width="18" height="18" viewBox="0 0 18 18" fill="none" aria-hidden>
      <path d="M3 4h4v11H3V4zm5 0h4v11H8V4zm5 0h2v11h-2V4z" stroke="currentColor" strokeWidth="1.2" />
    </svg>
  ),
};
