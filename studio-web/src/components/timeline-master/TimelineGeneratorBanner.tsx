import { useTranslation } from "react-i18next";

type Props = {
  /** Scene name shown far-right in the TIMELINE GENERATOR title bar. */
  sceneTitle?: string | null;
  /** Engine / ready / duration / mode meta — same string formerly under the bar. */
  sceneMeta?: string | null;
};

export function TimelineGeneratorBanner({ sceneTitle = null, sceneMeta = null }: Props) {
  const { t } = useTranslation("timeline");
  const hasScene = Boolean(sceneTitle || sceneMeta);
  return (
    <div
      className="timeline-generator-banner"
      aria-label={t("title")}
      data-testid="timeline-generator-banner"
    >
      <span className="timeline-generator-banner__label" data-testid="timeline-generator-banner-label">
        {t("title")}
      </span>
      {hasScene ? (
        <div
          className="timeline-generator-banner__scene"
          data-testid="timeline-generator-banner-scene"
          title={[sceneTitle, sceneMeta].filter(Boolean).join(" — ")}
        >
          {sceneTitle ? (
            <strong
              className="timeline-generator-banner__scene-title"
              data-testid="timeline-scene-header-title"
            >
              {sceneTitle}
            </strong>
          ) : null}
          {sceneMeta ? (
            <span
              className="timeline-generator-banner__scene-meta"
              data-testid="timeline-scene-header-meta"
            >
              {sceneMeta}
            </span>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}
