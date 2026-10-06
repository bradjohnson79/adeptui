import { useCallback, useEffect, useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import type { Asset, Project } from "../../types";
import { api } from "../../api";
import { PanelHeading } from "../HelpTip";
import {
  chipLabel,
  inferSemanticReferenceType,
  mediaKindForAssetKind,
  roleLabelForBinding,
  sanitizeAlias,
  type ReferenceBindingView,
} from "../../sceneReferences/referenceTokens";
import {
  buildAddReferenceCandidates,
  buildCreatorRegistryCandidates,
  collapseDuplicateIdentityCandidates,
  identityAliasKey,
  isAlreadyBound,
  mergeAddReferenceCandidates,
  pickCharacterBindAssetId,
  type AddReferenceCandidate,
  type CreatorRegistryRow,
} from "../../sceneReferences/referenceAddCandidates";
import { timelineLibraryIdentity } from "../library/timelineLibraryIdentity";
import { ReferencesAddInput } from "./ReferencesAddInput";

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
  const [preflight, setPreflight] = useState<Record<string, unknown> | null>(null);
  const [attachAssetId, setAttachAssetId] = useState("");
  const [attachType, setAttachType] = useState("character");
  const [creatorRows, setCreatorRows] = useState<CreatorRegistryRow[]>([]);
  const [creatorLoading, setCreatorLoading] = useState(false);
  const [creatorRegistryError, setCreatorRegistryError] = useState<string | null>(null);

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


﻿  // Load Character / Prop / Environment Creator registries (local + global).
  useEffect(() => {
    let cancelled = false;
    const loadCreators = async () => {
      setCreatorLoading(true);
      setCreatorRegistryError(null);
      try {
        const rows: CreatorRegistryRow[] = [];
        try {
          const listed = await api.listCharacterProfiles(project.id);
          const profiles = (listed?.items || []) as Array<Record<string, unknown>>;
          await Promise.all(
            profiles.map(async (profile) => {
              const id = String(profile.id || "");
              const name = String(profile.name || profile.display_name || "").trim();
              if (!id || !name) return;
              const isGlobal = Boolean(profile.is_global || profile.isGlobal);
              const owningProjectId = String(profile.project_id || profile.projectId || project.id);
              let assetId = "";
              try {
                const refsRes = await api.listCharacterReferences(project.id, id);
                const refs = (refsRes?.items || refsRes || []) as Array<{ asset_id?: string; reference_role?: string }>;
                assetId = pickCharacterBindAssetId(Array.isArray(refs) ? refs : []) || "";
              } catch {
                /* refs optional */
              }
              if (!assetId) {
                assetId = String(
                  profile.primary_asset_id ||
                    profile.primaryAssetId ||
                    profile.approved_sheet_asset_id ||
                    profile.approvedSheetAssetId ||
                    "",
                );
              }
              if (!assetId) return;
              rows.push({
                entityId: id,
                name,
                semanticType: "character",
                assetId,
                isGlobal,
                owningProjectId,
                storedTag: null,
                mediaKind: "image",
              });
            }),
          );
        } catch (e: any) {
          const detail = e?.detail || e?.message || e;
          const msg =
            typeof detail === "string"
              ? detail
              : detail?.message || detail?.code || "Character registry unavailable";
          // Do not silently empty the @ list — owner sees "No matching reference" otherwise.
          setCreatorRegistryError(String(msg));
        }
        try {
          const propRes = await api.propCreator.list(project.id, false);
          const props = (propRes?.props || []) as Array<Record<string, unknown>>;
          for (const prop of props) {
            const id = String(prop.id || prop.prop_id || "");
            const name = String(prop.display_label || prop.name || prop.tag || "").trim();
            const assetId = String(
              prop.reference_asset_id ||
                prop.approved_asset_id ||
                prop.prs_asset_id ||
                prop.primary_approved_asset_id ||
                prop.library_asset_id ||
                "",
            );
            if (!id || !name || !assetId) continue;
            rows.push({
              entityId: id,
              name,
              semanticType: "prop",
              assetId,
              isGlobal: Boolean(prop.is_global || prop.isGlobal),
              owningProjectId: String(prop.project_id || prop.projectId || project.id),
              storedTag: String(prop.canonical_tag || prop.tag || "") || null,
              mediaKind: "image",
            });
          }
        } catch {
          /* props optional */
        }
        try {
          const ers = await api.environmentReferenceSheet.listSheets(project.id);
          const sheets = (ers?.sheets || []) as Array<Record<string, unknown>>;
          for (const sheet of sheets) {
            const id = String(sheet.sheetId || sheet.sheet_id || sheet.id || "");
            const name = String(sheet.name || "").trim();
            const assetId = String(
              sheet.ers_composite_asset_id ||
                sheet.composite ||
                sheet.derivativeAssetId ||
                sheet.referenceImageAssetId ||
                "",
            );
            if (!id || !name || !assetId) continue;
            rows.push({
              entityId: id,
              name,
              semanticType: "environment",
              assetId,
              isGlobal: Boolean(sheet.is_global || sheet.isGlobal),
              owningProjectId: String(sheet.projectId || sheet.project_id || project.id),
              storedTag: null,
              mediaKind: "image",
            });
          }
        } catch {
          /* ers optional */
        }
        if (!cancelled) setCreatorRows(rows);
      } finally {
        if (!cancelled) setCreatorLoading(false);
      }
    };
    void loadCreators();
    return () => {
      cancelled = true;
    };
  }, [project.id]);

  const addCandidates = useMemo(() => {
    const characterNames: Record<string, string> = {};
    for (const row of creatorRows) {
      if (row.semanticType !== "character" || !row.entityId || !row.name) continue;
      characterNames[row.entityId] = row.name;
      characterNames[row.entityId.slice(0, 8)] = row.name;
    }
    const fromAssets = buildAddReferenceCandidates({
      assets: project.assets || [],
      projectId: project.id,
      identityOf: (asset) =>
        timelineLibraryIdentity(asset, { relatedAssets: project.assets, characterNames }),
      thumbnailUrlOf: (asset) => {
        const anyAsset = asset as Asset & { thumbnail_url?: string | null };
        return anyAsset.thumbnail_url || null;
      },
    });
    const fromCreators = buildCreatorRegistryCandidates({ rows: creatorRows, projectId: project.id });
    return collapseDuplicateIdentityCandidates(
      mergeAddReferenceCandidates(fromAssets, fromCreators),
    );
  }, [project.assets, project.id, creatorRows]);


  const boundIdentities = useMemo(
    () =>
      items.map((b) => ({
        assetId: b.asset_id,
        alias: sanitizeAlias(b.alias || b.asset_name || "") || "",
      })),
    [items],
  );

  const addFromCandidate = async (candidate: AddReferenceCandidate): Promise<boolean> => {
    // Bind by canonical asset identity on the selected candidate — not display text.
    // Do NOT require the asset to already appear in project.assets (Global / other-project
    // creator rows are available for reference even when owned elsewhere).
    if (!candidate?.assetId) {
      setError("No matching reference");
      return false;
    }
    const localAsset = (project.assets || []).find((item) => item.id === candidate.assetId);
    // Prefer live asset kind when present; otherwise trust candidate.mediaKind from resolver.
    const assetMediaKind =
      (localAsset ? mediaKindForAssetKind(localAsset.kind) : null) ||
      (candidate.mediaKind === "video" || candidate.mediaKind === "audio" || candidate.mediaKind === "image"
        ? candidate.mediaKind
        : null) ||
      "image";
    if (assetMediaKind !== "image" && assetMediaKind !== "video" && assetMediaKind !== "audio") {
      setError("Only images, videos, and audio can be named as references.");
      return false;
    }
    // H3 (and any generator) caps: refuse 4th video/audio — never silently discard.
    if (assetMediaKind === "video" || assetMediaKind === "audio") {
      const maxRefs = 3;
      const sameKind = items.filter((b) => String(b.media_kind || "").toLowerCase() === assetMediaKind);
      if (sameKind.length >= maxRefs) {
        setError(
          assetMediaKind === "video"
            ? `This generator supports up to ${maxRefs} video references.`
            : `This generator supports up to ${maxRefs} audio references.`,
        );
        return false;
      }
    }
    // One @/%/# tag per identity. @Cade is the same character as @CadeCRS.
    const dup = isAlreadyBound(
      { assetId: candidate.assetId, alias: candidate.alias },
      items.map((b) => ({
        assetId: b.asset_id,
        alias: sanitizeAlias(b.alias || b.asset_name || "") || "",
      })),
    );
    if (dup) {
      setError(`Already added: ${candidate.displayToken}`);
      return false;
    }
    setError(null);
    try {
      // Same Timeline reference-binding entry as Library drag / Add to References.
      await api.sceneReferences.attach(project.id, {
        asset_id: candidate.assetId,
        scope_type: scopeType,
        scope_id: scopeId,
        reference_type: candidate.referenceType,
        media_kind: assetMediaKind,
        alias: candidate.alias,
        usage_modes: assetMediaKind === "video" ? ["motion"] : assetMediaKind === "audio" ? ["informational"] : ["appearance"],
        reference_roles: [candidate.referenceType],
      });
      await load();
      onChange?.();
      return true;
    } catch (e: any) {
      const detail = e?.detail || e?.message || e;
      const msg = typeof detail === "string" ? detail : detail?.message || "Could not add reference";
      // Differentiate: lookup miss vs bind fail. Never reuse "No matching reference" for attach failures.
      setError(msg === "No matching reference" ? "Could not add reference" : (msg || "Could not add reference"));
      return false;
    }
  };

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
    const assetMediaKind = mediaKindForAssetKind(asset.kind);
    if (!assetMediaKind) {
      setError("Only images, videos, and audio can be named as references.");
      return;
    }
    if (assetMediaKind === "video" || assetMediaKind === "audio") {
      const maxRefs = 3;
      const sameKind = items.filter((b) => String(b.media_kind || "").toLowerCase() === assetMediaKind);
      if (sameKind.length >= maxRefs) {
        setError(
          assetMediaKind === "video"
            ? `This generator supports up to ${maxRefs} video references.`
            : `This generator supports up to ${maxRefs} audio references.`,
        );
        return;
      }
    }
    const identity = timelineLibraryIdentity(asset, { relatedAssets: project.assets });
    const referenceType = inferSemanticReferenceType({
      tag: asset.tag,
      filename: asset.filename,
      alias: identity.title,
      mediaKind: assetMediaKind,
    });
    // Keep media_kind as image/video/audio from the asset; semantic type is separate.
    const mediaKind = assetMediaKind;
    const alias =
      sanitizeAlias(identity.title) ||
      sanitizeAlias(asset.tag || asset.filename || referenceType) ||
      "Reference";
    const dup = isAlreadyBound(
      { assetId: asset.id, alias },
      items.map((b) => ({
        assetId: b.asset_id,
        alias: sanitizeAlias(b.alias || b.asset_name || "") || "",
      })),
    );
    if (dup) {
      const existing = items.find(
        (b) => identityAliasKey(b.alias || b.asset_name || "") === identityAliasKey(alias),
      );
      setError(existing ? `Already added: ${chipLabel(existing)}` : `Already added: ${alias}`);
      return;
    }
    await api.sceneReferences.attach(project.id, {
      asset_id: asset.id,
      scope_type: scopeType,
      scope_id: scopeId,
      reference_type: referenceType,
      media_kind: mediaKind,
      alias,
      usage_modes: mediaKind === "video" ? ["motion"] : mediaKind === "audio" ? ["informational"] : ["appearance"],
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
    const duplicate = items.some(
      (other) =>
        other.id !== b.id &&
        sanitizeAlias(other.alias || other.asset_name || "").toLowerCase() === alias.toLowerCase(),
    );
    if (duplicate) {
      setError(`Tag "${alias}" is already used by another active reference. Pick a unique tag.`);
      return;
    }
    setError(null);
    try {
      // Rename updates canonical tag (alias) only — asset_id is unchanged.
      await api.sceneReferences.update(project.id, b.id, { alias });
      setRenamingId(null);
      await load();
      onChange?.();
    } catch (e: any) {
      const detail = e?.detail || e?.message || e;
      const code = typeof detail === "object" ? detail?.code : null;
      if (code === "ALIAS_TAKEN") {
        const suggested = detail?.suggested_alias ? ` Try ${detail.suggested_alias}.` : "";
        setError(`Tag "${alias}" is already used.${suggested}`);
        return;
      }
      setError(typeof detail === "string" ? detail : detail?.message || "Rename failed");
    }
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

      <ReferencesAddInput
        candidates={addCandidates}
        bound={boundIdentities}
        disabled={loading || creatorLoading}
        onSelect={(candidate) => { setError(null); return addFromCandidate(candidate); }}
          onActivity={() => setError(null)}
      />

      {loading && <p data-testid="references-loading">Loading references…</p>}
      {creatorRegistryError && (
        <p className="scene-meta" data-testid="references-creator-registry-error" role="status">
          {creatorRegistryError}
        </p>
      )}
      {error && (
        <p className="error" data-testid="references-error">
          {error}{" "}
          <button type="button" onClick={() => void load()}>
            Retry
          </button>
        </p>
      )}

      {!loading && !error && items.length === 0 && (
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
          {items.map((b) => {
            const approved = b.approval_status === "approved";
            const roleLabel = roleLabelForBinding(b);
            return (
            <li
              key={b.id}
              className={`ref-chip${approved ? " ref-chip--approved" : ""}`}
              data-testid={`reference-binding-${b.id}`}
              data-approved={approved ? "true" : "false"}
            >
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
              <span
                className="ref-chip__role"
                data-testid={`reference-role-${b.id}`}
              >
                ({roleLabel}){approved ? " ✓" : ""}
              </span>
              {renamingId === b.id ? null : (
                <button
                  type="button"
                  className="ghost"
                  data-testid={`reference-rename-${b.id}`}
                  title="Rename canonical tag. Asset id stays the same."
                  onClick={() => {
                    setRenamingId(b.id);
                    setRenameValue(b.alias || b.asset_name || "");
                  }}
                >
                  Rename
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
            );
          })}
        </ul>
      ) : (
      <ul className="asset-list" data-testid="references-list">
        {items.map((b) => (
          <li key={b.id} data-testid={`reference-binding-${b.id}`} className={!b.enabled ? "muted" : ""}>
            <div className="row-actions" style={{ alignItems: "center", gap: 8 }}>
              {b.thumbnail_url ? (
                <img src={b.thumbnail_url} alt="" width={40} height={40} style={{ objectFit: "cover" }} />
              ) : null}
              <div>
                <strong dir="auto">{b.broken ? "Broken Reference" : chipLabel(b)}</strong>
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
              {renamingId === b.id ? (
                <form
                  onSubmit={(e) => {
                    e.preventDefault();
                    void rename(b);
                  }}
                  style={{ display: "inline-flex", gap: 6, alignItems: "center" }}
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
                  <button type="button" className="ghost" onClick={() => setRenamingId(null)}>
                    Cancel
                  </button>
                </form>
              ) : (
                <button
                  type="button"
                  data-testid={`reference-rename-${b.id}`}
                  title="Rename canonical tag (alias). Asset id stays the same."
                  onClick={() => {
                    setRenamingId(b.id);
                    setRenameValue(b.alias || b.asset_name || "");
                  }}
                >
                  Rename
                </button>
              )}
              <button type="button" onClick={() => void toggleEnabled(b)}>
                {b.enabled ? "Disable" : "Enable"}
              </button>
              <button type="button" data-testid={`reference-remove-${b.id}`} onClick={() => void remove(b)}>
                Remove
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
