import { useCallback, useEffect, useState } from "react";
import { isSpatialMapEnabled } from "../core/featureFlags";
import { api, ApiError } from "../api";
import type { EssentialAgreementPayload, EssentialReadinessBadges } from "../setup/types";
import { HelpTip, PanelHeading } from "./HelpTip";

const SPATIAL_ESSENTIALS = [
  { id: "moge2_geometry", label: "MoGe-2 Geometry" },
  { id: "vggt_1b_commercial", label: "VGGT-1B Commercial" },
] as const;

const BADGE_LABELS: Array<{ key: keyof EssentialReadinessBadges; label: string }> = [
  { key: "agreementAccepted", label: "Agreement Accepted" },
  { key: "sourceInstalled", label: "Source Installed" },
  { key: "runtimeReady", label: "Runtime Ready" },
  { key: "commercialModelAccess", label: "Commercial Model Access" },
  { key: "modelReady", label: "Model Ready" },
  { key: "gpuReady", label: "GPU Ready" },
  { key: "productionCertified", label: "Production Certified" },
];

function badgeOn(value: unknown): boolean {
  return value === true;
}

export function EssentialAgreementPanel({ onChanged }: { onChanged?: () => void }) {
  const [agreement, setAgreement] = useState<EssentialAgreementPayload | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [fullOpen, setFullOpen] = useState(false);
  const [viewed, setViewed] = useState(false);
  const [viewedVersion, setViewedVersion] = useState("");
  const [readiness, setReadiness] = useState<Record<string, EssentialReadinessBadges>>({});

  const load = useCallback(async () => {
    if (!isSpatialMapEnabled()) return;
    try {
      const next = await api.essentialAgreement();
      setAgreement(next);
      setError(null);
      if (!next.documentAvailable) {
        setViewed(false);
      }
      const rows = await Promise.all(
        SPATIAL_ESSENTIALS.map(async (item) => {
          try {
            return [item.id, await api.essentialReadiness(item.id)] as const;
          } catch {
            return [item.id, null] as const;
          }
        }),
      );
      const mapped: Record<string, EssentialReadinessBadges> = {};
      rows.forEach(([id, row]) => {
        if (row) mapped[id] = row;
      });
      setReadiness(mapped);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : String(err));
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const openFull = async () => {
    setBusy(true);
    setError(null);
    try {
      const document = await api.essentialAgreementDocument();
      setAgreement((current) =>
        current
          ? { ...current, body: document.body, documentAvailable: document.available, currentVersion: document.version }
          : current,
      );
      setFullOpen(true);
      const available = Boolean(document.available && document.body);
      setViewed(available);
      if (available) setViewedVersion(document.version);
    } catch (err: unknown) {
      setViewed(false);
      setFullOpen(false);
      if (err instanceof ApiError && err.status === 503) {
        setError("document unavailable");
      } else {
        setError(err instanceof Error ? err.message : String(err));
      }
    } finally {
      setBusy(false);
    }
  };

  const agree = async () => {
    if (!agreement?.documentAvailable || !viewed || viewedVersion !== agreement.currentVersion) {
      setError("Open the full notice before you agree. Adept will not accept a missing document.");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const next = await api.acceptEssentialAgreement({
        version: agreement.currentVersion,
        documentAvailableConfirmed: true,
      });
      setAgreement(next);
      onChanged?.();
      await load();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  };

  const decline = async () => {
    setBusy(true);
    setError(null);
    try {
      const next = await api.declineEssentialAgreement();
      setAgreement(next);
      onChanged?.();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  };

  const needsAgreement = Boolean(agreement && (!agreement.accepted || !agreement.eligible));
  const documentMissing = agreement?.documentAvailable === false;

  // Spatial Map shelved for v1.1 — hide Spatial Essentials so Setup is not Needs Attention / Blocked.
  if (!isSpatialMapEnabled()) return null;

  return (
    <section className="essential-agreement-panel" data-testid="essential-agreement-panel" aria-labelledby="essential-agreement-heading">
      <PanelHeading
        title="Essential Components"
        tip="These are the building blocks Adept needs for Spatial Map and other core tools. Read the notice, then agree. A missing notice cannot be accepted."
      />
      <div className="setup-section-heading">
        <div>
          <h2 id="essential-agreement-heading">Essential Components notice</h2>
          <p>
            Adept asks you to review one notice for Essential tools. This is separate from any single-model license you accept when linking a folder.
          </p>
        </div>
        <span data-testid="essential-agreement-version">
          Version {agreement?.currentVersion ?? "…"}
        </span>
      </div>

      {agreement?.message && (
        <div
          className={`setup-message${needsAgreement ? " essential-agreement-attention" : ""}`}
          role="status"
          data-testid="essential-agreement-status"
        >
          {agreement.message}
        </div>
      )}
      {error && (
        <div className="setup-message essential-agreement-attention" role="alert" data-testid="essential-agreement-error">
          {error === "document unavailable"
            ? "The notice is unavailable. Retry. Adept will not treat this as accepted."
            : error}
        </div>
      )}

      <div className="row-actions essential-agreement-actions">
        <button
          type="button"
          className="ghost"
          data-testid="essential-agreement-view"
          onClick={() => {
            setFullOpen((open) => !open);
            if (agreement?.documentAvailable && agreement.body) {
              setViewed(true);
              setViewedVersion(agreement.currentVersion);
            }
          }}
          disabled={busy}
        >
          {fullOpen ? "Hide notice" : "View"}
        </button>
        <button type="button" className="ghost" data-testid="essential-agreement-open-full" onClick={() => void openFull()} disabled={busy}>
          Open Full
        </button>
        <button
          type="button"
          className="primary"
          data-testid="essential-agreement-agree"
          onClick={() => void agree()}
          disabled={busy || documentMissing || !viewed || viewedVersion !== (agreement?.currentVersion ?? "") || Boolean(agreement?.accepted)}
        >
          AGREE
        </button>
        <button type="button" className="ghost" data-testid="essential-agreement-decline" onClick={() => void decline()} disabled={busy}>
          Decline
        </button>
        <button type="button" className="linkish" data-testid="essential-agreement-retry" onClick={() => void load()} disabled={busy}>
          Retry
        </button>
      </div>
      <p className="muted">
        View later: stay on Setup. The same notice stays available after you agree.
        <HelpTip text="You can reopen this notice any time from Setup. Agreeing here does not download models by itself." />
      </p>

      {fullOpen && (
        <article className="essential-agreement-document" data-testid="essential-agreement-document">
          {documentMissing || !agreement?.body ? (
            <p>document unavailable</p>
          ) : (
            <pre>{agreement.body}</pre>
          )}
        </article>
      )}

      <div className="essential-readiness-grid">
        {SPATIAL_ESSENTIALS.map((item) => {
          const badges = readiness[item.id];
          return (
            <div key={item.id} className="essential-readiness-card" data-testid={`essential-readiness-${item.id}`}>
              <strong>{item.label}</strong>
              <ul>
                {BADGE_LABELS.map((badge) => (
                  <li key={badge.key} data-ready={badgeOn(badges?.[badge.key]) ? "yes" : "no"}>
                    <span>{badge.label}</span>
                    <em>{badgeOn(badges?.[badge.key]) ? "Yes" : "No"}</em>
                  </li>
                ))}
              </ul>
            </div>
          );
        })}
      </div>
    </section>
  );
}
