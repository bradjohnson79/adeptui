import { useEffect, useMemo, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import type { Asset, EngineName, Project } from "../types";
import { api } from "../api";
import { PanelHeading } from "./HelpTip";
import {
  CONTINUITY_KEYS,
  parseContinuity,
  type ContinuityKey,
  type ContinuityLock,
} from "../directorSelection";
import { isTimelineMediaAsset, normalizeTimelineMediaKind } from "../timelineMediaTypes";
import { LibraryQuickPreviewModal } from "./library/LibraryQuickPreviewModal";
import { eventFromActionControl, isQuickPreviewKind } from "./library/libraryQuickPreview";
import {
  assetMatchesLibrarySearch,
  buildCharacterNameMap,
  timelineLibraryIdentity,
} from "./library/timelineLibraryIdentity";
import { EngineAuthoritySelect } from "./generation/EngineAuthoritySelect";
import { VideoResolutionSelect } from "./generation/VideoResolutionSelect";
import { inferVideoTier, resolveSubmitCanvas } from "../video/legalCanvas";

const LIBRARY_FILTERS = [
  { id: "all" as const, label: "All" },
  { id: "image" as const, label: "Image" },
  { id: "audio" as const, label: "Audio" },
  { id: "video" as const, label: "Video" },
];

export function AssetTray({
  project,
  onChange,
  selectedAssetId,
  onSelectAsset,
  onAddToTimeline,
  onAddAsReference,
  onRemoveFromLibrary,
  allowUpload = true,
  stagedAssetIds,
  onOpenProjectLibrary,
}: {
  project: Project;
  onChange: () => void;
  selectedAssetId?: string | null;
  onSelectAsset?: (asset: Asset) => void;
  onAddToTimeline?: (asset: Asset) => void;
  onAddAsReference?: (asset: Asset) => void;
  /** Soft-remove from Timeline Library tray (library_asset_ids). Not Project Library delete. */
  onRemoveFromLibrary?: (asset: Asset) => void;
  allowUpload?: boolean;
  stagedAssetIds?: string[] | null;
  onOpenProjectLibrary?: () => void;
}) {
  const { t } = useTranslation(["timeline", "library", "common"]);
  const [tag, setTag] = useState("");
  const [filter, setFilter] = useState<"all" | "image" | "audio" | "video">("all");
  const [search, setSearch] = useState("");
  const [previewAsset, setPreviewAsset] = useState<Asset | null>(null);
  const [characterNames, setCharacterNames] = useState<Record<string, string>>({});
  const fileRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    let cancelled = false;
    void api
      .listCharacterProfiles(project.id)
      .then((payload) => {
        if (cancelled) return;
        setCharacterNames(buildCharacterNameMap(payload.items || []));
      })
      .catch(() => {
        if (!cancelled) setCharacterNames({});
      });
    return () => {
      cancelled = true;
    };
  }, [project.id]);

  const upload = async (files: FileList | null, kind: string) => {
    if (!files?.length) return;
    for (const file of Array.from(files)) {
      const autoTag = tag || file.name.replace(/\.[^.]+$/, "").replace(/\s+/g, "_").toLowerCase();
      await api.uploadAsset(project.id, file, autoTag, kind);
    }
    setTag("");
    onChange();
  };

  // TIMELINE_LIBRARY_MEDIA_ONLY: the Library only lists media that can live
  // on a track (image/video/audio). Documents and other non-media are
  // excluded. "all" means all compatible media, never every asset kind.
  const timelineAssets = useMemo(() => {
    const media = project.assets.filter((a) => isTimelineMediaAsset(a));
    if (stagedAssetIds === undefined) return media;
    const allowed = new Set(stagedAssetIds || []);
    return media.filter((a) => allowed.has(a.id));
  }, [project.assets, stagedAssetIds]);
  const identities = useMemo(() => {
    const map = new Map<string, ReturnType<typeof timelineLibraryIdentity>>();
    for (const asset of timelineAssets) {
      map.set(asset.id, timelineLibraryIdentity(asset, { characterNames, relatedAssets: project.assets }));
    }
    return map;
  }, [characterNames, project.assets, timelineAssets]);
  const filtered = timelineAssets.filter((a) => {
    if (filter !== "all" && normalizeTimelineMediaKind(a.kind, a.filename) !== filter) return false;
    return assetMatchesLibrarySearch(a, search, identities.get(a.id));
  });
  const libraryTip = `${t("timeline:libraryTip")} ${t("timeline:libraryPreviewHint")}`;

  return (
    <div className="panel asset-tray">
      <PanelHeading title={t("timeline:library")} tip={libraryTip}>
        {onOpenProjectLibrary ? (
          <button
            type="button"
            className="ghost asset-tray__open"
            data-testid="timeline-library-open"
            onClick={onOpenProjectLibrary}
          >
            {t("timeline:library")}
          </button>
        ) : null}
      </PanelHeading>
      {allowUpload ? (
        <div className="asset-tray__upload">
          <div className="field">
            <label>Reference Name (optional)</label>
            <input
              placeholder="korri_front"
              value={tag}
              onChange={(e) => setTag(e.target.value)}
              aria-describedby="asset-ref-name-hint"
            />
            <p id="asset-ref-name-hint" className="scene-meta">
              {tag.trim() ? `Use in prompts as: @${tag.trim()}` : "Auto name assigned on upload if left empty."}
            </p>
          </div>
          <div className="row-actions">
            <button type="button" onClick={() => fileRef.current?.click()}>Upload image</button>
            <button
              type="button"
              onClick={() => {
                const input = document.createElement("input");
                input.type = "file";
                input.accept = "audio/*";
                input.onchange = () => upload(input.files, "audio");
                input.click();
              }}
            >
              Upload audio
            </button>
            <button
              type="button"
              onClick={() => {
                const input = document.createElement("input");
                input.type = "file";
                input.accept = "video/*";
                input.onchange = () => upload(input.files, "video");
                input.click();
              }}
            >
              Upload video
            </button>
          </div>
          <input
            ref={fileRef}
            type="file"
            accept="image/*"
            hidden
            multiple
            onChange={(e) => upload(e.target.files, "image")}
          />
        </div>
      ) : null}
      <div className="asset-tray__browse">
        <div className="asset-filters" role="group" aria-label={t("timeline:library")}>
          {LIBRARY_FILTERS.map((f) => (
            <button
              key={f.id}
              type="button"
              className={filter === f.id ? "primary" : "ghost"}
              onClick={() => setFilter(f.id)}
            >
              {f.label}
            </button>
          ))}
        </div>
        <label className="sr-only" htmlFor="asset-library-search">Search Library</label>
        <input
          id="asset-library-search"
          className="asset-tray__search"
          data-testid="asset-library-search"
          placeholder={t("timeline:searchLibrary")}
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
      </div>
      <div
        className="asset-list"
        data-testid="asset-library-list"
        onDragOver={(event) => {
          if (event.dataTransfer.types.includes("application/x-adept-asset")) event.preventDefault();
        }}
        onDrop={(event) => {
          const assetId = event.dataTransfer.getData("application/x-adept-asset");
          if (!assetId || !onAddToTimeline) return;
          event.preventDefault();
          const asset = project.assets.find((row) => row.id === assetId);
          if (asset) onAddToTimeline(asset);
        }}
      >
        {filtered.length === 0 && (
          <div className="empty" data-testid="timeline-library-empty">
            {onOpenProjectLibrary
              ? t("timeline:libraryChooseFiles", { defaultValue: "Click Library to choose files from this project." })
              : t("timeline:libraryEmpty", { defaultValue: "No files in this project yet." })}
          </div>
        )}
        {filtered.map((a: Asset) => {
          const selected = selectedAssetId === a.id;
          const identity = identities.get(a.id) || timelineLibraryIdentity(a, { characterNames, relatedAssets: project.assets });
          const mediaKind = normalizeTimelineMediaKind(a.kind, a.filename);
          return (
            <div
              className={`asset-item${selected ? " selected" : ""}`}
              key={a.id}
              data-testid={`asset-library-item-${a.id}`}
              data-kind={a.kind}
              data-sheet-kind={identity.sheetKind}
              draggable
              role="button"
              tabIndex={0}
              aria-pressed={selected}
              aria-label={`Preview ${identity.title}`}
              title={identity.tooltip}
              onClick={() => onSelectAsset?.(a)}
              onDoubleClick={(e) => {
                if (eventFromActionControl(e.target)) return;
                if (!isQuickPreviewKind(mediaKind)) return;
                e.preventDefault();
                setPreviewAsset({ ...a, kind: mediaKind, name: identity.title });
              }}
              onKeyDown={(e) => {
                if (e.key === "Enter" || e.key === " ") {
                  e.preventDefault();
                  onSelectAsset?.(a);
                }
              }}
              onDragStart={(e) => {
                e.dataTransfer.setData("application/x-adept-asset", a.id);
                e.dataTransfer.setData("application/x-adept-kind", a.kind);
                e.dataTransfer.effectAllowed = "copy";
              }}
            >
              {mediaKind === "image" ? (
                <img src={api.assetUrl(a.id, null, project.id)} alt="" />
              ) : (
                <div className="ph">{mediaKind === "audio" ? "Aud" : "Vid"}</div>
              )}
              <div className="asset-item__body">
                <div className="asset-item__title">{identity.title}</div>
                <div className="asset-item__meta">{identity.context}</div>
              </div>
              <div
                className="asset-item__actions"
                onClick={(e) => e.stopPropagation()}
                onDoubleClick={(e) => e.stopPropagation()}
              >
                <button
                  type="button"
                  className="ghost asset-item__action"
                  data-testid={`asset-add-timeline-${a.id}`}
                  title={t("timeline:addToTimeline")}
                  aria-label={t("timeline:addToTimeline")}
                  onClick={() => onAddToTimeline?.(a)}
                >
                  Timeline
                </button>
                <button
                  type="button"
                  className="ghost asset-item__action"
                  data-testid={`asset-add-reference-${a.id}`}
                  title={t("timeline:addToReferences")}
                  aria-label={t("timeline:addToReferences")}
                  onClick={() => onAddAsReference?.(a)}
                >
                  Reference
                </button>
                {onRemoveFromLibrary ? (
                  <button
                    type="button"
                    className="ghost asset-item__action asset-item__action--remove"
                    data-testid={`asset-remove-library-${a.id}`}
                    title={t("timeline:removeFromLibraryTitle", {
                      defaultValue: "Remove from Timeline Library. File stays in Project Library.",
                    })}
                    aria-label={t("timeline:removeFromLibrary", {
                      defaultValue: "Remove from Library",
                    })}
                    onClick={() => onRemoveFromLibrary(a)}
                  >
                    ×
                  </button>
                ) : null}
              </div>
            </div>
          );
        })}
      </div>
      <LibraryQuickPreviewModal asset={previewAsset} onClose={() => setPreviewAsset(null)} />
    </div>
  );
}

export function PromptComposer({
  project,
  sceneId,
  onChange,
  showContinuity,
}: {
  project: Project;
  sceneId?: string;
  onChange: () => void;
  showContinuity?: boolean;
}) {
  const scene = project.scenes.find((s) => s.id === sceneId) || project.scenes[0];
  const [suggestOpen, setSuggestOpen] = useState(false);
  const [rec, setRec] = useState<Awaited<ReturnType<typeof api.recommendEngine>> | null>(null);
  const tags = useMemo(() => project.assets.filter((a) => a.tag).map((a) => a.tag), [project.assets]);

  useEffect(() => {
    if (!scene || !showContinuity) return;
    api.recommendEngine(project.id, scene.id).then(setRec).catch(() => setRec(null));
  }, [project.id, scene?.id, scene?.engine, scene?.duration_sec, showContinuity]);

  if (!scene) return null;

  const update = async (patch: Partial<typeof scene>) => {
    await api.updateScene(project.id, scene.id, { ...scene, ...patch });
    onChange();
  };

  const onPrompt = (value: string) => {
    update({ prompt: value });
    setSuggestOpen(value.endsWith("@") || /@\w*$/.test(value));
  };

  const insertTag = (tag: string) => {
    const next = scene.prompt.replace(/@\w*$/, `@${tag}`) + (scene.prompt.endsWith("@") ? tag : "");
    const fixed = /@\w*$/.test(scene.prompt)
      ? scene.prompt.replace(/@\w*$/, `@${tag} `)
      : `${scene.prompt}@${tag} `;
    update({ prompt: fixed || next });
    setSuggestOpen(false);
  };

  const continuity = parseContinuity(scene.continuity_json);
  const setLock = async (key: ContinuityKey, mode: ContinuityLock) => {
    const next = { ...continuity, [key]: mode };
    await update({ continuity_json: JSON.stringify(next) });
  };

  return (
    <div className="panel">
      <PanelHeading
        title={scene.name}
        tip="Per-scene engine, duration, and prompt. Use @tags from Assets. Continuity locks are production instructions until adapters consume them."
      />
      <div className="field">
        <label>Engine {scene.engine === "auto" ? <span className="pill">Auto</span> : null}</label>
        <EngineAuthoritySelect
          value={scene.engine}
          onChange={(engine) => update({ engine })}
        />
      </div>
      {rec && showContinuity && (
        <div className="recommend-card">
          <div className="scene-meta">
            Recommends <strong>{rec.engineId}</strong> ({Math.round(rec.confidence * 100)}%)
          </div>
          <button
            type="button"
            onClick={() => update({ engine: rec.engineId as EngineName })}
          >
            Apply recommendation
          </button>
        </div>
      )}
      <div className="field">
        <label>Duration (seconds)</label>
        <input
          type="number"
          min={1}
          max={30}
          step={0.5}
          value={scene.duration_sec}
          onChange={(e) => update({ duration_sec: Number(e.target.value) })}
        />
      </div>
      {(scene.aspect_ratio || "16:9") !== "custom" && (
        <div className="field">
          <label htmlFor="asset-tray-resolution">Resolution</label>
          <VideoResolutionSelect
            id="asset-tray-resolution"
            engine={String(scene.engine || "auto")}
            aspect={scene.aspect_ratio || "16:9"}
            value={inferVideoTier(
              Number(scene.width || project.width || 0),
              Number(scene.height || project.height || 0),
            )}
            onChange={(_tier, width, height) => update({ width, height })}
          />
        </div>
      )}
      <div className="field">
        <label>Aspect ratio</label>
        <select
          value={scene.aspect_ratio || "16:9"}
          onChange={(e) => update({ aspect_ratio: e.target.value })}
        >
          {["1:1", "4:3", "3:2", "16:10", "16:9", "18:9", "21:9", "9:16", "2.39:1", "custom"].map((a) => (
            <option key={a} value={a}>
              {a}
            </option>
          ))}
        </select>
      </div>
      {(scene.aspect_ratio || "16:9") === "custom" && (
        <div className="row-actions">
          <label className="scene-meta">
            W
            <input
              style={{ width: 80 }}
              type="number"
              value={scene.width || project.width}
              onChange={(e) => update({ width: Number(e.target.value) })}
            />
          </label>
          <label className="scene-meta">
            H
            <input
              style={{ width: 80 }}
              type="number"
              value={scene.height || project.height}
              onChange={(e) => update({ height: Number(e.target.value) })}
            />
          </label>
        </div>
      )}
      <div className="field">
        <label>Frame rate</label>
        <select
          value={scene.fps_mode || "auto"}
          onChange={(e) => {
            const v = e.target.value;
            if (v === "auto") update({ fps_mode: "auto", fps: 0 });
            else update({ fps_mode: v, fps: Number(v) });
          }}
        >
          <option value="auto">Auto</option>
          {[12, 16, 18, 24, 25, 30, 48, 50, 60].map((f) => (
            <option key={f} value={String(f)}>
              {f} fps
            </option>
          ))}
        </select>
        {(project.vram_gb || 32) < 32 && (scene.fps_mode || "auto") !== "auto" && (
          <p className="scene-meta">VRAM advice is shown separately. Adept will not silently change this frame rate.</p>
        )}
      </div>
      <div className="field prompt-box">
        <label>Scene prompt (@tags supported)</label>
        <textarea value={scene.prompt} onChange={(e) => onPrompt(e.target.value)} />
        {suggestOpen && tags.length > 0 && (
          <div className="suggest">
            {tags.map((t) => (
              <button key={t} type="button" onClick={() => insertTag(t)}>
                @{t}
              </button>
            ))}
          </div>
        )}
      </div>
      <div className="field">
        <label>Camera note</label>
        <input
          value={scene.camera_note}
          onChange={(e) => update({ camera_note: e.target.value })}
          placeholder="slow push in from doorway"
        />
      </div>
      <div className="field">
        <label>Seed</label>
        <input type="number" value={scene.seed} onChange={(e) => update({ seed: Number(e.target.value) })} />
      </div>
      {/* Performance Retake quarantine: legacy LatentSync arming removed — see docs/release-gate/performance-retake/PERFORMANCE_RETAKE_ARCHITECTURE.md §8 */}
      {showContinuity && (
        <>
          <div className="section-label">Continuity locks</div>
          <p className="scene-meta">Production instructions — not model guarantees.</p>
          <div className="continuity-grid">
            {CONTINUITY_KEYS.map((k) => (
              <label key={k} className="continuity-row">
                <span>{k.replace(/_/g, " ")}</span>
                <select
                  value={continuity[k]}
                  onChange={(e) => setLock(k, e.target.value as ContinuityLock)}
                >
                  <option value="locked">locked</option>
                  <option value="unlocked">unlocked</option>
                  <option value="inherit_project">inherit project</option>
                  <option value="inherit_previous">inherit previous</option>
                </select>
              </label>
            ))}
          </div>
        </>
      )}
      <div className="row-actions">
        <button
          className="primary"
          onClick={async () => {
            const canvas = resolveSubmitCanvas(
              String(scene.engine || "auto"),
              Number(scene.width || project.width || 0),
              Number(scene.height || project.height || 0),
              scene.aspect_ratio || "16:9",
            );
            if (!canvas.available) return;
            await api.render(project.id, "scene", scene.id, {
              engine: scene.engine,
              width: canvas.width,
              height: canvas.height,
              resolution: `${canvas.width}x${canvas.height}`,
            });
            onChange();
          }}
        >
          Retake scene
        </button>
        <button
          className="danger"
          onClick={async () => {
            await api.deleteScene(project.id, scene.id);
            onChange();
          }}
        >
          Delete scene
        </button>
      </div>
    </div>
  );
}
