import {
  useEffect,
  useId,
  useRef,
  type KeyboardEvent,
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
};

export function Menu({
  label,
  items,
  open,
  onOpenChange,
  onHoverOpen,
  showChevron = true,
  className = "",
}: MenuProps) {
  const id = useId();
  const rootRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const onDoc = (e: MouseEvent) => {
      if (!rootRef.current?.contains(e.target as Node)) onOpenChange(false);
    };
    document.addEventListener("mousedown", onDoc);
    return () => document.removeEventListener("mousedown", onDoc);
  }, [open, onOpenChange]);

  const onKeyDown = (e: KeyboardEvent) => {
    if (e.key === "Escape") {
      e.stopPropagation();
      onOpenChange(false);
    }
  };

  return (
    <div
      className={["ds-menu-root", className].filter(Boolean).join(" ")}
      ref={rootRef}
      onMouseEnter={onHoverOpen}
      onKeyDown={onKeyDown}
    >
      <button
        type="button"
        className="ds-menu-trigger"
        aria-haspopup="menu"
        aria-expanded={open}
        aria-controls={id}
        onClick={() => onOpenChange(!open)}
      >
        <span>{label}</span>
        {showChevron ? <span className="ds-menu-trigger__chevron" aria-hidden>▾</span> : null}
      </button>
      {open ? (
        <div className="ds-menu-panel" role="menu" id={id}>
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
                className={["ds-menu-item", item.selected ? "is-selected" : ""].filter(Boolean).join(" ")}
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
