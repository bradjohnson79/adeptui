import { useCallback, useEffect, useState } from "react";
import { api } from "../api";
import { Button } from "./ui";

type CatalogRow = {
  rowId: string;
  provider: string;
  family: string;
  model: string;
  endpoint: string;
  t2v: boolean;
  i2v: boolean;
  r2v: boolean;
  firstFrame: boolean;
  lastFrame: boolean;
  references: number;
  durationMinSec?: number | null;
  durationMaxSec?: number | null;
  durationsSec?: number[];
  resolutions?: string[];
  audio: boolean;
  liveSubmit: boolean;
  status: string;
  reviewStatus: string;
  notes?: string;
};

type CatalogState = {
  updatedAt: string | null;
  totalRows: number;
  pendingReview: number;
  rows: CatalogRow[];
  providers?: Record<string, { status: string; rowCount?: number; message?: string | null }>;
  lastRefresh?: { at?: string; new?: number; updated?: number; removed?: number; durationMs?: number } | null;
};

function durationLabel(row: CatalogRow): string {
  if (row.durationsSec && row.durationsSec.length) return row.durationsSec.join("/") + "s";
  if (row.durationMinSec != null && row.durationMaxSec != null) return `${row.durationMinSec}-${row.durationMaxSec}s`;
  if (row.durationMaxSec != null) return `<=${row.durationMaxSec}s`;
  return "—";
}

/**
 * Provider Catalog Sync admin — developer chrome for Settings → Advanced.
 * Creators never see this: newly discovered endpoints stay pending_review
 * until a human approves them, and approval never auto-exposes an endpoint.
 */
export function ProviderCatalogAdmin() {
  const [catalog, setCatalog] = useState<CatalogState | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [showAll, setShowAll] = useState(false);

  const load = useCallback(async () => {
    const data = (await api.hostedProvidersVideoCatalog()) as CatalogState;
    setCatalog(data);
  }, []);

  useEffect(() => {
    load().catch((e) => setError(e instanceof Error ? e.message : String(e)));
  }, [load]);

  const refresh = async () => {
    setBusy(true);
    setError(null);
    try {
      await api.hostedProvidersCatalogRefresh();
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  };

  const review = async (rowId: string, action: "approved" | "hidden") => {
    setError(null);
    try {
      await api.hostedProvidersCatalogReview(rowId, action);
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  };

  const pending = (catalog?.rows || []).filter((r) => r.reviewStatus === "pending_review");
  const visible = showAll ? catalog?.rows || [] : pending;

  return (
    <section className="provider-catalog-admin" data-testid="provider-catalog-admin" style={{ marginTop: "1rem" }}>
      <div className="row-actions" style={{ gap: "0.5rem", alignItems: "center", flexWrap: "wrap" }}>
        <Button data-testid="refresh-provider-catalogs" disabled={busy} onClick={() => void refresh()}>
          {busy ? "Refreshing…" : "Refresh Provider Catalogs"}
        </Button>
        {catalog?.updatedAt && (
          <span className="muted" data-testid="provider-catalog-updated-at">
            Last refresh: {catalog.updatedAt}
          </span>
        )}
      </div>
      <p className="muted" style={{ marginTop: "0.35rem" }}>
        Read-only discovery against provider catalogs — never runs a generation. New endpoints arrive as
        &ldquo;pending review&rdquo; and are never shown to creators automatically.
      </p>

      {catalog && (
        <p className="muted" data-testid="provider-catalog-summary">
          {catalog.totalRows} endpoints tracked · {catalog.pendingReview} pending review
          {catalog.lastRefresh?.new != null ? ` · last run: +${catalog.lastRefresh.new} new` : ""}
          {catalog.providers &&
            ` · ${Object.entries(catalog.providers)
              .map(([pid, s]) => `${pid}: ${s.status}${s.rowCount != null ? ` (${s.rowCount})` : ""}`)
              .join(", ")}`}
        </p>
      )}

      {error && (
        <p className="error" role="alert" data-testid="provider-catalog-error">
          {error}
        </p>
      )}

      {visible.length > 0 && (
        <>
          <div className="row-actions" style={{ gap: "0.5rem", margin: "0.5rem 0" }}>
            <Button
              variant="secondary"
              data-testid="provider-catalog-toggle-all"
              onClick={() => setShowAll((v) => !v)}
            >
              {showAll ? "Show pending only" : `Show all ${catalog?.totalRows ?? 0}`}
            </Button>
          </div>
          <ul data-testid="provider-catalog-review-list" style={{ display: "grid", gap: "0.4rem", padding: 0 }}>
            {visible.slice(0, 200).map((r) => (
              <li
                key={r.rowId}
                data-testid={`provider-catalog-row-${r.rowId}`}
                className="panel"
                style={{ padding: "0.5rem", border: "1px solid var(--border, #333)", listStyle: "none" }}
              >
                <div style={{ display: "flex", justifyContent: "space-between", gap: "0.5rem", flexWrap: "wrap" }}>
                  <span>
                    <strong>{r.model || r.endpoint}</strong>{" "}
                    <span className="muted">
                      {r.provider} · {r.family || "—"} · {r.endpoint}
                    </span>
                  </span>
                  <span className="muted" data-testid={`provider-catalog-row-status-${r.rowId}`}>
                    {r.reviewStatus}
                    {r.liveSubmit ? " · live" : ""}
                  </span>
                </div>
                <div className="muted" style={{ fontSize: "0.85rem" }}>
                  {[
                    r.t2v && "T2V",
                    r.i2v && "I2V",
                    r.r2v && `R2V(${r.references || "?"})`,
                    r.firstFrame && r.lastFrame && "FLF",
                    durationLabel(r),
                    (r.resolutions || []).join("/"),
                    r.audio && "audio",
                  ]
                    .filter(Boolean)
                    .join(" · ") || "capabilities unverified"}
                  {r.notes ? ` — ${r.notes}` : ""}
                </div>
                {r.reviewStatus === "pending_review" && (
                  <div className="row-actions" style={{ gap: "0.5rem", marginTop: "0.35rem" }}>
                    <Button
                      data-testid={`provider-catalog-approve-${r.rowId}`}
                      onClick={() => void review(r.rowId, "approved")}
                    >
                      Approve
                    </Button>
                    <Button
                      variant="secondary"
                      data-testid={`provider-catalog-hide-${r.rowId}`}
                      onClick={() => void review(r.rowId, "hidden")}
                    >
                      Hide
                    </Button>
                  </div>
                )}
              </li>
            ))}
          </ul>
        </>
      )}
    </section>
  );
}
