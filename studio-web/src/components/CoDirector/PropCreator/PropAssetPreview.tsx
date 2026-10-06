import { useEffect, useState } from "react";
import { api } from "../../../api";

type PropAssetPreviewProps = {
  assetId: string;
  projectId?: string;
  alt: string;
  className?: string;
  testId?: string;
  unavailableLabel?: string;
  onClick?: () => void;
  clickableHint?: string;
};

export function PropAssetPreview({
  assetId,
  projectId,
  alt,
  className,
  testId,
  unavailableLabel = "Primary candidate unavailable",
  onClick,
  clickableHint,
}: PropAssetPreviewProps) {
  const [failed, setFailed] = useState(false);
  const src = api.assetUrl(assetId, assetId, projectId);

  useEffect(() => {
    setFailed(false);
  }, [assetId, src]);

  if (!assetId || !src) {
    return (
      <p className="prop-creator-core__error" role="alert" data-testid={testId ? `${testId}-error` : undefined}>
        {unavailableLabel}
      </p>
    );
  }
  if (failed) {
    return (
      <p className="prop-creator-core__error" role="alert" data-testid={testId ? `${testId}-error` : undefined}>
        {unavailableLabel}
      </p>
    );
  }

  const img = (
    <img
      key={assetId}
      className={className}
      src={src}
      alt={alt}
      data-testid={testId}
      onLoad={() => setFailed(false)}
      onError={() => setFailed(true)}
    />
  );

  if (!onClick) return img;

  return (
    <button
      type="button"
      className="prop-creator-core__thumb-btn"
      data-testid={testId ? `${testId}-open-prs` : "prop-creator-result-image-open-prs"}
      title={clickableHint || "Open Prop Reference Sheet"}
      aria-label={clickableHint || "Open Prop Reference Sheet"}
      onClick={onClick}
    >
      {img}
    </button>
  );
}
