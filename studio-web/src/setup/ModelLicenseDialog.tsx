import { useEffect, useId, useState } from "react";
import { api } from "../api";
import type { ModelLicenseDetail } from "./types";

const STATUS_LABEL: Record<string, string> = {
  "LICENSE SETUP REQUIRED": "License setup required",
  "LICENSE CONFIRMED": "License confirmed",
  "SEPARATE AUTHORIZATION REQUIRED": "Separate authorization required",
  "NO LICENSE REQUIRED": "No license required",
};

export function modelLicenseStatusLabel(status: string): string {
  return STATUS_LABEL[status] || status;
}

export function ModelLicenseDialog({
  modelId,
  onClose,
  onConfirmed,
}: {
  modelId: string;
  onClose: () => void;
  onConfirmed: () => void;
}) {
  const titleId = useId();
  const [detail, setDetail] = useState<ModelLicenseDetail | null>(null);
  const [region, setRegion] = useState("");
  const [agreed, setAgreed] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    let cancelled = false;
    void api.setupModelLicense(modelId).then((next) => {
      if (!cancelled) setDetail(next);
    }).catch(() => {
      if (!cancelled) setError("MiniMax H3 licensing information could not be verified.");
    });
    return () => {
      cancelled = true;
    };
  }, [modelId]);

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  const selected = detail?.regions.find((item) => item.code === region);
  const separate = selected?.route === "separate_authorization";
  const verified = Boolean(detail?.verified && detail.licenseUrl);

  async function enable() {
    if (!detail || !selected || !agreed) return;
    setBusy(true);
    setError("");
    try {
      await api.setupAcknowledgeModelLicense(detail.modelId, { region: selected.code, confirmed: true });
      onConfirmed();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "License setup required");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="setup-dialog-backdrop" role="presentation" onMouseDown={onClose}>
      <section
        className="setup-dialog model-license-dialog"
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        onMouseDown={(event) => event.stopPropagation()}
      >
        <header className="setup-dialog-header">
          <h2 id={titleId}>MiniMax H3 License</h2>
          <button type="button" className="linkish" onClick={onClose}>Cancel</button>
        </header>
        <p>MiniMax H3 is provided by MiniMax and is governed by MiniMax's own license.</p>
        <p>Adept UI does not grant you a license to use MiniMax H3.</p>
        {!verified && (
          <p>
            {error || detail?.message || "MiniMax H3 licensing information could not be verified."}
            {" "}
            <a href={detail?.officialSource || "https://huggingface.co/MiniMaxAI/MiniMax-H3"} target="_blank" rel="noreferrer">
              View Official MiniMax Source
            </a>
          </p>
        )}
        {verified && detail && (
          <>
            <label className="model-license-region">
              Your region
              <select value={region} onChange={(event) => { setRegion(event.target.value); setAgreed(false); }}>
                <option value="">Select country / region</option>
                {detail.regions.map((item) => (
                  <option key={item.code} value={item.code}>{item.name}</option>
                ))}
              </select>
            </label>
            {selected && !separate && (
              <div>
                <p><strong>{detail.licenseName}</strong></p>
                <p><a href={detail.licenseUrl} target="_blank" rel="noreferrer">Read Official License</a></p>
                <p>
                  The official license also asks for separate written authorization from MiniMax if commercial
                  products and services exceed US$20 million in yearly revenue. That request goes to MiniMax.
                </p>
                <p>
                  <a href="mailto:api@minimax.io?subject=MiniMax%20H3%20licensing%20-%20authorization%20request">
                    Contact MiniMax about that authorization
                  </a>
                </p>
              </div>
            )}
            {selected && separate && (
              <div>
                <p>Separate MiniMax authorization is required for your region.</p>
                <p>
                  <a href={detail.authorizationUrl} target="_blank" rel="noreferrer">Apply / Request Authorization</a>
                </p>
                <p><a href={detail.licenseUrl} target="_blank" rel="noreferrer">Read Official License</a></p>
              </div>
            )}
            {selected && (
              <label className="model-license-check">
                <input type="checkbox" checked={agreed} onChange={(event) => setAgreed(event.target.checked)} />
                <span>
                  {separate
                    ? "I confirm that I have obtained the required MiniMax authorization."
                    : "I have read and agree to the applicable MiniMax H3 license."}
                </span>
              </label>
            )}
            {error && <p className="setup-issue">{error}</p>}
            <button type="button" className="primary" disabled={!selected || !agreed || busy} onClick={() => void enable()}>
              Enable MiniMax H3
            </button>
          </>
        )}
      </section>
    </div>
  );
}
