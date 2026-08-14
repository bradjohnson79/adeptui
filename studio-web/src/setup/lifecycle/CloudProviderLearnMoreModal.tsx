import type { LifecycleCloudProvider } from "../types";
import { cloudProviderLearnMoreCopy } from "./cloudProviderCardCopy";

export function CloudProviderLearnMoreModal({
  provider,
  onClose,
  onSetUp,
}: {
  provider: LifecycleCloudProvider;
  onClose: () => void;
  onSetUp?: () => void;
}) {
  const copy = cloudProviderLearnMoreCopy(provider);
  return (
    <div
      className="ds-dialog-backdrop"
      role="presentation"
      data-testid={`setup-cloud-learn-more-backdrop-${provider.providerId}`}
      onMouseDown={(event) => {
        if (event.target === event.currentTarget) onClose();
      }}
    >
      <div
        className="ds-dialog"
        role="dialog"
        aria-modal="true"
        aria-label={`${provider.displayName} details`}
        data-testid={`setup-cloud-learn-more-${provider.providerId}`}
        onKeyDown={(event) => {
          if (event.key === "Escape") onClose();
        }}
      >
        <h2 className="ds-dialog__title">{provider.displayName}</h2>
        <div className="ds-dialog__body">
          {copy.fallback ? <p>{copy.fallback}</p> : null}
          {copy.summary ? <p>{copy.summary}</p> : null}
          {copy.useCases.length ? (
            <p>
              <strong>Use cases</strong> {copy.useCases.join(" · ")}
            </p>
          ) : null}
          {copy.localVsCloud ? (
            <p>
              <strong>Local vs cloud</strong> {copy.localVsCloud}
            </p>
          ) : null}
          {copy.requirements.length ? (
            <p>
              <strong>Requirements</strong> {copy.requirements.join(" · ")}
            </p>
          ) : null}
          {copy.costPrivacyNote ? (
            <p>
              <strong>Cost / privacy</strong> {copy.costPrivacyNote}
            </p>
          ) : null}
          {copy.capabilities.length ? (
            <p>
              <strong>Capabilities</strong> {copy.capabilities.join(" · ")}
            </p>
          ) : null}
          <div className="setup-card-actions">
            {provider.docsUrl ? (
              <a className="linkish" href={provider.docsUrl} target="_blank" rel="noreferrer">
                Documentation
              </a>
            ) : null}
            {provider.keysUrl ? (
              <a className="linkish" href={provider.keysUrl} target="_blank" rel="noreferrer">
                Get API key
              </a>
            ) : null}
          </div>
        </div>
        <div className="ds-dialog__actions">
          <button type="button" onClick={onClose}>
            Close
          </button>
          {onSetUp ? (
            <button type="button" className="primary" onClick={onSetUp}>
              {provider.configured ? "Manage" : "Set Up"}
            </button>
          ) : null}
        </div>
      </div>
    </div>
  );
}

