import { useTranslation } from "react-i18next";
import type { Project, Scene } from "../../types";
import { GpuVramPanel } from "../GpuVramPanel";
import type { PlanDims } from "../../filmTimeline/filmTimelinePresentation";

/**
 * Timeline GPU tab — reconnects the shared GpuVramPanel (same authority as 1 Frame)
 * instead of a weaker parallel telemetry meter.
 *
 * Film Timeline passes resolvedGeneration / H3 Auto Quality plan dims so Live
 * execution plan never lies with Scene/project canvas (e.g. 1920×824) for H3.
 */
export function TimelineGpuPane({
  project,
  scene,
  onChange,
  generatorId,
  planDims,
}: {
  project: Project;
  scene?: Scene;
  onChange: () => void;
  generatorId?: string | null;
  planDims?: PlanDims | null;
}) {
  const { t } = useTranslation("timeline");
  return (
    <section className="panel timeline-gpu-pane" data-testid="timeline-gpu-pane">
      <div className="timeline-inspector__eyebrow">{t("gpu")}</div>
      <p className="scene-meta">{t("gpuTip")}</p>
      <GpuVramPanel
        project={project}
        onChange={onChange}
        compact
        sceneId={scene?.id}
        engine={String(generatorId || scene?.engine || "auto")}
        surface="i2v"
        aspect={scene?.aspect_ratio || "16:9"}
        durationSec={scene?.duration_sec}
        fps={project.fps}
        generatorId={generatorId || undefined}
        genWidth={planDims?.width}
        genHeight={planDims?.height}
        planSource={planDims?.source}
      />
    </section>
  );
}
