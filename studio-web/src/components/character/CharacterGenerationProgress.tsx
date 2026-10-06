type Props = {
  view: string;
  status?: string;
  provider?: string;
  progress?: number | null;
  stage?: string;
  label?: string;
  error?: string | null;
};

export function CharacterGenerationProgress({
  view,
  status,
  provider,
  progress,
  stage,
  label,
  error,
}: Props) {
  const failed = status === "failed" || stage === "failed" || Boolean(error);
  const idle = !failed && (!stage || stage === "idle") && !label && (progress == null || progress <= 0);
  if (idle) return null;

  const showBar = progress != null && Number.isFinite(progress);
  const width = showBar ? Math.max(0, Math.min(100, Number(progress))) : 0;

  return (
    <div
      className={`cc-v2__progress${failed ? " cc-v2__progress--failed" : ""}`}
      data-testid={`cc-v2-progress-${view}`}
      data-stage={stage || ""}
      data-status={status || ""}
    >
      {label ? <p className="cc-v2__progress-label">{label}</p> : null}
      {showBar ? (
        <div className="cc-v2__progress-track" role="progressbar" aria-valuenow={width} aria-valuemin={0} aria-valuemax={100}>
          <div className="cc-v2__progress-fill" style={{ width: `${width}%` }} />
        </div>
      ) : (
        <div className="cc-v2__progress-stage" aria-live="polite" />
      )}
      {showBar ? <p className="cc-v2__progress-pct">{Math.round(width)}%</p> : null}
      {provider ? <p className="cc-v2__progress-provider">{provider}</p> : null}
      {error ? <p className="cc-v2__error">{error}</p> : null}
    </div>
  );
}
