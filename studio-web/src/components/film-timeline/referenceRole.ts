import type { Asset } from "../../types";

export type ImageRole = "character" | "prop" | "environment";
export type ReferenceTab = ImageRole | "video" | "audio";

const IMAGE_ROLES: ImageRole[] = ["character", "prop", "environment"];

const ROLE_LABEL: Record<ImageRole, string> = {
  character: "Character",
  prop: "Prop",
  environment: "Environment",
};

const SAVED_LABEL: Record<ImageRole, string> = {
  character: "Saved Character",
  prop: "Saved Prop",
  environment: "Saved Environment",
};

export interface ReferenceMenuOption {
  id: string;
  label: string;
  approvedAs: ImageRole | null;
}

export interface ReferencePresentation {
  effectiveRole: ReferenceTab | null;
  source: "explicit" | "creator" | "override" | "media" | "none";
  creatorRole: ImageRole | null;
  badge: string | null;
  note: string | null;
  menuLabel: "Reference As" | "Change" | null;
  options: ReferenceMenuOption[];
  offersRemoveReference: boolean;
  offersResetToSavedRole: boolean;
}

function imageRole(value: unknown): ImageRole | null {
  const role = String(value || "").toLowerCase();
  return role === "character" || role === "prop" || role === "environment" ? role : null;
}

function tabRole(value: unknown): ReferenceTab | null {
  const role = String(value || "").toLowerCase();
  if (role === "character" || role === "prop" || role === "environment" || role === "video" || role === "audio") {
    return role;
  }
  return null;
}

export function referencePresentation(asset: Pick<Asset, "kind" | "effectiveReferenceRole" | "referenceRoleSource" | "creatorReferenceRole">): ReferencePresentation {
  const kind = String(asset.kind || "").toLowerCase();
  const serverRole = tabRole(asset.effectiveReferenceRole);
  const creator = imageRole(asset.creatorReferenceRole);
  const sourceRaw = String(asset.referenceRoleSource || "").toLowerCase();

  if (kind === "video" || kind === "audio" || sourceRaw === "media") {
    const media = kind === "audio" || serverRole === "audio" ? "audio" : "video";
    return {
      effectiveRole: media,
      source: "media",
      creatorRole: creator,
      badge: media === "audio" ? "Audio" : "Video",
      note: null,
      menuLabel: null,
      options: [],
      offersRemoveReference: false,
      offersResetToSavedRole: false,
    };
  }

  const effective = imageRole(serverRole);
  let source: ReferencePresentation["source"] = "none";
  if (sourceRaw === "explicit" || sourceRaw === "creator" || sourceRaw === "override" || sourceRaw === "none") {
    source = sourceRaw;
  } else if (effective && creator && effective !== creator) {
    source = "override";
  } else if (effective && creator) {
    source = "creator";
  } else if (effective) {
    source = "explicit";
  }

  if (!effective || source === "none") {
    return {
      effectiveRole: null,
      source: "none",
      creatorRole: creator,
      badge: null,
      note: null,
      menuLabel: "Reference As",
      options: IMAGE_ROLES.map((role) => ({ id: `set-${role}`, label: ROLE_LABEL[role], approvedAs: role })),
      offersRemoveReference: false,
      offersResetToSavedRole: false,
    };
  }

  const others = IMAGE_ROLES.filter((role) => role !== effective);
  if (source === "creator") {
    return {
      effectiveRole: effective,
      source,
      creatorRole: creator || effective,
      badge: ROLE_LABEL[effective],
      note: SAVED_LABEL[creator || effective],
      menuLabel: "Change",
      options: others.map((role) => ({ id: `set-${role}`, label: ROLE_LABEL[role], approvedAs: role })),
      offersRemoveReference: false,
      offersResetToSavedRole: false,
    };
  }

  if (source === "override" && creator) {
    const remaining = IMAGE_ROLES.filter((role) => role !== effective && role !== creator);
    return {
      effectiveRole: effective,
      source,
      creatorRole: creator,
      badge: ROLE_LABEL[effective],
      note: `Override of ${SAVED_LABEL[creator]}`,
      menuLabel: "Change",
      options: [
        ...remaining.map((role) => ({ id: `set-${role}`, label: ROLE_LABEL[role], approvedAs: role })),
        { id: "reset", label: "Reset to Saved Role", approvedAs: null },
      ],
      offersRemoveReference: false,
      offersResetToSavedRole: true,
    };
  }

  return {
    effectiveRole: effective,
    source: "explicit",
    creatorRole: creator,
    badge: ROLE_LABEL[effective],
    note: null,
    menuLabel: "Change",
    options: [
      ...others.map((role) => ({ id: `set-${role}`, label: ROLE_LABEL[role], approvedAs: role })),
      { id: "clear", label: "Remove Reference", approvedAs: null },
    ],
    offersRemoveReference: true,
    offersResetToSavedRole: false,
  };
}

export function assetsForReferenceTab(assets: Asset[], kind: ReferenceTab): Asset[] {
  return assets.filter((asset) => referencePresentation(asset).effectiveRole === kind);
}

/**
 * Library images the creator explicitly classified via Reference As for this tab.
 * Creator-sourced raw images (a saved Character's hero still) are excluded — the
 * saved ENTITY is the picker option, not every image associated with that entity.
 * Only an explicit Reference As classification lists a generic image here.
 */
export function explicitLibraryAssetsForTab(assets: Asset[], kind: ReferenceTab): Asset[] {
  return assets.filter((asset) => {
    const view = referencePresentation(asset);
    if (view.effectiveRole !== kind) return false;
    return view.source === "explicit" || view.source === "override";
  });
}
