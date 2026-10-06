export type AudioStudioKind = "music" | "sfx" | "ambience";

export type AudioSourceStatus = {
  kind: AudioStudioKind;
  ready: boolean;
  checking?: boolean;
  label: string;
  detail: string;
  runtime: string;
  mode: string;
};

const CREATOR_RUNTIME: Record<string, string> = {
  "ACE-Step": "Music Engine",
  MMAudio: "Sound Engine",
};

export function creatorRuntimeName(runtime: string | null | undefined): string {
  const key = String(runtime || "").trim();
  return CREATOR_RUNTIME[key] || key || "Audio Engine";
}

export function sourceStatusFromProviders(kind: AudioStudioKind, payload: any): AudioSourceStatus {
  const rec = payload?.recommendation || {};
  const local = payload?.local || {};
  const runtimeKey = kind === "music" ? "ACE-Step" : "MMAudio";
  const row = local[runtimeKey] || {};
  const recMatchesKind = String(rec.runtime || "") === runtimeKey;
  const mode = recMatchesKind ? String(rec.mode || "") : "";
  const runtime = recMatchesKind ? String(rec.runtime || runtimeKey) : runtimeKey;
  const label = creatorRuntimeName(runtime);
  const probed = Boolean(payload && (payload.recommendation || payload.local));
  if (!probed) {
    return {
      kind,
      ready: false,
      checking: true,
      label,
      detail: `Checking ${label}…`,
      runtime,
      mode: "checking",
    };
  }
  // sandboxOnly is an adapter location, not a creator-facing unavailable state.
  const ready = Boolean(row.ready && row.cuda) || (mode === "local" && recMatchesKind && Boolean(rec.cuda));
  if (ready) {
    return {
      kind,
      ready: true,
      checking: false,
      label,
      detail: "Ready on this machine",
      runtime,
      mode: "local",
    };
  }
  if (mode === "blocked_cpu") {
    return {
      kind,
      ready: false,
      label,
      detail: "Needs the GPU worker. Audio will not run on CPU by itself.",
      runtime,
      mode,
    };
  }
  return {
    kind,
    ready: false,
    label,
    detail: String(rec.reason || row.message || `${label} is not ready yet.`),
    runtime,
    mode: mode || "unavailable",
  };
}

export function audioTabFromSearch(search: string): "music" | "sfx" | "ambience" | "library" {
  const tab = new URLSearchParams(search.startsWith("?") ? search.slice(1) : search).get("audioTab") || "";
  if (tab === "sfx" || tab === "ambience" || tab === "library" || tab === "music") return tab;
  return "music";
}

export function withAudioTab(search: string, tab: string): string {
  const params = new URLSearchParams(search.startsWith("?") ? search.slice(1) : search);
  params.set("workspace", "audiostudio");
  params.set("audioTab", tab);
  return `?${params.toString()}`;
}
