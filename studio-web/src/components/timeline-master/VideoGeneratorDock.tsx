import { useEffect, useMemo, useRef, useState } from "react";
import type { Scene } from "../../types";
import type { SceneTimelineMaster } from "../../timelineMaster/contracts";
import { resolveGeneratorOption, supportsTurboLora } from "../../timelineMaster/draftCapabilities";
import {
  applyTimelineSceneGenerator,
  applyTimelineTurboLora,
  sceneWouldOverflow,
} from "../../timelineMaster/applySceneGenerator";
import { creatorGeneratorLine, generatorMaxDurationSec } from "../../timelineMaster/generatorDuration";
import { useTimelineVideoGenerators } from "../../timelineMaster/useTimelineVideoGenerators";
import { ActionWithHelp, PanelHeading } from "../HelpTip";

const TURBO_LORA_HELP =
  "Turbo LoRA accelerates supported video generation while preserving the normal generator workflow as closely as possible. Available only on supported models.";
import type { TimelineBoardView } from "../DirectorTracks";

export function VideoGeneratorDock({
  projectId,
  scene,
  master,
  timeline,
  onRefresh,
  mutateTimeline,
}: {
  projectId: string;
  scene: Scene;
  master: SceneTimelineMaster | null;
  timeline: TimelineBoardView | null;
  onRefresh: () => void | Promise<void>;
  mutateTimeline: (
    mutator: (current: TimelineBoardView) => TimelineBoardView,
    opts?: { refresh?: boolean },
  ) => Promise<void>;
}) {
  const options = useTimelineVideoGenerators();
  const [pendingId, setPendingId] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [turboPending, setTurboPending] = useState<boolean | null>(null);

  const selected = useMemo(
    () =>
      resolveGeneratorOption(
        options,
        master?.sceneGeneratorId,
        master?.batchBlocks[0]?.generatorId,
        scene.engine,
      ),
    [master?.batchBlocks, master?.sceneGeneratorId, options, scene.engine],
  );
  const hydratedRef = useRef(false);

  const applyGenerator = async (generatorId: string, trim: boolean) => {
    setBusy(true);
    setError(null);
    try {
      await applyTimelineSceneGenerator({
        projectId,
        scene,
        master,
        timeline,
        options,
        generatorId,
        trim,
        mutateTimeline,
        onRefresh,
      });
    } catch (err) {
      setError(err instanceof Error && err.message ? err.message : "Could not save the engine. Try again.");
    } finally {
      setBusy(false);
      setPendingId(null);
    }
  };

  useEffect(() => {
    if (hydratedRef.current || busy || !master || !selected?.id) return;
    const missing =
      !master.sceneGeneratorId ||
      master.batchBlocks.some((batch) => !String(batch.generatorId || "").trim());
    if (!missing) {
      hydratedRef.current = true;
      return;
    }
    hydratedRef.current = true;
    void applyGenerator(selected.id, false);
    // Persist the visible engine onto empty batches — not a silent model swap.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [busy, master, selected?.id]);

  const onSelect = (generatorId: string) => {
    if (!generatorId || generatorId === selected?.id) return;
    const option = resolveGeneratorOption(options, generatorId);
    const maxSec = generatorMaxDurationSec(option);
    if (sceneWouldOverflow(timeline, master, scene, maxSec)) {
      setPendingId(generatorId);
      return;
    }
    void applyGenerator(generatorId, false);
  };

  useEffect(() => {
    setTurboPending(null);
  }, [master?.turboLora]);

  const onTurboChange = (enabled: boolean) => {
    if (!master) return;
    setTurboPending(enabled);
    setError(null);
    void applyTimelineTurboLora({
      projectId,
      sceneId: scene.id,
      master,
      options,
      enabled,
      onRefresh,
    }).catch((err) => {
      setTurboPending(null);
      setError(err instanceof Error && err.message ? err.message : "Could not save Turbo LoRA.");
    });
  };
  const turboOn = turboPending ?? Boolean(master?.turboLora);

  return (
    <div className="timeline-v2__dock timeline-v2__dock--generator" data-testid="timeline-video-generator">
      <PanelHeading
        title="Video Generator"
        tip="The engine that makes this scene. Shot length comes from Duration in the Inspector, not from this menu."
      />
      <label className="field">
        <span className="sr-only">Video Generator</span>
        <select
          data-testid="timeline-video-generator-select"
          value={selected?.id || ""}
          disabled={busy}
          onChange={(event) => onSelect(event.target.value)}
        >
          <option value="">{options.length ? "Choose an engine" : "No local engines ready"}</option>
          {options.map((option) => (
            <option
              key={option.id}
              value={option.id}
              title={option.disabledReason || option.notes}
              disabled={!option.executable}
            >
              {creatorGeneratorLine(option)}
            </option>
          ))}
        </select>
      </label>
      {supportsTurboLora(selected) ? (
        <div className="timeline-v2__turbo-lora" data-testid="timeline-turbo-lora">
          <ActionWithHelp
            help={{
              label: "What is Turbo LoRA?",
              content: TURBO_LORA_HELP,
              text: TURBO_LORA_HELP,
            }}
          >
            <span className="timeline-v2__turbo-lora-label">Turbo LoRA</span>
          </ActionWithHelp>
          <input
            className="timeline-v2__turbo-lora-toggle"
            type="checkbox"
            role="switch"
            data-testid="timeline-turbo-lora-toggle"
            aria-label="Turbo LoRA"
            checked={turboOn}
            disabled={!master}
            onChange={(event) => onTurboChange(event.target.checked)}
          />
        </div>
      ) : null}
      {selected ? (
        <p className="scene-meta" data-testid="timeline-video-generator-summary">
          {creatorGeneratorLine(selected)}
        </p>
      ) : null}
      {error ? (
        <p className="scene-meta" role="alert" data-testid="timeline-video-generator-error">
          {error}
        </p>
      ) : null}
      {pendingId ? (
        <div className="ds-dialog-backdrop" role="presentation" data-testid="timeline-generator-overflow-dialog">
          <div className="ds-dialog" role="dialog" aria-labelledby="timeline-generator-overflow-title">
            <h2 id="timeline-generator-overflow-title" className="ds-dialog__title">
              Trim this scene?
            </h2>
            <p className="ds-dialog__body">
              The new engine cannot keep clips past its longest run. Trim this scene to that length, or cancel and
              keep everything as it is.
            </p>
            <div className="ds-dialog__actions">
              <button
                type="button"
                className="ghost"
                data-testid="timeline-generator-overflow-cancel"
                onClick={() => setPendingId(null)}
              >
                Cancel
              </button>
              <button type="button" className="primary" onClick={() => void applyGenerator(pendingId, true)}>
                Trim to Scene
              </button>
            </div>
          </div>
        </div>
      ) : null}
    </div>
  );
}
