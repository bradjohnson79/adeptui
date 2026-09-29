import { AdeptCompositionGuides } from "../shared/AdeptCompositionGuides";
import { normalizeProductionAspect } from "../../workspacePrefs";

/**
 * Timeline Preview Monitor composition guides.
 * Viewer-only. Selected Timeline aspect is the sole composition authority.
 */
export function PreviewGuidesOverlay({
  stage,
  aspectRatio,
  visible,
}: {
  stage: HTMLElement | null;
  aspectRatio: string | null | undefined;
  visible: boolean;
}) {
  const aspect = normalizeProductionAspect(aspectRatio);
  return (
    <AdeptCompositionGuides
      key={aspect}
      host={stage}
      aspectRatio={aspect}
      visible={visible}
      mode="fit"
      className="preview-guides"
    />
  );
}
