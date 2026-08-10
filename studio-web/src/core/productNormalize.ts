/** Central product-id normalization for Wave 4C Timeline rename. */

export const PRODUCT_DISPLAY = {
  timeline: {
    id: "timeline",
    name: "Timeline",
    fullName: "Timeline Generator",
    description: "Build and organize production timelines, scenes, shots, and sequences.",
  },
  magi: {
    id: "magi",
    name: "MAGI Editor",
    fullName: "MAGI Editor",
    description: "AI-native editing with MAGI Command, Actions, and Recipes.",
  },
  codirector: {
    id: "codirector",
    name: "Co-Director",
    fullName: "Co-Director",
    description: "Adept UI AI production assistant.",
  },
} as const;

export type ProductKind = "timeline" | "magi" | "codirector";

/** Map legacy Director product/workspace identifiers to Timeline. */
export function normalizeWorkspaceId(value: string | null | undefined): string | null {
  if (!value) return null;
  const v = value.trim().toLowerCase();
  if (!v) return null;
  if (v === "director" || v === "director-generator" || v === "director_workspace") {
    return "timeline";
  }
  return v;
}

export function normalizeProductKind(value: string | null | undefined): ProductKind | null {
  if (!value) return null;
  const v = value.trim().toLowerCase();
  if (v === "director" || v === "timeline" || v === "timeline-generator") return "timeline";
  if (v === "magi" || v === "magi-editor") return "magi";
  if (v === "codirector" || v === "co-director" || v === "co_director") return "codirector";
  return null;
}

/** Search terms that should resolve to a single Timeline product (not Director + Timeline). */
export function timelineSearchAliases(): readonly string[] {
  return ["timeline", "timeline generator", "director", "director generator", "open director"];
}

export function matchesTimelineSearch(query: string): boolean {
  const q = query.trim().toLowerCase();
  if (!q) return false;
  return timelineSearchAliases().some((a) => a.includes(q) || q.includes(a));
}
