import { api } from "../../api";
import type { AudioCandidate, AudioStudioTrack } from "./types";

function firstString(...values: unknown[]) {
  for (const value of values) {
    if (typeof value === "string" && value.trim()) return value.trim();
  }
  return "";
}

function firstNumber(...values: unknown[]) {
  for (const value of values) {
    if (typeof value === "number" && Number.isFinite(value)) return value;
    if (typeof value === "string" && value.trim() && Number.isFinite(Number(value))) return Number(value);
  }
  return undefined;
}

function asArray(value: unknown): any[] {
  return Array.isArray(value) ? value : [];
}

export function extractCandidates(result: any, kind: AudioStudioTrack): AudioCandidate[] {
  const batchId = firstString(result?.id, result?.batchId, result?.batch_id);
  const rawItems = [
    ...asArray(result?.candidates),
    ...asArray(result?.items),
    ...asArray(result?.assets),
    ...asArray(result?.tracks),
    ...asArray(result?.sounds),
    ...asArray(result?.beds),
  ];
  if (!rawItems.length && result?.assetId) {
    rawItems.push({ id: result.assetId, assetId: result.assetId });
  }

  return rawItems
    .map((item, index) => {
      const candidateId = firstString(item?.id, item?.candidateId, item?.candidate_id) || `${kind}-${index + 1}`;
      const assetId = firstString(item?.asset_id, item?.assetId);
      const variationIndex = firstNumber(item?.variation_index, item?.variationIndex) || index + 1;
      const variationHint = firstString(item?.variation_hint, item?.variationHint);
      const title =
        firstString(item?.title, item?.name) ||
        `${kind === "music" ? "Track" : kind === "sfx" ? "Sound" : "Bed"} ${variationIndex}`;
      const audioUrl = assetId
        ? firstString(item?.audio_url, item?.audioUrl) || api.assetUrl(assetId)
        : "";
      return {
        id: candidateId,
        batchId: batchId || firstString(item?.batch_id, item?.batchId) || undefined,
        assetId: assetId || undefined,
        title,
        subtitle:
          firstString(item?.subtitle, item?.error, variationHint) ||
          (typeof item?.seed === "number" ? `Seed ${item.seed}` : undefined),
        description: firstString(item?.description, item?.summary, item?.prompt, variationHint),
        prompt: firstString(item?.prompt),
        durationSec: firstNumber(
          item?.durationSec,
          item?.duration_sec,
          item?.m29?.durationSec,
          result?.duration_sec,
          result?.durationSec,
        ),
        loop: Boolean(item?.loop ?? kind === "ambience"),
        audioUrl,
        typeLabel: kind === "music" ? "Track" : kind === "sfx" ? "Sound" : "Bed",
        status: firstString(item?.status),
        stemsSupported: Boolean(item?.stems_supported ?? item?.stemsSupported),
        seed: firstNumber(item?.seed),
        variationIndex,
        variationHint: variationHint || undefined,
        raw: item,
      } satisfies AudioCandidate;
    })
    .filter(
      (candidate) =>
        candidate.audioUrl ||
        candidate.assetId ||
        ["failed", "queued", "generating", "ready", "selected", "approved"].includes(String(candidate.status || "")),
    )
    .slice(0, 6);
}

export function latestBatchForKind(batches: any[], kind: AudioStudioTrack): any | null {
  const matches = (Array.isArray(batches) ? batches : []).filter(
    (batch) => String(batch?.method || batch?.kind || "") === kind,
  );
  if (!matches.length) return null;
  return [...matches].sort((a, b) =>
    String(b?.created_at || b?.createdAt || "").localeCompare(String(a?.created_at || a?.createdAt || "")),
  )[0];
}

export function approvedIdsFromBatches(batches: any[]): Record<string, boolean> {
  const next: Record<string, boolean> = {};
  for (const batch of Array.isArray(batches) ? batches : []) {
    for (const candidate of asArray(batch?.candidates)) {
      if (String(candidate?.status || "").toLowerCase() === "approved" && candidate?.asset_id) {
        next[String(candidate.asset_id)] = true;
      }
    }
  }
  return next;
}

export function classifyLibraryAudio(asset: {
  title?: string;
  tag?: string;
  filename?: string;
  kind?: string;
  category?: string;
  libraryKey?: string;
}): "music" | "sfx" | "ambience" | "voice" | "audio" {
  const haystack = [asset.category, asset.libraryKey, asset.tag, asset.title, asset.filename, asset.kind]
    .filter(Boolean)
    .join(" ")
    .toLowerCase();
  if (haystack.includes("voice") || haystack.includes("dialogue") || haystack.includes("speech")) return "voice";
  if (haystack.includes("ambience") || haystack.includes("ambient") || haystack.includes("bed") || haystack.includes("room tone")) {
    return "ambience";
  }
  if (haystack.includes("sfx") || haystack.includes("sound effect") || haystack.includes("foley") || haystack.includes("impact")) {
    return "sfx";
  }
  if (haystack.includes("music") || haystack.includes("score") || haystack.includes("track")) return "music";
  return "audio";
}

export async function probeAudioDurationSec(url: string | undefined, timeoutMs = 4000): Promise<number | undefined> {
  if (!url || typeof Audio === "undefined") return undefined;
  return await new Promise((resolve) => {
    const el = new Audio();
    const finish = (value?: number) => {
      window.clearTimeout(timer);
      el.removeAttribute("src");
      resolve(value);
    };
    const timer = window.setTimeout(() => finish(undefined), timeoutMs);
    el.preload = "metadata";
    el.onloadedmetadata = () => {
      const duration = Number(el.duration);
      finish(Number.isFinite(duration) && duration > 0 && duration < 600 ? Math.round(duration * 10) / 10 : undefined);
    };
    el.onerror = () => finish(undefined);
    el.src = url;
  });
}
