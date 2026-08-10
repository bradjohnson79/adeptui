import {
  useCallback,
  useEffect,
  useId,
  useMemo,
  useRef,
  useState,
  type KeyboardEvent as ReactKeyboardEvent,
} from "react";
import { HelpTip } from "../HelpTip";
import {
  buildProductionMenu,
  PRODUCTION_CATEGORY_ORDER,
  type BuiltProductionMenuEntry,
  type CoDirectorQuickActionId,
  type ProductionCategoryId,
} from "../../core/productionMenu";
import type { ProductionAvailability } from "../../core/productionAvailability";
import { loadProductionRecent, type ProductionRecentItem } from "../../core/productionRecent";
import type { EditorTab } from "../../core/workspaces";
import "../ui/menu.css";
import "./production-menu.css";

type Props = {
  open: boolean;
  onOpenChange: (open: boolean, opts?: { restoreFocus?: boolean }) => void;
  onHoverOpen?: () => void;
  availability: ProductionAvailability;
  projectId?: string;
  projectName?: string;
  selectedCharacterId?: string;
  onSelectWorkspace: (tab: EditorTab) => void;
  onOpenCoDirector: () => void;
  onChooseCharacterForAvatar?: () => void;
};

function focusableItems(root: HTMLElement | null): HTMLElement[] {
  if (!root) return [];
  return Array.from(
    root.querySelectorAll<HTMLElement>(
      '[role="menuitem"]:not([disabled]), button.production-menu__featured-open:not([disabled])',
    ),
  );
}

export function ProductionMenu({
  open,
  onOpenChange,
  onHoverOpen,
  availability,
  projectId,
  projectName,
  selectedCharacterId,
  onSelectWorkspace,
  onOpenCoDirector,
  onChooseCharacterForAvatar,
}: Props) {
  const id = useId();
  const rootRef = useRef<HTMLDivElement>(null);
  const triggerRef = useRef<HTMLButtonElement>(null);
  const panelRef = useRef<HTMLDivElement>(null);
  const [recentTick, setRecentTick] = useState(0);

  const recent = useMemo(
    () => loadProductionRecent(projectId),
    [projectId, recentTick, open],
  );

  const menu = useMemo(
    () =>
      buildProductionMenu({
        availability,
        projectId,
        selectedCharacterId,
        recent,
      }),
    [availability, projectId, selectedCharacterId, recent],
  );

  const closeWithoutNavigate = useCallback(() => {
    onOpenChange(false, { restoreFocus: true });
  }, [onOpenChange]);

  const closeAfterNavigate = useCallback(() => {
    onOpenChange(false, { restoreFocus: false });
  }, [onOpenChange]);

  useEffect(() => {
    if (!open) return;
    setRecentTick((n) => n + 1);
    const onDoc = (e: MouseEvent) => {
      if (!rootRef.current?.contains(e.target as Node)) {
        closeWithoutNavigate();
      }
    };
    document.addEventListener("mousedown", onDoc);
    return () => document.removeEventListener("mousedown", onDoc);
  }, [open, closeWithoutNavigate]);

  useEffect(() => {
    if (!open) return;
    const items = focusableItems(panelRef.current);
    items[0]?.focus();
  }, [open]);

  const activateWorkspace = (tab: EditorTab, characterGate?: boolean) => {
    if (characterGate) {
      onChooseCharacterForAvatar?.();
      closeAfterNavigate();
      return;
    }
    onSelectWorkspace(tab);
    closeAfterNavigate();
  };

  const activateEntry = (entry: BuiltProductionMenuEntry) => {
    if (entry.action === "workspace" && entry.workspace) {
      activateWorkspace(entry.workspace, entry.characterMissing);
      return;
    }
    if (entry.action === "coDirectorAction") {
      runCoDirectorAction(entry.coDirectorAction);
    }
  };

  const runCoDirectorAction = (action?: CoDirectorQuickActionId) => {
    switch (action) {
      case "continueProject":
        activateWorkspace("home");
        break;
      case "reviewTimeline":
        activateWorkspace("timeline");
        break;
      case "generateAssets":
        activateWorkspace("imagegen");
        break;
      case "openChat":
      default:
        onOpenCoDirector();
        closeAfterNavigate();
        break;
    }
  };

  const activateRecent = (item: ProductionRecentItem) => {
    onSelectWorkspace(item.tab);
    closeAfterNavigate();
  };

  const onTriggerKeyDown = (e: ReactKeyboardEvent) => {
    if (e.key === "ArrowDown" || e.key === "Enter" || e.key === " ") {
      e.preventDefault();
      onOpenChange(true);
    } else if (e.key === "Escape" && open) {
      e.preventDefault();
      closeWithoutNavigate();
    }
  };

  const onPanelKeyDown = (e: ReactKeyboardEvent) => {
    if (e.key === "Escape") {
      e.preventDefault();
      e.stopPropagation();
      closeWithoutNavigate();
      return;
    }
    const items = focusableItems(panelRef.current);
    if (!items.length) return;
    const idx = items.indexOf(document.activeElement as HTMLElement);
    if (e.key === "ArrowDown") {
      e.preventDefault();
      items[(idx + 1 + items.length) % items.length]?.focus();
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      items[(idx - 1 + items.length) % items.length]?.focus();
    } else if (e.key === "Home") {
      e.preventDefault();
      items[0]?.focus();
    } else if (e.key === "End") {
      e.preventDefault();
      items[items.length - 1]?.focus();
    }
  };

  const byId = Object.fromEntries(menu.categories.map((c) => [c.id, c]));

  const renderEntry = (entry: BuiltProductionMenuEntry) => {
    const status = entry.availability?.status;
    const showBadge = status && status !== "Available";
    const badgeText = entry.characterMissing
      ? "Choose a character"
      : showBadge
        ? entry.availability?.reason || status
        : null;
    return (
      <button
        key={entry.id}
        type="button"
        role="menuitem"
        className="production-menu__item"
        data-testid={`production-item-${entry.id}`}
        data-workspace={entry.workspace || ""}
        onClick={() => activateEntry(entry)}
      >
        <span className="production-menu__item-main">
          <span className="production-menu__item-label-row">
            <span className="production-menu__item-label">{entry.label}</span>
            <HelpTip label={entry.helpLabel} content={entry.helpContent} />
          </span>
          <span className="production-menu__item-desc">{entry.description}</span>
          {badgeText ? (
            <span className="production-menu__badge" data-testid={`production-badge-${entry.id}`}>
              {badgeText}
            </span>
          ) : null}
        </span>
      </button>
    );
  };

  const renderCategory = (catId: ProductionCategoryId) => {
    const cat = byId[catId];
    if (!cat) return null;
    const headingId = `${id}-${catId}`;
    return (
      <section
        key={cat.id}
        className="production-menu__category"
        role="group"
        aria-labelledby={headingId}
        data-testid={`production-cat-${cat.id}`}
        data-category={cat.id}
      >
        <h3 id={headingId} className="production-menu__category-heading">
          {cat.label}
        </h3>
        <div className="production-menu__category-items">{cat.entries.map(renderEntry)}</div>
      </section>
    );
  };

  return (
    <div
      className="ds-menu-root production-menu-root"
      ref={rootRef}
      onMouseEnter={onHoverOpen}
      data-testid="production-menu-root"
    >
      <button
        ref={triggerRef}
        type="button"
        className="ds-menu-trigger"
        aria-haspopup="menu"
        aria-expanded={open}
        aria-controls={id}
        data-testid="chrome-production-menu-button"
        onClick={() => {
          if (open) closeWithoutNavigate();
          else onOpenChange(true);
        }}
        onKeyDown={onTriggerKeyDown}
      >
        <span>Production</span>
        <span className="ds-menu-trigger__chevron" aria-hidden>
          ▾
        </span>
      </button>
      {open ? (
        <div
          ref={panelRef}
          className="ds-menu-panel production-menu"
          role="menu"
          id={id}
          aria-label="Production"
          data-testid="production-menu"
          onKeyDown={onPanelKeyDown}
        >
          <section
            className="production-menu__featured-panel"
            data-testid="production-menu-codirector"
            aria-label="Co-Director"
          >
            <div className="production-menu__featured-head">
              <span className="production-menu__featured-mark" aria-hidden>
                ✦
              </span>
              <div>
                <div className="production-menu__featured-title">
                  {menu.coDirector.label}
                  <HelpTip label={menu.coDirector.helpLabel} content={menu.coDirector.helpContent} />
                </div>
                <div className="production-menu__featured-desc">{menu.coDirector.description}</div>
                {projectName ? (
                  <div className="production-menu__featured-project" data-testid="production-menu-project">
                    {projectName}
                  </div>
                ) : null}
              </div>
            </div>
            <div className="production-menu__featured-actions">
              {menu.coDirector.quickActions.map((action) => (
                <button
                  key={action.id}
                  type="button"
                  role="menuitem"
                  className="production-menu__featured-action"
                  data-testid={`production-cd-${action.coDirectorAction || action.id}`}
                  onClick={() => activateEntry(action)}
                >
                  {action.label}
                </button>
              ))}
              <button
                type="button"
                role="menuitem"
                className="production-menu__featured-open"
                data-testid="production-cd-open-full"
                onClick={() => {
                  onOpenCoDirector();
                  closeAfterNavigate();
                }}
              >
                Open Co-Director
              </button>
            </div>
          </section>

          <div className="production-menu__grid">
            {PRODUCTION_CATEGORY_ORDER.map(renderCategory)}
          </div>

          {menu.recent.length > 0 ? (
            <section
              className="production-menu__recent"
              role="group"
              aria-label="Recent"
              data-testid="production-menu-recent"
            >
              <h3 className="production-menu__category-heading">Recent</h3>
              <div className="production-menu__recent-items">
                {menu.recent.map((item) => (
                  <button
                    key={`${item.tab}-${item.projectId || ""}-${item.at}`}
                    type="button"
                    role="menuitem"
                    className="production-menu__recent-item"
                    data-testid={`production-recent-${item.tab}`}
                    onClick={() => activateRecent(item)}
                  >
                    <span className="production-menu__recent-label">{item.label}</span>
                    {item.projectName && item.projectId !== projectId ? (
                      <span className="production-menu__recent-meta">{item.projectName}</span>
                    ) : null}
                  </button>
                ))}
              </div>
            </section>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}

export function focusProductionTrigger() {
  document.querySelector<HTMLButtonElement>('[data-testid="chrome-production-menu-button"]')?.focus();
}
