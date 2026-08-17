import { useCallback, useEffect, useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import type { Asset, Project } from "../../types";
import { api } from "../../api";
import { PanelHeading } from "../HelpTip";
import {
  chipLabel,
  mediaKindForAssetKind,
  referenceTypeForAssetKind,
  sanitizeAlias,
  type ReferenceBindingView,
} from "../../sceneReferences/referenceTokens";

type Binding = ReferenceBindingView & {
  scope_type: string;
  scope_id: string;
  usage_modes: string[];
  reference_roles: string[];
  enabled: boolean;
  order_index: number;
  identity_version_id?: string | null;
  thumbnail_url?: string | null;
  approval_status?: string | null;
  inherited_from?: string | null;
  is_override?: boolean;
  notes?: string | null;
};

const WORKFLOW_BY_TAB: Record<string, string> = {
  txt2vid: "text_to_video",
  one: "one_frame",
  three: "three_frame",
  timeline: "timeline",
  director: "timeline",
  storyboard: "storyboard",
};

function supportLabel(cls: string | undefined): string {
  switch (cls) {
    case "reference_conditioned":
      return "Reference-conditioned";
    case "prompt_guided":
      return "Prompt-guided";
    case "unsupported":
      return "Unsupported";
    case "excluded_by_limit":
      return "Excluded by limit";
    case "blocked":
      return "Blocked";
    default:
      return cls || "Unknown";
  }
}

export function ReferencesPane({
  project,
  sceneId,
  workflowTab,
  onChange,
  reloadKey = 0,
}: {
  project: Project;
  sceneId: string | null;
  workflowTab?: string;
  onChange?: () => void;
  reloadKey?: number;
}) {
  const { t } = useTranslation(["timeline", "common", "errors"]);
  const [items, setItems] = useState<Binding[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [filter, setFilter] = useState("");
  const [preflight, setPreflight] = useState<Record<string, unknown> | null>(null);
  const [attachAssetId, setAttachAssetId] = useState("");
  const [attachType, setAttachType] = useState("character");

  const [renamingId, setRenamingId] = useState<string | null>(null);
  const [renameValue, setRenameValue] = useState("");

  const workflowKey = WORKFLOW_BY_TAB[workflowTab || "timeline"] || "timeline";
  const compact = workflowKey === "timeline";
  const scopeId = compact ? project.id : sceneId || "project";
  const scopeType = compact ? "project" : sceneId ? "scene" : "project";

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await api.sceneReferences.list(project.id, {
        scopeType,
        scopeId,
        includeInherited: true,
        sceneId: sceneId || undefined,
      });
      setItems((res.items || []) as Binding[]);
      const pf = await api.sceneReferences.preflight(project.id, {
        scope_type: scopeType,
        scope_id: scopeId,
        workflow_key: workflowKey,
      });
      setPreflight(pf);
    } catch (e: any) {
      setError(e?.message || "Failed to load scene references");
      setItems([]);
    } finally {
      setLoading(false);
    }
  }, [project.id, scopeId, scopeType, sceneId, workflowKey]);

  useEffect(() => {
    void load();
  }, [load, reloadKey]);

  const filtered = useMemo(() => {
    const q = filter.trim().toLowerCase();
    if (!q) return items;
    return items.filter(
      (b) =>
        (b.asset_name || "").toLowerCase().includes(q) ||
        (b.alias || "").toLowerCase().includes(q) ||
        b.reference_type.includes(q) ||
        (b.reference_roles || []).join(" ").toLowerCase().includes(q)
    );
  }, [items, filter]);

  const attach = async () => {
    if (!attachAssetId.trim()) return;
    await api.sceneReferences.attach(project.id, {
      asset_id: attachAssetId.trim(),
      scope_type: scopeType,
      scope_id: scopeId,
      reference_type: attachType,
      usage_modes: ["appearance"],
      reference_roles: [attachType],
    });
    setAttachAssetId("");
    await load();
    onChange?.();
  };

  const toggleEnabled = async (b: Binding) => {
    await api.sceneReferences.update(project.id, b.id, { enabled: !b.enabled });
    await load();
    onChange?.();
  };

  const remove = async (b: Binding) => {
    await api.sceneReferences.remove(project.id, b.id);
    await load();
    onChange?.();
  };

  const copyPrevious = async () => {
    if (!sceneId) return;
    const scenes = project.scenes || [];
    const idx = scenes.findIndex((s) => s.id === sceneId);
    if (idx <= 0) {
      setError("No previous scene to copy from");
      return;
    }
    const prev = scenes[idx - 1];
    await api.sceneReferences.copy(project.id, {
      source_scope_type: "scene",
      source_scope_id: prev.id,
      target_scope_type: "scene",
      target_scope_id: sceneId,
    });
    await load();
    onChange?.();
  };

  const attachAsset = async (asset: Pick<Asset, "id" | "kind" | "tag" | "filename">) => {
    if (asset.kind === "audio") {
      setError("Audio stays on Lip Sync, SFX, or Music. It cannot be a typed reference.");
      return;
    }
    const mediaKind = mediaKindForAssetKind(asset.kind);
    const referenceType = referenceTypeForAssetKind(asset.kind);
    if (!mediaKind || !referenceType) {
      setError("Only images and videos can be named as references.");
      return;
    }
    await api.sceneReferences.attach(project.id, {
      asset_id: asset.id,
      scope_type: scopeType,
      scope_id: scopeId,
      reference_type: referenceType,
      media_kind: mediaKind,
      alias: sanitizeAlias(asset.tag || asset.filename || referenceType),
      usage_modes: mediaKind === "video" ? ["motion"] : ["appearance"],
      reference_roles: [referenceType],
    });
    await load();
    onChange?.();
  };

  const onDrop = async (e: React.DragEvent) => {
    e.preventDefault();
    const assetId =
      e.dataTransfer.getData("application/x-adept-asset") ||
      e.dataTransfer.getData("text/asset-id") ||
      e.dataTransfer.getData("text/plain");
    if (!assetId) return;
    const asset = project.assets.find((item) => item.id === assetId);
    if (asset) {
      await attachAsset(asset);
      return;
    }
    await api.sceneReferences.attach(project.id, {
      asset_id: assetId,
      scope_type: scopeType,
      scope_id: scopeId,
      reference_type: "other",
      usage_modes: ["informational"],
      reference_roles: ["reference"],
    });
    await load();
    onChange?.();
  };

  const rename = async (b: Binding) => {
    const alias = sanitizeAlias(renameValue);
    if (!alias) return;
    await api.sceneReferences.update(project.id, b.id, { alias });
    setRenamingId(null);
    await load();
    onChange?.();
  };

  const supportClass = String(preflight?.supportClass || "");
  const readiness = (preflight?.referenceReadiness as Record<string, unknown>) || {};

  return (
    <div
      className="panel"
      data-testid="scene-references-pane"
      onDragOver={(e) => e.preventDefault()}
      onDrop={(e) => void onDrop(e)}
    >
      <PanelHeading
        title={t("timeline:references")}
        tip={t("timeline:referencesTip")}
      />
      {compact ? (
        <p className="scene-meta">{t("timeline:referencesHint")}</p>
      ) : (
        <p className="scene-meta" data-testid="reference-capability-status">
          {supportLabel(supportClass)}
          {supportClass === "prompt_guided" ? " — prompt guidance only, not image conditioning" : ""}
          {" · "}
          Readiness: {String(readiness.referenceReadiness || "—")} (not Continuity Score)
        </p>
      )}

      <div className="field">
        <label htmlFor="ref-filter">Filter</label>
        <input
          id="ref-filter"
          data-testid="references-filter"
          value={filter}
          onChange={(e) => setFilter(e.target.value)}
          placeholder="Search type, role, name"
        />
      </div>

      {loading && <p data-testid="references-loading">Loading references…</p>}
      {error && (
        <p className="error" data-testid="references-error">
          {error}{" "}
          <button type="button" onClick={() => void load()}>
            Retry
          </button>
        </p>
      )}

      {!loading && !error && filtered.length === 0 && (
        <div data-testid="references-empty">
          <p>{t("timeline:referencesEmpty")}</p>
          {!compact ? (
            <div className="row-actions">
              <button type="button" data-testid="ref-add-library" onClick={() => setAttachAssetId(project.assets[0]?.id || "")}>
                {t("timeline:addFromLibrary")}
              </button>
              <button
                type="button"
                data-testid="ref-copy-previous"
                onClick={() => void copyPrevious()}
                disabled={!sceneId}
              >
                Copy from previous scene
              </button>
            </div>
          ) : null}
        </div>
      )}

      {compact ? (
        <ul className="ref-chip-list" data-testid="references-list">
          {filtered.map((b) => (
            <li key={b.id} className="ref-chip" data-testid={`reference-binding-${b.id}`}>
              {renamingId === b.id ? (
                <form
                  onSubmit={(e) => {
                    e.preventDefault();
                    void rename(b);
                  }}
                >
                  <input
                    data-testid={`reference-alias-input-${b.id}`}
                    value={renameValue}
                    onChange={(e) => setRenameValue(e.target.value)}
                    aria-label="Reference name"
                    autoFocus
                  />
                  <button type="submit" data-testid={`reference-alias-save-${b.id}`}>
                    Save
                  </button>
                </form>
              ) : (
                <button
                  type="button"
                  className="ref-chip__label"
                  data-testid={`reference-chip-${b.id}`}
                  dir="auto"
                  title="Click to rename. The Timeline still uses the same file."
                  onClick={() => {
                    setRenamingId(b.id);
                    setRenameValue(b.alias || b.asset_name || "");
                  }}
                >
                  {b.broken ? "Broken Reference" : chipLabel(b)}
                </button>
              )}
              <button
                type="button"
                className="ghost"
                data-testid={`reference-remove-${b.id}`}
                title={t("timeline:removeReferenceTitle")}
                onClick={() => void remove(b)}
              >
                Remove
              </button>
            </li>
          ))}
        </ul>
      ) : (
      <ul className="asset-list" data-testid="references-list">
        {filtered.map((b) => (
          <li key={b.id} data-testid={`reference-binding-${b.id}`} className={!b.enabled ? "muted" : ""}>
            <div className="row-actions" style={{ alignItems: "center", gap: 8 }}>
              {b.thumbnail_url ? (
                <img src={b.thumbnail_url} alt="" width={40} height={40} style={{ objectFit: "cover" }} />
              ) : null}
              <div>
                <strong>{b.asset_name || b.asset_id.slice(0, 8)}</strong>
                <div className="scene-meta">
                  {b.reference_type}
                  {(b.reference_roles || []).length ? ` · ${(b.reference_roles || []).join(", ")}` : ""}
                  {b.identity_version_id ? ` · ver ${b.identity_version_id.slice(0, 8)}` : ""}
                  {b.approval_status ? ` · ${b.approval_status}` : ""}
                  {b.inherited_from ? ` · inherited from ${b.inherited_from}` : ""}
                  {b.is_override ? " · override" : ""}
                </div>
              </div>
            </div>
            <div className="row-actions">
              <button type="button" onClick={() => void toggleEnabled(b)}>
                {b.enabled ? "Disable" : "Enable"}
              </button>
              <button type="button" onClick={() => void remove(b)}>
                Remove binding
              </button>
            </div>
          </li>
        ))}
      </ul>
      )}

      {!compact && (preflight?.excluded as unknown[])?.length ? (
        <div data-testid="references-excluded">
          <p className="scene-meta">Excluded (with reasons — never silent):</p>
          <ul>
            {((preflight?.excluded as Binding[]) || []).map((b) => (
              <li key={b.id}>
                {b.asset_name || b.id.slice(0, 8)} —{" "}
                {String((preflight?.exclusionReasons as Record<string, string>)?.[b.id] || "excluded")}
              </li>
            ))}
          </ul>
        </div>
      ) : null}

      {!compact ? (
      <div className="field" data-testid="references-attach-form">
        <label>Attach asset id</label>
        <input value={attachAssetId} onChange={(e) => setAttachAssetId(e.target.value)} placeholder="asset uuid" />
        <label>Type</label>
        <select value={attachType} onChange={(e) => setAttachType(e.target.value)}>
          {["character", "environment", "prop", "style", "lighting", "composition", "other"].map((t) => (
            <option key={t} value={t}>
              {t}
            </option>
          ))}
        </select>
        <button type="button" className="primary" data-testid="ref-attach-submit" onClick={() => void attach()}>
          Attach reference
        </button>
      </div>
      ) : null}
    </div>
  );
}
