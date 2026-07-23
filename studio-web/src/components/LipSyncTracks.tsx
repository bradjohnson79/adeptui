import { useEffect, useRef, useState } from "react";
import type { Asset, Project, Scene } from "../types";
import { api } from "../api";
import { PanelHeading } from "./HelpTip";

export type MouthRoi = { x: number; y: number; w: number; h: number };
export type LipSyncTrack = {
  slot: number;
  label: string;
  enabled: boolean;
  audio_asset_id?: string | null;
  roi: MouthRoi;
  track_path: { frame: number; x: number; y: number; w: number; h: number; visible?: boolean; mode?: string }[];
  notes: string;
};
export type LipSyncTracks = { tracks: LipSyncTrack[] };

const DEFAULT_TRACKS: LipSyncTracks = {
  tracks: [
    { slot: 1, label: "Character 1", enabled: false, roi: { x: 0.35, y: 0.55, w: 0.18, h: 0.12 }, track_path: [], notes: "" },
    { slot: 2, label: "Character 2", enabled: false, roi: { x: 0.55, y: 0.55, w: 0.18, h: 0.12 }, track_path: [], notes: "" },
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
  const stageRef = useRef<HTMLDivElement>(null);
  const dragRef = useRef<{ mode: "move" | "resize"; ox: number; oy: number; start: MouthRoi } | null>(null);

  const previewSrc =
    (scene?.lipsync_output_path && api.mediaUrl(scene.lipsync_output_path)) ||
    (scene?.output_path && api.mediaUrl(scene.output_path)) ||
    (scene?.start_asset_id && api.assetUrl(scene.start_asset_id)) ||
    "";

  useEffect(() => {
    if (!scene) return;
    api
      .getLipSyncTracks(project.id, scene.id)
      .then((t) => setTracks(t?.tracks?.length ? t : DEFAULT_TRACKS))
      .catch(() => setTracks(DEFAULT_TRACKS));
  }, [project.id, scene?.id]);

  if (!scene) {
    return (
      <div className="panel">
        <PanelHeading
          title="Lip sync tracks"
          tip="Up to two characters: place mouth boxes, bake sticky tracks, then apply dialogue audio so lips match speech."
        />
        <p className="empty">Select a scene</p>
      </div>
    );
  }

  const audios = project.assets.filter((a: Asset) => a.kind === "audio");
  const active = tracks.tracks.find((t) => t.slot === activeSlot) || tracks.tracks[0];

  const save = async (next: LipSyncTracks) => {
    setTracks(next);
    await api.putLipSyncTracks(project.id, scene.id, next);
    onChange();
  };

  const updateTrack = (slot: number, patch: Partial<LipSyncTrack>) => {
    const next = {
      tracks: tracks.tracks.map((t) => (t.slot === slot ? { ...t, ...patch, roi: patch.roi ? clampRoi(patch.roi) : t.roi } : t)),
    };
    save(next);
  };

  const onPointer = (e: React.PointerEvent, mode: "move" | "resize") => {
    if (!stageRef.current || !active) return;
    e.preventDefault();
    e.stopPropagation();
    const rect = stageRef.current.getBoundingClientRect();
    dragRef.current = {
      mode,
      ox: (e.clientX - rect.left) / rect.width,
      oy: (e.clientY - rect.top) / rect.height,
      start: { ...active.roi },
    };
    (e.target as HTMLElement).setPointerCapture?.(e.pointerId);
  };

  const onMove = (e: React.PointerEvent) => {
    if (!dragRef.current || !stageRef.current || !active) return;
    const rect = stageRef.current.getBoundingClientRect();
    const nx = (e.clientX - rect.left) / rect.width;
    const ny = (e.clientY - rect.top) / rect.height;
    const { mode, ox, oy, start } = dragRef.current;
    let roi = { ...start };
    if (mode === "move") {
      roi.x = start.x + (nx - ox);
      roi.y = start.y + (ny - oy);
    } else {
      roi.w = start.w + (nx - ox);
      roi.h = start.h + (ny - oy);
    }
    setTracks({
      tracks: tracks.tracks.map((t) => (t.slot === active.slot ? { ...t, roi: clampRoi(roi) } : t)),
    });
  };

  const onUp = () => {
    if (!dragRef.current || !active) return;
    dragRef.current = null;
    const current = tracks.tracks.find((t) => t.slot === active.slot);
    if (current) updateTrack(active.slot, { roi: current.roi });
  };

  return (
    <div className="panel lipsync-panel">
      <PanelHeading
        title="Lip sync tracks"
        tip="Up to two characters: place mouth boxes, bake sticky tracks, then apply dialogue audio so lips match speech."
      />
      <p className="scene-meta">
        Place a black rectangle on each speaking mouth. Sticky tracking follows the mouth through turns;
        when the face leaves frame (full 180° away), flow keeps the box until the face returns.
      </p>

      <div className="lipsync-slots">
        {tracks.tracks.map((t) => (
          <button
            key={t.slot}
            className={activeSlot === t.slot ? "primary" : ""}
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
            />
          </div>
          <div className="field">
            <label>
              <input
                type="checkbox"
                checked={active.enabled}
                onChange={(e) => updateTrack(active.slot, { enabled: e.target.checked })}
                style={{ width: "auto", marginRight: 8 }}
              />
              Enable track {active.slot}
            </label>
          </div>
          <div className="field">
            <label>Dialogue audio</label>
            <select
              value={active.audio_asset_id || ""}
              onChange={(e) => updateTrack(active.slot, { audio_asset_id: e.target.value || null })}
            >
              <option value="">None</option>
              {audios.map((a) => (
                <option key={a.id} value={a.id}>
                  @{a.tag || a.filename}
                </option>
              ))}
            </select>
          </div>

          <div className="section-label">Mouth rectangle (drag black box onto mouth)</div>
          <div
            className="mouth-stage"
            ref={stageRef}
            onPointerMove={onMove}
            onPointerUp={onUp}
            onPointerLeave={onUp}
          >
            {previewSrc ? (
              previewSrc.match(/\.(mp4|webm|mov)(\?|$)/i) || scene.output_path ? (
                <video src={previewSrc} muted playsInline controls />
              ) : (
                <img src={previewSrc} alt="preview" />
              )
            ) : (
              <div className="empty">Add a start frame or render the scene to place mouth boxes</div>
            )}
            {tracks.tracks
              .filter((t) => t.enabled || t.slot === activeSlot)
              .map((t) => (
                <div
                  key={t.slot}
                  className={`mouth-rect ${t.slot === activeSlot ? "active" : ""}`}
                  style={{
                    left: `${t.roi.x * 100}%`,
                    top: `${t.roi.y * 100}%`,
                    width: `${t.roi.w * 100}%`,
                    height: `${t.roi.h * 100}%`,
                  }}
                  onPointerDown={(e) => {
                    setActiveSlot(t.slot as 1 | 2);
                    onPointer(e, "move");
                  }}
                >
                  <span>{t.label || `C${t.slot}`}</span>
                  <i
                    className="mouth-handle"
                    onPointerDown={(e) => {
                      setActiveSlot(t.slot as 1 | 2);
                      onPointer(e, "resize");
                    }}
                  />
                </div>
              ))}
          </div>

          <div className="row-actions">
            <button
              disabled={busy !== null}
              onClick={async () => {
                setBusy("bake");
                setMsg("");
                try {
                  const res = await api.bakeLipSyncTracks(project.id, scene.id);
                  setTracks(res.tracks);
                  setMsg("Sticky tracks baked from the scene video.");
                  onChange();
                } catch (err) {
                  setMsg(err instanceof Error ? err.message : String(err));
                } finally {
                  setBusy(null);
                }
              }}
            >
              {busy === "bake" ? "Baking…" : "Bake sticky tracks"}
            </button>
            <button
              className="primary"
              disabled={busy !== null}
              onClick={async () => {
                setBusy("apply");
                setMsg("");
                try {
                  await api.applyLipSyncTracks(project.id, scene.id);
                  setMsg("Lip sync job queued — watch Render queue.");
                  onChange();
                } catch (err) {
                  setMsg(err instanceof Error ? err.message : String(err));
                } finally {
                  setBusy(null);
                }
              }}
            >
              {busy === "apply" ? "Queuing…" : "Apply lip sync"}
            </button>
          </div>
          {msg && <p className="scene-meta">{msg}</p>}
          {active.track_path?.length > 0 && (
            <p className="scene-meta">
              Track {active.slot} baked · {active.track_path.length} frames · modes include landmark/flow/frozen for
              head turns
            </p>
          )}
        </>
      )}
    </div>
  );
}
