import {
  useEffect,
  useId,
  useRef,
  type KeyboardEvent,
  type MouseEvent,
  type ReactNode,
} from "react";
import "./menu.css";

export type MenuItem =
  | {
      id: string;
      label: string;
      shortcut?: string;
      disabled?: boolean;
      selected?: boolean;
      danger?: boolean;
      testId?: string;
      onSelect?: () => void;
    }
  | { id: string; type: "separator" }
  | { id: string; type: "label"; label: string };

type MenuProps = {
  label: string;
  items: MenuItem[];
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onHoverOpen?: () => void;
  /** Show chevron like classic EXE menus */
  showChevron?: boolean;
  className?: string;
  ariaLabel?: string;
  align?: "start" | "end";
  /** Compact overflow control (scene cards, project cards). */
  compact?: boolean;
  trigger?: ReactNode;
  testId?: string;
};

function isActionItem(
  item: MenuItem,
): item is Exclude<MenuItem, { type: string }> {
  return !("type" in item);
}

export function Menu({
  label,
  items,
  open,
  onOpenChange,
  onHoverOpen,
  showChevron = true,
  className = "",
  ariaLabel,
  align = "start",
  compact = false,
  trigger,
  testId,
}: MenuProps) {
  const id = useId();
  const rootRef = useRef<HTMLDivElement>(null);
  const panelRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const onDoc = (e: globalThis.MouseEvent) => {
      if (!rootRef.current?.contains(e.target as Node)) onOpenChange(false);
    };
    document.addEventListener("mousedown", onDoc);
    return () => document.removeEventListener("mousedown", onDoc);
  }, [open, onOpenChange]);

  useEffect(() => {
    if (!open) return;
    const panel = panelRef.current;
    if (!panel) return;
    const first = panel.querySelector<HTMLElement>("[role='menuitem']:not([disabled])");
    first?.focus();
    const box = panel.getBoundingClientRect();
    const pad = 8;
    let shiftX = 0;
    let shiftY = 0;
    if (box.right > window.innerWidth - pad) shiftX = window.innerWidth - pad - box.right;
    if (box.left + shiftX < pad) shiftX = pad - box.left;
    if (box.bottom > window.innerHeight - pad) shiftY = window.innerHeight - pad - box.bottom;
    if (box.top + shiftY < pad) shiftY = pad - box.top;
    if (shiftX || shiftY) {
      panel.style.transform = `translate(${shiftX}px, ${shiftY}px)`;
    }
  }, [open]);

  const stopCardSelect = (e: MouseEvent) => {
    e.stopPropagation();
  };

  const actionItems = items.filter(isActionItem);
  const moveFocus = (delta: number) => {
    const enabled = actionItems.filter((item) => !item.disabled);
    if (!enabled.length) return;
    const currentId = document.activeElement?.getAttribute("data-menu-item-id");
    const index = Math.max(0, enabled.findIndex((item) => item.id === currentId));
    const next = enabled[(index + delta + enabled.length) % enabled.length];
    panelRef.current?.querySelector<HTMLElement>(`[data-menu-item-id="${next.id}"]`)?.focus();
  };

  const onKeyDown = (e: KeyboardEvent) => {
    if (e.key === "Escape") {
      e.stopPropagation();
      e.preventDefault();
      onOpenChange(false);
      rootRef.current?.querySelector<HTMLElement>(".ds-menu-trigger")?.focus();
      return;
    }
    if (!open) return;
    if (e.key === "ArrowDown") {
      e.preventDefault();
      moveFocus(1);
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      moveFocus(-1);
    } else if (e.key === "Home") {
      e.preventDefault();
      const first = actionItems.find((item) => !item.disabled);
      if (first) panelRef.current?.querySelector<HTMLElement>(`[data-menu-item-id="${first.id}"]`)?.focus();
    } else if (e.key === "End") {
      e.preventDefault();
      const last = [...actionItems].reverse().find((item) => !item.disabled);
      if (last) panelRef.current?.querySelector<HTMLElement>(`[data-menu-item-id="${last.id}"]`)?.focus();
    }
  };

  return (
    <div
      className={["ds-menu-root", compact ? "ds-menu-root--compact" : "", className].filter(Boolean).join(" ")}
      ref={rootRef}
      onMouseEnter={onHoverOpen}
      onKeyDown={onKeyDown}
      onClick={stopCardSelect}
      onMouseDown={stopCardSelect}
    >
      <button
        type="button"
        className={["ds-menu-trigger", compact ? "ds-menu-trigger--overflow" : ""].filter(Boolean).join(" ")}
        aria-haspopup="menu"
        aria-expanded={open}
        aria-controls={id}
        aria-label={ariaLabel || label}
        data-testid={testId}
        onClick={(e) => {
          e.stopPropagation();
          onOpenChange(!open);
        }}
      >
        {trigger ?? (
          <>
            <span>{label}</span>
            {showChevron ? <span className="ds-menu-trigger__chevron" aria-hidden>▾</span> : null}
          </>
        )}
      </button>
      {open ? (
        <div
          ref={panelRef}
          className={["ds-menu-panel", align === "end" ? "ds-menu-panel--end" : ""].filter(Boolean).join(" ")}
          role="menu"
          id={id}
        >
          {items.map((item) => {
            if ("type" in item && item.type === "separator") {
              return <hr key={item.id} className="ds-menu-sep" />;
            }
            if ("type" in item && item.type === "label") {
              return (
                <div key={item.id} className="ds-menu-label" role="presentation">
                  {item.label}
                </div>
              );
            }
            if ("type" in item) return null;
            return (
              <button
                key={item.id}
                type="button"
                role="menuitem"
                data-menu-item-id={item.id}
                data-testid={item.testId}
                className={[
                  "ds-menu-item",
                  item.selected ? "is-selected" : "",
                  item.danger ? "ds-menu-item--danger" : "",
                ]
                  .filter(Boolean)
                  .join(" ")}
                disabled={item.disabled}
                onClick={() => {
                  if (item.disabled) return;
                  item.onSelect?.();
                  onOpenChange(false);
                }}
              >
                <span>{item.label}</span>
                {item.shortcut ? <span className="ds-menu-item__shortcut">{item.shortcut}</span> : null}
              </button>
            );
          })}
        </div>
      ) : null}
    </div>
  );
}

export function MenuBarShell({
  brand,
  trailing,
  children,
  className = "",
}: {
  brand?: ReactNode;
  trailing?: ReactNode;
  children: ReactNode;
  className?: string;
}) {
  return (
    <div className={["ds-menubar", className].filter(Boolean).join(" ")} role="menubar" data-testid="ds-menubar">
      {brand}
      <div className="ds-menubar__menus">{children}</div>
      {trailing ? <div className="ds-menubar__trailing">{trailing}</div> : null}
    </div>
  );
}
