import { useEffect, useState, type ReactNode } from "react";

export function CisAccordion({
  id,
  title,
  status,
  defaultOpen = false,
  persistKey,
  headerAction,
  children,
  className = "",
}: {
  id: string;
  title: string;
  status?: string;
  defaultOpen?: boolean;
  persistKey?: string;
  headerAction?: ReactNode;
  children: ReactNode;
  className?: string;
}) {
  const storageKey = persistKey ? `${persistKey}:${id}` : "";
  const [open, setOpen] = useState(() => {
    if (storageKey) {
      try {
        const raw = localStorage.getItem(storageKey);
        if (raw === "1") return true;
        if (raw === "0") return false;
      } catch {
        /* ignore */
      }
    }
    return defaultOpen;
  });

  useEffect(() => {
    if (!storageKey) return;
    try {
      localStorage.setItem(storageKey, open ? "1" : "0");
    } catch {
      /* ignore */
    }
  }, [open, storageKey]);

  return (
    <details
      className={`cis-card cis-accordion ${className}`.trim()}
      data-testid={`cis-accordion-${id}`}
      open={open}
      onToggle={(event) => setOpen((event.target as HTMLDetailsElement).open)}
    >
      <summary className="cis-accordion__summary">
        <span className="cis-accordion__heading">
          <span className="cis-card__title">{title}</span>
          {status ? <span className="cis-accordion__status">{status}</span> : null}
        </span>
        {headerAction ? (
          <span
            className="cis-accordion__action"
            onClick={(event) => event.stopPropagation()}
            onKeyDown={(event) => event.stopPropagation()}
          >
            {headerAction}
          </span>
        ) : null}
      </summary>
      <div className="cis-accordion__body">{children}</div>
    </details>
  );
}
