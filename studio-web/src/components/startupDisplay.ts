/**
 * Startup screen presentation. Boot certification stays the readiness authority.
 * This module only decides what the launch screen says and how rows are grouped.
 */
import type { SystemRow, SystemState } from "./startupSnapshot";

export type BootCheckView = {
  id: string;
  system: string;
  check: string;
  result: string;
  detail: string;
  required?: boolean;
};

export type DisplayBadge =
  | "ONLINE"
  | "PASS"
  | "ON DEMAND"
  | "OPTIONAL"
  | "MISSING"
  | "FAILED"
  | "STARTING"
  | "CHECKING";

export type DisplaySectionId = "core" | "production" | "optional";

export type DisplayRow = {
  id: string;
  label: string;
  badge: DisplayBadge;
  section: DisplaySectionId;
};

export type DisplaySection = {
  id: DisplaySectionId;
  title: string;
  rows: DisplayRow[];
};

export type FinalStatus = {
  phaseTitle: string;
  progressLabel: string;
  message: string;
  headline: string;
  body: string;
  optionalNote: string;
  items: string[];
  itemKind: "required" | "optional" | "none";
  /** True only when the incoming boot payload itself says GO and also lists a required failure. */
  contradiction: boolean;
};

const CLOUD = /cloud\s*1\.2/i;

const SECTION_TITLES: Record<DisplaySectionId, string> = {
  core: "Core Runtime",
  production: "Production Systems",
  optional: "Optional / On Demand",
};

const SECTION_BY_LABEL: Record<string, DisplaySectionId> = {
  "Adept Core": "core",
  "Studio API": "core",
  "Creator UI": "core",
  "Creator Engine": "core",
  "Co-Director": "core",
  "Co-Director Runtime": "core",
  "Local AI Runtime": "core",
  "Runtime Supervisor": "core",
  "Setup / Update": "core",
  "Image Generator": "production",
  Storyboard: "production",
  Timeline: "production",
  MAGI: "production",
  Library: "production",
  "Script Writer": "production",
  Voice: "production",
  "Video Runtime": "optional",
  "Remote Access": "optional",
  "Comfy MCP": "optional",
};

const DISPLAY_ORDER = [
  "Adept Core",
  "Studio API",
  "Creator UI",
  "Creator Engine",
  "Co-Director Runtime",
  "Local AI Runtime",
  "Runtime Supervisor",
  "Setup / Update",
  "Image Generator",
  "Storyboard",
  "Timeline",
  "MAGI",
  "Library",
  "Script Writer",
  "Voice",
  "Video Runtime",
  "Remote Access",
  "Comfy MCP",
];

/** Snapshot and boot use different names for the same owner. */
const OWNER_ALIAS: Record<string, string> = {
  "Co-Director Runtime": "Co-Director",
};

const DISPLAY_LABEL: Record<string, string> = {
  "Co-Director": "Co-Director Runtime",
};

export function isCloud12(value: string | undefined | null): boolean {
  return Boolean(value && (value === "cloud_12" || CLOUD.test(value)));
}

function ownerKey(label: string): string {
  return OWNER_ALIAS[label] ?? label;
}

function displayLabel(owner: string): string {
  return DISPLAY_LABEL[owner] ?? owner;
}

function slug(label: string): string {
  return label.toLowerCase().replace(/[^a-z0-9]+/g, "_").replace(/^_|_$/g, "");
}

function sectionFor(label: string, required: boolean): DisplaySectionId {
  return SECTION_BY_LABEL[label] ?? SECTION_BY_LABEL[ownerKey(label)] ?? (required ? "core" : "optional");
}

export function badgeClass(badge: DisplayBadge): string {
  switch (badge) {
    case "ONLINE":
    case "PASS":
      return "online";
    case "OPTIONAL":
    case "ON DEMAND":
      return "on_demand";
    case "FAILED":
    case "MISSING":
      return "failed";
    case "STARTING":
      return "starting";
    default:
      return "checking";
  }
}

function badgeFromChecks(checks: BootCheckView[]): DisplayBadge {
  const blocking = checks.filter(
    (check) => check.required !== false && ["FAIL", "TIMEOUT", "NOT_RUN", "MISSING"].includes(check.result),
  );
  if (blocking.length) return "FAILED";
  const required = checks.filter((check) => check.required !== false && check.result !== "OPTIONAL");
  if (required.length && required.every((check) => check.result === "PASS")) return "ONLINE";
  if (checks.some((check) => check.result === "ON_DEMAND")) return "ON DEMAND";
  if (checks.every((check) => check.result === "OPTIONAL" || check.result === "PASS")) {
    return checks.some((check) => check.result === "OPTIONAL") ? "OPTIONAL" : "ONLINE";
  }
  return "CHECKING";
}

function badgeFromSnapshot(state: SystemState): DisplayBadge {
  switch (state) {
    case "online":
      return "ONLINE";
    case "starting":
      return "STARTING";
    case "failed":
    case "degraded":
      return "FAILED";
    case "on_demand":
      return "ON DEMAND";
    default:
      return "CHECKING";
  }
}

export function buildStartupBoard(snapshotRows: SystemRow[], checks: BootCheckView[]): DisplaySection[] {
  const liveChecks = checks.filter(
    (check) => !isCloud12(check.id) && !isCloud12(check.system) && !isCloud12(check.check) && !isCloud12(check.detail),
  );
  const byOwner = new Map<string, BootCheckView[]>();
  for (const check of liveChecks) {
    const key = ownerKey(check.system);
    const list = byOwner.get(key) ?? [];
    list.push(check);
    byOwner.set(key, list);
  }
  const snapshotByOwner = new Map<string, SystemRow>();
  for (const row of snapshotRows) {
    if (isCloud12(row.label)) continue;
    const key = ownerKey(row.label);
    if (!snapshotByOwner.has(key)) snapshotByOwner.set(key, row);
  }

  const order: string[] = [];
  const push = (key: string) => {
    if (!order.includes(key)) order.push(key);
  };
  for (const label of DISPLAY_ORDER) push(ownerKey(label));
  for (const row of snapshotRows) {
    if (!isCloud12(row.label)) push(ownerKey(row.label));
  }
  for (const check of liveChecks) push(ownerKey(check.system));

  const rows: DisplayRow[] = [];
  for (const key of order) {
    const group = byOwner.get(key);
    const snap = snapshotByOwner.get(key);
    if (!group && !snap) continue;
    const label = displayLabel(key);
    const badge = group?.length ? badgeFromChecks(group) : badgeFromSnapshot(snap!.state);
    const required = group
      ? group.some((check) => check.required !== false && check.result !== "OPTIONAL")
      : Boolean(snap?.required);
    rows.push({
      id: snap?.id ?? slug(key),
      label,
      badge,
      section: sectionFor(label, required),
    });
  }

  return (["core", "production", "optional"] as const)
    .map((id) => ({ id, title: SECTION_TITLES[id], rows: rows.filter((row) => row.section === id) }))
    .filter((section) => section.rows.length > 0);
}

export function duplicateLabels(sections: DisplaySection[]): string[] {
  const counts = new Map<string, number>();
  for (const section of sections) {
    for (const row of section.rows) counts.set(row.label, (counts.get(row.label) ?? 0) + 1);
  }
  return [...counts.entries()].filter(([, count]) => count > 1).map(([label]) => label);
}

function namedItem(system: string, detail?: string): string {
  const name = system.trim();
  const extra = (detail || "").trim();
  if (!extra || extra.toLowerCase() === name.toLowerCase()) return name;
  return `${name}: ${extra}`;
}

export function describeFinalStatus(input: {
  verdict?: "GO" | "NO-GO";
  progressPct: number;
  failed?: Array<{ system: string; check?: string; detail?: string; result?: string }>;
  setupOptional?: Array<{ name: string }>;
  allRequiredOnline: boolean;
}): FinalStatus {
  const requiredMissing = (input.failed ?? []).filter((row) => !isCloud12(row.system) && !isCloud12(row.check));
  const setupNames = [...new Set(
    (input.setupOptional ?? [])
      .map((item) => item.name.trim())
      .filter((name) => name && !isCloud12(name)),
  )];
  const contradiction = input.verdict === "GO" && requiredMissing.length > 0;
  const go = input.verdict === "GO" && requiredMissing.length === 0;
  const needsSetup = input.verdict === "NO-GO" || requiredMissing.length > 0;
  const complete = go && input.progressPct >= 100;

  if (needsSetup) {
    return {
      phaseTitle: "Startup Requires Attention",
      progressLabel: "Startup needs attention",
      message: "",
      headline: "ADEPT UI SETUP REQUIRED",
      body: `${requiredMissing.length} required ${requiredMissing.length === 1 ? "component needs" : "components need"} attention.`,
      optionalNote: "",
      items: requiredMissing.map((row) => namedItem(row.system, row.detail)),
      itemKind: "required",
      contradiction,
    };
  }

  if (go) {
    return {
      phaseTitle: complete ? "Adept UI Ready" : "Bringing Adept UI Online",
      progressLabel: complete ? "Startup Complete" : "Bringing Adept UI Online",
      message: "ALL REQUIRED SYSTEMS ONLINE",
      headline: "ADEPT UI READY — GO",
      body: "All required systems are ready.",
      optionalNote: setupNames.length ? "Optional components can be configured from Setup." : "",
      items: setupNames,
      itemKind: setupNames.length ? "optional" : "none",
      contradiction: false,
    };
  }

  return {
    phaseTitle: input.allRequiredOnline ? "Adept UI Ready" : "Bringing Adept UI Online",
    progressLabel: input.allRequiredOnline ? "Startup Complete" : "Bringing Adept UI Online",
    message: input.allRequiredOnline ? "ALL REQUIRED SYSTEMS ONLINE" : "",
    headline: "",
    body: "",
    optionalNote: "",
    items: [],
    itemKind: "none",
    contradiction: false,
  };
}
