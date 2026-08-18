import { api } from "../../../api";
import {
  ERS_GENERATOR_OPTIONS,
  ersGeneratorOptionDisabled,
  type ErsGeneratorId,
} from "./ersGenerator";
import { MINI_ASPECTS, miniResultSelectable, miniResultState, type MiniResult } from "./sceneCreatorMiniApi";
import { useSceneCreatorMini } from "./useSceneCreatorMini";
import type { SpatialMapDocument } from "./types";

type Props = {
  projectId: string;
  document: SpatialMapDocument | null;
  isDirty: boolean;
  qwenI2IReady?: boolean | null;
  gptI2IReady?: boolean | null;
  onOpenSceneCreator?: () => void;
};

export function SceneCreatorMini({
  projectId,
  document,
  isDirty,
  qwenI2IReady,
  gptI2IReady,
  onOpenSceneCreator,
}: Props) {
  const mini = useSceneCreatorMini({
    projectId,
    document,
    isDirty,
    qwenI2IReady,
    gptI2IReady,
  });

  return (
    <div className="spatial-map__mini" data-testid="scene-creator-mini">
      <div className="spatial-map__mini-header">
        <button
          type="button"
          className="spatial-map__mini-toggle"
          onClick={() => mini.setOpen((v) => !v)}
          aria-expanded={mini.open}
          data-testid="scene-creator-mini-toggle"
        >
          {mini.open ? "▾" : "▸"} Scene Creator Mini
        </button>
        <div
          className={`spatial-map__mini-enable${mini.enabled ? " is-on" : " is-off"}`}
          onClick={(e) => {
            e.stopPropagation();
            mini.setEnabled(!mini.enabled);
          }}
        >
          <span>Enable Mini</span>
          <button
            type="button"
            role="switch"
            className={`spatial-map__slot-toggle${mini.enabled ? " is-on" : ""}`}
            aria-checked={mini.enabled}
            aria-label="Enable Mini"
            data-testid="scene-creator-mini-enable"
            onClick={(e) => {
              e.preventDefault();
              e.stopPropagation();
              mini.setEnabled(!mini.enabled);
            }}
          >
            <span className="spatial-map__slot-toggle-thumb" aria-hidden="true" />
          </button>
        </div>
      </div>
      {mini.open && mini.enabled ? (
        <div className="spatial-map__mini-body">
              <div className="spatial-map__mini-controls">
                <label>
                  Generator
                  <select
                    value={mini.generator}
                    onChange={(e) => mini.setGenerator(e.target.value as ErsGeneratorId)}
                    data-testid="scene-creator-mini-generator"
                  >
                    {ERS_GENERATOR_OPTIONS.map((opt) => (
                      <option
                        key={opt.id}
                        value={opt.id}
                        disabled={ersGeneratorOptionDisabled(opt.id, qwenI2IReady, gptI2IReady)}
                      >
                        {opt.label}
                      </option>
                    ))}
                  </select>
                </label>
                <label>
                  Frame Size
                  <select
                    value={mini.aspect}
                    onChange={(e) => mini.setAspect(e.target.value as (typeof MINI_ASPECTS)[number])}
                    data-testid="scene-creator-mini-aspect"
                  >
                    {MINI_ASPECTS.map((ratio) => (
                      <option key={ratio} value={ratio}>
                        {ratio}
                      </option>
                    ))}
                  </select>
                </label>
              </div>
              <p className="spatial-map__mini-math" data-testid="scene-creator-mini-output">
                Active Cameras: {mini.cameras.length} · Output: {mini.outputCount} images
              </p>
              {mini.gateMessage ? (
                <p className="spatial-map__hint" data-testid="scene-creator-mini-gate">
                  {mini.gateMessage}
                </p>
              ) : null}
              <button
                type="button"
                className="ui-btn ui-btn--primary"
                onClick={() => void mini.generate()}
                disabled={!mini.canGenerate}
                data-testid="scene-creator-mini-generate"
              >
                {mini.busy ? "Generating…" : "Generate Mini Take"}
              </button>
              {mini.error ? (
                <p className="spatial-map__hint spatial-map__hint--error" role="alert">
                  {mini.error}
                </p>
              ) : null}
              {mini.take ? (
                <div className="spatial-map__mini-results" data-testid="scene-creator-mini-results">
                  <p className="spatial-map__mini-take-id">Mini Take {mini.take.takeNumber}</p>
                  {mini.take.mapVersion ? (
                    <p className="spatial-map__hint" data-testid="scene-creator-mini-take-version">
                      Map v{mini.take.mapVersion}
                      {mini.take.ersRevision ? " · ERS locked" : ""}
                      {mini.take.ersSheetId ? " · ERS sheet present" : ""}
                    </p>
                  ) : null}
                  {mini.resultsByCamera.map((group) => (
                    <div key={group.cameraId} className="spatial-map__mini-camera" data-testid={`mini-camera-${group.label}`}>
                      <p className="spatial-map__mini-camera-title">{group.label}</p>
                      <div className="spatial-map__mini-pair">
                        {group.results.map((result) => {
                          const state = miniResultState(result);
                          const selectable = miniResultSelectable(result);
                          return (
                            <label key={result.id} className={"spatial-map__mini-card is-" + state}>
                              <input
                                type="checkbox"
                                checked={!!mini.selected[result.id]}
                                disabled={!selectable}
                                onChange={() => mini.toggleSelected(result.id)}
                                aria-label={"Select variation " + result.variation + " " + result.cameraLabel}
                              />
                              {result.assetId ? (
                                <img src={api.assetUrl(result.assetId)} alt={result.cameraLabel + " " + result.variation} />
                              ) : (
                                <span>{result.status === "failed" ? result.error || "Failed" : "Generating…"}</span>
                              )}
                              <span className="spatial-map__mini-card-meta">
                                <span>
                                  Variation {result.variation}
                                  {result.inLibrary ? " · In Library" : ""}
                                </span>
                                <MiniStatusChip result={result} />
                              </span>
                            </label>
                          );
                        })}
                      </div>
                      <button
                        type="button"
                        className="ui-btn ui-btn--secondary"
                        onClick={() => void mini.regenerate(group.cameraId)}
                        disabled={mini.busy || isDirty}
                      >
                        Regenerate Pair
                      </button>
                    </div>
                  ))}
                  <div className="spatial-map__mini-footer">
                    <button type="button" className="ui-btn ui-btn--secondary" onClick={mini.selectAll}>
                      Select All
                    </button>
                    <button
                      type="button"
                      className="ui-btn ui-btn--primary"
                      onClick={() => void mini.sendSelected()}
                      disabled={mini.selectedIds.length === 0 || mini.busy}
                      data-testid="scene-creator-mini-send-library"
                    >
                      Send Selected to Library
                    </button>
                    <button
                      type="button"
                      className="ui-btn ui-btn--secondary"
                      onClick={() => void mini.regenerate()}
                      disabled={mini.busy || isDirty}
                      data-testid="scene-creator-mini-regen-all"
                    >
                      Regenerate All
                    </button>
                  </div>
                </div>
              ) : null}
              {onOpenSceneCreator ? (
                <button type="button" className="spatial-map__mini-link" onClick={onOpenSceneCreator}>
                  Need more control? Open Scene Creator
                </button>
              ) : null}
        </div>
      ) : null}
    </div>
  );
}

function MiniStatusChip({ result }: { result: MiniResult }) {
  const state = miniResultState(result);
  if (state === "generating") {
    return <span className="spatial-map__mini-chip is-generating">Generating…</span>;
  }
  if (state === "validating") {
    return <span className="spatial-map__mini-chip is-validating">Validating…</span>;
  }
  if (state === "pass") {
    return <span className="spatial-map__mini-chip is-pass">Pass</span>;
  }
  if (state === "generation_failed") {
    return <span className="spatial-map__mini-chip is-failed">Generation failed</span>;
  }
  if (state === "validation_unavailable") {
    return (
      <span className="spatial-map__mini-chip is-unavailable" title={result.validation?.summary || "Continuity review unavailable"}>
        Review unavailable
      </span>
    );
  }
  const reason = result.validation?.summary || "Required production facts not met";
  return (
    <span className="spatial-map__mini-chip is-failed" title={reason}>
      Continuity failed
    </span>
  );
}

