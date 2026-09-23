import { useEffect, useMemo, useRef, useState } from "react";
import type { Asset, Project, Scene } from "../types";
import { api, ApiError } from "../api";
import { PanelHeading } from "./HelpTip";

export type MouthRoi = { x: number; y: number; w: number; h: number };

export type LipSyncClip = {
  id?: string;
  start?: number;
  length?: number;
  label?: string;
  status?: string;
  speaker_binding_id?: string | null;
  character_id?: string | null;
  character_name?: string | null;
  audio_asset_id?: string | null;
  follow_policy?: string;
  line?: string;
};

export type LipSyncTrack = {
  slot: number;
  label: string;
  enabled: boolean;
  audio_asset_id?: string | null;
  character_id?: string | null;
  character_name?: string | null;
  clips?: LipSyncClip[];
  roi: MouthRoi;
  track_path: { frame: number; x: number; y: number; w: number; h: number; visible?: boolean; mode?: string }[];
  notes: string;
};

export type LipSyncTracks = { tracks: LipSyncTrack[] };

type RetakeBeat =
  | { kind: "silence"; startSec: number; endSec: number }
  | {
      kind: "dialogue";
      startSec: number;
      endSec: number;
      characterId: string | null;
      characterName: string | null;
      line: string;
      voiceAssetId: string;
    };

type CharacterSheetRef = { characterId: string; assetId: string };

const DEFAULT_TRACKS: LipSyncTracks = {
  tracks: [
    {
      slot: 1,
      label: "Character 1",
      enabled: false,
      clips: [],
      roi: { x: 0.35, y: 0.55, w: 0.18, h: 0.12 },
      track_path: [],
      notes: "",
    },
    {
      slot: 2,
      label: "Character 2",
      enabled: false,
      clips: [],
      roi: { x: 0.55, y: 0.55, w: 0.18, h: 0.12 },
      track_path: [],
      notes: "",
    },
  ],
};

function clampRoi(r: MouthRoi): MouthRoi {
  const w = Math.min(0.6, Math.max(0.05, r.w));
  const h = Math.min(0.5, Math.max(0.04, r.h));
  return {
    w,
    h,
    x: Math.min(1 - w, Math.max(0, r.x)),
    y: Math.min(1 - h, Math.max(0, r.y)),
  };
}

function parseJson<T>(raw: string | null | undefined): T | null {
  if (!raw || !String(raw).trim()) return null;
  try {
    return JSON.parse(raw) as T;
  } catch {
    return null;
  }
}

function parseLabels(asset: Asset): string[] {
  const parsed = parseJson<unknown>(asset.labels_json);
  return Array.isArray(parsed) ? parsed.map(String).filter(Boolean) : [];
}

function assetCharacterId(asset: Asset): string {
  const meta = parseJson<Record<string, unknown>>(asset.prompt_meta_json) || {};
  let id = String(meta.characterId || meta.character_id || "").trim();
  if (!id && meta.creativeContext && typeof meta.creativeContext === "object") {
    id = String((meta.creativeContext as Record<string, unknown>).characterId || "").trim();
  }
  if (!id) {
    const match = (asset.filename || "").match(/character_sheet_([0-9a-f]{8})/i);
    id = match?.[1] || "";
  }
  return id;
}

function normalizeId(id: string): string {
  return id.replace(/-/g, "").toLowerCase();
}

function isCharacterSheetAsset(asset: Asset): boolean {
  if (asset.kind !== "image") return false;
  const labels = parseLabels(asset);
  const blob = [...labels, asset.tag || "", asset.filename || ""].join(" ").toLowerCase();
  return (
    blob.includes("character_sheet") ||
    blob.includes("character_reference") ||
    blob.includes("composed_sheet") ||
    blob.includes("identity_references") ||
    blob.includes("hero_identity")
  );
}

export function resolveCharacterSheetAssetId(characterId: string, assets: Asset[]): string | null {
  const target = normalizeId(characterId);
  if (!target) return null;
  const candidates = assets.filter((a) => {
    if (!isCharacterSheetAsset(a)) return false;
    const aid = normalizeId(assetCharacterId(a));
    if (!aid || aid.length < 8) return false;
    return target === aid || target.startsWith(aid) || aid.startsWith(target);
  });
  if (!candidates.length) return null;
  const approved = candidates.filter((a) =>
    parseLabels(a).some((l) => l.toLowerCase().includes("approved")),
  );
  const pool = approved.length ? approved : candidates;
  pool.sort((a, b) => String(b.created_at).localeCompare(String(a.created_at)));
  return pool[0]?.id || null;
}

function formatClock(sec: number): string {
  if (!Number.isFinite(sec) || sec < 0) return "0:00";
  const m = Math.floor(sec / 60);
  const s = Math.floor(sec % 60);
  const d = Math.round((sec % 1) * 100) / 100;
  const ds = d >= 0.01 ? `.${Math.round(d * 10)}` : "";
  return `${m}:${s.toString().padStart(2, "0")}${ds}`;
}

export function buildPerformanceRetakeBody(
  scene: Scene,
  tracks: LipSyncTracks,
  assets: Asset[],
  advanced: boolean,
  inSec: number,
  outSec: number,
): { mode: "performance_retake"; retake: { window: Record<string, unknown>; beats: RetakeBeat[]; references: Record<string, unknown> } } {
  const duration = Number(scene.duration_sec || 0);
  const windowStart = advanced ? Math.max(0, Math.min(inSec, duration)) : 0;
  const windowEnd = advanced ? Math.max(windowStart, Math.min(outSec, duration)) : duration;
  const window = {
    startSec: windowStart,
    endSec: windowEnd,
    scope: advanced ? "sub_window" : "whole_shot",
    boundarySource: advanced ? "creator_manual" : "qwen_shot_analysis",
  };

  const dialogueClips: Array<{
    start: number;
    end: number;
    characterId: string;
    characterName: string;
    line: string;
    voiceAssetId: string;
  }> = [];
  for (const track of tracks.tracks) {
    if (!track.enabled) continue;
    for (const clip of track.clips || []) {
      if (!clip.audio_asset_id) continue;
      const start = Number(clip.start ?? 0);
      const end = start + Number(clip.length ?? 0);
      const characterId = String(clip.character_id || track.character_id || "").trim();
      const characterName = String(
        clip.character_name || track.character_name || track.label || characterId || "Character",
      ).trim();
      dialogueClips.push({
        start,
        end,
        characterId,
        characterName,
        line: (clip.line || "").trim(),
        voiceAssetId: clip.audio_asset_id,
      });
    }
  }
  dialogueClips.sort((a, b) => a.start - b.start);

  const beats: RetakeBeat[] = [];
  let cursor = windowStart;
  for (const clip of dialogueClips) {
    const start = Math.max(windowStart, clip.start);
    const end = Math.min(windowEnd, clip.end);
    if (start >= end) continue;
    if (start > cursor) {
      beats.push({ kind: "silence", startSec: cursor, endSec: start });
    }
    beats.push({
      kind: "dialogue",
      startSec: start,
      endSec: end,
      characterId: clip.characterId || null,
      characterName: clip.characterName || null,
      line: clip.line,
      voiceAssetId: clip.voiceAssetId,
    });
    cursor = Math.max(cursor, end);
  }
  if (cursor < windowEnd) {
    beats.push({ kind: "silence", startSec: cursor, endSec: windowEnd });
  }

  const charIds = new Set(
    beats.filter((b) => b.kind === "dialogue" && b.characterId).map((b) => b.characterId as string),
  );
  const characterSheets: CharacterSheetRef[] = [];
  for (const cid of charIds) {
    const assetId = resolveCharacterSheetAssetId(cid, assets);
    if (assetId) {
      characterSheets.push({ characterId: cid, assetId });
    }
  }

  return {
    mode: "performance_retake",
    retake: {
      window,
      beats,
      references: {
        sourceVideo: true,
        includeSourceAudio: false,
        characterSheets,
      },
    },
  };
}

export function canApplyPerformanceRetake(
  scene: Scene,
  tracks: LipSyncTracks,
  assets: Asset[],
  advanced: boolean,
  inSec: number,
  outSec: number,
): { ok: boolean; reason: string | null } {
  const duration = Number(scene.duration_sec || 0);
  if (duration <= 0) {
    return { ok: false, reason: "Scene duration is not set yet" };
  }
  const enabled = tracks.tracks.filter((t) => t.enabled);
  if (!enabled.length) {
    return { ok: false, reason: "Enable at least one Performance Retake track" };
  }
  const voicedClips: Array<{ characterId: string; hasLine: boolean; hasAudio: boolean }> = [];
  for (const track of enabled) {
    for (const clip of track.clips || []) {
      const hasAudio = Boolean(clip.audio_asset_id);
      const characterId = String(clip.character_id || track.character_id || "").trim();
      const hasLine = Boolean((clip.line || "").trim());
      voicedClips.push({ characterId, hasLine, hasAudio });
    }
  }
  if (!voicedClips.some((c) => c.hasAudio)) {
    return {
      ok: false,
      reason: "Every dialogue clip needs a voice clip — render one in Voice Studio first",
    };
  }
  for (const c of voicedClips) {
    if (!c.hasLine) {
      return { ok: false, reason: "Add dialogue lines for every voiced clip" };
    }
  }
  for (const c of voicedClips) {
    if (!c.characterId) {
      return { ok: false, reason: "A dialogue clip is missing a character binding" };
    }
  }
  for (const track of enabled) {
    for (const clip of track.clips || []) {
      if (!clip.audio_asset_id) continue;
      const cid = String(clip.character_id || track.character_id || "").trim();
      if (cid && !resolveCharacterSheetAssetId(cid, assets)) {
        return {
          ok: false,
          reason: `Add an approved character sheet for the speaking character`,
        };
      }
    }
  }
  const body = buildPerformanceRetakeBody(scene, tracks, assets, advanced, inSec, outSec);
  const expectedSheets = new Set(
    body.retake.beats
      .filter((b) => b.kind === "dialogue" && b.characterId)
      .map((b) => b.characterId as string),
  );
  const actualSheets = new Set(body.retake.references.characterSheets.map((c) => c.characterId));
  for (const cid of expectedSheets) {
    if (!actualSheets.has(cid)) {
      return { ok: false, reason: `Add an approved character sheet for the speaking character` };
    }
  }
  return { ok: true, reason: null };
}

export function performanceRetakeErrorMessage(err: unknown): string {
  if (err instanceof ApiError && err.status === 410) {
    return "This older lip-sync tool has been replaced by Performance Retake.";
  }
  if (err instanceof ApiError && err.status === 400) {
    return err.message;
  }
  return err instanceof Error ? err.message : String(err);
}

export function LipSyncTracksPanel({
  project,
  scene,
  onChange,
}: {
  project: Project;
  scene?: Scene;
  onChange: () => void;
}) {
  const [tracks, setTracks] = useState<LipSyncTracks>(DEFAULT_TRACKS);
  const [activeSlot, setActiveSlot] = useState<1 | 2>(1);
  const [busy, setBusy] = useState<string | null>(null);
  const [msg, setMsg] = useState("");
  const [advanced, setAdvanced] = useState(false);
  const [inSec, setInSec] = useState(0);
  const [outSec, setOutSec] = useState(0);
  const saveTimeoutRef = useRef<number | null>(null);

  const previewSrc =
    (scene?.lipsync_output_path && api.mediaUrl(scene.lipsync_output_path)) ||
    (scene?.output_path && api.mediaUrl(scene.output_path)) ||
    (scene?.start_asset_id && api.assetUrl(scene.start_asset_id)) ||
    "";

  useEffect(() => {
    if (!scene) return;
    api
      .getLipSyncTracks(project.id, scene.id)
      .then((t) => {
        const next = t?.tracks?.length
          ? t
          : {
              tracks: DEFAULT_TRACKS.tracks.map((d) => ({
                ...d,
                roi: clampRoi(d.roi),
              })),
            };
        setTracks(next);
      })
      .catch(() => setTracks(DEFAULT_TRACKS));
    const duration = Number(scene.duration_sec || 0);
    setInSec(0);
    setOutSec(duration);
  }, [project.id, scene?.id]);

  useEffect(() => {
    return () => {
      if (saveTimeoutRef.current !== null) {
        window.clearTimeout(saveTimeoutRef.current);
      }
    };
  }, []);

  const scheduleSave = (next: LipSyncTracks) => {
    if (saveTimeoutRef.current !== null) {
      window.clearTimeout(saveTimeoutRef.current);
    }
    saveTimeoutRef.current = window.setTimeout(() => {
      if (!scene) return;
      api
        .putLipSyncTracks(project.id, scene.id, next)
        .then(() => onChange())
        .catch(() => {});
    }, 600);
  };

  const save = async (next: LipSyncTracks) => {
    setTracks(next);
    scheduleSave(next);
  };

  const updateTrack = (slot: number, patch: Partial<LipSyncTrack>) => {
    const next = {
      tracks: tracks.tracks.map((t) =>
        t.slot === slot ? { ...t, ...patch, roi: patch.roi ? clampRoi(patch.roi) : t.roi } : t,
      ),
    };
    save(next);
  };

  const updateClip = (slot: number, clipId: string | undefined, patch: Partial<LipSyncClip>) => {
    if (!clipId) return;
    const next = {
      tracks: tracks.tracks.map((t) =>
        t.slot === slot
          ? {
              ...t,
              clips: (t.clips || []).map((c) => (c.id === clipId ? { ...c, ...patch } : c)),
            }
          : t,
      ),
    };
    save(next);
  };

  const active = tracks.tracks.find((t) => t.slot === activeSlot) || tracks.tracks[0];

  const applyCheck = useMemo(
    () => (scene ? canApplyPerformanceRetake(scene, tracks, project.assets, advanced, inSec, outSec) : { ok: false, reason: "Select a scene" }),
    [scene, tracks, project.assets, advanced, inSec, outSec],
  );

  if (!scene) {
    return (
      <div className="panel">
        <PanelHeading
          title="Performance Retake"
          tip="Re-films this shot with new dialogue. The original performance inside the window is replaced by a newly rendered one."
        />
        <p className="empty">Select a scene</p>
      </div>
    );
  }

  const duration = Number(scene.duration_sec || 0);
  const windowChip = advanced
    ? `Sub-window ${formatClock(inSec)}–${formatClock(outSec)}`
    : `Whole shot ${formatClock(0)}–${formatClock(duration)}`;

  return (
    <div className="panel lipsync-panel">
      <PanelHeading
        title="Performance Retake"
        tip="Re-films this shot with new dialogue. The original performance inside the window is replaced by a newly rendered one."
      />
      <p className="scene-meta" data-testid="pr-intro">
        Choose which clips speak, type the new dialogue line for each one, then apply a retake.
      </p>

      <div className="lipsync-slots" data-testid="pr-track-tabs">
        {tracks.tracks.map((t) => (
          <button
            key={t.slot}
            className={activeSlot === t.slot ? "primary" : ""}
            data-testid={`pr-track-tab-${t.slot}`}
            onClick={() => setActiveSlot(t.slot as 1 | 2)}
          >
            {t.label || `Character ${t.slot}`}
            {t.enabled ? " · on" : ""}
          </button>
        ))}
      </div>

      {active && (
        <>
          <div className="field">
            <label>Character label</label>
            <input
              value={active.label}
              onChange={(e) => updateTrack(active.slot, { label: e.target.value })}
              placeholder={`Character ${active.slot}`}
              data-testid={`pr-track-label-${active.slot}`}
            />
          </div>
          <div className="field">
            <label>
              <input
                type="checkbox"
                checked={active.enabled}
                onChange={(e) => updateTrack(active.slot, { enabled: e.target.checked })}
                style={{ width: "auto", marginRight: 8 }}
                data-testid={`pr-track-enable-${active.slot}`}
              />
              Enable track {active.slot}
            </label>
          </div>

          <div className="section-label">Voice clips</div>
          {(active.clips || []).length === 0 ? (
            <p className="scene-meta" data-testid={`pr-no-clips-${active.slot}`}>
              No voice clips on this track yet. Add them in Voice Studio first.
            </p>
          ) : (
            <div className="pr-clip-list" data-testid={`pr-clip-list-${active.slot}`}>
              {(active.clips || []).map((clip, idx) => {
                const characterName = String(
                  clip.character_name || active.character_name || active.label || `Character ${active.slot}`,
                );
                const hasAudio = Boolean(clip.audio_asset_id);
                return (
                  <div key={clip.id || idx} className="pr-clip" data-testid={`pr-clip-${active.slot}-${idx}`}>
                    <div className="pr-clip-meta">
                      <span data-testid={`pr-clip-time-${active.slot}-${idx}`}>
                        {formatClock(Number(clip.start ?? 0))}–
                        {formatClock(Number(clip.start ?? 0) + Number(clip.length ?? 0))}
                      </span>
                      <span className="pill" data-testid={`pr-clip-character-${active.slot}-${idx}`}>
                        {characterName}
                      </span>
                      {hasAudio ? (
                        <span className="success" data-testid={`pr-clip-voice-attached-${active.slot}-${idx}`}>
                          Voice clip attached
                        </span>
                      ) : (
                        <span className="warning" data-testid={`pr-clip-voice-missing-${active.slot}-${idx}`}>
                          Needs a voice clip — render one in Voice Studio first
                        </span>
                      )}
                    </div>
                    <div className="field">
                      <label htmlFor={`pr-clip-line-${active.slot}-${idx}`}>
                        What does {characterName} say?
                      </label>
                      <input
                        id={`pr-clip-line-${active.slot}-${idx}`}
                        value={clip.line || ""}
                        disabled={!hasAudio}
                        placeholder={hasAudio ? "Type the new dialogue line" : "Attach a voice clip first"}
                        onChange={(e) =>
                          updateClip(active.slot, clip.id, { line: e.target.value })
                        }
                        data-testid={`pr-clip-line-${active.slot}-${idx}`}
                      />
                    </div>
                  </div>
                );
              })}
            </div>
          )}

          <div className="section-label">Window</div>
          <p className="scene-meta">
            <span className="pill" data-testid="pr-window-chip">
              {windowChip}
            </span>
            <button
              type="button"
              className="ghost"
              onClick={() => setAdvanced((v) => !v)}
              data-testid="pr-window-advanced-toggle"
            >
              {advanced ? "Hide advanced" : "Advanced"}
            </button>
          </p>
          {advanced && (
            <div className="row-actions" data-testid="pr-window-fields">
              <div className="field">
                <label>IN (seconds)</label>
                <input
                  type="number"
                  step={0.1}
                  min={0}
                  max={duration}
                  value={inSec}
                  onChange={(e) => setInSec(Math.max(0, Math.min(Number(e.target.value) || 0, duration)))}
                  data-testid="pr-window-in"
                />
              </div>
              <div className="field">
                <label>OUT (seconds)</label>
                <input
                  type="number"
                  step={0.1}
                  min={0}
                  max={duration}
                  value={outSec}
                  onChange={(e) => setOutSec(Math.max(0, Math.min(Number(e.target.value) || 0, duration)))}
                  data-testid="pr-window-out"
                />
              </div>
            </div>
          )}

          <div className="section-label">Preview</div>
          <div className="mouth-stage">
            {previewSrc ? (
              previewSrc.match(/\.(mp4|webm|mov)(\?|$)/i) || scene.output_path ? (
                <video src={previewSrc} muted playsInline controls />
              ) : (
                <img src={previewSrc} alt="preview" />
              )
            ) : (
              <div className="empty">Add a start frame or render the scene to preview the shot</div>
            )}
          </div>

          <div className="row-actions">
            <button
              className="primary"
              disabled={busy !== null || !applyCheck.ok}
              data-testid="pr-apply-performance-retake"
              onClick={async () => {
                setBusy("apply");
                setMsg("");
                try {
                  const body = buildPerformanceRetakeBody(
                    scene,
                    tracks,
                    project.assets,
                    advanced,
                    inSec,
                    outSec,
                  );
                  await api.applyLipSyncTracks(project.id, scene.id, body);
                  setMsg("Performance Retake queued — watch Render queue.");
                  onChange();
                } catch (err) {
                  setMsg(performanceRetakeErrorMessage(err));
                } finally {
                  setBusy(null);
                }
              }}
            >
              {busy === "apply" ? "Queuing…" : "Apply Performance Retake"}
            </button>
          </div>
          {applyCheck.reason && (
            <p className="scene-meta" data-testid="pr-apply-blocker">
              {applyCheck.reason}
            </p>
          )}
          {msg && (
            <p className="scene-meta" data-testid="pr-retake-message">
              {msg}
            </p>
          )}
        </>
      )}
    </div>
  );
}
