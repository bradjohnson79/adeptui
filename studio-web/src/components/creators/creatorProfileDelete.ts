export type CreatorEntityType = "character" | "prop" | "environment";

export type CreatorDeleteUsage = {
  projectId: string;
  projectName: string;
  kind: string;
  label?: string;
  bindingId?: string;
  alias?: string;
};

export type CreatorDeletePreview = {
  entityType: CreatorEntityType;
  entityId: string;
  name: string;
  isGlobal: boolean;
  owningProjectId: string;
  usage: CreatorDeleteUsage[];
  usageCount: number;
  projectCount: number;
  libraryAssetsKept: boolean;
  canDelete: boolean;
  blockReason?: string;
};

export type DeleteConfirmCopy = {
  title: string;
  body: string;
  usageSummary?: string;
  primaryLabel: string;
};

export function buildDeleteCopy(
  entityType: CreatorEntityType,
  preview: CreatorDeletePreview,
): DeleteConfirmCopy {
  const typeLabel =
    entityType === "character"
      ? "Character"
      : entityType === "prop"
        ? "Prop"
        : "Environment";
  const name = preview.name || `this ${typeLabel.toLowerCase()}`;
  const scopeDesc = preview.isGlobal
    ? `This is a Global ${typeLabel} profile. Deleting it will remove the canonical profile from Adept UI and may affect every project currently using this Global profile. Existing scenes, references, and creator assignments that depend on it may be affected.`
    : `This is a local ${typeLabel} profile assigned to this project. Deleting it will remove this profile and its creator data from this project. Existing scenes or assets that reference this profile may be affected.`;
  const primaryLabel = preview.isGlobal
    ? `Delete Global ${typeLabel}`
    : `Delete ${typeLabel}`;

  let usageSummary: string | undefined;
  if (preview.usageCount > 0) {
    const projectWord = preview.projectCount === 1 ? "project" : "projects";
    const sceneWord = preview.usageCount === 1 ? "scene" : "scenes";
    usageSummary = `This profile is currently referenced by ${preview.usageCount} ${sceneWord} across ${preview.projectCount} ${projectWord}.${
      preview.isGlobal ? " It will disappear from every project that uses it." : ""
    }`;
  }

  const body = [
    `Delete ${name}?`,
    scopeDesc,
    "This action cannot be undone.",
    usageSummary,
  ]
    .filter(Boolean)
    .join("\n\n");

  return { title: `Delete ${name}?`, body, usageSummary, primaryLabel };
}

export function isGlobalDirty(
  persistedIsGlobal: boolean,
  currentIsGlobal: boolean,
): boolean {
  return persistedIsGlobal !== currentIsGlobal;
}
