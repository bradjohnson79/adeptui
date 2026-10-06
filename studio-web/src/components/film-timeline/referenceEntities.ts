/**
 * Timeline V2 reference picker entity sources.
 *
 * Restores the V1 wiring: the Reference picker lists saved creator ENTITIES
 * (Character / Prop / Environment) resolved through the same authoritative
 * creator stores and APIs that Character Creator / V1 Timeline already use.
 * It does NOT reconstruct entities from raw Library image files.
 *
 * V1 authority (see TIMELINE V1 REFERENCE AUDIT):
 *   Characters   api.listCharacterProfiles + api.listCharacterReferences
 *                -> pickCharacterBindAssetId (hero_identity > reference_image > first)
 *   Props        api.propCreator.list
 *                -> reference_asset_id || approved_asset_id || prs_asset_id
 *                   || primary_approved_asset_id || library_asset_id
 *   Environments api.environmentReferenceSheet.listSheets
 *                -> ers_composite_asset_id || composite || derivativeAssetId
 *                   || referenceImageAssetId
 */
import { api } from "../../api";
import type { Asset } from "../../types";
import { pickCharacterBindAssetId } from "../../sceneReferences/referenceAddCandidates";
import { resolveStoryboardEnvironment, type StoryboardFrameRef } from "./storyboardEnvironmentReference";

export type EntityKind = "character" | "prop" | "environment";

/** One selectable reference option: a saved entity OR an explicit library image. */
export type ReferenceOption = {
  /** Stable key for React + selection state. */
  key: string;
  /** Bindable asset id resolved through the creator identity chain. */
  assetId: string;
  /** Creator entity name (Renkoka) or library image display name (Renkoka-CRS). */
  name: string;
  /** Default alias for the Name field (entity name / library display name). */
  defaultAlias: string;
  /** Grouping for the picker. */
  group: "project" | "global" | "library" | "storyboard";
  /** Thumbnail / reference image asset id (same as assetId for binding). */
  thumbAssetId: string;
  /** Project that owns the thumbnail. Global sheets are not this project's assets. */
  thumbProjectId?: string;
  /** False when the bound picture is gone, so the picker does not request a dead thumb. */
  thumbReady?: boolean;
  /** Set when this option is a storyboard rather than one Environment Creator sheet. */
  storyboardId?: string;
  frames?: StoryboardFrameRef[];
  /** The underlying library asset when this option came from an explicit classification. */
  asset?: Asset;
};

export type ReferenceOptionGroups = {
  project: ReferenceOption[];
  global: ReferenceOption[];
  storyboard: ReferenceOption[];
  library: ReferenceOption[];
};

const EMPTY_GROUPS: ReferenceOptionGroups = { project: [], global: [], storyboard: [], library: [] };

function stripExt(filename: string): string {
  return String(filename || "").replace(/\.[A-Za-z0-9]{2,5}$/, "").trim();
}

function libraryDisplayName(asset: Asset): string {
  const tag = String(asset.tag || "").trim();
  if (tag && tag !== "character_reference") return tag;
  return stripExt(asset.filename || "") || tag || "Image";
}

/**
 * Load saved Character entities (project + global) exactly as V1 does.
 * The bind asset is the canonical/approved character reference image that
 * Character Creator already considers authoritative.
 */
async function loadCharacterOptions(projectId: string): Promise<ReferenceOption[]> {
  const out: ReferenceOption[] = [];
  const listed = await api.listCharacterProfiles(projectId);
  const profiles = (listed?.items || []) as Array<Record<string, unknown>>;
  await Promise.all(
    profiles.map(async (profile) => {
      const id = String(profile.id || "");
      const name = String(profile.name || profile.display_name || "").trim();
      if (!id || !name) return;
      const isGlobal = Boolean(profile.is_global || profile.isGlobal);
      let assetId = "";
      try {
        const refsRes = await api.listCharacterReferences(projectId, id);
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
      out.push({
        key: `character:${id}`,
        assetId,
        name,
        defaultAlias: name,
        group: isGlobal ? "global" : "project",
        thumbAssetId: assetId,
      });
    }),
  );
  return out;
}

/** Load saved Prop entities (project + global) exactly as V1 does. */
async function loadPropOptions(projectId: string): Promise<ReferenceOption[]> {
  const out: ReferenceOption[] = [];
  const propRes = await api.propCreator.list(projectId, false);
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
    const isGlobal = Boolean(prop.is_global || prop.isGlobal);
    out.push({
      key: `prop:${id}`,
      assetId,
      name,
      defaultAlias: name,
      group: isGlobal ? "global" : "project",
      thumbAssetId: assetId,
    });
  }
  return out;
}

/** Load saved Environment entities (project + global) exactly as V1 does. */
async function loadEnvironmentOptions(projectId: string): Promise<ReferenceOption[]> {
  const out: ReferenceOption[] = [];
  const ers = await api.environmentReferenceSheet.listSheets(projectId);
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
    const isGlobal = Boolean(sheet.is_global || sheet.isGlobal);
    const thumbReady = sheet.thumbReady !== false;
    out.push({
      key: `environment:${id}`,
      assetId,
      name,
      defaultAlias: name,
      group: isGlobal ? "global" : "project",
      thumbAssetId: thumbReady ? assetId : "",
      thumbProjectId: String(sheet.thumbProjectId || sheet.projectId || ""),
      thumbReady,
    });
  }
  return out;
}

/** The open project's storyboard, when it has ordered Library frames. */
export async function loadStoryboardOptions(projectId: string): Promise<ReferenceOption[]> {
  const workspace = await api.storyboardStudio.workspace(projectId);
  const claimed = resolveStoryboardEnvironment(projectId, workspace);
  if (!claimed.ok) return [];
  const ids = claimed.candidate.frames.map((frame) => frame.assetId).join(",");
  const library = await api.library(projectId, { scope: "project", ids, limit: claimed.candidate.frames.length });
  const available = new Set(
    ((library?.items || []) as Array<{ id?: string }>).map((item) => String(item.id || "")).filter(Boolean),
  );
  const resolved = resolveStoryboardEnvironment(projectId, workspace, available);
  if (!resolved.ok) return [];
  const { candidate } = resolved;
  const first = candidate.frames[0];
  return [
    {
      key: `storyboard:${candidate.documentId}`,
      assetId: first.assetId,
      name: candidate.title,
      defaultAlias: candidate.title,
      group: "storyboard",
      thumbAssetId: first.assetId,
      thumbProjectId: projectId,
      thumbReady: true,
      storyboardId: candidate.documentId,
      frames: candidate.frames,
    },
  ];
}

/**
 * Build the grouped picker options for one image tab.
 *
 * Saved entities come from the creator registries. Library options are the
 * generic images the creator explicitly classified via Reference As for this
 * tab. An entity's bind asset is suppressed from the Library group so the
 * entity (Renkoka) appears, not its raw hero image (Renkoka Front) twice.
 */
export function groupReferenceOptions(
  entities: ReferenceOption[],
  libraryAssets: Asset[],
  kind: EntityKind,
): ReferenceOptionGroups {
  const entityAssetIds = new Set(
    entities.flatMap((option) => [option.assetId, ...(option.frames || []).map((frame) => frame.assetId)]),
  );
  const groups: ReferenceOptionGroups = { project: [], global: [], storyboard: [], library: [] };
  for (const option of entities) {
    if (option.group === "storyboard") groups.storyboard.push(option);
    else if (option.group === "global") groups.global.push(option);
    else groups.project.push(option);
  }
  for (const asset of libraryAssets) {
    if (!asset?.id) continue;
    if (entityAssetIds.has(asset.id)) continue;
    groups.library.push({
      key: `library:${asset.id}`,
      assetId: asset.id,
      name: libraryDisplayName(asset),
      defaultAlias: libraryDisplayName(asset),
      group: "library",
      thumbAssetId: asset.id,
      asset,
    });
  }
  const byName = (a: ReferenceOption, b: ReferenceOption) => a.name.localeCompare(b.name);
  groups.project.sort(byName);
  groups.global.sort(byName);
  groups.library.sort(byName);
  return groups;
}

export async function loadEntityOptions(projectId: string, kind: EntityKind): Promise<ReferenceOption[]> {
  try {
    if (kind === "character") return await loadCharacterOptions(projectId);
    if (kind === "prop") return await loadPropOptions(projectId);
    const [sheets, storyboards] = await Promise.all([
      loadEnvironmentOptions(projectId),
      loadStoryboardOptions(projectId).catch(() => []),
    ]);
    return [...sheets, ...storyboards];
  } catch {
    return [];
  }
}

export function emptyReferenceGroups(): ReferenceOptionGroups {
  return { project: [], global: [], storyboard: [], library: [] };
}

export { EMPTY_GROUPS };
