import { useTranslation } from "react-i18next";

export function TimelineGeneratorBanner() {
  const { t } = useTranslation("timeline");
  return (
    <div
      className="timeline-generator-banner"
      aria-label={t("title")}
      data-testid="timeline-generator-banner"
    >
      <span>{t("title")}</span>
    </div>
  );
}
