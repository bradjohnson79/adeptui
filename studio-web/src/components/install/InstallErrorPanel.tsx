import { useState } from "react";
import { Button } from "../ui";
import type { InstallJobError, InstallRecoveryAction } from "../../contracts/installJobs";
import "./install-progress.css";

export function InstallErrorPanel({
  error,
  recoveryActions,
  onRetry,
  onRepair,
  onAction,
  onDetails,
}: {
  error: InstallJobError;
  recoveryActions?: InstallRecoveryAction[] | null;
  onRetry?: () => void;
  onRepair?: () => void;
  onAction?: (action: string) => void;
  onDetails?: () => void;
}) {
  const [showTech, setShowTech] = useState(false);
  const title = error.title || error.kind || error.code || "Installation could not be completed";
  const userMessage = error.userMessage || error.message;
  const files = error.affectedFiles || [];
  const namedActions = (recoveryActions || []).filter((action) => action.enabled !== false);

  return (
    <div className="install-error-panel" role="alert" data-testid="install-error-panel">
      <div className="install-error-panel__header">
        <strong>{title}</strong>
        {error.code ? <span className="install-error-panel__code">{error.code}</span> : null}
      </div>
      <p>{userMessage}</p>
      {files.length ? (
        <div className="install-error-panel__files">
          <div className="install-error-panel__eyebrow">Missing or affected</div>
          <ul>
            {files.map((file) => (
              <li key={file}>{file}</li>
            ))}
          </ul>
        </div>
      ) : null}
      {error.suggestedAction || error.recommendedAction ? (
        <p className="install-error-panel__suggest">
          Recommended: {(error.suggestedAction || error.recommendedAction || "").replace(/_/g, " ")}
        </p>
      ) : null}
      <div className="install-error-panel__actions">
        {namedActions.length
          ? namedActions.map((action) => (
              <Button
                key={action.action}
                variant={action.destructive ? "ghost" : "secondary"}
                onClick={() => onAction?.(action.action)}
                data-testid={`install-error-action-${action.action}`}
                title={action.description}
              >
                {action.label}
              </Button>
            ))
          : null}
        {!namedActions.length && onRetry ? (
          <Button variant="primary" onClick={onRetry} data-testid="install-error-retry">
            Retry
          </Button>
        ) : null}
        {!namedActions.length && onRepair ? (
          <Button variant="secondary" onClick={onRepair} data-testid="install-error-repair">
            Repair
          </Button>
        ) : null}
        <Button
          variant="ghost"
          onClick={() => {
            setShowTech((value) => !value);
            onDetails?.();
          }}
          data-testid="install-error-details"
        >
          {showTech ? "Hide technical details" : "View technical details"}
        </Button>
      </div>
      {showTech ? (
        <div className="install-error-panel__tech" data-testid="install-error-tech">
          {error.technicalMessage ? <pre>{error.technicalMessage}</pre> : null}
          {error.logReference ? <p>Log: {error.logReference}</p> : null}
          {error.details?.length ? (
            <ul>
              {error.details.map((detail) => (
                <li key={detail}>{detail}</li>
              ))}
            </ul>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}
