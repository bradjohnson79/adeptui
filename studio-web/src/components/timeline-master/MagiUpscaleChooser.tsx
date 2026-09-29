import { MAGI_SPATIAL_ONLY } from "../../timelineMaster/magiUpscaleTargets";

export type MagiUpscaleChoice = {
  engine: string;
  model: string;
  targetResolution: string;
};

type TargetRow = { id: string; label: string; width: number; height: number };
type EngineRow = {
  id: string;
  label?: string;
  available?: boolean;
  models?: Array<{ id: string; label?: string }>;
};

export function MagiUpscaleChooser({
  loading,
  error,
  honesty,
  sourceResolution,
  realesrganReady,
  engines,
  targets,
  engine,
  model,
  targetId,
  busy,
  statusText,
  onEngineChange,
  onModelChange,
  onTargetChange,
  onCancel,
  onConfirm,
  onOpenInMagi,
}: {
  loading: boolean;
  error?: string | null;
  honesty?: string | null;
  sourceResolution?: string;
  realesrganReady?: boolean;
  engines: EngineRow[];
  targets: TargetRow[];
  engine: string;
  model: string;
  targetId: string;
  busy: boolean;
  statusText?: string | null;
  onEngineChange: (engine: string) => void;
  onModelChange: (model: string) => void;
  onTargetChange: (targetId: string) => void;
  onCancel: () => void;
  onConfirm: () => void;
  onOpenInMagi?: () => void;
}) {
  const gpuEngine = engines.find((row) => row.id === "realesrgan-ncnn-vulkan");
  const gpuModels = gpuEngine?.models || [];
  const gpuAvailable = Boolean(realesrganReady && gpuEngine?.available !== false);
  const showGpuModels = engine === "realesrgan-ncnn-vulkan" && gpuModels.length > 0;
  const noTargets = !loading && targets.length === 0;

  return (
    <div className="live-preview-magi-chooser" data-testid="live-preview-magi-chooser">
      <p className="live-preview-magi-chooser__honesty">
        {honesty || MAGI_SPATIAL_ONLY}
      </p>
      {sourceResolution ? (
        <p className="live-preview-magi-chooser__meta">Current master: {sourceResolution}</p>
      ) : null}
      {loading ? <p className="live-preview-magi-chooser__meta">Checking MAGI…</p> : null}
      {error ? (
        <p className="live-preview-magi-chooser__error" data-testid="live-preview-magi-chooser-error">
          {error}
        </p>
      ) : null}
      {noTargets ? (
        <p className="live-preview-magi-chooser__error">This master is already at the highest size MAGI can reach.</p>
      ) : null}
      <label className="live-preview-magi-chooser__field">
        <span>Engine</span>
        <select
          data-testid="live-preview-magi-engine"
          value={engine}
          disabled={busy || loading}
          onChange={(event) => onEngineChange(event.target.value)}
        >
          <option value="realesrgan-ncnn-vulkan" disabled={!gpuAvailable}>
            {gpuAvailable ? "Real-ESRGAN GPU" : "Real-ESRGAN GPU (not ready)"}
          </option>
          <option value="ffmpeg-scale">FFmpeg Fast</option>
        </select>
      </label>
      <label className="live-preview-magi-chooser__field">
        <span>Target size</span>
        <select
          data-testid="live-preview-magi-target"
          value={targetId}
          disabled={busy || loading || noTargets}
          onChange={(event) => onTargetChange(event.target.value)}
        >
          {targets.map((row) => (
            <option key={row.id} value={row.id}>
              {row.label} ({row.width}×{row.height})
            </option>
          ))}
        </select>
      </label>
      {showGpuModels ? (
        <label className="live-preview-magi-chooser__field">
          <span>Look</span>
          <select
            data-testid="live-preview-magi-model"
            value={model}
            disabled={busy || loading}
            onChange={(event) => onModelChange(event.target.value)}
          >
            {gpuModels.map((row) => (
              <option key={row.id} value={row.id}>
                {row.label || row.id}
              </option>
            ))}
          </select>
        </label>
      ) : null}
      {statusText ? (
        <p className="live-preview-magi-chooser__status" data-testid="live-preview-magi-chooser-status">
          {statusText}
        </p>
      ) : null}
      <div className="live-preview-magi-chooser__actions">
        <button
          type="button"
          className="live-preview-publish-bar__btn live-preview-publish-bar__btn--upscale"
          data-testid="live-preview-magi-start"
          disabled={busy || loading || noTargets || Boolean(error)}
          onClick={onConfirm}
        >
          {busy ? "Upscaling…" : "Start upscale"}
        </button>
        <button
          type="button"
          className="live-preview-publish-bar__btn live-preview-magi-chooser__cancel"
          data-testid="live-preview-magi-cancel"
          disabled={busy}
          onClick={onCancel}
        >
          Cancel
        </button>
        {onOpenInMagi ? (
          <button
            type="button"
            className="live-preview-magi-chooser__open"
            data-testid="live-preview-open-magi"
            disabled={busy}
            onClick={onOpenInMagi}
          >
            Open in MAGI
          </button>
        ) : null}
      </div>
    </div>
  );
}

export function choiceFromChooser(input: {
  engine: string;
  model: string;
  targetId: string;
  targets: TargetRow[];
}): MagiUpscaleChoice {
  const target = input.targets.find((row) => row.id === input.targetId) || input.targets[0];
  return {
    engine: input.engine,
    model: input.engine === "ffmpeg-scale" ? "lanczos" : input.model,
    targetResolution: target ? `${target.width}x${target.height}` : input.targetId,
  };
}
