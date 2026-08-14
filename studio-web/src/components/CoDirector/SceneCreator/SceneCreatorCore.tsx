/**
 * SceneCreatorCore — shared Express + Standard views over useSceneCreator.
 * Express stays light. Advanced controls live in Standard.
 */
import { api } from "../../../api";
import { CoDirectorEmptyState } from "../cards";
import { candidateProgress } from "./types";
import { useSceneCreator, type SceneCreatorVariant } from "./useSceneCreator";
import { CinematographerPanel } from "./cinematographer/CinematographerPanel";
import "./sceneCreator.css";

export type SceneCreatorCoreProps = {
  projectId: string;
  variant: SceneCreatorVariant;
  onGoTab?: (tab: string, extra?: Record<string, string>) => void;
};

export function SceneCreatorCore({ projectId, variant, onGoTab }: SceneCreatorCoreProps) {
  const sc = useSceneCreator(projectId);
  const sheets = sc.workspace?.sheets || [];

  if (sc.loading) {
    return <p className="muted" data-testid="scene-creator-loading">Loading Scene Creator…</p>;
  }

  if (!sheets.length) {
    return (
      <CoDirectorEmptyState
        testId="scene-creator-empty-no-ers"
        title="Scene Creator"
        description="Scene Creator needs an Environment Reference Sheet. Create one in Spatial Map, or choose an existing sheet if this project already has one."
        action={
          <div className="scene-creator-core__row">
            <button
              type="button"
              className="primary"
              onClick={() => onGoTab?.("spatial_map")}
              data-testid="scene-creator-open-spatial-map"
            >
              Open Spatial Map
            </button>
            <label className="scene-creator-core__label">
              Choose Existing ERS
              <select
                data-testid="scene-creator-choose-existing-ers"
                value=""
                onChange={(e) => {
                  if (e.target.value) void sc.selectSheet(e.target.value);
                }}
              >
                <option value="">No Environment Reference Sheet yet</option>
              </select>
            </label>
          </div>
        }
      />
    );
  }

  if (variant === "standard") {
    return <StandardLayout sc={sc} onGoTab={onGoTab} />;
  }
  return <ExpressLayout sc={sc} onGoTab={onGoTab} />;
}

type LayoutProps = {
  sc: ReturnType<typeof useSceneCreator>;
  onGoTab?: (tab: string, extra?: Record<string, string>) => void;
};

function ExpressLayout({ sc, onGoTab }: LayoutProps) {
  return (
    <section className="scene-creator-core" data-testid="scene-creator-panel">
      <EnvironmentBlock sc={sc} onGoTab={onGoTab} />
      <CharactersPropsBlock sc={sc} />
      <CinematographerPanel sc={sc} />
      <ShotPromptBlock sc={sc} />
      <GeneratorBlock sc={sc} />
      <ActionsBlock sc={sc} />
      {sc.approved ? <RetakeBlock sc={sc} /> : null}
      <StatusBlock sc={sc} />
      <CandidateGrid sc={sc} />
    </section>
  );
}

function StandardLayout({ sc, onGoTab }: LayoutProps) {
  const approved = sc.approved;
  const previewId = approved?.asset_id || sc.shot?.candidates.find((c) => c.asset_id)?.asset_id;
  return (
    <div className="scene-creator-standard" data-testid="scene-creator-standard">
      <aside className="scene-creator-standard__browser" data-testid="scene-creator-browser">
        <p className="scene-creator-core__label">Scenes</p>
        {(sc.workspace?.scenes || []).map((scene) => (
          <button
            key={scene.id}
            type="button"
            className={scene.id === sc.sceneId ? "scene-creator-core__chip is-on" : "scene-creator-core__chip"}
            onClick={() => void sc.selectScene(scene.id)}
          >
            {scene.name}
          </button>
        ))}
        <p className="scene-creator-core__label" style={{ marginTop: "1rem" }}>Shots</p>
        <button type="button" className="ghost" onClick={sc.newShot} data-testid="scene-creator-new-shot">
          New Shot
        </button>
        {(sc.workspace?.shots || []).map((shot, index) => (
          <button
            key={shot.id}
            type="button"
            className={shot.id === sc.shot?.id ? "scene-creator-core__chip is-on" : "scene-creator-core__chip"}
            onClick={() => void sc.selectShot(shot.id)}
          >
            Shot {index + 1}
          </button>
        ))}
      </aside>
      <div className="scene-creator-standard__preview">
        {previewId ? (
          <img src={api.assetUrl(previewId)} alt="Approved take" data-testid="scene-creator-preview-image" />
        ) : (
          <p className="muted">Generate a look, then approve one to see it here.</p>
        )}
      </div>
      <aside className="scene-creator-standard__inspector">
        <EnvironmentBlock sc={sc} onGoTab={onGoTab} />
        <CharactersPropsBlock sc={sc} />
        <CinematographerPanel sc={sc} />
        <ShotPromptBlock sc={sc} />
        <GeneratorBlock sc={sc} />
        <ActionsBlock sc={sc} />
        {sc.approved ? <RetakeBlock sc={sc} /> : null}
        <StatusBlock sc={sc} />
      </aside>
      <div className="scene-creator-standard__strip" data-testid="scene-creator-take-strip">
        {(sc.shot?.candidates || []).map((cand) => (
          <button
            key={cand.id}
            type="button"
            onClick={() => cand.status === "complete" && cand.asset_id && void sc.approve(cand.id)}
          >
            {cand.asset_id ? (
              <img src={api.assetUrl(cand.asset_id)} alt={cand.take_label} />
            ) : (
              <span className="muted">{cand.take_label}</span>
            )}
          </button>
        ))}
      </div>
    </div>
  );
}

function EnvironmentBlock({ sc, onGoTab }: LayoutProps) {
  const sheets = sc.workspace?.sheets || [];
  return (
    <div>
      <p className="scene-creator-core__label">Environment</p>
      <div className="scene-creator-core__row">
        <select
          data-testid="scene-creator-ers-select"
          value={sc.sheetId}
          onChange={(e) => void sc.selectSheet(e.target.value)}
        >
          {sheets.map((sheet) => (
            <option key={sheet.sheetId} value={sheet.sheetId}>
              {sheet.name}
            </option>
          ))}
        </select>
        <button type="button" className="ghost" onClick={() => onGoTab?.("spatial_map")}>
          View in Spatial Map
        </button>
      </div>
    </div>
  );
}

function CharactersPropsBlock({ sc }: { sc: ReturnType<typeof useSceneCreator> }) {
  const chars = sc.workspace?.characters || [];
  const props = sc.workspace?.props || [];
  return (
    <div data-testid="scene-creator-placed-entities">
      <p className="scene-creator-core__label">Characters / Props</p>
      <div className="scene-creator-core__chips">
        {chars.map((c) => (
          <button
            key={c.character_id}
            type="button"
            className={sc.characterIds.includes(c.character_id) ? "scene-creator-core__chip is-on" : "scene-creator-core__chip"}
            data-testid="scene-creator-character-chip"
            onClick={() => sc.toggleCharacter(c.character_id)}
          >
            {c.name}
          </button>
        ))}
        {props.map((p) => {
          const id = p.prop_id || p.tag;
          const on = Boolean(p.prop_id && sc.propIds.includes(p.prop_id));
          return (
            <button
              key={id}
              type="button"
              className={on ? "scene-creator-core__chip is-on" : "scene-creator-core__chip"}
              data-testid="scene-creator-prop-chip"
              onClick={() => p.prop_id && sc.toggleProp(p.prop_id)}
            >
              #{p.display_label}
            </button>
          );
        })}
        {!chars.length && !props.length ? <span className="muted">Place characters and props on the Spatial Map.</span> : null}
      </div>
    </div>
  );
}

function ShotPromptBlock({ sc }: { sc: ReturnType<typeof useSceneCreator> }) {
  return (
    <div>
      <p className="scene-creator-core__label">Shot Prompt</p>
      <textarea
        className="scene-creator-core__prompt"
        data-testid="scene-creator-shot-textarea"
        value={sc.intent}
        onChange={(e) => sc.setIntent(e.target.value)}
        placeholder="What happens in this shot?"
      />
    </div>
  );
}

function GeneratorBlock({ sc }: { sc: ReturnType<typeof useSceneCreator> }) {
  const apiModels = sc.workspace?.api_models || [];
  const hasApi = apiModels.length > 0;
  const caps = sc.workspace?.preview_capabilities;
  let apiLabel = caps?.api?.noneLabel || "API Generation — Not Available";
  if (hasApi && sc.apiEnabled && sc.apiModel) {
    apiLabel = "Standard-Cost Preview Only — cloud previews cost the same as a full image unless the provider says otherwise.";
  } else if (hasApi && sc.apiEnabled && !sc.apiModel) {
    apiLabel = "Preview Unsupported until you choose a cloud model.";
  } else if (hasApi && !sc.apiEnabled) {
    apiLabel = "Cloud generators use credits. Nothing is generated until you click Preview or Final Quality Render.";
  }
  return (
    <div data-testid="scene-creator-generators">
      <p className="scene-creator-core__label">Generator</p>
      <label className="scene-creator-core__row">
        <input
          type="checkbox"
          data-testid="generator-local-enable"
          checked={sc.localEnabled}
          onChange={(e) => sc.setLocalEnabled(e.target.checked)}
        />
        Local Image Generator
        <select
          data-testid="generator-local-select"
          value={sc.localFamily}
          disabled={!sc.localEnabled}
          onChange={(e) => sc.setLocalFamily(e.target.value)}
        >
          <option value="">Auto Select</option>
          {(sc.workspace?.local_families || []).map((fam) => (
            <option key={fam.id} value={fam.id}>{fam.label}</option>
          ))}
        </select>
      </label>
      <label className="scene-creator-core__row">
        <input
          type="checkbox"
          data-testid="generator-api-enable"
          checked={sc.apiEnabled}
          disabled={!hasApi}
          onChange={(e) => sc.setApiEnabled(e.target.checked)}
        />
        Cloud Generators (uses credits)
        <select
          data-testid="generator-api-model"
          value={sc.apiModel}
          disabled={!sc.apiEnabled}
          onChange={(e) => sc.setApiModel(e.target.value)}
        >
          <option value="">Choose a cloud model</option>
          {apiModels.map((model) => {
            const id = String(model.modelId || model.id || "");
            const label = String(model.label || model.name || id);
            return (
              <option key={id} value={id}>{label}</option>
            );
          })}
        </select>
      </label>
      <p className="muted" data-testid="scene-creator-api-unavailable">
        {sc.localEnabled ? `${caps?.local?.label || "Economy Preview Available"} for local generators. ` : ""}
        {apiLabel}
      </p>
    </div>
  );
}

function ActionsBlock({ sc }: { sc: ReturnType<typeof useSceneCreator> }) {
  const canSend = !!sc.approved && !sc.busy;
  const progress = candidateProgress(sc.shot?.candidates || []);
  return (
    <div className="scene-creator-core__row">
      <button
        type="button"
        className="ghost"
        data-testid="scene-creator-send-to-timeline"
        disabled={!canSend}
        onClick={() => void sc.sendToTimeline()}
      >
        Send to Timeline
      </button>
        {sc.generating ? (
        <span className="muted" data-testid="generation-progress">
          {progress.total ? `${progress.done} of ${progress.total} looks complete` : "Working…"}
        </span>
      ) : null}
      {sc.approved ? (
        <span className="muted" data-testid="scene-creator-use-retake-hint">
          Use Re-Take to change this look. The approved take stays until you approve a new one.
        </span>
      ) : null}
    </div>
  );
}

function RetakeBlock({ sc }: { sc: ReturnType<typeof useSceneCreator> }) {
  return (
    <div>
      <p className="scene-creator-core__label">Re-Take</p>
      <textarea
        className="scene-creator-core__prompt"
        data-testid="scene-creator-retake-correction"
        value={sc.correction}
        onChange={(e) => sc.setCorrection(e.target.value)}
        placeholder="What should change? The approved look stays until you approve a new one."
      />
      <button
        type="button"
        className="ghost"
        data-testid="scene-creator-retake"
        disabled={!sc.correction.trim() || sc.busy || (!sc.localEnabled && !sc.apiEnabled)}
        onClick={() => void sc.retake()}
      >
        Re-Take
      </button>
    </div>
  );
}

function StatusBlock({ sc }: { sc: ReturnType<typeof useSceneCreator> }) {
  return (
    <>
      {sc.error ? (
        <p className="muted" style={{ color: "var(--danger, #c33)" }} data-testid="scene-creator-error">
          {sc.error}
        </p>
      ) : null}
      {sc.notice ? (
        <p className="muted" style={{ color: "var(--good, #4a8)" }} data-testid="scene-creator-notice">
          {sc.notice}
        </p>
      ) : null}
    </>
  );
}

function CandidateGrid({ sc }: { sc: ReturnType<typeof useSceneCreator> }) {
  const candidates = sc.shot?.candidates || [];
  if (!candidates.length) return null;
  return (
    <div className="scene-creator-core__candidates" data-testid="scene-creator-result-grid">
      {candidates.map((cand) => {
        const approved = cand.id === sc.shot?.approved_candidate_id;
        return (
          <article
            key={cand.id}
            className={approved ? "scene-creator-core__card is-approved" : "scene-creator-core__card"}
            data-testid="scene-creator-result-card"
          >
            <div className="scene-creator-core__thumb">
              {cand.asset_id ? (
                <img src={api.assetUrl(cand.asset_id)} alt={cand.take_label} data-testid="scene-creator-result-image" />
              ) : (
                <span className="muted">{cand.status === "failed" ? "Failed" : "Generating…"}</span>
              )}
            </div>
            <div className="scene-creator-core__card-body">
              <strong>{cand.take_label}</strong>
              <span className="muted">{cand.provenance_label}</span>
              {cand.status === "complete" ? (
                <button
                  type="button"
                  className="primary"
                  data-testid="scene-creator-approve"
                  disabled={sc.busy}
                  onClick={() => void sc.approve(cand.id)}
                >
                  {approved ? "Approved" : "Use This Look"}
                </button>
              ) : null}
            </div>
          </article>
        );
      })}
    </div>
  );
}
