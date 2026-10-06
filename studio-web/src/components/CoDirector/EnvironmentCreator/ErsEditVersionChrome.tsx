/**
 * Minimal ERS edit Version handoff chrome.
 * Locked contract:
 *   POST .../sheets/{sheetId}/versions  { derivativeAssetId, editPrompt? } → draft ERS vN
 *   POST .../versions/{versionSheetId}/approve → creator Approve only (no auto-approve)
 * View / Compare / Revert / Approve labels align with Version Bot terms.
 */
import { useCallback, useEffect, useState } from "react";
import { ApiError, api } from "../../../api";

type Props = {
  projectId: string;
  sheetId: string;
  sourceAssetId: string;
  derivativeAssetId: string;
  editPrompt?: string;
  /** Select a lineage draft for display (NO Approve). */
  onSelectVersion?: (info: { versionSheetId: string; compositeAssetId?: string | null }) => void;
};

type VersionRow = {
  versionSheetId?: string;
  sheetId?: string;
  parentSheetId?: string;
  status?: string;
  derivativeAssetId?: string;
  versionNumber?: number;
};

export function ErsEditVersionChrome({
  projectId,
  sheetId,
  sourceAssetId,
  derivativeAssetId,
  editPrompt,
  onSelectVersion,
}: Props) {
  const [busy, setBusy] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [gap, setGap] = useState<string | null>(null);
  const [compareMode, setCompareMode] = useState(false);
  const [versionSheetId, setVersionSheetId] = useState<string | null>(null);
  const [versions, setVersions] = useState<VersionRow[]>([]);
  const [approved, setApproved] = useState(false);

  const refreshVersions = useCallback(async () => {
    try {
      const res = await api.environmentReferenceSheet.listVersions(projectId, sheetId);
      setVersions(Array.isArray(res.versions) ? (res.versions as VersionRow[]) : []);
    } catch (err) {
      if (err instanceof ApiError && err.status === 404) {
        setGap("listVersions 404 — Version list API not ready yet.");
      }
    }
  }, [projectId, sheetId]);

  useEffect(() => {
    void refreshVersions();
  }, [refreshVersions]);

  /** Create draft ERS vN from derivative (does not overwrite parent, does not approve). */
  const ensureDraftVersion = useCallback(async (): Promise<string> => {
    if (versionSheetId) return versionSheetId;
    const created = await api.environmentReferenceSheet.createVersion(projectId, sheetId, {
      derivativeAssetId,
      editPrompt: editPrompt || undefined,
    });
    const id = String(created.versionSheetId || created.sheetId || "").trim();
    if (!id) throw new Error("createVersion returned no versionSheetId.");
    setVersionSheetId(id);
    await refreshVersions();
    return id;
  }, [derivativeAssetId, editPrompt, projectId, refreshVersions, sheetId, versionSheetId]);

  const run = useCallback(
    async (action: "view" | "compare" | "revert" | "approve" | "create_draft") => {
      setBusy(action);
      setMessage(null);
      try {
        if (action === "view") {
          window.open(api.assetUrl(derivativeAssetId), "_blank", "noopener,noreferrer");
          setMessage("Opened derivative (View). Draft/Approve still required to promote vN.");
          return;
        }
        if (action === "compare") {
          setCompareMode((v) => !v);
          setMessage(compareMode ? "Compare closed." : "Compare: parent composite (left) vs derivative (right).");
          return;
        }
        if (action === "create_draft") {
          const id = await ensureDraftVersion();
          setMessage(`Draft ERS version created (${id.slice(0, 8)}…) — not approved.`);
          return;
        }
        if (action === "revert") {
          // Revert = select prior parent / non-derivative view; Version Bot owns restore persistence.
          setCompareMode(false);
          setMessage(
            "Revert: showing parent composite. Persistence restore is owned by Version Bot — parent sheet was not overwritten.",
          );
          return;
        }
        // approve — creator gate only
        try {
          const id = await ensureDraftVersion();
          await api.environmentReferenceSheet.approveVersion(projectId, sheetId, id);
          setApproved(true);
          setMessage(`Approved version ${id.slice(0, 8)}… — creator Approve promotes vN (parent preserved).`);
          await refreshVersions();
        } catch (err) {
          if (err instanceof ApiError && err.status === 404) {
            setGap(
              "Version create/approve route 404 — Backend/Version Bot not landed yet. Derivative retained; no auto-approve.",
            );
            setMessage(
              "Version Approve API not available (HTTP 404). Derivative kept for handoff — not auto-approved.",
            );
          } else {
            throw err;
          }
        }
      } catch (err) {
        const detail = err instanceof Error ? err.message : String(err);
        setMessage(detail);
        if (err instanceof ApiError && err.status === 404) {
          setGap("ERS Version API 404 — stub gap recorded.");
        }
      } finally {
        setBusy(null);
      }
    },
    [compareMode, derivativeAssetId, ensureDraftVersion, projectId, refreshVersions, sheetId],
  );

  return (
    <div
      className="ers-edit-version-chrome"
      data-testid="ers-edit-version-chrome"
      style={{
        marginTop: "0.75rem",
        padding: "0.65rem 0.75rem",
        border: "1px dashed var(--border, #2c3346)",
        borderRadius: "0.5rem",
      }}
    >
      <p style={{ margin: "0 0 0.45rem", fontWeight: 600 }}>Version handoff</p>
      <p className="muted" style={{ margin: "0 0 0.55rem" }}>
        Derivative only until creator Approve. createVersion → draft vN; approveVersion → promote. Never auto-approved.
        {versionSheetId ? ` Draft: ${versionSheetId.slice(0, 8)}…` : ""}
        {approved ? " · Approved" : ""}
      </p>
      <div style={{ display: "flex", flexWrap: "wrap", gap: "0.35rem" }}>
        <button
          type="button"
          className="secondary"
          data-testid="ers-edit-version-view"
          disabled={busy !== null}
          onClick={() => void run("view")}
        >
          View
        </button>
        <button
          type="button"
          className="secondary"
          data-testid="ers-edit-version-compare"
          disabled={busy !== null}
          aria-pressed={compareMode}
          onClick={() => void run("compare")}
        >
          Compare
        </button>
        <button
          type="button"
          className="ghost"
          data-testid="ers-edit-version-revert"
          disabled={busy !== null}
          onClick={() => void run("revert")}
        >
          Revert
        </button>
        <button
          type="button"
          className="secondary"
          data-testid="ers-edit-version-create-draft"
          disabled={busy !== null || Boolean(versionSheetId)}
          onClick={() => void run("create_draft")}
          title="POST .../versions { derivativeAssetId } — draft only"
        >
          {versionSheetId ? "Draft created" : "Create draft vN"}
        </button>
        <button
          type="button"
          className="primary"
          data-testid="ers-edit-version-approve"
          disabled={busy !== null || approved}
          title="Creator Approve — POST .../versions/{versionSheetId}/approve"
          onClick={() => void run("approve")}
        >
          {busy === "approve" ? "Approving…" : approved ? "Approved" : "Approve"}
        </button>
      </div>
      {compareMode ? (
        <div
          data-testid="ers-edit-version-compare-pane"
          style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "0.5rem", marginTop: "0.65rem" }}
        >
          <div>
            <p className="muted" style={{ margin: "0 0 0.25rem" }}>
              Parent (original)
            </p>
            <img
              src={api.assetUrl(sourceAssetId)}
              alt="Parent ERS composite"
              style={{ width: "100%", maxHeight: 180, objectFit: "contain", borderRadius: 6 }}
            />
          </div>
          <div>
            <p className="muted" style={{ margin: "0 0 0.25rem" }}>
              Derivative (candidate)
            </p>
            <img
              src={api.assetUrl(derivativeAssetId)}
              alt="ERS edit derivative"
              style={{ width: "100%", maxHeight: 180, objectFit: "contain", borderRadius: 6 }}
            />
          </div>
        </div>
      ) : null}
      {versions.length ? (
        <ul data-testid="ers-edit-version-list" style={{ margin: "0.5rem 0 0", paddingLeft: "1.1rem" }}>
          {versions.slice(0, 6).map((v, i) => {
            const vid = String(v.versionSheetId || v.sheetId || "");
            const comp = String((v as { composite?: string; derivativeAssetId?: string }).composite || v.derivativeAssetId || "").trim() || null;
            return (
            <li key={vid || String(i)} className="muted">
              <button
                type="button"
                className="ghost"
                data-testid="ers-edit-version-select"
                style={{ padding: 0, border: "none", background: "transparent", color: "inherit", cursor: "pointer" }}
                onClick={() => {
                  if (!vid) return;
                  onSelectVersion?.({ versionSheetId: vid, compositeAssetId: comp });
                  setMessage(`Selected draft/version ${vid.slice(0, 8)}… for display (not approved).`);
                }}
              >
                v{v.versionNumber ?? "?"} · {v.status || "draft"} · {vid.slice(0, 8)}…
              </button>
            </li>
            );
          })}
        </ul>
      ) : null}
      {message ? (
        <p className="muted" role="status" data-testid="ers-edit-version-message" style={{ marginTop: "0.5rem" }}>
          {message}
        </p>
      ) : null}
      {gap ? (
        <p role="status" data-testid="ers-edit-version-gaps" style={{ marginTop: "0.35rem" }} className="muted">
          Gap: {gap}
        </p>
      ) : null}
    </div>
  );
}
