import type { Project, Asset } from "../../types";

export const CAMPAIGN_TYPES = [
  {
    id: "launch",
    label: "Product Launch",
    blurb: "Hero key art, packaging moments, and reveal visuals.",
  },
  {
    id: "social",
    label: "Social Campaign",
    blurb: "Short-form promos, story cards, and feed-ready cutdowns.",
  },
  {
    id: "seasonal",
    label: "Seasonal Drop",
    blurb: "Timed campaigns with giftable, event, or tentpole styling.",
  },
  {
    id: "retail",
    label: "Retail Promo",
    blurb: "Shelf-ready sell sheets, offers, bundles, and display art.",
  },
] as const;

export const VISUAL_DIRECTIONS = [
  {
    id: "hero",
    label: "Hero Spotlight",
    blurb: "Polished, premium, central subject treatment.",
  },
  {
    id: "lifestyle",
    label: "Lifestyle Story",
    blurb: "Real-world context with warmth and lived-in energy.",
  },
  {
    id: "graphic",
    label: "Graphic Punch",
    blurb: "Bold contrast, shapes, and typography-led framing.",
  },
  {
    id: "editorial",
    label: "Editorial Luxe",
    blurb: "Fashion-forward framing with artful negative space.",
  },
] as const;

export const COMPOSITION_OPTIONS = ["Centered hero", "Rule of thirds", "Close crop", "Wide story frame"] as const;
export const BACKGROUND_OPTIONS = ["Studio sweep", "Soft gradient", "Lifestyle set", "Transparent cutout"] as const;
export const FORMAT_OPTIONS = ["Square 1:1", "Portrait 4:5", "Story 9:16", "Landscape 16:9"] as const;
export const TYPOGRAPHY_TEMPLATES = ["Hero headline", "Product callout", "Offer stack", "Quiet caption"] as const;
export const RESULT_LANES = ["concepts", "variations", "formats", "approved"] as const;

export type CampaignTypeId = (typeof CAMPAIGN_TYPES)[number]["id"];
export type VisualDirectionId = (typeof VISUAL_DIRECTIONS)[number]["id"];
export type ResultLane = (typeof RESULT_LANES)[number];

export interface BrandStudioBrandKit {
  source: "manual" | "production_bible" | "library";
  logoAssetId: string;
  productAssetId: string;
  colorPalette: string[];
  requiredWording: string;
  productName: string;
  typography: string;
  styleNotes: string;
  bibleSummary: string;
  inheritedEntityKeys: string[];
  inheritedAt?: string | null;
}

export interface BrandStudioCampaign {
  id: string;
  name: string;
  campaignType: CampaignTypeId;
  brief: string;
  visualDirection: VisualDirectionId;
  composition: string;
  background: string;
  heroFormat: string;
  campaignFormats: string[];
  typographyTemplate: string;
  advancedNotes: string;
  resultLane: ResultLane;
  approvedAssetIds: string[];
  latestProposalId?: string | null;
  lastGeneratedAt?: string | null;
  brandKit: BrandStudioBrandKit;
}

export interface BrandStudioResult {
  id: string;
  assetId?: string;
  jobId?: string;
  lane: ResultLane;
  format: string;
  title: string;
  status: "queued" | "ready";
  createdAt?: string | null;
}

export interface BrandCheckSummary {
  ready: number;
  total: number;
  items: { label: string; ok: boolean; note: string }[];
}

export interface BrandStudioState {
  version: 1;
  activeCampaign: BrandStudioCampaign;
  results: BrandStudioResult[];
}

function safeParse<T>(raw: string | undefined, fallback: T): T {
  if (!raw) return fallback;
  try {
    return JSON.parse(raw) as T;
  } catch {
    return fallback;
  }
}

function nowStamp() {
  return new Date().toISOString();
}

export function createDefaultCampaign(project: Project): BrandStudioCampaign {
  return {
    id: `brand-campaign-${project.id}`,
    name: `${project.name || "Untitled Project"} Campaign`,
    campaignType: "launch",
    brief: "Create a brand-safe hero visual with premium lighting and clean product focus.",
    visualDirection: "hero",
    composition: COMPOSITION_OPTIONS[0],
    background: BACKGROUND_OPTIONS[0],
    heroFormat: FORMAT_OPTIONS[0],
    campaignFormats: [FORMAT_OPTIONS[0], FORMAT_OPTIONS[1], FORMAT_OPTIONS[2]],
    typographyTemplate: TYPOGRAPHY_TEMPLATES[0],
    advancedNotes: "",
    resultLane: "concepts",
    approvedAssetIds: [],
    latestProposalId: null,
    lastGeneratedAt: null,
    brandKit: {
      source: "manual",
      logoAssetId: "",
      productAssetId: "",
      colorPalette: ["#0d9488", "#f8fafc", "#111827"],
      requiredWording: "",
      productName: "",
      typography: "Modern sans serif with confident, cinematic spacing.",
      styleNotes: "",
      bibleSummary: "",
      inheritedEntityKeys: [],
      inheritedAt: null,
    },
  };
}

export function parseBrandStudioState(project: Project): BrandStudioState {
  const settings = safeParse<Record<string, unknown>>(project.settings_json, {});
  const saved = (settings.brandStudio || null) as Partial<BrandStudioState> | null;
  const defaults = createDefaultCampaign(project);
  const activeCampaign = {
    ...defaults,
    ...(saved?.activeCampaign || {}),
    brandKit: {
      ...defaults.brandKit,
      ...((saved?.activeCampaign?.brandKit as Partial<BrandStudioBrandKit> | undefined) || {}),
    },
    campaignFormats:
      Array.isArray(saved?.activeCampaign?.campaignFormats) && saved?.activeCampaign?.campaignFormats.length
        ? (saved.activeCampaign?.campaignFormats as string[])
        : defaults.campaignFormats,
    approvedAssetIds: Array.isArray(saved?.activeCampaign?.approvedAssetIds)
      ? (saved?.activeCampaign?.approvedAssetIds as string[])
      : [],
  };
  return {
    version: 1,
    activeCampaign,
    results: Array.isArray(saved?.results) ? (saved?.results as BrandStudioResult[]) : [],
  };
}

export function serializeBrandStudioState(settingsJson: string | undefined, state: BrandStudioState): string {
  const settings = safeParse<Record<string, unknown>>(settingsJson, {});
  return JSON.stringify(
    {
      ...settings,
      brandStudio: {
        version: 1,
        activeCampaign: state.activeCampaign,
        results: state.results,
      },
    },
    null,
    2,
  );
}

export function parseAssetMeta(asset: Asset): Record<string, unknown> {
  return safeParse<Record<string, unknown>>(asset.prompt_meta_json, {});
}

function lanePriority(value: string | undefined): ResultLane {
  if (value === "approved") return "approved";
  if (value === "variations") return "variations";
  if (value === "formats") return "formats";
  return "concepts";
}

export function collectBrandResults(project: Project, campaign: BrandStudioCampaign, savedResults: BrandStudioResult[]) {
  const savedByAsset = new Map(savedResults.filter((item) => item.assetId).map((item) => [item.assetId as string, item]));
  const generatedAssets = (project.assets || [])
    .filter((asset) => asset.kind === "image")
    .map((asset) => {
      const meta = parseAssetMeta(asset);
      const brandStudio = (meta.brandStudio || {}) as Record<string, unknown>;
      const brandLock = (meta.brandLock || {}) as Record<string, unknown>;
      if (!brandStudio.campaignId && !brandLock.requiredWording && meta.op !== "brand_generate" && !meta.m32aBrand) {
        return null;
      }
      const saved = savedByAsset.get(asset.id);
      const lane = campaign.approvedAssetIds.includes(asset.id)
        ? "approved"
        : saved?.lane || lanePriority(typeof brandStudio.resultLane === "string" ? brandStudio.resultLane : undefined);
      return {
        id: saved?.id || asset.id,
        assetId: asset.id,
        lane,
        format: String(brandStudio.heroFormat || brandStudio.format || campaign.heroFormat || "Square 1:1"),
        title: saved?.title || String(brandStudio.title || asset.tag || asset.filename || "Brand artwork"),
        status: "ready" as const,
        createdAt: asset.created_at,
      };
    })
    .filter(Boolean) as BrandStudioResult[];

  const queued = savedResults.filter((item) => !item.assetId);
  return [...generatedAssets, ...queued].sort((a, b) => String(b.createdAt || "").localeCompare(String(a.createdAt || "")));
}

export function buildBrandCheck(campaign: BrandStudioCampaign): BrandCheckSummary {
  const items = [
    {
      label: "Logo lock",
      ok: Boolean(campaign.brandKit.logoAssetId),
      note: campaign.brandKit.logoAssetId ? "Brand mark selected from this project library." : "Choose a logo from the project library.",
    },
    {
      label: "Product / packaging lock",
      ok: Boolean(campaign.brandKit.productAssetId),
      note: campaign.brandKit.productAssetId
        ? "Primary product reference is pinned."
        : "Pick a hero product or package to keep the silhouette trustworthy.",
    },
    {
      label: "Required copy",
      ok: Boolean(campaign.brandKit.requiredWording.trim()),
      note: campaign.brandKit.requiredWording.trim()
        ? "Locked copy is ready for finishing."
        : "Add headline, offer, or legal wording that cannot drift.",
    },
    {
      label: "Palette",
      ok: campaign.brandKit.colorPalette.length >= 2,
      note:
        campaign.brandKit.colorPalette.length >= 2
          ? "Color swatches are loaded into the campaign."
          : "Add at least two swatches for brand-safe styling.",
    },
    {
      label: "Canon guidance",
      ok: Boolean(campaign.brandKit.bibleSummary.trim()),
      note: campaign.brandKit.bibleSummary.trim()
        ? "Production Bible guidance has been inherited read-only."
        : "Optional: import story, world, and style notes from the Production Bible.",
    },
  ];
  const ready = items.filter((item) => item.ok).length;
  return { ready, total: items.length, items };
}

export function assetLabel(asset: Asset): string {
  return asset.tag || asset.filename || "Project asset";
}

export function pickBrandImages(project: Project): Asset[] {
  return (project.assets || []).filter((asset) => asset.kind === "image");
}

export function upsertQueuedResults(
  current: BrandStudioResult[],
  entries: Array<Omit<BrandStudioResult, "id" | "status" | "createdAt">>,
): BrandStudioResult[] {
  const createdAt = nowStamp();
  const queued = entries.map((entry, index) => ({
    id: `${entry.jobId || entry.assetId || entry.format}-${index}-${Date.now()}`,
    status: "queued" as const,
    createdAt,
    ...entry,
  }));
  return [...queued, ...current];
}
