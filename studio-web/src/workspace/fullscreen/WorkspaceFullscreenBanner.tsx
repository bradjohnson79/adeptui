export function WorkspaceFullscreenBanner({ visible }: { visible: boolean }) {
  if (!visible) return null;
  return (
    <div
      className="workspace-fs-banner"
      role="status"
      aria-live="polite"
      data-testid="workspace-fullscreen-banner"
    >
      <strong>Full-screen workspace active</strong>
      <span>Press Esc or select Full Screen again to return.</span>
    </div>
  );
}
