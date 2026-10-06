/**
 * Journey 1 Image Generator authority selectors (management surface).
 * Character (@) multi / Props (%) multi / Environment (#) ONE / PoseCraft (~PoseCraft_) ONE.
 * Library picks become ~ chips. Dropdown source == autocomplete == active tags == referenceAssetIds.
 */
import { useCallback, useEffect, useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import { api } from "../../api";
import { isPoseCraftEnabled } from "../../core/featureFlags";
import { listSnapshots } from "../../posecraft/posecraftApi";
import type { PoseCraftSnapshot } from "../../posecraft/types";
import type { Asset } from "../../types";
import { sanitizeAlias } from "../../sceneReferences/referenceTokens";
import {
  extractApprovedProp,
  extractCharacterThumbAndCrs,
} from "../CoDirector/EnvironmentCreator/environmentCreatorPlanning";
import type { LibraryAsset } from "../CoDirector/library/assetModel";
import { getAssetName } from "../CoDirector/library/assetModel";
import { LibraryImagePickerModal } from "../LibraryImagePickerModal";
import { isReferenceImage, referenceRole } from "./ReferenceBrowser";
import type { CisAuthorityKind, CisAuthorityRef } from "./cisAuthorityTypes";
import { groupScopeItems, readIsGlobal, owningProjectId } from "../../creatorScope";
import {
  applyAuthoritySelection,
  poseCraftChip,
  type IgCatalogOption,
} from "./igPromptTokens";

export type { CisAuthorityKind, CisAuthorityRef } from "./cisAuthorityTypes";

type Option = {
  key: string;
  kind: CisAuthorityKind;
  assetId: string;
  name: string;
  chip: string;
  disabled?: boolean;
  hint?: string;
  /** Option label shown inside the dropdown (may differ from chip). */
  label: string;
  projectId?: string;
  isGlobal?: boolean;
};

function aliasName(raw: string): string {
  return sanitizeAlias(raw) || "Ref";
}

function optionToRef(o: Option): CisAuthorityRef {
  return {
    key: o.key,
    kind: o.kind,
    assetId: o.assetId,
    name: o.name,
    chip: o.chip,
  };
}

function asRecordRows(payload: unknown, keys: string[]): Record<string, unknown>[] {
  if (Array.isArray(payload)) return payload as Record<string, unknown>[];
  if (payload && typeof payload === "object") {
    const obj = payload as Record<string, unknown>;
    for (const key of keys) {
      const val = obj[key];
      if (Array.isArray(val)) return val as Record<string, unknown>[];
    }
  }
  return [];
}

function asSnapshots(payload: unknown): PoseCraftSnapshot[] {
  if (Array.isArray(payload)) return payload as PoseCraftSnapshot[];
  if (payload && typeof payload === "object") {
    const obj = payload as Record<string, unknown>;
    for (const key of ["snapshots", "items", "data"]) {
      const val = obj[key];
      if (Array.isArray(val)) return val as PoseCraftSnapshot[];
    }
  }
  return [];
}

/** Prefer approved CRS; then portrait/identity image; only disable when no image at all. */
async function resolveCharacterOption(
  projectId: string,
  row: Record<string, unknown>,
): Promise<Option | null> {
  const base = extractCharacterThumbAndCrs(row);
  if (!base.characterId) return null;

  let crsAssetId = base.crsAssetId;
  let thumbAssetId = base.thumbAssetId;

  // listCharacterProfiles does not include CRS/portrait asset ids — resolve them.
  if (!crsAssetId) {
    try {
      const crs = await api.getCharacterCrs(projectId, base.characterId);
      const approved = String(
        (crs as { approved_reference_asset_id?: string; approvedReferenceAssetId?: string })
          ?.approved_reference_asset_id ||
          (crs as { approvedReferenceAssetId?: string })?.approvedReferenceAssetId ||
          "",
      ).trim();
      if (approved) crsAssetId = approved;
    } catch {
      /* keep falling through */
    }
  }

  if (!crsAssetId && !thumbAssetId) {
    try {
      const refs = await api.listCharacterReferences(projectId, base.characterId);
      const items = asRecordRows(refs, ["items"]);
      const approvedHero = items.find((r) => {
        const role = String(r.reference_role || "").toLowerCase();
        const status = String(r.approval_status || "").toLowerCase();
        return (
          (role === "hero_identity" || role === "hero_portrait") &&
          status === "approved" &&
          Boolean(r.asset_id)
        );
      });
      const anyIdentity = items.find((r) => {
        const role = String(r.reference_role || "").toLowerCase();
        return (
          (role === "hero_identity" ||
            role === "hero_portrait" ||
            role === "reference_image" ||
            role === "portrait") &&
          Boolean(r.asset_id)
        );
      });
      const pick = approvedHero || anyIdentity;
      const assetId = String(pick?.asset_id || "").trim();
      if (assetId) {
        const role = String(pick?.reference_role || "").toLowerCase();
        const status = String(pick?.approval_status || "").toLowerCase();
        if (
          status === "approved" &&
          (role === "hero_identity" || role === "hero_portrait")
        ) {
          crsAssetId = assetId;
        } else {
          thumbAssetId = assetId;
        }
      }
    } catch {
      /* no image */
    }
  }

  const name = base.name;
  const assetId = crsAssetId || thumbAssetId || "";
  const hasCrs = Boolean(crsAssetId);
  const selectable = Boolean(assetId);
  return {
    key: `character:${base.characterId}`,
    kind: "character",
    assetId,
    name,
    chip: `@${aliasName(name)}`,
    disabled: !selectable,
    hint: hasCrs ? "CRS" : assetId ? "Portrait / identity image" : "No identity image",
    label: selectable
      ? hasCrs
        ? `@${aliasName(name)}`
        : `@${aliasName(name)} (portrait)`
      : `${name} (no image)`,
    projectId: owningProjectId(row),
    isGlobal: readIsGlobal(row),
  };
}

function chipForLibraryAsset(asset: LibraryAsset): { kind: CisAuthorityKind; chip: string } {
  const role = referenceRole(asset).toLowerCase();
  const name = aliasName(getAssetName(asset));
  if (role === "character") return { kind: "character", chip: `@${name}` };
  if (role === "prop") return { kind: "prop", chip: `%${name}` };
  if (role === "location") return { kind: "environment", chip: `#${name}` };
  return { kind: "other", chip: `~${name}` };
}

function toPickerImages(items: LibraryAsset[]): Asset[] {
  return items.filter(isReferenceImage).map((a) => ({
    id: a.id,
    project_id: a.project_id || "",
    tag: a.tag || a.title || "",
    kind: a.kind || "image",
    filename: a.filename || a.tag || a.title || a.id,
    path: "",
    comfy_name: "",
    created_at: a.created_at || "",
  }));
}

export function AuthorityReferencePanel({
  projectId,
  libraryItems,
  selected,
  onChange,
  onGoLibraryPoseCraft,
  onCatalogsChange,
}: {
  projectId: string;
  libraryItems: LibraryAsset[];
  selected: CisAuthorityRef[];
  onChange: (next: CisAuthorityRef[]) => void;
  /** Optional: open Library filtered to PoseCraft (canonical browse path). */
  onGoLibraryPoseCraft?: () => void;
  /** Shared authority catalogs for prompt autocomplete (same source as dropdowns). */
  onCatalogsChange?: (catalogs: IgCatalogOption[]) => void;
}) {
  const { t } = useTranslation(["imageGenerator", "common"]);
  const [charOpts, setCharOpts] = useState<Option[]>([]);
  const [propOpts, setPropOpts] = useState<Option[]>([]);
  const [ersOpts, setErsOpts] = useState<Option[]>([]);
  const [poseOpts, setPoseOpts] = useState<Option[]>([]);
  const [loadErr, setLoadErr] = useState<string | null>(null);
  const [libraryOpen, setLibraryOpen] = useState(false);

  const loadCatalogs = useCallback(async () => {
    if (!projectId) {
      setCharOpts([]);
      setPropOpts([]);
      setErsOpts([]);
      setPoseOpts([]);
      setLoadErr("No project selected.");
      return;
    }
    setLoadErr(null);
    const errors: string[] = [];

    const charsP = api.listCharacterProfiles(projectId).catch((e: unknown) => {
      errors.push(`Characters: ${e instanceof Error ? e.message : String(e)}`);
      return { items: [] as Record<string, unknown>[] };
    });
    const propsP = api.propCreator.list(projectId, false).catch((e: unknown) => {
      errors.push(`Props: ${e instanceof Error ? e.message : String(e)}`);
      return { props: [] as Record<string, unknown>[] };
    });
    const ersP = api.environmentReferenceSheet.listSheets(projectId).catch((e: unknown) => {
      errors.push(`Environment: ${e instanceof Error ? e.message : String(e)}`);
      return { sheets: [] };
    });
    const snapsP = isPoseCraftEnabled()
      ? listSnapshots(projectId).catch((e: unknown) => {
          errors.push(`Snapshots: ${e instanceof Error ? e.message : String(e)}`);
          return [] as PoseCraftSnapshot[];
        })
      : Promise.resolve([] as PoseCraftSnapshot[]);

    try {
      const [charsRes, propsRes, ersRes, snaps] = await Promise.all([charsP, propsP, ersP, snapsP]);

      const charRows = asRecordRows(charsRes, ["items"]);
      const resolvedChars = (
        await Promise.all(charRows.map((row) => resolveCharacterOption(projectId, row)))
      ).filter((o): o is Option => Boolean(o));
      setCharOpts(resolvedChars);

      const propRows = asRecordRows(propsRes, ["props", "items"]);
      setPropOpts(
        propRows
          .map((raw) => ({ raw, extracted: extractApprovedProp(raw) }))
          .filter((row): row is { raw: Record<string, unknown>; extracted: NonNullable<ReturnType<typeof extractApprovedProp>> } =>
            Boolean(row.extracted?.propId),
          )
          .map(({ raw, extracted }) => {
            const assetId = extracted.prsAssetId || extracted.thumbAssetId || "";
            const selectable = Boolean(assetId);
            return {
              key: `prop:${extracted.propId}`,
              kind: "prop" as const,
              assetId,
              name: extracted.name,
              chip: `%${aliasName(extracted.name)}`,
              disabled: !selectable,
              hint: extracted.prsAssetId ? "PRS" : assetId ? "Prop image" : "No prop image",
              label: selectable ? `%${aliasName(extracted.name)}` : `${extracted.name} (no image)`,
              projectId: owningProjectId(raw),
              isGlobal: readIsGlobal(raw),
            };
          }),
      );

      const sheets = asRecordRows(ersRes, ["sheets", "items"]) as Array<
        Record<string, unknown> & {
          sheetId?: string;
          name?: string;
          status?: string;
          ers_composite_asset_id?: string | null;
        }
      >;
      // Prefer approved sheets, but keep any sheet that already has a composite
      // image — status-only filtering was emptying the dropdown while assets existed.
      const ersMapped = sheets
        .map((s) => {
          const sheetId = String(s.sheetId || s.id || "").trim();
          if (!sheetId) return null;
          const assetId = String(s.ers_composite_asset_id || "").trim();
          const status = String(s.status || "").toLowerCase();
          const approved = status === "approved";
          const name = String(s.name || "Environment").trim() || "Environment";
          return {
            key: `environment:${sheetId}`,
            kind: "environment" as const,
            assetId,
            name,
            chip: `#${aliasName(name)}`,
            disabled: !assetId,
            hint: approved
              ? "Approved ERS"
              : assetId
                ? `ERS (${status || "ready"})`
                : "No composite asset",
            label: assetId
              ? approved
                ? `#${aliasName(name)}`
                : `#${aliasName(name)} (${status || "draft"})`
              : `${name} (no composite)`,
            projectId: owningProjectId(s),
            isGlobal: readIsGlobal(s),
            _approved: approved,
          };
        })
        .filter((o): o is NonNullable<typeof o> => Boolean(o && o.assetId));
      ersMapped.sort((a, b) => Number(b._approved) - Number(a._approved));
      setErsOpts(
        ersMapped.map(({ _approved: _a, ...opt }) => {
          void _a;
          return opt;
        }),
      );

      setPoseOpts(
        asSnapshots(snaps)
          .filter((snap) => Boolean(snap.imageAssetId))
          .map((snap) => ({
            key: `posecraft:${snap.snapshotId}`,
            kind: "posecraft" as const,
            assetId: snap.imageAssetId,
            name: snap.name || snap.snapshotId,
            chip: poseCraftChip(snap.name || snap.snapshotId),
            hint: "Staging guidance (not identity)",
            label: poseCraftChip(snap.name || snap.snapshotId),
          })),
      );

      if (errors.length) setLoadErr(errors.join(" · "));
    } catch (e: unknown) {
      setLoadErr(e instanceof Error ? e.message : String(e));
    }
  }, [projectId]);

  useEffect(() => {
    void loadCatalogs();
  }, [loadCatalogs]);

  useEffect(() => {
    if (!onCatalogsChange) return;
    const flat: IgCatalogOption[] = [...charOpts, ...propOpts, ...ersOpts, ...poseOpts];
    onCatalogsChange(flat);
  }, [charOpts, propOpts, ersOpts, poseOpts, onCatalogsChange]);

  const selectedKeys = useMemo(() => new Set(selected.map((s) => s.key)), [selected]);
  const selectedAssetIds = useMemo(() => new Set(selected.map((s) => s.assetId)), [selected]);
  const pickerImages = useMemo(() => toPickerImages(libraryItems), [libraryItems]);

  /**
   * Compact native dropdown. Multi kinds append to chips; Environment replaces its group.
   * Select resets to placeholder after pick so the control stays a true dropdown.
   */
  const renderDropdown = (
    label: string,
    testId: string,
    options: Option[],
    placeholder: string,
    multi = true,
  ) => {
    const usable = options.filter((o) => !o.disabled && o.assetId);
    const empty = !options.length;

    return (
      <div className="cis-auth-ref__field" data-testid={testId}>
        <label htmlFor={`${testId}-select`}>{label}</label>
        <select
          id={`${testId}-select`}
          className="cis-auth-ref__select"
          value=""
          aria-label={label}
          disabled={false}
          onChange={(e) => {
            const key = e.target.value;
            e.target.value = "";
            if (!key) return;
            const opt = options.find((o) => o.key === key);
            if (!opt || opt.disabled || !opt.assetId) return;
            const applied = applyAuthoritySelection(selected, optionToRef(opt));
            onChange(applied.refs);
          }}
        >
          <option value="">
            {empty ? t("imageGenerator:refNoneAvailable") : placeholder}
          </option>
          {!empty &&
            (() => {
              const grouped = groupScopeItems(options, projectId, (o) => o.projectId || "");
              const renderOpt = (o: Option) => {
                const already = selectedKeys.has(o.key);
                const disabled = Boolean(o.disabled || !o.assetId || (multi && already));
                return (
                  <option key={o.key} value={o.key} disabled={disabled} title={o.hint}>
                    {already ? `✓ ${o.label}` : o.label}
                  </option>
                );
              };
              if (!grouped.global.length) return options.map(renderOpt);
              return (
                <>
                  <optgroup label="Project">{grouped.project.map(renderOpt)}</optgroup>
                  <optgroup label="Global">{grouped.global.map(renderOpt)}</optgroup>
                </>
              );
            })()}
        </select>
        {!empty && !usable.length ? (
          <p className="muted tiny">{t("imageGenerator:refNoUsableImages")}</p>
        ) : null}
      </div>
    );
  };

  return (
    <section className="cis-auth-refs" data-testid="cis-authority-references">
      <div className="cis-auth-refs__header">
        <h3>{t("imageGenerator:referencesSection")}</h3>
        <span className="muted tiny">{t("imageGenerator:referencesHint")}</span>
      </div>
      {loadErr ? <p className="pill warn">{loadErr}</p> : null}
      <div className="cis-auth-refs__grid">
        {renderDropdown(
          t("imageGenerator:refCharacterAdd", { defaultValue: "+ Add Character" }),
          "cis-ref-character",
          charOpts,
          t("imageGenerator:refSelectCharacter", { defaultValue: "+ Add Character" }),
          true,
        )}
        {renderDropdown(
          t("imageGenerator:refPropsAdd", { defaultValue: "+ Add Prop" }),
          "cis-ref-props",
          propOpts,
          t("imageGenerator:refSelectProp", { defaultValue: "+ Add Prop" }),
          true,
        )}
        {renderDropdown(
          t("imageGenerator:refEnvironment"),
          "cis-ref-environment",
          ersOpts,
          t("imageGenerator:refSelectEnvironment", { defaultValue: "Select Environment Reference" }),
          false,
        )}
        {isPoseCraftEnabled() ? (
        <div className="cis-auth-ref__field cis-auth-ref__field--pose" data-testid="cis-ref-posecraft-wrap">
          {renderDropdown(
            t("imageGenerator:refPoseCraft"),
            "cis-ref-posecraft",
            poseOpts,
            t("imageGenerator:refSelectPoseCraft", { defaultValue: "Select snapshot" }),
            false,
          )}
          <p className="muted tiny">{t("imageGenerator:refPoseCraftHint")}</p>
          {onGoLibraryPoseCraft ? (
            <button type="button" className="ghost tiny" onClick={onGoLibraryPoseCraft}>
              {t("imageGenerator:refPoseCraftOpen")}
            </button>
          ) : null}
        </div>
        ) : null}
        <div className="cis-auth-ref__field" data-testid="cis-ref-library">
          <label>{t("imageGenerator:refLibrary")}</label>
          <button
            type="button"
            className="ghost cis-auth-ref__library-btn"
            data-testid="cis-ref-library-pick"
            onClick={() => setLibraryOpen(true)}
          >
            {t("imageGenerator:refLibraryPick", { defaultValue: "Choose from Library" })}
          </button>
          <p className="muted tiny">
            {t("imageGenerator:refLibraryHint", {
              defaultValue:
                "Picked images become ~GenericImage (or @/%/# when the Library asset already carries that role).",
            })}
          </p>
        </div>
      </div>

      <LibraryImagePickerModal
        images={pickerImages}
        open={libraryOpen}
        title={t("imageGenerator:refLibraryPickTitle", {
          defaultValue: "Choose a Library image reference",
        })}
        confirmLabel={t("imageGenerator:refLibraryConfirm", { defaultValue: "Use as reference" })}
        onCancel={() => setLibraryOpen(false)}
        onPick={(assetId) => {
          setLibraryOpen(false);
          if (!assetId) return;
          if (selectedAssetIds.has(assetId)) return;
          const asset = libraryItems.find((a) => a.id === assetId);
          const name = asset ? getAssetName(asset) : assetId.slice(0, 8);
          const tagged = asset
            ? chipForLibraryAsset(asset)
            : { kind: "other" as const, chip: `~${aliasName(name)}` };
          const nextRef: CisAuthorityRef = {
            key: `library:${assetId}`,
            kind: tagged.kind,
            assetId,
            name,
            chip: tagged.chip,
          };
          onChange(applyAuthoritySelection(selected, nextRef).refs);
        }}
      />

    </section>
  );
}

/** Flatten authority selections into unique asset IDs for generation. */
export function authorityRefAssetIds(refs: CisAuthorityRef[]): string[] {
  return Array.from(new Set(refs.map((r) => r.assetId).filter(Boolean)));
}

export function mergeAssetIdsIntoAuthority(
  refs: CisAuthorityRef[],
  assetIds: string[],
  kind: CisAuthorityKind = "other",
): CisAuthorityRef[] {
  const have = new Set(refs.map((r) => r.assetId));
  const extra = assetIds
    .filter((id) => id && !have.has(id))
    .map((id) => ({
      key: `${kind}:${id}`,
      kind,
      assetId: id,
      name: id.slice(0, 8),
      chip: kind === "posecraft" ? poseCraftChip(id.slice(0, 8)) : `~${aliasName(id.slice(0, 8))}`,
    }));
  return [...refs, ...extra];
}
