import { useEffect, useMemo, useRef, useState } from "react";
import type { Asset, Project, Scene } from "../types";
import { api } from "../api";
import { LipSyncTracksPanel } from "./LipSyncTracks";
import { PanelHeading } from "./HelpTip";
import { useDirectorSelectionOptional } from "./DirectorSelectionContext";
import { VisualReferencesPanel } from "./VisualReferencesPanel";

export type RegionBox = { x: number; y: number; w: number; h: number };
export type TimelineClip = {
  id: string;
  asset_id?: string | null;
  start: number;
  length: number;
  trim_start?: number;
  label?: string;
  role?: "start" | "middle" | "end" | "guide";
  /** Stable timeline tag e.g. @Image1 — never renumbered on delete/move. */
  display_tag?: string | null;
  volume?: number;
  fade_in?: number;
  fade_out?: number;
};
export type PromptSegment = {
  id: string;
  start: number;
  length: number;
  text: string;
  weight?: number;
  region?: RegionBox | null;
  /** Foley / ambience / music cues for Audio Studio / Editor (intent only). */
  audio_intent?: string[];
  script_segment_id?: string | null;
  storyboard_panel_id?: string | null;
  scene_state_id?: string | null;
  model_prompt?: string | null;
  negative_prompt?: string | null;
};
export type CameraClip = {
  id: string;
  start: number;
  length: number;
  motion_type: string;
  speed?: number;
  distance?: number;
  ease?: string;
  shake?: number;
  blend?: number;
  rig: string;
  label?: string;
  preset_id?: string | null;
};
export type DirectorTimeline = {
  media_mode: "image" | "video";
  duration_sec: number;
  image_clips: TimelineClip[];
  video_clips: TimelineClip[];
  prompt_segments: PromptSegment[];
  camera_clips?: CameraClip[];
  audio_clips: TimelineClip[];
  sfx_clips: TimelineClip[];
  lipsync: { tracks: any[] };
  playhead: number;
  /** Monotonic allocator for @ImageN tags (per scene timeline). */
  next_image_tag_number?: number;
};

function nid() {
  return Math.random().toString(36).slice(2, 10);
}

function pct(start: number, length: number, duration: number) {
  const d = Math.max(0.1, duration);
  return {
    left: `${(start / d) * 100}%`,
    width: `${(Math.max(0.15, length) / d) * 100}%`,
  };
}

function snapTime(t: number, snap: boolean, step = 0.25) {
  if (!snap) return Math.max(0, t);
  return Math.max(0, Math.round(t / step) * step);
}

/** Normalize legacy start/middle/end roles into free guide clips for Director 2.0.
 * Preserves stable display_tag; never overwrites tags with index-based Image N.
 */
function freeImageClips(tl: DirectorTimeline): TimelineClip[] {
  const clips = tl.image_clips || [];
  if (!clips.length) return [];
  return clips.map((c, i) => {
    const resolvedLabel = c.display_tag
      ? c.display_tag
      : c.label && !["Start", "Middle", "End"].includes(c.label)
        ? c.label
        : `Image ${i + 1}`;
    return {
      ...c,
      role: "guide" as const,
      label: resolvedLabel,
    };
  });
}

export function DirectorTracks({
  project,
  scene,
  onChange,
  viewMode = "tracks",
  onGoEditor,
}: {
  project: Project;
  scene?: Scene;
  onChange: () => void;
  viewMode?: "tracks" | "prompt" | "full";
  onGoEditor?: () => void;
}) {
  const sel = useDirectorSelectionOptional();
  const [tl, setTl] = useState<DirectorTimeline | null>(null);
  const [selectedSeg, setSelectedSeg] = useState<string>();
  const [selectedClip, setSelectedClip] = useState<string>();
  const [saving, setSaving] = useState(false);
  const [tagWarnings, setTagWarnings] = useState<string[]>([]);
  const [sendMsg, setSendMsg] = useState<string | null>(null);
  const [sendBusy, setSendBusy] = useState(false);
  const [includeAudio, setIncludeAudio] = useState(true);
  const [proxyFlag, setProxyFlag] = useState(false);
  const [audioIntentDraft, setAudioIntentDraft] = useState("");
  const zoom = sel?.zoom ?? 1;
  const setZoom = sel?.setZoom ?? (() => undefined);
  const snap = sel?.snap ?? true;
  const setSnap = sel?.setSnap ?? (() => undefined);
  const fileImageRef = useRef<HTMLInputElement>(null);
  const fileVideoRef = useRef<HTMLInputElement>(null);
  const fileAudioRef = useRef<HTMLInputElement>(null);
  const fileSfxRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (!scene) return;
    api.getDirector(project.id, scene.id).then((d) => {
      const next = { ...d, image_clips: freeImageClips(d) };
      setTl(next);
      setSelectedSeg(next.prompt_segments[0]?.id);
    });
  }, [project.id, scene?.id]);

  const assetsById = useMemo(() => {
    const m = new Map<string, Asset>();
    project.assets.forEach((a) => m.set(a.id, a));
    return m;
  }, [project.assets]);

  if (!scene || !tl) {
    return (
      <div className="panel">
        <PanelHeading
          title="Prompt Timeline"
          tip="Director Prompt Timeline: stack images or a video, add audio and SFX, and prompt-edit timed segments. Director creates the shots — Editor assembles the film."
        />
        <p className="empty">Select a scene</p>
      </div>
    );
  }

  const hasOutput = !!(scene.output_path || scene.lipsync_output_path || tl.video_clips[0]?.asset_id);

  const sendToEditor = async (mode: "shot" | "sequence" | "selected") => {
    if (!scene) return;
    setSendBusy(true);
    setSendMsg(null);
    try {
      const segmentIds =
        mode === "selected" && selectedSeg
          ? [selectedSeg]
          : mode === "selected"
            ? tl.prompt_segments.map((s) => s.id)
            : undefined;
      const seq = await api.directorSequenceFromScene(project.id, {
        scene_id: scene.id,
        name: `${scene.name} · ${mode === "shot" ? "Shot" : mode === "selected" ? "Segments" : "Sequence"}`,
        status: hasOutput ? "approved" : "draft",
        include_audio: includeAudio,
        proxy: proxyFlag,
        segment_ids: segmentIds,
      });
      if (hasOutput || mode === "sequence") {
        await api.patchDirectorSequence(project.id, seq.id, { approve: true });
      }
      await api.sendDirectorToEditor(project.id, seq.id, {
        track: "video",
        include_audio: includeAudio,
        proxy: proxyFlag,
        label: seq.name,
      });
      setSendMsg(`Sent to Editor (${mode}${proxyFlag ? ", proxy" : ""}${includeAudio ? "" : ", video only"}).`);
      onGoEditor?.();
    } catch (e) {
      setSendMsg(e instanceof Error ? e.message : "Send to Editor failed");
    } finally {
      setSendBusy(false);
    }
  };

  const save = async (next: DirectorTimeline) => {
    setTl(next);
    setSaving(true);
    try {
      await api.putDirector(project.id, scene.id, next);
      onChange();
    } finally {
      setSaving(false);
    }
  };

  const duration = tl.duration_sec || scene.duration_sec || 5;
  const activeSeg = tl.prompt_segments.find((s) => s.id === selectedSeg) || tl.prompt_segments[0];
  const images = project.assets.filter((a) => a.kind === "image");
  const videos = project.assets.filter((a) => a.kind === "video");
  const audios = project.assets.filter((a) => a.kind === "audio");
  const imageClips = freeImageClips(tl);
  const boardWidth = Math.max(480, duration * 90 * zoom);

  const selectSeg = (id: string) => {
    setSelectedSeg(id);
    sel?.setSelection({ kind: "promptSeg", id });
  };
  const selectClip = (kind: "imageClip" | "videoClip" | "audio" | "sfx", id: string) => {
    setSelectedClip(id);
    sel?.setSelection({ kind, id });
  };

  const uploadAndAdd = async (kind: "image" | "video" | "audio" | "sfx", file: File) => {
    const tag = `${scene.name}_${kind}_${nid()}`.replace(/\s+/g, "_").toLowerCase();
    const assetKind = kind === "sfx" ? "audio" : kind;
    const asset = (await api.uploadAsset(project.id, file, tag, assetKind)) as Asset;
    const next = { ...tl };

    if (kind === "image") {
      const start = imageClips.reduce((m, c) => Math.max(m, c.start + c.length), 0);
      const clip: TimelineClip = {
        id: nid(),
        start: snapTime(Math.min(start, Math.max(0, duration - 1)), snap),
        length: Math.min(2, duration),
        label: `Image ${imageClips.length + 1}`,
        role: "guide",
        display_tag: null,
        asset_id: asset.id,
      };
      next.image_clips = [...imageClips, clip];
      next.media_mode = "image";
      selectClip("imageClip", clip.id);
    } else if (kind === "video") {
      next.media_mode = "video";
      next.video_clips = [
        {
          id: nid(),
          start: 0,
          length: duration,
          label: "Video",
          asset_id: asset.id,
          trim_start: 0,
        },
      ];
      selectClip("videoClip", next.video_clips[0].id);
    } else if (kind === "audio") {
      next.audio_clips = [
        ...tl.audio_clips,
        { id: nid(), start: 0, length: duration, label: "Audio", asset_id: asset.id, volume: 1 },
      ];
    } else {
      next.sfx_clips = [
        ...tl.sfx_clips,
        {
          id: nid(),
          start: snapTime(Math.min(1, duration - 0.5), snap),
          length: 1,
          label: "SFX",
          asset_id: asset.id,
          volume: 1,
        },
      ];
    }
    await save(next);
  };

  const addImageFromLibrary = async (assetId: string) => {
    if (!assetId) return;
    const start = imageClips.reduce((m, c) => Math.max(m, c.start + c.length), 0);
    const clip: TimelineClip = {
      id: nid(),
      start: snapTime(Math.min(start, Math.max(0, duration - 1)), snap),
      length: Math.min(2, duration),
      label: `Image ${imageClips.length + 1}`,
      role: "guide",
      display_tag: null,
      asset_id: assetId,
    };
    await save({ ...tl, media_mode: "image", image_clips: [...imageClips, clip] });
    selectClip("imageClip", clip.id);
  };

  const onDropAsset = async (e: React.DragEvent, kind: "image" | "audio" | "sfx") => {
    e.preventDefault();
    const assetId = e.dataTransfer.getData("application/x-adept-asset");
    if (!assetId) return;
    if (kind === "image") await addImageFromLibrary(assetId);
    else if (kind === "audio") {
      await save({
        ...tl,
        audio_clips: [
          ...tl.audio_clips,
          { id: nid(), start: 0, length: duration, label: "Audio", asset_id: assetId, volume: 1 },
        ],
      });
    } else {
      await save({
        ...tl,
        sfx_clips: [
          ...tl.sfx_clips,
          { id: nid(), start: snapTime(1, snap), length: 1, label: "SFX", asset_id: assetId, volume: 1 },
        ],
      });
    }
  };

  const switchToVideo = async () => {
    await save({
      ...tl,
      media_mode: "video",
      video_clips: tl.video_clips.length
        ? tl.video_clips
        : [{ id: nid(), start: 0, length: duration, label: "Video", asset_id: null, trim_start: 0 }],
    });
  };

  const switchToImage = async () => {
    await save({ ...tl, media_mode: "image", image_clips: imageClips });
  };

  const addPromptSegment = async () => {
    const seg: PromptSegment = {
      id: nid(),
      start: snapTime(Math.min(duration - 1, activeSeg ? activeSeg.start + activeSeg.length : 0), snap),
      length: Math.min(2, duration),
      text: "",
      weight: 1,
      region: null,
    };
    await save({ ...tl, prompt_segments: [...tl.prompt_segments, seg] });
    selectSeg(seg.id);
  };

  const duplicateSeg = async () => {
    if (!activeSeg) return;
    const seg: PromptSegment = {
      ...activeSeg,
      id: nid(),
      start: snapTime(Math.min(duration - 0.2, activeSeg.start + activeSeg.length), snap),
    };
    await save({ ...tl, prompt_segments: [...tl.prompt_segments, seg] });
    selectSeg(seg.id);
  };

  const splitSeg = async () => {
    if (!activeSeg || activeSeg.length < 0.5) return;
    const mid = activeSeg.length / 2;
    const a = { ...activeSeg, length: mid };
    const b: PromptSegment = {
      ...activeSeg,
      id: nid(),
      start: snapTime(activeSeg.start + mid, snap),
      length: mid,
    };
    await save({
      ...tl,
      prompt_segments: tl.prompt_segments.flatMap((s) => (s.id === activeSeg.id ? [a, b] : [s])),
    });
    selectSeg(b.id);
  };

  const deleteSeg = async () => {
    if (!activeSeg || tl.prompt_segments.length <= 1) return;
    const next = tl.prompt_segments.filter((s) => s.id !== activeSeg.id);
    await save({ ...tl, prompt_segments: next });
    selectSeg(next[0].id);
  };

  const previewMedia =
    tl.media_mode === "video" && tl.video_clips[0]?.asset_id
      ? api.assetUrl(tl.video_clips[0].asset_id)
      : imageClips.find((c) => c.asset_id)?.asset_id
        ? api.assetUrl(imageClips.find((c) => c.asset_id)!.asset_id!)
        : scene.output_path
          ? api.mediaUrl(scene.output_path)
          : "";

  const videoClip = tl.video_clips[0];
  const showTracks = viewMode === "tracks" || viewMode === "full";
  const showPromptEditor = viewMode === "prompt" || viewMode === "full";
  const showStage = viewMode !== "prompt";

  return (
    <div className="panel director-tracks">
      <p className="scene-meta" style={{ margin: "0 0 0.35rem", letterSpacing: "0.04em", textTransform: "uppercase", fontSize: "0.7rem" }}>
        Prompt Timeline
      </p>
      <PanelHeading
        title="Director · Prompt Timeline"
        tip="Director creates the shots: timed prompts, camera direction, and model-ready sequences. Assemble the film in Editor."
      >
        <span className="scene-meta">
          {duration.toFixed(1)}s · {saving ? "Saving…" : tl.media_mode === "image" ? "Image timeline" : "Video timeline"}
        </span>
      </PanelHeading>

      {scene && (
        <VisualReferencesPanel
          project={project}
          scene={scene}
          assets={project.assets || []}
          onChange={onChange}
        />
      )}

      {(showTracks || hasOutput) && (
        <div className="director-toolbar send-to-editor-bar" style={{ marginBottom: 8, flexWrap: "wrap" }}>
          <span className="scene-meta">Send to Editor</span>
          <label className="scene-meta">
            <input type="checkbox" checked={includeAudio} onChange={(e) => setIncludeAudio(e.target.checked)} /> Video+audio
          </label>
          <label className="scene-meta">
            <input type="checkbox" checked={!includeAudio} onChange={(e) => setIncludeAudio(!e.target.checked)} /> Video only
          </label>
          <label className="scene-meta">
            <input type="checkbox" checked={proxyFlag} onChange={(e) => setProxyFlag(e.target.checked)} /> Proxy
          </label>
          <button type="button" disabled={sendBusy || !hasOutput} onClick={() => sendToEditor("shot")} title="Current generated shot">
            Current shot
          </button>
          <button type="button" disabled={sendBusy} onClick={() => sendToEditor("sequence")}>
            Full sequence
          </button>
          <button type="button" disabled={sendBusy || !selectedSeg} onClick={() => sendToEditor("selected")}>
            Selected segments
          </button>
          {sendMsg && <span className="pill">{sendMsg}</span>}
        </div>
      )}

      {showStage && (
        <div className="director-stage">
          {(() => {
            const renderSrc = scene.lipsync_output_path
              ? api.mediaUrl(scene.lipsync_output_path)
              : scene.output_path
                ? api.mediaUrl(scene.output_path)
                : "";
            const stageSrc = renderSrc || previewMedia;
            const isVideo =
              !!renderSrc ||
              tl.media_mode === "video" ||
              /\.(mp4|webm|mov)(\?|$)/i.test(stageSrc || "");

            if (!stageSrc) {
              return (
                <div className="director-stage-empty">
                  <strong>Prompt Timeline preview</strong>
                  <span>Add images or switch to video to preview here</span>
                </div>
              );
            }

            return (
              <>
                {isVideo ? (
                  <video key={stageSrc} src={stageSrc} controls playsInline muted={false} />
                ) : (
                  <img src={stageSrc} alt="Director preview" />
                )}
                {activeSeg?.region && (
                  <div
                    className="region-box"
                    style={{
                      left: `${activeSeg.region.x * 100}%`,
                      top: `${activeSeg.region.y * 100}%`,
                      width: `${activeSeg.region.w * 100}%`,
                      height: `${activeSeg.region.h * 100}%`,
                    }}
                    title="Segment prompt region"
                  />
                )}
              </>
            );
          })()}
        </div>
      )}

      {showTracks && (
        <>
          <div className="director-toolbar">
            <input
              ref={fileImageRef}
              type="file"
              accept="image/*"
              hidden
              onChange={(e) => {
                const f = e.target.files?.[0];
                if (f) uploadAndAdd("image", f);
                e.target.value = "";
              }}
            />
            <input
              ref={fileVideoRef}
              type="file"
              accept="video/*"
              hidden
              onChange={(e) => {
                const f = e.target.files?.[0];
                if (f) uploadAndAdd("video", f);
                e.target.value = "";
              }}
            />
            <input
              ref={fileAudioRef}
              type="file"
              accept="audio/*"
              hidden
              onChange={(e) => {
                const f = e.target.files?.[0];
                if (f) uploadAndAdd("audio", f);
                e.target.value = "";
              }}
            />
            <input
              ref={fileSfxRef}
              type="file"
              accept="audio/*"
              hidden
              onChange={(e) => {
                const f = e.target.files?.[0];
                if (f) uploadAndAdd("sfx", f);
                e.target.value = "";
              }}
            />

            {tl.media_mode === "image" ? (
              <>
                <button type="button" onClick={() => fileImageRef.current?.click()}>
                  Add image
                </button>
                {images.length > 0 && (
                  <select
                    defaultValue=""
                    onChange={(e) => {
                      addImageFromLibrary(e.target.value);
                      e.target.value = "";
                    }}
                  >
                    <option value="">Library image…</option>
                    {images.map((a) => (
                      <option key={a.id} value={a.id}>
                        @{a.tag || a.filename}
                      </option>
                    ))}
                  </select>
                )}
              </>
            ) : (
              <button type="button" onClick={() => fileVideoRef.current?.click()}>
                {videoClip?.asset_id ? "Replace video" : "Upload video"}
              </button>
            )}

            <button type="button" onClick={() => fileAudioRef.current?.click()}>
              Add audio
            </button>
            <button type="button" onClick={() => fileSfxRef.current?.click()}>
              Add SFX
            </button>

            {tl.media_mode === "image" ? (
              <button type="button" className="primary" onClick={switchToVideo}>
                Switch to Video
              </button>
            ) : (
              <button type="button" className="primary" onClick={switchToImage}>
                Switch to Image
              </button>
            )}

            <label className="scene-meta director-duration">
              Duration
              <input
                style={{ width: 64 }}
                type="number"
                min={1}
                max={30}
                step={0.5}
                value={duration}
                onChange={(e) => save({ ...tl, duration_sec: Number(e.target.value) || 5 })}
              />
              s
            </label>
          </div>

          <div className="director-zoom">
            <span className="scene-meta">Track zoom</span>
            <button
              type="button"
              className="ghost"
              onClick={() => setZoom(Math.max(0.5, +(zoom - 0.25).toFixed(2)))}
            >
              −
            </button>
            <input
              type="range"
              min={0.5}
              max={3}
              step={0.05}
              value={zoom}
              onChange={(e) => setZoom(Number(e.target.value))}
              aria-label="Zoom timeline tracks"
            />
            <button
              type="button"
              className="ghost"
              onClick={() => setZoom(Math.min(3, +(zoom + 0.25).toFixed(2)))}
            >
              +
            </button>
            <span className="scene-meta">{zoom.toFixed(2)}×</span>
            <label
              className="scene-meta"
              style={{ display: "inline-flex", gap: 6, alignItems: "center", marginLeft: 8 }}
            >
              <input
                type="checkbox"
                checked={snap}
                onChange={(e) => setSnap(e.target.checked)}
                style={{ width: "auto" }}
              />
              Snap
            </label>
          </div>

          <div className="track-board-scroll">
            <div className="track-board" style={{ width: boardWidth, minWidth: "100%" }}>
              <div className="track-ruler">
                {Array.from({ length: Math.floor(duration) + 1 }).map((_, i) => (
                  <span key={i} style={{ left: `${(i / duration) * 100}%` }}>
                    {i}s
                  </span>
                ))}
              </div>

              {tl.media_mode === "image" ? (
                <div
                  className="track-row"
                  onDragOver={(e) => e.preventDefault()}
                  onDrop={(e) => onDropAsset(e, "image")}
                >
                  <div className="track-label">Images</div>
                  <div className="track-lane">
                    {imageClips.length === 0 && (
                      <div className="track-empty">Add images to build the timeline</div>
                    )}
                    {imageClips.map((clip) => {
                      const asset = clip.asset_id ? assetsById.get(clip.asset_id) : undefined;
                      return (
                        <div
                          key={clip.id}
                          className={`track-clip media ${selectedClip === clip.id ? "active" : ""}`}
                          style={pct(clip.start, clip.length, duration)}
                          onClick={() => selectClip("imageClip", clip.id)}
                        >
                          <strong>{clip.display_tag || clip.label || "Image"}</strong>
                          <span>{asset ? `@${asset.tag || asset.filename}` : "empty"}</span>
                          <select
                            value={clip.asset_id || ""}
                            onClick={(e) => e.stopPropagation()}
                            onChange={(e) =>
                              save({
                                ...tl,
                                image_clips: imageClips.map((c) =>
                                  c.id === clip.id ? { ...c, asset_id: e.target.value || null } : c
                                ),
                              })
                            }
                          >
                            <option value="">Asset…</option>
                            {images.map((a) => (
                              <option key={a.id} value={a.id}>
                                @{a.tag || a.filename}
                              </option>
                            ))}
                          </select>
                        </div>
                      );
                    })}
                  </div>
                </div>
              ) : (
                <div className="track-row">
                  <div className="track-label">Video</div>
                  <div className="track-lane">
                    {(tl.video_clips.length
                      ? tl.video_clips
                      : [{ id: "video-empty", start: 0, length: duration, asset_id: null, label: "Video" }]
                    ).map((clip) => {
                      const asset = clip.asset_id ? assetsById.get(clip.asset_id) : undefined;
                      return (
                        <div
                          key={clip.id}
                          className={`track-clip media ${selectedClip === clip.id ? "active" : ""}`}
                          style={pct(clip.start, clip.length, duration)}
                          onClick={() =>
                            selectClip("videoClip", clip.id === "video-empty" ? "" : clip.id)
                          }
                        >
                          <strong>Video</strong>
                          <span>{asset ? `@${asset.tag || asset.filename}` : "Upload a video"}</span>
                          {videos.length > 0 && (
                            <select
                              value={clip.asset_id || ""}
                              onClick={(e) => e.stopPropagation()}
                              onChange={(e) =>
                                save({
                                  ...tl,
                                  video_clips: [
                                    {
                                      id: clip.id === "video-empty" ? nid() : clip.id,
                                      start: 0,
                                      length: duration,
                                      label: "Video",
                                      asset_id: e.target.value || null,
                                      trim_start: 0,
                                    },
                                  ],
                                })
                              }
                            >
                              <option value="">Library…</option>
                              {videos.map((a) => (
                                <option key={a.id} value={a.id}>
                                  @{a.tag || a.filename}
                                </option>
                              ))}
                            </select>
                          )}
                        </div>
                      );
                    })}
                  </div>
                </div>
              )}

              <div className="track-row">
                <div className="track-label">
                  Prompt
                  <button
                    className="ghost"
                    style={{ padding: "0.15rem 0.45rem", marginTop: 4 }}
                    onClick={addPromptSegment}
                  >
                    + Seg
                  </button>
                </div>
                <div className="track-lane">
                  {tl.prompt_segments.map((seg) => (
                    <button
                      key={seg.id}
                      type="button"
                      className={`track-clip prompt ${selectedSeg === seg.id ? "active" : ""}`}
                      style={pct(seg.start, seg.length, duration)}
                      onClick={() => selectSeg(seg.id)}
                    >
                      <strong>{seg.region ? "Region" : `w${(seg.weight ?? 1).toFixed(1)}`}</strong>
                      <span>{seg.text ? seg.text.slice(0, 28) : "Empty prompt"}</span>
                    </button>
                  ))}
                </div>
              </div>

              <div className="track-row">
                <div className="track-label">
                  Camera Motion
                  <button
                    className="ghost"
                    style={{ padding: "0.15rem 0.45rem", marginTop: 4 }}
                    onClick={() => {
                      const clip: CameraClip = {
                        id: nid(),
                        start: 0,
                        length: Math.min(2, duration),
                        motion_type: "dolly_in",
                        speed: 1,
                        distance: 1,
                        ease: "ease_in_out",
                        shake: 0,
                        blend: 0.5,
                        rig: "dolly",
                        label: "Dolly In",
                      };
                      save({ ...tl, camera_clips: [...(tl.camera_clips || []), clip] });
                    }}
                  >
                    + Cam
                  </button>
                </div>
                <div
                  className="track-lane"
                  onDragOver={(e) => e.preventDefault()}
                  onDrop={(e) => {
                    e.preventDefault();
                    const presetKind = e.dataTransfer.getData("application/x-adept-profile-kind");
                    if (presetKind !== "camera_preset" && presetKind !== "motion_preset") return;
                    const tag = e.dataTransfer.getData("application/x-adept-profile-tag");
                    const clip: CameraClip = {
                      id: nid(),
                      start: 0,
                      length: Math.min(2, duration),
                      motion_type: "dolly_in",
                      speed: 0.8,
                      distance: 1,
                      ease: "ease_in_out",
                      shake: 0,
                      blend: 0.5,
                      rig: "dolly",
                      label: tag || "Preset",
                      preset_id: e.dataTransfer.getData("application/x-adept-profile"),
                    };
                    save({ ...tl, camera_clips: [...(tl.camera_clips || []), clip] });
                  }}
                >
                  {(tl.camera_clips || []).length === 0 && (
                    <div className="track-empty">Add camera motion · drop presets</div>
                  )}
                  {(tl.camera_clips || []).map((clip) => (
                    <div
                      key={clip.id}
                      className={`track-clip media ${selectedClip === clip.id ? "active" : ""}`}
                      style={pct(clip.start, clip.length, duration)}
                      onClick={() => {
                        setSelectedClip(clip.id);
                        sel?.setSelection({ kind: "lipsync", id: clip.id });
                      }}
                    >
                      <strong>{clip.motion_type.replace(/_/g, " ")}</strong>
                      <span>{clip.rig}</span>
                      <select
                        value={clip.motion_type}
                        onClick={(e) => e.stopPropagation()}
                        onChange={(e) =>
                          save({
                            ...tl,
                            camera_clips: (tl.camera_clips || []).map((c) =>
                              c.id === clip.id ? { ...c, motion_type: e.target.value } : c
                            ),
                          })
                        }
                      >
                        {[
                          "static",
                          "dolly_in",
                          "dolly_out",
                          "push",
                          "pull",
                          "pan",
                          "tilt",
                          "orbit",
                          "crane",
                          "rail",
                          "handheld",
                          "drone",
                        ].map((m) => (
                          <option key={m} value={m}>
                            {m}
                          </option>
                        ))}
                      </select>
                      <select
                        value={clip.rig}
                        onClick={(e) => e.stopPropagation()}
                        onChange={(e) =>
                          save({
                            ...tl,
                            camera_clips: (tl.camera_clips || []).map((c) =>
                              c.id === clip.id ? { ...c, rig: e.target.value } : c
                            ),
                          })
                        }
                      >
                        {[
                          "tripod",
                          "dolly",
                          "crane",
                          "steadicam",
                          "handheld",
                          "drone",
                          "rail",
                          "gimbal",
                          "virtual",
                        ].map((r) => (
                          <option key={r} value={r}>
                            {r}
                          </option>
                        ))}
                      </select>
                    </div>
                  ))}
                </div>
              </div>

              <div
                className="track-row"
                onDragOver={(e) => e.preventDefault()}
                onDrop={(e) => onDropAsset(e, "audio")}
              >
                <div className="track-label">Audio</div>
                <div className="track-lane">
                  {tl.audio_clips.length === 0 && <div className="track-empty">Add audio bed</div>}
                  {tl.audio_clips.map((clip) => (
                    <div
                      key={clip.id}
                      className={`track-clip audio ${selectedClip === clip.id ? "active" : ""}`}
                      style={pct(clip.start, clip.length, duration)}
                      onClick={() => selectClip("audio", clip.id)}
                    >
                      <strong>Audio</strong>
                      <select
                        value={clip.asset_id || ""}
                        onClick={(e) => e.stopPropagation()}
                        onChange={(e) =>
                          save({
                            ...tl,
                            audio_clips: tl.audio_clips.map((c) =>
                              c.id === clip.id ? { ...c, asset_id: e.target.value || null } : c
                            ),
                          })
                        }
                      >
                        <option value="">Select…</option>
                        {audios.map((a) => (
                          <option key={a.id} value={a.id}>
                            @{a.tag || a.filename}
                          </option>
                        ))}
                      </select>
                    </div>
                  ))}
                </div>
              </div>

              <div
                className="track-row"
                onDragOver={(e) => e.preventDefault()}
                onDrop={(e) => onDropAsset(e, "sfx")}
              >
                <div className="track-label">SFX</div>
                <div className="track-lane">
                  {tl.sfx_clips.length === 0 && <div className="track-empty">Add SFX clips</div>}
                  {tl.sfx_clips.map((clip) => (
                    <div
                      key={clip.id}
                      className={`track-clip sfx ${selectedClip === clip.id ? "active" : ""}`}
                      style={pct(clip.start, clip.length, duration)}
                      onClick={() => selectClip("sfx", clip.id)}
                    >
                      <strong>SFX</strong>
                      <select
                        value={clip.asset_id || ""}
                        onClick={(e) => e.stopPropagation()}
                        onChange={(e) =>
                          save({
                            ...tl,
                            sfx_clips: tl.sfx_clips.map((c) =>
                              c.id === clip.id ? { ...c, asset_id: e.target.value || null } : c
                            ),
                          })
                        }
                      >
                        <option value="">Select…</option>
                        {audios.map((a) => (
                          <option key={a.id} value={a.id}>
                            @{a.tag || a.filename}
                          </option>
                        ))}
                      </select>
                    </div>
                  ))}
                </div>
              </div>

              <div className="track-row">
                <div className="track-label">Lip sync 1</div>
                <div className="track-lane">
                  <div
                    className="track-clip lipsync"
                    style={pct(0, duration, duration)}
                    onClick={() => sel?.setSelection({ kind: "lipsync", id: "0", trackIndex: 0 })}
                  >
                    <strong>{tl.lipsync?.tracks?.[0]?.label || "Character 1"}</strong>
                    <span>{tl.lipsync?.tracks?.[0]?.enabled ? "Enabled" : "Off — Lip Sync tab"}</span>
                  </div>
                </div>
              </div>
              <div className="track-row">
                <div className="track-label">Lip sync 2</div>
                <div className="track-lane">
                  <div
                    className="track-clip lipsync"
                    style={pct(0, duration, duration)}
                    onClick={() => sel?.setSelection({ kind: "lipsync", id: "1", trackIndex: 1 })}
                  >
                    <strong>{tl.lipsync?.tracks?.[1]?.label || "Character 2"}</strong>
                    <span>{tl.lipsync?.tracks?.[1]?.enabled ? "Enabled" : "Off — Lip Sync tab"}</span>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </>
      )}

      {showPromptEditor && tl.media_mode === "video" && videoClip && (
        <div className="segment-editor">
          <div className="section-label">Video segment for prompt edit</div>
          <div className="row-actions">
            <label className="scene-meta">
              In-point (s)
              <input
                style={{ width: 72 }}
                type="number"
                min={0}
                max={duration}
                step={0.1}
                value={videoClip.trim_start || 0}
                onChange={(e) =>
                  save({
                    ...tl,
                    video_clips: tl.video_clips.map((c) =>
                      c.id === videoClip.id ? { ...c, trim_start: Number(e.target.value) || 0 } : c
                    ),
                  })
                }
              />
            </label>
            <button type="button" onClick={addPromptSegment}>
              New prompt segment
            </button>
          </div>
        </div>
      )}

      {showPromptEditor && activeSeg && (
        <div className="segment-editor">
          <div className="section-label">Selected prompt segment</div>
          <div className="row-actions" style={{ marginBottom: 8 }}>
            <label className="scene-meta">
              Start
              <input
                style={{ width: 72 }}
                type="number"
                min={0}
                max={duration}
                step={0.1}
                value={activeSeg.start}
                onChange={(e) =>
                  setTl({
                    ...tl,
                    prompt_segments: tl.prompt_segments.map((s) =>
                      s.id === activeSeg.id
                        ? { ...s, start: snapTime(Number(e.target.value) || 0, snap) }
                        : s
                    ),
                  })
                }
                onBlur={() => save(tl)}
              />
            </label>
            <label className="scene-meta">
              Length
              <input
                style={{ width: 72 }}
                type="number"
                min={0.2}
                max={duration}
                step={0.1}
                value={activeSeg.length}
                onChange={(e) =>
                  setTl({
                    ...tl,
                    prompt_segments: tl.prompt_segments.map((s) =>
                      s.id === activeSeg.id ? { ...s, length: Number(e.target.value) || 1 } : s
                    ),
                  })
                }
                onBlur={() => save(tl)}
              />
            </label>
            <label className="scene-meta">
              Weight
              <input
                style={{ width: 72 }}
                type="number"
                min={0.1}
                max={2}
                step={0.1}
                value={activeSeg.weight ?? 1}
                onChange={(e) =>
                  setTl({
                    ...tl,
                    prompt_segments: tl.prompt_segments.map((s) =>
                      s.id === activeSeg.id ? { ...s, weight: Number(e.target.value) || 1 } : s
                    ),
                  })
                }
                onBlur={() => save(tl)}
              />
            </label>
          </div>
          <div className="field">
            <label>Segment prompt</label>
            <textarea
              value={activeSeg.text}
              onChange={(e) =>
                setTl({
                  ...tl,
                  prompt_segments: tl.prompt_segments.map((s) =>
                    s.id === activeSeg.id ? { ...s, text: e.target.value } : s
                  ),
                })
              }
              onBlur={async () => {
                await save(tl);
                try {
                  const v = await api.validateMotionTags(activeSeg.text || "");
                  setTagWarnings(v.warnings || []);
                } catch {
                  setTagWarnings([]);
                }
              }}
            />
          </div>
          <div className="field">
            <label>Audio Intent</label>
            <p className="muted" style={{ margin: "0 0 0.35rem" }}>
              Foley / ambience / music cues for Editor &amp; Audio Studio (labels only — no synthesis yet).
            </p>
            <div className="row-actions" style={{ flexWrap: "wrap", marginBottom: 6 }}>
              {(activeSeg.audio_intent || []).map((intent) => (
                <button
                  key={intent}
                  type="button"
                  className="pill"
                  title="Remove"
                  onClick={() =>
                    save({
                      ...tl,
                      prompt_segments: tl.prompt_segments.map((s) =>
                        s.id === activeSeg.id
                          ? { ...s, audio_intent: (s.audio_intent || []).filter((x) => x !== intent) }
                          : s
                      ),
                    })
                  }
                >
                  {intent} ×
                </button>
              ))}
            </div>
            <div className="row-actions">
              <input
                style={{ flex: 1, minWidth: 160 }}
                placeholder="e.g. hydraulic door, corridor ambience"
                value={audioIntentDraft}
                onChange={(e) => setAudioIntentDraft(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter") {
                    e.preventDefault();
                    const v = audioIntentDraft.trim();
                    if (!v) return;
                    const next = Array.from(new Set([...(activeSeg.audio_intent || []), v]));
                    setAudioIntentDraft("");
                    save({
                      ...tl,
                      prompt_segments: tl.prompt_segments.map((s) =>
                        s.id === activeSeg.id ? { ...s, audio_intent: next } : s
                      ),
                    });
                  }
                }}
              />
              <button
                type="button"
                onClick={() => {
                  const v = audioIntentDraft.trim();
                  if (!v) return;
                  const next = Array.from(new Set([...(activeSeg.audio_intent || []), v]));
                  setAudioIntentDraft("");
                  save({
                    ...tl,
                    prompt_segments: tl.prompt_segments.map((s) =>
                      s.id === activeSeg.id ? { ...s, audio_intent: next } : s
                    ),
                  });
                }}
              >
                Add intent
              </button>
            </div>
          </div>
          {tagWarnings.length > 0 && (
            <div className="pill warn" style={{ marginBottom: 8 }}>
              {tagWarnings.join(" · ")}
            </div>
          )}
          <div className="row-actions">
            <button
              onClick={() =>
                save({
                  ...tl,
                  prompt_segments: tl.prompt_segments.map((s) =>
                    s.id === activeSeg.id
                      ? { ...s, region: s.region || { x: 0.25, y: 0.25, w: 0.5, h: 0.5 } }
                      : s
                  ),
                })
              }
            >
              {activeSeg.region ? "Region on" : "Add region highlight"}
            </button>
            {activeSeg.region && (
              <button
                onClick={() =>
                  save({
                    ...tl,
                    prompt_segments: tl.prompt_segments.map((s) =>
                      s.id === activeSeg.id ? { ...s, region: null } : s
                    ),
                  })
                }
              >
                Clear region
              </button>
            )}
            <button type="button" onClick={duplicateSeg}>
              Duplicate
            </button>
            <button type="button" onClick={splitSeg}>
              Split
            </button>
            <button type="button" className="danger" onClick={deleteSeg}>
              Delete
            </button>
          </div>
        </div>
      )}

      {viewMode === "full" && <LipSyncTracksPanel project={project} scene={scene} onChange={onChange} />}
    </div>
  );
}
