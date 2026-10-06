import { useEffect, useMemo, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { useTranslation } from "react-i18next";
import { api } from "../../api";
import type { Asset, Project } from "../../types";
import { isTimelineMediaAsset } from "../../timelineMediaTypes";
import { inferLibraryUploadKind, libraryUploadTag } from "../library/libraryUpload";

async function loadProjectLibraryMedia(projectId: string): Promise<Asset[]> {
  const collected: Asset[] = [];
  const pageSize = 200;
  let offset = 0;
  let total = Number.POSITIVE_INFINITY;
  while (offset < total && offset < 2000) {
    const payload = await api.library(projectId, { scope: "project", limit: pageSize, offset });
    const rows = (payload.items || []) as Asset[];
    collected.push(...rows);
    total = Number(payload.totalMatches ?? collected.length);
    if (!rows.length) break;
    offset += pageSize;
  }
  return collected.filter((item) => isTimelineMediaAsset(item));
}

export function AddFromProjectLibraryModal({
  project,
  alreadyIds,
  onAdd,
  onClose,
  onAssetsChanged,
  mediaKind = "all",
  single = false,
  confirmLabel,
}: {
  project: Project;
  alreadyIds: string[];
  onAdd: (assetIds: string[]) => void;
  onClose: () => void;
  onAssetsChanged?: () => void;
  mediaKind?: "all" | "video" | "audio";
  single?: boolean;
  confirmLabel?: string;
}) {
  const { t } = useTranslation(["timeline", "library", "common"]);
  const [items, setItems] = useState<Asset[]>([]);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [search, setSearch] = useState("");
  const [filter, setFilter] = useState<"all" | "image" | "audio" | "video">(
    mediaKind === "video" ? "video" : mediaKind === "audio" ? "audio" : "all",
  );
  const [uploading, setUploading] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const addMediaRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    let alive = true;
    void loadProjectLibraryMedia(project.id)
      .then((rows) => {
        if (!alive) return;
        setItems(rows);
      })
      .catch(() => {
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
    if (single) {
      setSelected(new Set([id]));
      return;
    }
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

  const reloadLibrary = async () => {
    const rows = await loadProjectLibraryMedia(project.id);
    setItems(rows);
  };

  const uploadFiles = async (files: FileList | null) => {
    if (!files?.length) return;
    setUploading(true);
    setUploadError(null);
    const addedIds: string[] = [];
    try {
      for (const file of Array.from(files)) {
        const kind = inferLibraryUploadKind(file);
        if (mediaKind === "video" && kind !== "video") {
          setUploadError("Choose a video.");
          continue;
        }
        if (mediaKind === "audio" && kind !== "audio") {
          setUploadError("Choose an audio file.");
          continue;
        }
        if (kind === "document") {
          setUploadError(t("library:addMediaTimelineOnly"));
          continue;
        }
        const asset = await api.uploadAsset(project.id, file, libraryUploadTag(file), kind);
        if (asset?.id) addedIds.push(asset.id);
      }
      if (addedIds.length) {
        await reloadLibrary();
        setSelected((curr) => {
          const next = new Set(curr);
          for (const id of addedIds) next.add(id);
          return next;
        });
        onAssetsChanged?.();
      }
    } catch (err) {
      setUploadError(err instanceof Error ? err.message : t("library:addMediaFailed"));
    } finally {
      setUploading(false);
      if (addMediaRef.current) addMediaRef.current.value = "";
    }
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
        data-media-kind={mediaKind}
      >
        <header className="timeline-library-modal__header">
          <h2 id="timeline-add-from-project-library-title">{t("addFromProjectLibrary")}</h2>
          <div className="timeline-library-modal__header-actions">
            <button
              type="button"
              className="primary"
              data-testid="timeline-add-from-project-library-add-top"
              disabled={selected.size === 0}
              onClick={commit}
            >
              {confirmLabel || t("libraryAdd")}
            </button>
            <button
              type="button"
              className="ghost"
              data-testid="timeline-add-from-project-library-close"
              aria-label={t("common:close", { defaultValue: "Close" })}
              onClick={onClose}
            >
              X
            </button>
          </div>
        </header>
        <div className="timeline-library-modal__tools">
          <input
            ref={addMediaRef}
            type="file"
            hidden
            multiple
            accept={
              mediaKind === "video" ? "video/*" : mediaKind === "audio" ? "audio/*" : "image/*,video/*,audio/*"
            }
            data-testid="timeline-library-add-media-input"
            onChange={(event) => void uploadFiles(event.target.files)}
          />
          <button
            type="button"
            className="primary"
            data-testid="timeline-library-add-media"
            disabled={uploading}
            onClick={() => addMediaRef.current?.click()}
          >
            {uploading ? t("addingMedia") : t("addMedia")}
          </button>
          {mediaKind === "video" || mediaKind === "audio"
            ? null
            : (["all", "image", "audio", "video"] as const).map((kind) => (
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
        {uploadError ? (
          <p className="timeline-library-modal__error" data-testid="timeline-library-add-media-error" role="alert">
            {uploadError}
          </p>
        ) : null}
        <div className="timeline-library-modal__grid" data-testid="timeline-add-from-project-library-grid">
          {visible.length === 0 ? <p className="empty">No assets match filters.</p> : null}
          {visible.map((item) => {
            const staged = already.has(item.id);
            const on = staged || selected.has(item.id);
            if (item.kind === "audio") {
              // Audio cards carry an inline preview player, so the card itself
              // is a div with button semantics — a nested <audio> inside a
              // <button> is invalid HTML and would toggle selection on play.
              return (
                <div
                  key={item.id}
                  role="button"
                  tabIndex={staged ? -1 : 0}
                  className={`library-card library-card--audio${on ? " selected is-library-selected" : ""} is-selectable`}
                  data-testid={`library-card-${item.id}`}
                  aria-pressed={on}
                  aria-disabled={staged}
                  onClick={(e) => {
                    if (staged) return;
                    toggle(item.id, e.metaKey || e.ctrlKey || true);
                  }}
                  onKeyDown={(e) => {
                    if (staged) return;
                    if (e.key === "Enter" || e.key === " ") {
                      e.preventDefault();
                      toggle(item.id, true);
                    }
                  }}
                >
                  <span>{item.tag || item.filename}</span>
                  <audio
                    controls
                    preload="metadata"
                    src={api.assetUrl(item.id, null, project.id)}
                    data-testid={`library-card-audio-${item.id}`}
                    onClick={(e) => e.stopPropagation()}
                    onKeyDown={(e) => e.stopPropagation()}
                  />
                </div>
              );
            }
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
                  <img src={api.assetUrl(item.id, null, project.id)} alt={item.filename} loading="lazy" />
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
            {confirmLabel || t("libraryAdd")}
          </button>
        </footer>
      </div>
    </div>,
    document.body,
  );
}
