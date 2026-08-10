/**
 * M4.9 Professional Storyboard Studio — page sheets (6|9|12) over storyboard_panels.
 */
import { useCallback, useEffect, useState } from "react";
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
import { SCRIPT_LINK_LABELS } from "../../contracts/scriptSync";
import "./storyboard-studio.css";

const PAGE_SIZES: StoryboardPageSize[] = [6, 9, 12];

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
      setMsg("Timeline prep proposal ready — review, then Confirm Proposal.");
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

  return (
    <div className="page storyboard-studio">
      <header className="sb-header">
        <div>
          <h1>Storyboard Studio</h1>
          <p className="muted">Page sheets for production sequences — default 9 panels per page.</p>
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
            className="primary"
            disabled={busy}
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

      {msg && <p className="pill warn">{msg}</p>}

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
        <button type="button" onClick={() => void reload()}>
          Refresh
        </button>
        {undoPanelId && (
          <button type="button" onClick={() => void undoReplace(undoPanelId)}>
            Undo replace
          </button>
        )}
      </div>

      <div className={`sb-grid sb-grid-${pageSize}`} onDragOver={(e) => e.preventDefault()}>
        {slots.map((panel, idx) => (
          <div
            key={panel?.panelId || `empty-${idx}`}
            className={`sb-slot ${panel ? "" : "empty"} ${
              selectedPanelId && panel?.panelId === selectedPanelId ? "selected" : ""
            }`}
            draggable={!!panel}
            onClick={() => panel && setSelectedPanelId(panel.panelId)}
            onDragStart={() => panel && setDragId(panel.panelId)}
            onDrop={() => void onDropReorder(panel?.panelId || null, idx)}
          >
            {panel?.assetId ? (
              <img src={api.assetUrl(panel.assetId)} alt={panel.label || ""} loading="lazy" />
            ) : (
              <div className="sb-slot-empty">{panel ? panel.status : "Empty"}</div>
            )}
            {panel && (
              <div className="sb-slot-meta">
                <div className="sb-slot-title">{panel.label || `Slot ${idx + 1}`}</div>
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
                    Open in Image Generator
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
                  <button
                    type="button"
                    onClick={() => void prepareTimeline([panel.panelId])}
                  >
                    Prep Timeline
                  </button>
                </div>
              </div>
            )}
          </div>
        ))}
      </div>

      {proposal && (
        <section className="sb-proposal card-panel">
          <h2>Timeline prep proposal</h2>
          <p className="muted">{proposal.note}</p>
          <ul>
            {proposal.shots.map((s) => (
              <li key={s.panelId}>
                <strong>{s.label}</strong> · {s.durationEst}s · {s.cameraNote || "—"}
                {s.dialogue ? ` — “${s.dialogue.slice(0, 80)}”` : ""}
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
