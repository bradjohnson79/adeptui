import { useEffect, useMemo, useRef, useState } from "react";
import type { Asset, Project, Scene } from "../types";
import { api } from "../api";
import { LipSyncTracksPanel } from "./LipSyncTracks";
import { PanelHeading } from "./HelpTip";

export type RegionBox = { x: number; y: number; w: number; h: number };
export type TimelineClip = {
  id: string;
  asset_id?: string | null;
  start: number;
  length: number;
  trim_start?: number;
  label?: string;
  role?: "start" | "middle" | "end" | "guide";
};
export type PromptSegment = {
  id: string;
  start: number;
  length: number;
  text: string;
  region?: RegionBox | null;
};
export type DirectorTimeline = {
  media_mode: "image" | "video";
  duration_sec: number;
  image_clips: TimelineClip[];
  video_clips: TimelineClip[];
  prompt_segments: PromptSegment[];
  audio_clips: TimelineClip[];
  sfx_clips: TimelineClip[];
  lipsync: { tracks: any[] };
  playhead: number;
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

/** Normalize legacy start/middle/end roles into free guide clips for Director 2.0. */
function freeImageClips(tl: DirectorTimeline): TimelineClip[] {
  const clips = tl.image_clips || [];
  if (!clips.length) return [];
  return clips.map((c, i) => ({
    ...c,
    role: "guide" as const,
    label: c.label && !["Start", "Middle", "End"].includes(c.label) ? c.label : `Image ${i + 1}`,
  }));
}

export function DirectorTracks({
  project,
  scene,
  onChange,
}: {
  project: Project;
  scene?: Scene;
  onChange: () => void;
}) {
  const [tl, setTl] = useState<DirectorTimeline | null>(null);
  const [selectedSeg, setSelectedSeg] = useState<string>();
  const [selectedClip, setSelectedClip] = useState<string>();
  const [saving, setSaving] = useState(false);
  const [zoom, setZoom] = useState(1); // 0.5–3 → timeline horizontal scale
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
          title="Director tracks"
          tip="Director 2.0 timeline: stack images or a video, add audio and SFX, and prompt-edit timed segments."
        />
        <p className="empty">Select a scene</p>
      </div>
    );
  }

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

  const uploadAndAdd = async (
    kind: "image" | "video" | "audio" | "sfx",
    file: File
  ) => {
    const tag = `${scene.name}_${kind}_${nid()}`.replace(/\s+/g, "_").toLowerCase();
    const assetKind = kind === "sfx" ? "audio" : kind;
    const asset = (await api.uploadAsset(project.id, file, tag, assetKind)) as Asset;
    const next = { ...tl };

    if (kind === "image") {
      const start = imageClips.reduce((m, c) => Math.max(m, c.start + c.length), 0);
      const clip: TimelineClip = {
        id: nid(),
        start: Math.min(start, Math.max(0, duration - 1)),
        length: Math.min(2, duration),
        label: `Image ${imageClips.length + 1}`,
        role: "guide",
        asset_id: asset.id,
      };
      next.image_clips = [...imageClips, clip];
      next.media_mode = "image";
      setSelectedClip(clip.id);
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
      setSelectedClip(next.video_clips[0].id);
    } else if (kind === "audio") {
      next.audio_clips = [
        ...tl.audio_clips,
        { id: nid(), start: 0, length: duration, label: "Audio", asset_id: asset.id },
      ];
    } else {
      next.sfx_clips = [
        ...tl.sfx_clips,
        { id: nid(), start: Math.min(1, duration - 0.5), length: 1, label: "SFX", asset_id: asset.id },
      ];
    }
    await save(next);
  };

  const addImageFromLibrary = async (assetId: string) => {
    if (!assetId) return;
    const start = imageClips.reduce((m, c) => Math.max(m, c.start + c.length), 0);
    const clip: TimelineClip = {
      id: nid(),
      start: Math.min(start, Math.max(0, duration - 1)),
      length: Math.min(2, duration),
      label: `Image ${imageClips.length + 1}`,
      role: "guide",
      asset_id: assetId,
    };
    await save({ ...tl, media_mode: "image", image_clips: [...imageClips, clip] });
    setSelectedClip(clip.id);
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
      start: Math.min(duration - 1, activeSeg ? activeSeg.start + activeSeg.length : 0),
      length: Math.min(2, duration),
      text: "",
      region: null,
    };
    await save({ ...tl, prompt_segments: [...tl.prompt_segments, seg] });
    setSelectedSeg(seg.id);
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

  return (
    <div className="panel director-tracks">
      <PanelHeading
        title="Director tracks"
        tip="Director 2.0: add free image clips or switch to video, layer audio/SFX, and prompt-edit timed segments on the screen."
      >
        <span className="scene-meta">
          {duration.toFixed(1)}s · {saving ? "Saving…" : tl.media_mode === "image" ? "Image timeline" : "Video timeline"}
        </span>
      </PanelHeading>

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
                <strong>Director screen</strong>
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
              <select defaultValue="" onChange={(e) => { addImageFromLibrary(e.target.value); e.target.value = ""; }}>
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
        <button type="button" className="ghost" onClick={() => setZoom((z) => Math.max(0.5, +(z - 0.25).toFixed(2)))}>
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
        <button type="button" className="ghost" onClick={() => setZoom((z) => Math.min(3, +(z + 0.25).toFixed(2)))}>
          +
        </button>
        <span className="scene-meta">{zoom.toFixed(2)}×</span>
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
            <div className="track-row">
              <div className="track-label">Images</div>
              <div className="track-lane">
                {imageClips.length === 0 && <div className="track-empty">Add images to build the timeline</div>}
                {imageClips.map((clip) => {
                  const asset = clip.asset_id ? assetsById.get(clip.asset_id) : undefined;
                  return (
                    <div
                      key={clip.id}
                      className={`track-clip media ${selectedClip === clip.id ? "active" : ""}`}
                      style={pct(clip.start, clip.length, duration)}
                      onClick={() => setSelectedClip(clip.id)}
                    >
                      <strong>{clip.label || "Image"}</strong>
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
                    <div key={clip.id} className="track-clip media" style={pct(clip.start, clip.length, duration)}>
                      <strong>Video</strong>
                      <span>{asset ? `@${asset.tag || asset.filename}` : "Upload a video"}</span>
                      {videos.length > 0 && (
                        <select
                          value={clip.asset_id || ""}
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
              <button className="ghost" style={{ padding: "0.15rem 0.45rem", marginTop: 4 }} onClick={addPromptSegment}>
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
                  onClick={() => setSelectedSeg(seg.id)}
                >
                  <strong>{seg.region ? "Region" : "Segment"}</strong>
                  <span>{seg.text ? seg.text.slice(0, 28) : "Empty prompt"}</span>
                </button>
              ))}
            </div>
          </div>

          <div className="track-row">
            <div className="track-label">Audio</div>
            <div className="track-lane">
              {tl.audio_clips.length === 0 && <div className="track-empty">Add audio bed</div>}
              {tl.audio_clips.map((clip) => (
                <div key={clip.id} className="track-clip audio" style={pct(clip.start, clip.length, duration)}>
                  <strong>Audio</strong>
                  <select
                    value={clip.asset_id || ""}
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

          <div className="track-row">
            <div className="track-label">SFX</div>
            <div className="track-lane">
              {tl.sfx_clips.length === 0 && <div className="track-empty">Add SFX clips</div>}
              {tl.sfx_clips.map((clip) => (
                <div key={clip.id} className="track-clip sfx" style={pct(clip.start, clip.length, duration)}>
                  <strong>SFX</strong>
                  <select
                    value={clip.asset_id || ""}
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
              <div className="track-clip lipsync" style={pct(0, duration, duration)}>
                <strong>{tl.lipsync?.tracks?.[0]?.label || "Character 1"}</strong>
                <span>{tl.lipsync?.tracks?.[0]?.enabled ? "Enabled" : "Off — edit below"}</span>
              </div>
            </div>
          </div>
          <div className="track-row">
            <div className="track-label">Lip sync 2</div>
            <div className="track-lane">
              <div className="track-clip lipsync" style={pct(0, duration, duration)}>
                <strong>{tl.lipsync?.tracks?.[1]?.label || "Character 2"}</strong>
                <span>{tl.lipsync?.tracks?.[1]?.enabled ? "Enabled" : "Off — edit below"}</span>
              </div>
            </div>
          </div>
        </div>
      </div>

      {tl.media_mode === "video" && videoClip && (
        <div className="segment-editor">
          <div className="section-label">Video segment for prompt edit</div>
          <p className="scene-meta">
            Highlight a time range on the prompt track, then describe the edit. Optional region boxes local changes on
            the Director screen.
          </p>
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

      {activeSeg && (
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
                      s.id === activeSeg.id ? { ...s, start: Number(e.target.value) || 0 } : s
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
          </div>
          <div className="field">
            <label>
              Segment prompt{tl.media_mode === "video" ? " (edits this video range" : " (this time range"}
              {activeSeg.region ? " + highlighted region)" : ")"}
            </label>
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
              onBlur={() => save(tl)}
              placeholder={
                tl.media_mode === "video"
                  ? "e.g. replace sky with dusk clouds, keep subject locked"
                  : "e.g. camera pushes in, she turns toward the window"
              }
            />
          </div>
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
          </div>
        </div>
      )}

      <LipSyncTracksPanel project={project} scene={scene} onChange={onChange} />
    </div>
  );
}
