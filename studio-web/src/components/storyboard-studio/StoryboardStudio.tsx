/**
 * M4.9 Professional Storyboard Studio — Library-driven production board.
 */
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { api } from "../../api";
import type { Project } from "../../types";
import type { EditorTab } from "../../workspacePrefs";
import type {
  ScriptLinkStatus,
  StoryboardDocument,
  StoryboardPageSize,
  StoryboardPanelLink,
  TimelinePrepProposal,
} from "../../contracts/storyboardStudio";
import { STORYBOARD_CAPTION_MAX } from "../../contracts/storyboardStudio";
import { SCRIPT_LINK_LABELS } from "../../contracts/scriptSync";
import {
  getAssetName,
  getCardPreviewUrl,
  isImageAsset,
  type LibraryAsset,
} from "../CoDirector/library/assetModel";
import "./storyboard-studio.css";

const PAGE_SIZES: StoryboardPageSize[] = [6, 9, 12];
const LIBRARY_ASSET_MIME = "application/x-adept-library-asset";

function syncClass(status: ScriptLinkStatus): string {
  return `sb-sync sb-sync-${status}`;
}

export function StoryboardStudio({
  project,
  onChange,
  onGo,
}: {
  project: Project;
  onChange: () => Promise<void>;
  onGo: (tab: EditorTab) => void;
}) {
  const [document, setDocument] = useState<StoryboardDocument | null>(null);
  const [panels, setPanels] = useState<StoryboardPanelLink[]>([]);
  const [pageIndex, setPageIndex] = useState(0);
  const [msg, setMsg] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [proposal, setProposal] = useState<TimelinePrepProposal | null>(null);
  const [timelinePayload, setTimelinePayload] = useState<Array<Record<string, unknown>> | null>(
    null
  );
  const [dragId, setDragId] = useState<string | null>(null);
  const [undoPanelId, setUndoPanelId] = useState<string | null>(null);
  const [selectedPanelId, setSelectedPanelId] = useState<string | null>(null);
  const [libraryOpen, setLibraryOpen] = useState(true);
  const [libraryQuery, setLibraryQuery] = useState("");
  const [libraryItems, setLibraryItems] = useState<LibraryAsset[]>([]);
  const [missingFamily, setMissingFamily] = useState<"qwen2512" | "imagen">("qwen2512");
  const captionTimers = useRef<Record<string, number>>({});

  const reload = useCallback(async () => {
    try {
      const res = await api.storyboardStudio.workspace(project.id);
      setDocument(res.document);
      setPanels(res.panels || []);
      if (res.document?.pages?.length && pageIndex >= res.document.pages.length) {
        setPageIndex(Math.max(0, res.document.pages.length - 1));
      }
    } catch (e: unknown) {
      setMsg(e instanceof Error ? e.message : String(e));
    }
  }, [project.id, pageIndex]);

  useEffect(() => {
    void reload();
  }, [reload]);

  const loadLibrary = useCallback(async () => {
    try {
      const res = await api.library(project.id, { q: libraryQuery.trim() || undefined });
      const items = (res.items || []).filter((item: LibraryAsset) => isImageAsset(item));
      setLibraryItems(items);
    } catch (e: unknown) {
      setMsg(e instanceof Error ? e.message : String(e));
    }
  }, [project.id, libraryQuery]);

  useEffect(() => {
    if (!libraryOpen) return;
    void loadLibrary();
  }, [libraryOpen, loadLibrary]);

  const pageSize = (document?.pageSize || 9) as StoryboardPageSize;
  const pages = document?.pages?.length
    ? document.pages
    : [{ pageIndex: 0, pageSize, panelIds: [], title: "Page 1" }];
  const page = pages[Math.min(pageIndex, pages.length - 1)] || pages[0];
  const pagePanels = (page?.panelIds || [])
    .map((id) => panels.find((p) => p.panelId === id))
    .filter(Boolean) as StoryboardPanelLink[];
  const slots: Array<StoryboardPanelLink | null> = [...pagePanels];
  while (slots.length < pageSize) slots.push(null);
  const emptyCount = slots.filter((p) => !p?.assetId).length;
  const pageFilled = slots.every((p) => !!p?.assetId);

  const nextEmptyPanel = useMemo(() => {
    if (selectedPanelId) {
      const selected = panels.find((p) => p.panelId === selectedPanelId);
      if (selected && !selected.assetId) return selected;
    }
    return pagePanels.find((p) => !p.assetId) || panels.find((p) => !p.assetId) || null;
  }, [selectedPanelId, panels, pagePanels]);

  const setPageSize = async (size: StoryboardPageSize) => {
    if (!document) return;
    setBusy(true);
    try {
      const res = await api.storyboardStudio.setPageSize(project.id, document.id, size);
      setDocument(res.document);
      await reload();
    } catch (e: unknown) {
      setMsg(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  };

  const onDropReorder = async (targetPanelId: string | null, slotIndex: number) => {
    if (!document || !dragId) return;
    const order = [...(document.panelOrder || panels.map((p) => p.panelId))];
    const from = order.indexOf(dragId);
    if (from < 0) return;
    order.splice(from, 1);
    let to = pageIndex * pageSize + slotIndex;
    if (targetPanelId) {
      const t = order.indexOf(targetPanelId);
      to = t >= 0 ? t : to;
    }
    to = Math.max(0, Math.min(order.length, to));
    order.splice(to, 0, dragId);
    setDragId(null);
    try {
      const res = await api.storyboardStudio.reorder(project.id, document.id, order);
      setDocument(res.document);
      await reload();
    } catch (e: unknown) {
      setMsg(e instanceof Error ? e.message : String(e));
    }
  };

  const assignAsset = async (assetId: string, panelId?: string | null) => {
    const target = panelId
      ? panels.find((p) => p.panelId === panelId)
      : nextEmptyPanel;
    if (!target) {
      setMsg("No empty panel to place this image. Select a slot or add a page.");
      return;
    }
    try {
      await api.storyboardStudio.assignPanel(project.id, target.panelId, assetId);
      setSelectedPanelId(target.panelId);
      setMsg("Image placed on the board. The Library copy stays in the Library.");
      await reload();
    } catch (e: unknown) {
      setMsg(e instanceof Error ? e.message : String(e));
    }
  };

  const saveCaption = (panelId: string, label: string) => {
    window.clearTimeout(captionTimers.current[panelId]);
    captionTimers.current[panelId] = window.setTimeout(() => {
      void api.storyboardStudio
        .patchPanel(project.id, panelId, { label: label.slice(0, STORYBOARD_CAPTION_MAX) })
        .catch((e: unknown) => setMsg(e instanceof Error ? e.message : String(e)));
    }, 400);
  };

  const prepareTimeline = async (panelIds?: string[]) => {
    setBusy(true);
    setMsg(null);
    setTimelinePayload(null);
    try {
      const res = await api.storyboardStudio.prepareTimeline(project.id, {
        documentId: document?.id,
        panelIds,
        approvedOnly: false,
      });
      setProposal(res.proposal);
      setMsg("Timeline prep ready — captions stay as shot labels, not spoken lines.");
    } catch (e: unknown) {
      setMsg(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  };

  const confirmProposal = async () => {
    if (!proposal) return;
    setBusy(true);
    try {
      const res = await api.storyboardStudio.confirmTimelineProposal(project.id, proposal.id, {
        panelIds: selectedPanelId ? [selectedPanelId] : undefined,
      });
      setProposal(res.proposal as unknown as TimelinePrepProposal);
      setTimelinePayload(res.timelinePayload || []);
      setMsg(`Proposal confirmed — ${res.createdSceneIds.length} Timeline scene(s). No clips generated.`);
      await onChange();
    } catch (e: unknown) {
      setMsg(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  };

  const openInImageGen = (panel: StoryboardPanelLink, mode: "open" | "replace" = "open") => {
    try {
      sessionStorage.setItem(
        "adept_cis_seed",
        JSON.stringify({
          prompt: panel.prompt,
          panelId: mode === "replace" ? panel.panelId : undefined,
          continuitySessionId: panel.continuitySessionId,
          assetId: panel.assetId || undefined,
        })
      );
    } catch {
      /* ignore */
    }
    onGo("imagegen");
  };

  const undoReplace = async (panelId: string) => {
    try {
      await api.storyboardStudio.undoReplacePanel(project.id, panelId);
      setUndoPanelId(null);
      setMsg("Panel replace undone.");
      await reload();
    } catch (e: unknown) {
      setMsg(e instanceof Error ? e.message : String(e));
    }
  };

  const clearPanel = async (panelId: string) => {
    try {
      await api.storyboardStudio.clearPanel(project.id, panelId);
      setMsg("Removed from the board. The Library image is unchanged.");
      await reload();
    } catch (e: unknown) {
      setMsg(e instanceof Error ? e.message : String(e));
    }
  };

  const generateMissing = async () => {
    setBusy(true);
    try {
      const res = await api.storyboardStudio.generateMissing(project.id, {
        family: missingFamily,
        documentId: document?.id,
        pageIndex,
      });
      setMsg(res.message || "Generate Missing Panels finished.");
      await reload();
    } catch (e: unknown) {
      setMsg(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  };

  const compose2k = async () => {
    if (!pageFilled) {
      setMsg("Fill every slot on this page before generating the 2K storyboard.");
      return;
    }
    setBusy(true);
    try {
      const res = await api.storyboardStudio.compose2k(project.id, {
        documentId: document?.id,
        pageIndex,
      });
      setMsg(`2K storyboard saved to the Library (${res.width}×${res.height}).`);
      await onChange();
      await loadLibrary();
    } catch (e: unknown) {
      setMsg(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  };

  const openScriptwriter = (panel?: StoryboardPanelLink | null) => {
    try {
      if (panel?.scriptwriterSceneId) {
        sessionStorage.setItem("adept_scriptwriter_scene", panel.scriptwriterSceneId);
      }
    } catch {
      /* ignore */
    }
    onGo("scriptwriter");
  };

  const onSlotDrop = async (
    event: import("react").DragEvent,
    panel: StoryboardPanelLink | null,
    slotIndex: number
  ) => {
    event.preventDefault();
    const libraryAssetId = event.dataTransfer.getData(LIBRARY_ASSET_MIME);
    if (libraryAssetId) {
      if (panel) {
        await assignAsset(libraryAssetId, panel.panelId);
      } else {
        setMsg("This empty slot is not ready yet. Refresh, then try again.");
      }
      return;
    }
    await onDropReorder(panel?.panelId || null, slotIndex);
  };

  return (
    <div className="page storyboard-studio">
      <header className="sb-header">
        <div>
          <h1>Storyboard Studio</h1>
          <p className="muted">Assemble production frames from the Library. AI creates the art; Adept builds the board.</p>
        </div>
        <div className="sb-header-actions">
          <button type="button" onClick={() => onGo("imagegen")}>
            Image Generator
          </button>
          <button type="button" onClick={() => openScriptwriter(selectedPanelId ? panels.find((p) => p.panelId === selectedPanelId) : null)}>
            Scriptwriter
          </button>
          <button
            type="button"
            className={libraryOpen ? "primary" : undefined}
            data-testid="sb-library-toggle"
            onClick={() => setLibraryOpen((open) => !open)}
          >
            {libraryOpen ? "Hide Library" : "Library"}
          </button>
          <button
            type="button"
            className="primary"
            disabled={busy}
            data-testid="sb-prepare-timeline"
            onClick={() =>
              void prepareTimeline(selectedPanelId ? [selectedPanelId] : undefined)
            }
          >
            Prepare for Timeline
          </button>
          <a
            className="button"
            href={api.storyboardStudio.exportPdfUrl(project.id, document?.id)}
            target="_blank"
            rel="noreferrer"
          >
            Export PDF
          </a>
          <a
            className="button"
            href={`/api/storyboard-studio/projects/${project.id}/export.json`}
            target="_blank"
            rel="noreferrer"
            data-testid="sb-export-json"
          >
            Export JSON
          </a>
          <a
            className="button"
            href={`/api/storyboard-studio/projects/${project.id}/export/contact-sheet`}
            target="_blank"
            rel="noreferrer"
          >
            Contact sheet
          </a>
        </div>
      </header>

      {msg && <p className="pill warn" data-testid="sb-message">{msg}</p>}

      <div className="sb-toolbar">
        <div className="sb-page-sizes" role="group" aria-label="Panels per page">
          {PAGE_SIZES.map((size) => (
            <button
              key={size}
              type="button"
              className={pageSize === size ? "primary" : undefined}
              disabled={busy}
              onClick={() => void setPageSize(size)}
            >
              {size}
            </button>
          ))}
        </div>
        <div className="sb-page-nav">
          <button
            type="button"
            disabled={pageIndex <= 0}
            onClick={() => setPageIndex((i) => Math.max(0, i - 1))}
          >
            Prev
          </button>
          <span>
            Page {pageIndex + 1} / {Math.max(1, pages.length)}
          </span>
          <button
            type="button"
            disabled={pageIndex >= pages.length - 1}
            onClick={() => setPageIndex((i) => Math.min(pages.length - 1, i + 1))}
          >
            Next
          </button>
        </div>
        <label className="sb-missing-family">
          Missing panels
          <select
            value={missingFamily}
            onChange={(e) => setMissingFamily(e.target.value as "qwen2512" | "imagen")}
            data-testid="sb-missing-family"
          >
            <option value="qwen2512">Qwen</option>
            <option value="imagen">GPT Image 2</option>
          </select>
        </label>
        <button
          type="button"
          disabled={busy || emptyCount === 0}
          data-testid="sb-generate-missing"
          onClick={() => void generateMissing()}
        >
          Generate Missing Panels
        </button>
        <button
          type="button"
          className="primary"
          disabled={busy || !pageFilled}
          data-testid="sb-compose-2k"
          title={pageFilled ? "Assemble this page into a 2K storyboard image" : "Fill every slot on this page first"}
          onClick={() => void compose2k()}
        >
          Generate 2K Storyboard
        </button>
        <button type="button" onClick={() => void reload()}>
          Refresh
        </button>
        {undoPanelId && (
          <button type="button" onClick={() => void undoReplace(undoPanelId)}>
            Undo replace
          </button>
        )}
      </div>

      <div className={`sb-workspace ${libraryOpen ? "sb-workspace--library" : ""}`}>
        <div className={`sb-grid sb-grid-${pageSize}`} onDragOver={(e) => e.preventDefault()} data-testid="sb-grid">
          {slots.map((panel, idx) => (
            <div
              key={panel?.panelId || `empty-${idx}`}
              className={`sb-slot ${panel ? "" : "empty"} ${
                selectedPanelId && panel?.panelId === selectedPanelId ? "selected" : ""
              }`}
              draggable={!!panel}
              data-testid={`sb-slot-${idx}`}
              onClick={() => panel && setSelectedPanelId(panel.panelId)}
              onDragStart={() => panel && setDragId(panel.panelId)}
              onDragOver={(e) => e.preventDefault()}
              onDrop={(e) => void onSlotDrop(e, panel, idx)}
            >
              {panel?.assetId ? (
                <img src={api.assetUrl(panel.assetId)} alt={panel.label || ""} loading="lazy" />
              ) : (
                <div className="sb-slot-empty">{panel ? "Drop a Library image" : "Empty"}</div>
              )}
              {panel && (
                <div className="sb-slot-meta">
                  <label className="sb-caption">
                    <span className="sb-caption-count">
                      {(panel.label || "").length} / {STORYBOARD_CAPTION_MAX}
                    </span>
                    <textarea
                      data-testid={`sb-caption-${idx}`}
                      maxLength={STORYBOARD_CAPTION_MAX}
                      value={panel.label || ""}
                      placeholder="Caption (production note, not dialogue)"
                      onChange={(e) => {
                        const next = e.target.value.slice(0, STORYBOARD_CAPTION_MAX);
                        setPanels((current) =>
                          current.map((p) => (p.panelId === panel.panelId ? { ...p, label: next } : p))
                        );
                        saveCaption(panel.panelId, next);
                      }}
                      onClick={(e) => e.stopPropagation()}
                    />
                  </label>
                  <button
                    type="button"
                    className={syncClass(panel.scriptLinkStatus)}
                    onClick={(e) => {
                      e.stopPropagation();
                      openScriptwriter(panel);
                    }}
                    title="Open Scriptwriter linkage"
                  >
                    {SCRIPT_LINK_LABELS[panel.scriptLinkStatus]}
                  </button>
                  <div className="sb-slot-actions">
                    <button type="button" onClick={() => openInImageGen(panel, "open")}>
                      Generate Panel
                    </button>
                    <button
                      type="button"
                      onClick={() => {
                        setUndoPanelId(panel.panelId);
                        openInImageGen(panel, "replace");
                      }}
                    >
                      Replace
                    </button>
                    <button type="button" onClick={() => void clearPanel(panel.panelId)}>
                      Remove
                    </button>
                  </div>
                </div>
              )}
            </div>
          ))}
        </div>

        {libraryOpen && (
          <aside className="sb-library" data-testid="sb-library-pane">
            <h2>Library</h2>
            <p className="muted tiny">Click or drag an image onto a slot. Files stay in the Library.</p>
            <input
              type="search"
              placeholder="Search images"
              value={libraryQuery}
              data-testid="sb-library-search"
              onChange={(e) => setLibraryQuery(e.target.value)}
            />
            <div className="sb-library-grid">
              {libraryItems.map((asset) => {
                const preview = getCardPreviewUrl(asset);
                return (
                  <button
                    key={asset.id}
                    type="button"
                    className="sb-library-card"
                    draggable
                    data-testid={`sb-library-asset-${asset.id}`}
                    title={getAssetName(asset)}
                    onClick={() => void assignAsset(asset.id)}
                    onDragStart={(e) => {
                      e.dataTransfer.setData(LIBRARY_ASSET_MIME, asset.id);
                      e.dataTransfer.effectAllowed = "copy";
                    }}
                  >
                    {preview ? <img src={preview} alt="" /> : <span>Image</span>}
                    <span>{getAssetName(asset)}</span>
                  </button>
                );
              })}
              {!libraryItems.length && <p className="muted">No images in this Library yet.</p>}
            </div>
          </aside>
        )}
      </div>

      {proposal && (
        <section className="sb-proposal card-panel">
          <h2>Timeline prep proposal</h2>
          <p className="muted">{proposal.note}</p>
          <ul data-testid="sb-timeline-shots">
            {proposal.shots.map((s) => (
              <li key={s.panelId}>
                <strong>{s.label}</strong> · {s.durationEst}s · {s.cameraNote || "—"}
                {s.dialogue ? ` — spoken: “${s.dialogue.slice(0, 80)}”` : " — no spoken line"}
              </li>
            ))}
          </ul>
          <p className="muted tiny">
            Status: {proposal.status} · id {proposal.id.slice(0, 8)}
          </p>
          {proposal.status !== "applied" && (
            <button type="button" className="primary" disabled={busy} onClick={() => void confirmProposal()}>
              Confirm Proposal
            </button>
          )}
          {timelinePayload && (
            <div className="sb-timeline-payload">
              <h3>Timeline payload</h3>
              <pre>{JSON.stringify(timelinePayload, null, 2)}</pre>
            </div>
          )}
        </section>
      )}
    </div>
  );
}
