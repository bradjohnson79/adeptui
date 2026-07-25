import { useEffect, useMemo, useState } from "react";
import type { Asset, Project, Scene } from "../types";
import { api } from "../api";
import type { TimelineClip } from "./DirectorTracks";

type Binding = {
  bindingId: string;
  referenceAssetId: string;
  role: string;
  influence: string;
  source?: string;
  label?: string;
  notes?: string;
  sortOrder?: number;
  sourceTimelineItemId?: string | null;
};

const ROLES = [
  "character_identity",
  "costume",
  "prop",
  "environment",
  "style",
  "lighting",
  "color",
  "composition",
  "camera",
  "motion",
  "start_frame",
  "end_frame",
  "continuity",
  "negative",
  "other",
] as const;

const INFLUENCES = ["locked", "strong", "moderate", "loose", "inspiration"] as const;

type SourceTab = "bible" | "assets" | "timeline" | "approved" | "upload";

export function TimelineReferencesPanel({
  project,
  scene,
  clip,
  timelineImages,
  enabled,
  onRefsCount,
}: {
  project: Project;
  scene: Scene;
  clip: TimelineClip;
  timelineImages: TimelineClip[];
  enabled: boolean;
  onRefsCount?: (itemId: string, count: number) => void;
}) {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [bindings, setBindings] = useState<Binding[]>([]);
  const [activeVersion, setActiveVersion] = useState(0);
  const [showAdd, setShowAdd] = useState(false);
  const [tab, setTab] = useState<SourceTab>("assets");
  const [role, setRole] = useState<string>("style");
  const [influence, setInfluence] = useState<string>("moderate");
  const [busy, setBusy] = useState(false);
  const [capabilityNote, setCapabilityNote] = useState<string | null>(null);

  const tag = clip.display_tag || clip.label || clip.id;
  const images = useMemo(
    () => (project.assets || []).filter((a) => a.kind === "image"),
    [project.assets]
  );
  const approved = useMemo(
    () => images.filter((a) => (a as any).production_approval === "approved"),
    [images]
  );
  const otherTimeline = useMemo(
    () => timelineImages.filter((c) => c.id !== clip.id && c.asset_id),
    [timelineImages, clip.id]
  );

  const reload = async () => {
    if (!enabled) return;
    setLoading(true);
    setError(null);
    try {
      const data = await api.getTimelineReferences(project.id, scene.id, clip.id);
      const next = (data.bindings || []) as Binding[];
      setBindings(next);
      setActiveVersion(Number(data.activeVersion || 0));
      onRefsCount?.(clip.id, next.length);
    } catch (e: any) {
      const detail = e?.detail || e?.message || "Failed to load references";
      setError(typeof detail === "string" ? detail : JSON.stringify(detail));
      setBindings([]);
      onRefsCount?.(clip.id, 0);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void reload();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [enabled, project.id, scene.id, clip.id]);

  if (!enabled) return null;

  const primaryAsset = clip.asset_id
    ? images.find((a) => a.id === clip.asset_id)
    : undefined;

  const addFromAsset = async (asset: Asset, source: string, sourceTimelineItemId?: string) => {
    setBusy(true);
    setError(null);
    try {
      await api.addTimelineReference(project.id, scene.id, clip.id, {
        referenceAssetId: asset.id,
        role,
        influence,
        source,
        sourceTimelineItemId: sourceTimelineItemId || null,
        label: asset.tag || asset.filename || "",
      });
      setShowAdd(false);
      await reload();
      try {
        const pkg = await api.getTimelineReferencePackage(project.id, scene.id, clip.id);
        if (pkg?.support?.status === "degraded") {
          setCapabilityNote("Some bindings are semantic-only until IC-LoRA is ready.");
        } else {
          setCapabilityNote(null);
        }
      } catch {
        /* optional */
      }
    } catch (e: any) {
      const detail = e?.detail || e?.message || "Save failed";
      setError(typeof detail === "string" ? detail : JSON.stringify(detail));
    } finally {
      setBusy(false);
    }
  };

  const onUpload = async (file: File | null) => {
    if (!file) return;
    setBusy(true);
    setError(null);
    try {
      const tagName = file.name.replace(/\.[^.]+$/, "").slice(0, 40) || "ref";
      const asset = await api.uploadAsset(project.id, file, tagName, "image");
      await addFromAsset(asset, "upload");
      onRefsCount?.(clip.id, bindings.length + 1);
    } catch (e: any) {
      setError(e?.message || "Upload failed");
      setBusy(false);
    }
  };

  const patchBinding = async (bindingId: string, patch: Record<string, unknown>) => {
    setBusy(true);
    setError(null);
    try {
      await api.patchTimelineReference(project.id, scene.id, clip.id, bindingId, {
        ...patch,
        expectedVersion: activeVersion,
      });
      await reload();
    } catch (e: any) {
      setError(e?.message || "Update failed");
    } finally {
      setBusy(false);
    }
  };

  const removeBinding = async (bindingId: string) => {
    setBusy(true);
    setError(null);
    try {
      await api.deleteTimelineReference(project.id, scene.id, clip.id, bindingId);
      await reload();
    } catch (e: any) {
      setError(e?.message || "Remove failed");
    } finally {
      setBusy(false);
    }
  };

  const byRole = useMemo(() => {
    const map = new Map<string, Binding[]>();
    for (const b of bindings) {
      const list = map.get(b.role) || [];
      list.push(b);
      map.set(b.role, list);
    }
    return [...map.entries()];
  }, [bindings]);

  return (
    <div className="panel" style={{ marginTop: 8, padding: "0.75rem 0.9rem" }}>
      <div style={{ display: "flex", justifyContent: "space-between", gap: 8, alignItems: "baseline" }}>
        <strong>References for {tag}</strong>
        <span className="scene-meta">Refs: {bindings.length}</span>
      </div>
      <p className="scene-meta" style={{ margin: "0.35rem 0 0.6rem" }}>
        Optional supporting references. Run never requires a reference set.
      </p>

      <div style={{ display: "flex", gap: 10, alignItems: "center", marginBottom: 8 }}>
        {primaryAsset ? (
          <img
            src={api.assetUrl(primaryAsset.id)}
            alt=""
            style={{ width: 64, height: 40, objectFit: "cover", borderRadius: 4 }}
          />
        ) : (
          <div className="scene-meta">No primary frame asset</div>
        )}
        <span className="scene-meta">Primary frame · {tag}</span>
      </div>

      {loading && <div className="scene-meta">Loading…</div>}
      {error && (
        <div className="scene-meta" style={{ color: "var(--danger, #b33)" }}>
          {error}
        </div>
      )}
      {capabilityNote && <div className="scene-meta">{capabilityNote}</div>}

      {!loading && bindings.length === 0 && (
        <div className="scene-meta" style={{ marginBottom: 8 }}>
          No supporting references (normal).
        </div>
      )}

      {byRole.map(([roleKey, items]) => (
        <div key={roleKey} style={{ marginBottom: 8 }}>
          <div className="scene-meta" style={{ textTransform: "uppercase", letterSpacing: "0.04em" }}>
            {roleKey}
          </div>
          {items.map((b) => {
            const asset = images.find((a) => a.id === b.referenceAssetId);
            return (
              <div
                key={b.bindingId}
                style={{
                  display: "grid",
                  gridTemplateColumns: "48px 1fr auto",
                  gap: 8,
                  alignItems: "center",
                  marginTop: 4,
                }}
              >
                {asset ? (
                  <img
                    src={api.assetUrl(asset.id)}
                    alt=""
                    style={{ width: 48, height: 32, objectFit: "cover", borderRadius: 3 }}
                  />
                ) : (
                  <span className="scene-meta">missing</span>
                )}
                <div>
                  <div>{b.label || asset?.tag || b.referenceAssetId}</div>
                  <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
                    <select
                      value={b.role}
                      disabled={busy}
                      onChange={(e) => patchBinding(b.bindingId, { role: e.target.value })}
                    >
                      {ROLES.map((r) => (
                        <option key={r} value={r}>
                          {r}
                        </option>
                      ))}
                    </select>
                    <select
                      value={b.influence}
                      disabled={busy}
                      onChange={(e) => patchBinding(b.bindingId, { influence: e.target.value })}
                    >
                      {INFLUENCES.map((inf) => (
                        <option key={inf} value={inf}>
                          {inf}
                        </option>
                      ))}
                    </select>
                  </div>
                </div>
                <button type="button" disabled={busy} onClick={() => removeBinding(b.bindingId)}>
                  Remove
                </button>
              </div>
            );
          })}
        </div>
      ))}

      <div style={{ display: "flex", gap: 8, marginTop: 8, flexWrap: "wrap" }}>
        <button type="button" onClick={() => setShowAdd((v) => !v)}>
          {showAdd ? "Close" : "Add reference"}
        </button>
        <button
          type="button"
          disabled={busy}
          onClick={async () => {
            setBusy(true);
            try {
              const res = await api.continuityPreviousReference(project.id, scene.id, clip.id);
              if (!res?.available) setError(res?.message || "Continuity unavailable");
              await reload();
            } catch (e: any) {
              setError(e?.message || "Continuity failed");
            } finally {
              setBusy(false);
            }
          }}
        >
          Continuity previous
        </button>
        {bindings.length > 0 && (
          <button
            type="button"
            disabled={busy}
            onClick={async () => {
              setBusy(true);
              try {
                await api.clearTimelineReferences(project.id, scene.id, clip.id);
                await reload();
              } catch (e: any) {
                setError(e?.message || "Clear failed");
              } finally {
                setBusy(false);
              }
            }}
          >
            Clear all
          </button>
        )}
      </div>

      {showAdd && (
        <div style={{ marginTop: 10, borderTop: "1px solid var(--border, #333)", paddingTop: 8 }}>
          <div style={{ display: "flex", gap: 6, flexWrap: "wrap", marginBottom: 8 }}>
            {(["bible", "assets", "timeline", "approved", "upload"] as SourceTab[]).map((t) => (
              <button key={t} type="button" className={tab === t ? "active" : ""} onClick={() => setTab(t)}>
                {t}
              </button>
            ))}
          </div>
          <div style={{ display: "flex", gap: 8, marginBottom: 8 }}>
            <label className="scene-meta">
              Role{" "}
              <select value={role} onChange={(e) => setRole(e.target.value)}>
                {ROLES.map((r) => (
                  <option key={r} value={r}>
                    {r}
                  </option>
                ))}
              </select>
            </label>
            <label className="scene-meta">
              Influence{" "}
              <select value={influence} onChange={(e) => setInfluence(e.target.value)}>
                {INFLUENCES.map((inf) => (
                  <option key={inf} value={inf}>
                    {inf}
                  </option>
                ))}
              </select>
            </label>
          </div>

          {tab === "assets" && (
            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(88px, 1fr))", gap: 6 }}>
              {images.map((a) => (
                <button
                  key={a.id}
                  type="button"
                  disabled={busy}
                  onClick={() => addFromAsset(a, "project_asset")}
                  style={{ padding: 4 }}
                >
                  <img src={api.assetUrl(a.id)} alt="" style={{ width: "100%", height: 48, objectFit: "cover" }} />
                  <div className="scene-meta">@{a.tag || a.filename}</div>
                </button>
              ))}
              {images.length === 0 && <div className="scene-meta">No project images</div>}
            </div>
          )}

          {tab === "timeline" && (
            <div style={{ display: "grid", gap: 6 }}>
              {otherTimeline.map((c) => {
                const a = images.find((x) => x.id === c.asset_id);
                if (!a) return null;
                return (
                  <button
                    key={c.id}
                    type="button"
                    disabled={busy}
                    onClick={() => addFromAsset(a, "timeline_image", c.id)}
                  >
                    {c.display_tag || c.label || c.id} → @{a.tag || a.filename}
                  </button>
                );
              })}
              {otherTimeline.length === 0 && <div className="scene-meta">No other timeline images</div>}
            </div>
          )}

          {tab === "approved" && (
            <div style={{ display: "grid", gap: 6 }}>
              {approved.map((a) => (
                <button key={a.id} type="button" disabled={busy} onClick={() => addFromAsset(a, "approved_frame")}>
                  @{a.tag || a.filename}
                </button>
              ))}
              {approved.length === 0 && <div className="scene-meta">No approved frames</div>}
            </div>
          )}

          {tab === "bible" && (
            <div className="scene-meta">
              Select a project asset linked from the Production Bible (entity reference links resolve to project assets).
              Use the Assets tab for the linked image, or Continuity previous for approved frames.
            </div>
          )}

          {tab === "upload" && (
            <input
              type="file"
              accept="image/*"
              disabled={busy}
              onChange={(e) => void onUpload(e.target.files?.[0] || null)}
            />
          )}
        </div>
      )}
    </div>
  );
}
