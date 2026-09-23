/**
 * Compact heading under Preview Monitor: `{Status} - {Take X}` only.
 * Project-wide lifecycle counts do not belong here.
 */
export function SceneStatusStrip({
  previewStatusLabel,
}: {
  previewStatusLabel?: string | null;
}) {
  if (!previewStatusLabel) return null;
  const statusWord = previewStatusLabel.split(" - ")[0] || "";

  return (
    <div className="scene-status-strip" data-testid="scene-status-strip">
      <span
        className="scene-status-pill scene-status-pill--preview-take"
        data-testid="timeline-preview-take-status"
        data-status={statusWord.toLowerCase().replace(/\s+/g, "-")}
      >
        {previewStatusLabel}
      </span>
    </div>
  );
}
