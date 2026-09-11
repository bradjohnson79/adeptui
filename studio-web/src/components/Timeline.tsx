import { useEffect, useMemo, useRef, useState } from "react";
import type { Project, Scene } from "../types";
import { ApiError, api } from "../api";
import { PanelHeading } from "./HelpTip";
import type { SceneTimelineMaster } from "../timelineMaster/contracts";
import { formatDurationSeconds } from "../lib/formatDuration";
import { LOCAL_SCENE_DURATION_CAP_SEC, nextLocalSceneDurationSec } from "./timelineSceneDuration";
import { Menu } from "./ui/Menu";
import { SceneRemoveDialog, SceneRenameDialog } from "./timeline-master/SceneCardDialogs";
import { isSceneDeleteAlreadyGone, neighborSceneId, normalizeSceneName } from "../sceneLifecycle";

/** Compact scene strip — detailed tracks live in DirectorTracks. */
export function Timeline({
  project,
  selectedId,
  onSelect,
  onChange,
}: {
  project: Project;
  selectedId?: string;
  onSelect: (id: string) => void;
  onChange: () => void;
}) {
  const total = useMemo(
    () => project.scenes.reduce((s, sc) => s + (sc.duration_sec || 0), 0),
    [project.scenes]
  );
  const [sceneMeta, setSceneMeta] = useState<Record<string, { batches: number; status: string }>>({});
  const [openMenuId, setOpenMenuId] = useState<string | null>(null);
  const [renameTarget, setRenameTarget] = useState<Scene | null>(null);
  const [removeTarget, setRemoveTarget] = useState<Scene | null>(null);
  const [dialogBusy, setDialogBusy] = useState(false);
  const [dialogError, setDialogError] = useState<string | null>(null);
  const scenesListRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!selectedId) return;
    const active = scenesListRef.current?.querySelector<HTMLElement>(`[data-scene-id="${selectedId}"]`);
    active?.scrollIntoView({ block: "nearest", inline: "nearest" });
  }, [selectedId]);

  useEffect(() => {
    setOpenMenuId(null);
  }, [selectedId]);

  useEffect(() => {
    let alive = true;
    void Promise.all(
      project.scenes.map(async (scene) => {
        try {
          const result = await api.directorTimelineMaster(project.id, scene.id);
          const master = result.master as SceneTimelineMaster;
          const statuses = master.batchBlocks.map((batch) => batch.status);
          const status = statuses.includes("Failed")
            ? "Needs Attention"
            : statuses.includes("Generating") || statuses.includes("Queued")
              ? "Working"
              : statuses.includes("Ready") || statuses.includes("Approved")
                ? "Ready"
                : "Draft";
          return [scene.id, { batches: master.batchBlocks.length, status }] as const;
        } catch {
          return [scene.id, { batches: 0, status: scene.output_path ? "Ready" : "Draft" }] as const;
        }
      }),
    ).then((entries) => {
      if (!alive) return;
      setSceneMeta(Object.fromEntries(entries));
    });
    return () => {
      alive = false;
    };
  }, [project.id, project.scenes]);

  const closeDialogs = () => {
    if (dialogBusy) return;
    setRenameTarget(null);
    setRemoveTarget(null);
    setDialogError(null);
  };

  const confirmRename = async (name: string) => {
    if (!renameTarget) return;
    const parsed = normalizeSceneName(name);
    if (!parsed.ok) {
      setDialogError(parsed.reason);
      return;
    }
    if (parsed.name === renameTarget.name) {
      setRenameTarget(null);
      setDialogError(null);
      return;
    }
    setDialogBusy(true);
    setDialogError(null);
    try {
      await api.updateScene(project.id, renameTarget.id, { name: parsed.name });
      setRenameTarget(null);
      onChange();
    } catch (error) {
      setDialogError(error instanceof ApiError ? error.message : "Could not rename this scene.");
    } finally {
      setDialogBusy(false);
    }
  };

  const confirmRemove = async () => {
    if (!removeTarget) return;
    setDialogBusy(true);
    setDialogError(null);
    const removedId = removeTarget.id;
    const removingActive = selectedId === removedId;
    const nextId = neighborSceneId(
      project.scenes.map((scene) => scene.id),
      removedId,
    );
    if (removingActive) onSelect(nextId || "");
    try {
      await api.deleteScene(project.id, removedId);
    } catch (error) {
      if (!isSceneDeleteAlreadyGone(error)) {
        if (removingActive) onSelect(removedId);
        setDialogError(error instanceof ApiError ? error.message : "Could not remove this scene.");
        setDialogBusy(false);
        return;
      }
    }
    setRemoveTarget(null);
    setDialogBusy(false);
    onChange();
  };

  return (
    <div className="panel timeline">
      <PanelHeading
        title="Scenes"
        tip="Ordered story beats for this project. Select one to open Timeline tracks. Each local Scene can be up to 20 seconds."
      >
        <span className="scene-meta">{formatDurationSeconds(total)} · {LOCAL_SCENE_DURATION_CAP_SEC}s max per Scene</span>
      </PanelHeading>
      <div className="timeline-v2__scenes-list" ref={scenesListRef}>
        {project.scenes.length === 0 ? (
          <p className="empty" data-testid="scenes-empty">
            No scenes yet. Add a Scene to start.
          </p>
        ) : null}
        {project.scenes.map((scene) => (
          <div
            key={scene.id}
            className={`scene-block ${selectedId === scene.id ? "active" : ""}`}
            data-testid={`scene-block-${scene.id}`}
            data-scene-id={scene.id}
            onClick={() => onSelect(scene.id)}
          >
            <div className="scene-head">
              <div className="scene-head__identity">
                <strong data-testid={`scene-block-name-${scene.id}`}>{scene.name}</strong>
                <span className="scene-meta scene-head__meta">
                  {scene.engine.replace(/^fal_/, "FAL/").toUpperCase()} · {formatDurationSeconds(scene.duration_sec)}
                </span>
              </div>
              <Menu
                compact
                align="end"
                showChevron={false}
                label="⋯"
                trigger="⋯"
                ariaLabel={`Scene options for ${scene.name}`}
                testId={`scene-overflow-${scene.id}`}
                className="scene-block__menu"
                open={openMenuId === scene.id}
                onOpenChange={(open) => setOpenMenuId(open ? scene.id : null)}
                items={[
                  {
                    id: "rename",
                    label: "Rename scene",
                    testId: "scene-menu-rename",
                    onSelect: () => {
                      setDialogError(null);
                      setRenameTarget(scene);
                    },
                  },
                  {
                    id: "remove",
                    label: "Remove scene",
                    danger: true,
                    testId: "scene-menu-remove",
                    onSelect: () => {
                      setDialogError(null);
                      setRemoveTarget(scene);
                    },
                  },
                ]}
              />
            </div>
            <div className="scene-meta" style={{ marginTop: 6 }}>
              {(sceneMeta[scene.id]?.batches ?? 0) || 0} batches · {sceneMeta[scene.id]?.status || "Draft"}
            </div>
          </div>
        ))}
      </div>
      <button
        type="button"
        title="Add a Scene"
        aria-label="Add a Scene"
        data-testid="timeline-add-scene"
        onClick={async () => {
          const next = nextLocalSceneDurationSec(LOCAL_SCENE_DURATION_CAP_SEC, {
            engine: project.engine_default,
          });
          if (!next.ok) {
            window.alert(next.reason || "Could not add a Scene.");
            return;
          }
          const created = await api.addScene(project.id, {
            name: `Scene ${project.scenes.length + 1}`,
            engine: project.engine_default,
            duration_sec: next.durationSec,
            prompt: "",
          });
          if (created?.id) onSelect(created.id);
          onChange();
        }}
      >
        Add scene
      </button>
      {renameTarget ? (
        <SceneRenameDialog
          currentName={renameTarget.name}
          busy={dialogBusy}
          error={dialogError}
          onCancel={closeDialogs}
          onConfirm={(name) => void confirmRename(name)}
        />
      ) : null}
      {removeTarget ? (
        <SceneRemoveDialog
          sceneName={removeTarget.name}
          busy={dialogBusy}
          working={sceneMeta[removeTarget.id]?.status === "Working"}
          error={dialogError}
          onCancel={closeDialogs}
          onConfirm={() => void confirmRemove()}
        />
      ) : null}
    </div>
  );
}
