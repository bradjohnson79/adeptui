/** Shared render-failure presentation for T2V / 1F / 3F (and JobPanel summaries). */
import type { ReactNode } from "react";
import { ApiError } from "../api";

export type RenderFailureInfo = {
  reason: string;
  technical?: string | null;
};

const EM = "\u2014"; // em dash

export function formatRenderFailedSummary(reason: string): string {
  const clean = (reason || "").trim() || "Unknown error.";
  const prefixed = clean.toLowerCase().startsWith("render failed")
    ? clean
    : `Render failed ${EM} ${clean}`;
  return prefixed;
}

/** Prefer a short human line; park long / traceback / JSON in technical. */
export function splitFailureMessage(message: string | null | undefined): RenderFailureInfo {
  const value = (message || "").trim();
  if (!value) return { reason: "Unknown error." };

  const looksHeavy =
    value.includes("Traceback") ||
    (value.match(/File "/g) || []).length > 1 ||
    value.length > 280 ||
    (value.startsWith("{") && value.includes("}")) ||
    (value.startsWith("[") && value.length > 120);

  if (!looksHeavy) return { reason: value };

  const firstLine = value.split(/\r?\n/).find((line) => line.trim()) || "Unknown error.";
  let reason = firstLine.trim().slice(0, 280);
  // Avoid dumping raw JSON as the primary reason
  if (reason.startsWith("{") || reason.startsWith("[")) {
    reason = "See Technical Details.";
  }
  return { reason, technical: value };
}

/**
 * Extract a creator-readable reason from a failed render request.
 * Studio API may return 409 SMART_PRODUCTION_GATE with `{ detail: { reason } }`,
 * or throw ApiError with message / details.
 */
export async function extractRenderFailure(err: unknown): Promise<RenderFailureInfo> {
  if (err instanceof ApiError) {
    let reason = (err.message || "Request failed.").trim();
    const technicalBits: string[] = [];
    if (err.code) technicalBits.push(`code: ${err.code}`);
    if (err.status) technicalBits.push(`status: ${err.status}`);

    // SMART_PRODUCTION_GATE and similar often return `{ detail: { reason } }` with no
    // `message`, so ApiError.message may be the raw JSON body. Prefer structured reason.
    const tryPullReason = (obj: unknown): string | null => {
      if (!obj || typeof obj !== "object") return null;
      const rec = obj as Record<string, unknown>;
      if (typeof rec.reason === "string" && rec.reason.trim()) return rec.reason.trim();
      if (typeof rec.message === "string" && rec.message.trim() && !rec.message.trim().startsWith("{")) {
        return rec.message.trim();
      }
      if (rec.detail && typeof rec.detail === "object") {
        const d = rec.detail as Record<string, unknown>;
        if (typeof d.reason === "string" && d.reason.trim()) return d.reason.trim();
        if (typeof d.message === "string" && d.message.trim()) return d.message.trim();
      }
      return null;
    };

    const fromDetails = tryPullReason(err.details);
    if (fromDetails) reason = fromDetails;

    try {
      const parsed = JSON.parse(err.message);
      const fromMsg = tryPullReason(parsed);
      if (fromMsg) reason = fromMsg;
      technicalBits.push(JSON.stringify(parsed, null, 2));
    } catch {
      /* message is plain text */
    }

    if (err.technical_evidence) {
      try {
        technicalBits.push(JSON.stringify(err.technical_evidence, null, 2));
      } catch {
        /* ignore */
      }
    }
    if (err.details && !fromDetails) {
      try {
        technicalBits.push(JSON.stringify(err.details, null, 2));
      } catch {
        /* ignore */
      }
    }
    const split = splitFailureMessage(reason);
    return {
      reason: split.reason,
      technical: split.technical || (technicalBits.length ? technicalBits.join("\n") : null),
    };
  }

  if (err instanceof Response) {
    let bodyText = "";
    let reason = `${err.status} ${err.statusText}`.trim();
    try {
      const body = await err.json();
      bodyText = JSON.stringify(body, null, 2);
      const detail = body?.detail;
      if (detail?.reason) reason = String(detail.reason);
      else if (typeof detail === "string") reason = detail;
      else if (detail?.message) reason = String(detail.message);
      else if (body?.message) reason = String(body.message);
    } catch {
      try {
        bodyText = await err.text();
      } catch {
        /* ignore */
      }
    }
    return {
      reason: splitFailureMessage(reason).reason,
      technical: bodyText || null,
    };
  }

  if (err instanceof Error) {
    return splitFailureMessage(err.message);
  }

  return splitFailureMessage(String(err));
}

export function RenderFailureAlert({
  reason,
  technical,
  testId,
}: {
  reason: string;
  technical?: string | null;
  testId?: string;
}): ReactNode {
  const summary = formatRenderFailedSummary(reason);
  return (
    <div className="pill warn render-failure-alert" role="alert" data-testid={testId}>
      <div className="render-failure-summary">{summary}</div>
      {technical ? (
        <details className="render-failure-details">
          <summary>Technical Details</summary>
          <pre>{technical}</pre>
        </details>
      ) : null}
    </div>
  );
}
