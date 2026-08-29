import { useEffect, useMemo, useState } from "react";
import { createPortal } from "react-dom";
import { useTranslation } from "react-i18next";
import { api } from "../../api";
import type { Asset, Project } from "../../types";
import { isTimelineMediaAsset } from "../../timelineMediaTypes";

export function AddFromProjectLibraryModal({
  project,
  alreadyIds,
  onAdd,
  onClose,
}: {
  project: Project;
  alreadyIds: string[];
  onAdd: (assetIds: string[]) => void;
  onClose: () => void;
}) {
  const { t } = useTranslation(["timeline", "library", "common"]);
  const [items, setItems] = useState<Asset[]>([]);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [search, setSearch] = useState("");
  const [filter, setFilter] = useState<"all" | "image" | "audio" | "video">("all");

  useEffect(() => {
    let alive = true;
    void api.library(project.id, { scope: "project" }).then((payload) => {
      if (!alive) return;
      const rows = ((payload.items || []) as Asset[]).filter((item) => isTimelineMediaAsset(item));
      setItems(rows);
    }).catch(() => {
      if (alive) setItems(project.assets.filter((item) => isTimelineMediaAsset(item)));
    });
    return () => {
      alive = false;
    };
  }, [project.assets, project.id]);

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        event.preventDefault();
        event.stopPropagation();
        onClose();
      }
    };
    window.addEventListener("keydown", onKey, true);
    return () => window.removeEventListener("keydown", onKey, true);
  }, [onClose]);

  const already = useMemo(() => new Set(alreadyIds), [alreadyIds]);
  const visible = items.filter((item) => {
    if (filter !== "all" && item.kind !== filter) return false;
    const q = search.trim().toLowerCase();
    if (!q) return true;
    return (item.tag || "").toLowerCase().includes(q) || (item.filename || "").toLowerCase().includes(q);
  });

  const toggle = (id: string, additive: boolean) => {
    if (already.has(id)) return;
    setSelected((curr) => {
      const next = additive ? new Set(curr) : new Set(curr);
      if (!additive && !curr.has(id)) {
        // click toggle stays multi; Ctrl/Cmd is also additive
      }
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const commit = () => {
    const ids = [...selected].filter((id) => !already.has(id));
    if (ids.length) onAdd(ids);
    onClose();
  };

  return createPortal(
    <div className="timeline-library-modal" role="presentation">
      <button
        type="button"
        className="timeline-library-modal__backdrop"
        aria-label={t("common:cancel", { defaultValue: "Cancel" })}
        data-testid="timeline-add-from-project-library-backdrop"
        onClick={onClose}
      />
      <div
        className="timeline-library-modal__panel"
        role="dialog"
        aria-modal="true"
        aria-labelledby="timeline-add-from-project-library-title"
        data-testid="timeline-add-from-project-library"
      >
        <header className="timeline-library-modal__header">
          <h2 id="timeline-add-from-project-library-title">{t("addFromProjectLibrary")}</h2>
          <button
            type="button"
            className="ghost"
            data-testid="timeline-add-from-project-library-close"
            aria-label={t("common:close", { defaultValue: "Close" })}
            onClick={onClose}
          >
            X
          </button>
        </header>
        <div className="timeline-library-modal__tools">
          {(["all", "image", "audio", "video"] as const).map((kind) => (
            <button
              key={kind}
              type="button"
              className={filter === kind ? "primary" : "ghost"}
              onClick={() => setFilter(kind)}
            >
              {kind}
            </button>
          ))}
          <input
            data-testid="timeline-add-from-project-library-search"
            placeholder={t("searchLibrary")}
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </div>
        <div className="timeline-library-modal__grid" data-testid="timeline-add-from-project-library-grid">
          {visible.length === 0 ? <p className="empty">No assets match filters.</p> : null}
          {visible.map((item) => {
            const staged = already.has(item.id);
            const on = staged || selected.has(item.id);
            return (
              <button
                key={item.id}
                type="button"
                className={`library-card${on ? " selected is-library-selected" : ""} is-selectable`}
                data-testid={`library-card-${item.id}`}
                aria-pressed={on}
                disabled={staged}
                onClick={(e) => toggle(item.id, e.metaKey || e.ctrlKey || true)}
              >
                {item.kind === "image" ? (
                  <img src={api.assetUrl(item.id)} alt={item.filename} loading="lazy" />
                ) : (
                  <div className="library-card-fallback">{item.kind}</div>
                )}
                <span>{item.tag || item.filename}</span>
              </button>
            );
          })}
        </div>
        <footer className="timeline-library-modal__footer">
          <button type="button" data-testid="timeline-add-from-project-library-cancel" onClick={onClose}>
            {t("common:cancel", { defaultValue: "Cancel" })}
          </button>
          <button
            type="button"
            className="primary"
            data-testid="timeline-add-from-project-library-add"
            disabled={selected.size === 0}
            onClick={commit}
          >
            {t("libraryAdd")}
          </button>
        </footer>
      </div>
    </div>,
    document.body,
  );
}
