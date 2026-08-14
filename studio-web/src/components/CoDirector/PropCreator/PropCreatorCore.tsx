/**
 * PropCreatorCore — Express view over usePropCreator.
 * Keep this hook/core surface-independent so a future Standard can reuse it.
 */
import { useRef, useState } from "react";
import { api } from "../../../api";
import { CHARACTER_STYLE_OPTIONS } from "../../character/types";
import { CharacterReferenceAssetPicker } from "../characters/CharacterReferenceAssetPicker";
import { candidateProgress } from "./types";
import { usePropCreator, type PropCreatorVariant } from "./usePropCreator";
import "./propCreator.css";

export type PropCreatorCoreProps = {
  projectId: string;
  variant: PropCreatorVariant;
  onGoTab?: (tab: string, extra?: Record<string, string>) => void;
};

export function PropCreatorCore({ projectId, variant }: PropCreatorCoreProps) {
  const pc = usePropCreator(projectId);
  if (pc.loading) {
    return <p className="muted" data-testid="prop-creator-loading">Loading Prop Creator…</p>;
  }
  if (variant === "standard") {
    return <ExpressLayout projectId={projectId} pc={pc} />;
  }
  return <ExpressLayout projectId={projectId} pc={pc} />;
}

function ExpressLayout({
  projectId,
  pc,
}: {
  projectId: string;
  pc: ReturnType<typeof usePropCreator>;
}) {
  return (
    <section className="prop-creator-core" data-testid="prop-creator-panel">
      <SavedPropBlock pc={pc} />
      <NameStyleBlock pc={pc} />
      <DescriptionBlock pc={pc} />
      <ReferenceBlock projectId={projectId} pc={pc} />
      <GeneratorBlock pc={pc} />
      <ActionsBlock pc={pc} />
      <StatusBlock pc={pc} />
      <CandidateGrid pc={pc} />
    </section>
  );
}

function SavedPropBlock({ pc }: { pc: ReturnType<typeof usePropCreator> }) {
  const props = pc.workspace?.props || [];
  return (
    <div className="prop-creator-core__row">
      <label className="prop-creator-core__field">
        <span className="prop-creator-core__label">Saved Prop</span>
        <select
          data-testid="prop-creator-saved-select"
          value={pc.prop?.id || ""}
          onChange={(e) => {
            if (e.target.value) void pc.selectProp(e.target.value);
          }}
        >
          <option value="">{props.length ? "Choose a saved Prop" : "No saved Props yet"}</option>
          {props.map((p) => (
            <option key={p.id} value={p.id}>
              {p.display_label || p.tag}
              {p.approved_asset_id ? "" : " (Draft)"}
            </option>
          ))}
        </select>
      </label>
      <button type="button" className="ghost" data-testid="prop-creator-new" onClick={() => pc.newProp()}>
        Create New
      </button>
    </div>
  );
}

function NameStyleBlock({ pc }: { pc: ReturnType<typeof usePropCreator> }) {
  return (
    <div className="prop-creator-core__row">
      <label className="prop-creator-core__field">
        <span className="prop-creator-core__label">Name</span>
        <input
          data-testid="prop-creator-name"
          value={pc.name}
          onChange={(e) => pc.setName(e.target.value)}
          placeholder=""
          aria-label="Prop name"
        />
      </label>
      <label className="prop-creator-core__field">
        <span className="prop-creator-core__label">Image Style</span>
        <select
          data-testid="prop-creator-style"
          value={pc.visualStyle}
          onChange={(e) => pc.setVisualStyle(e.target.value)}
        >
          {CHARACTER_STYLE_OPTIONS.map((opt) => (
            <option key={opt.value || "none"} value={opt.value}>
              {opt.label}
            </option>
          ))}
        </select>
      </label>
    </div>
  );
}

function DescriptionBlock({ pc }: { pc: ReturnType<typeof usePropCreator> }) {
  return (
    <div>
      <p className="prop-creator-core__label">Description</p>
      <textarea
        className="prop-creator-core__prompt"
        data-testid="prop-creator-description"
        value={pc.description}
        onChange={(e) => pc.setDescription(e.target.value)}
        placeholder="What is this prop? Shape, material, color, important details."
      />
    </div>
  );
}

function ReferenceBlock({
  projectId,
  pc,
}: {
  projectId: string;
  pc: ReturnType<typeof usePropCreator>;
}) {
  const [pickerOpen, setPickerOpen] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);
  const refId = pc.prop?.reference_asset_id || "";
  return (
    <div data-testid="prop-creator-reference">
      <p className="prop-creator-core__label">Reference</p>
      <div className="prop-creator-core__ref">
        {refId ? <img src={api.assetUrl(refId)} alt="Prop reference" data-testid="prop-creator-reference-thumb" /> : null}
        <div className="prop-creator-core__row">
          <button
            type="button"
            className="ghost"
            data-testid="prop-creator-reference-library"
            onClick={() => setPickerOpen(true)}
          >
            {refId ? "Change from Library" : "Add from Library"}
          </button>
          <button
            type="button"
            className="ghost"
            data-testid="prop-creator-reference-upload"
            onClick={() => fileRef.current?.click()}
          >
            Upload
          </button>
          {refId ? (
            <button
              type="button"
              className="ghost"
              data-testid="prop-creator-reference-remove"
              onClick={() => void pc.setReference(null)}
            >
              Remove
            </button>
          ) : null}
        </div>
      </div>
      <input
        ref={fileRef}
        type="file"
        accept="image/*"
        hidden
        onChange={(e) => {
          const file = e.target.files?.[0];
          e.target.value = "";
          if (!file) return;
          void api.uploadAsset(projectId, file, "prop_reference", "image").then((asset) => {
            void pc.setReference(asset.id);
          });
        }}
      />
      <CharacterReferenceAssetPicker
        projectId={projectId}
        currentAssetId={refId || null}
        open={pickerOpen}
        onCancel={() => setPickerOpen(false)}
        onConfirm={(asset) => {
          setPickerOpen(false);
          void pc.setReference(asset.id);
        }}
      />
    </div>
  );
}

function GeneratorBlock({ pc }: { pc: ReturnType<typeof usePropCreator> }) {
  return (
    <div data-testid="prop-creator-generators">
      <p className="prop-creator-core__label">Generator</p>
      <label className="prop-creator-core__row">
        <input
          type="checkbox"
          data-testid="prop-creator-local-enable"
          checked={pc.localEnabled}
          onChange={(e) => pc.setLocalEnabled(e.target.checked)}
        />
        Local Image Generator
        <select
          data-testid="prop-creator-local-select"
          value={pc.localFamily}
          disabled={!pc.localEnabled}
          onChange={(e) => pc.setLocalFamily(e.target.value)}
        >
          <option value="">Auto Select</option>
          {(pc.workspace?.local_families || []).map((fam) => (
            <option key={fam.id} value={fam.id}>
              {fam.label}
            </option>
          ))}
        </select>
      </label>
      <p className="muted" data-testid="prop-creator-api-unavailable">
        API Generation — Not Available
      </p>
    </div>
  );
}

function ActionsBlock({ pc }: { pc: ReturnType<typeof usePropCreator> }) {
  const progress = candidateProgress(pc.prop?.candidates || []);
  const canGenerate = !!pc.name.trim() && pc.localEnabled && !pc.busy;
  return (
    <div className="prop-creator-core__row">
      <button
        type="button"
        className="primary"
        data-testid="prop-creator-generate"
        disabled={!canGenerate}
        onClick={() => void pc.generate()}
      >
        {pc.generating ? "Generating…" : "Generate Prop Images"}
      </button>
      <button type="button" className="ghost" data-testid="prop-creator-save" disabled={pc.busy || !pc.name.trim()} onClick={() => void pc.persist()}>
        Save
      </button>
      <button type="button" className="ghost" data-testid="prop-creator-reset" onClick={() => pc.reset()}>
        Reset
      </button>
      <button type="button" className="ghost" data-testid="prop-creator-delete" disabled={!pc.prop || pc.busy} onClick={() => void pc.remove()}>
        Delete
      </button>
      {progress.total ? (
        <span className="muted" data-testid="prop-creator-progress">
          {progress.done} of {progress.total} complete
        </span>
      ) : null}
    </div>
  );
}

function StatusBlock({ pc }: { pc: ReturnType<typeof usePropCreator> }) {
  return (
    <>
      {pc.error ? (
        <p className="muted" style={{ color: "var(--danger, #c33)" }} data-testid="prop-creator-error">
          {pc.error}
        </p>
      ) : null}
      {pc.notice ? (
        <p className="muted" style={{ color: "var(--good, #4a8)" }} data-testid="prop-creator-notice">
          {pc.notice}
        </p>
      ) : null}
    </>
  );
}

function CandidateGrid({ pc }: { pc: ReturnType<typeof usePropCreator> }) {
  const candidates = pc.prop?.candidates || [];
  if (!candidates.length) return null;
  return (
    <div className="prop-creator-core__candidates" data-testid="prop-creator-result-grid">
      {candidates.map((cand) => {
        const approved = cand.asset_id && cand.asset_id === pc.prop?.approved_asset_id;
        return (
          <article
            key={cand.id}
            className={approved ? "prop-creator-core__card is-approved" : "prop-creator-core__card"}
            data-testid="prop-creator-result-card"
          >
            <div className="prop-creator-core__thumb">
              {cand.asset_id ? (
                <img src={api.assetUrl(cand.asset_id)} alt={cand.take_label} data-testid="prop-creator-result-image" />
              ) : (
                <span className="muted">{cand.status === "failed" ? "Failed" : "Generating…"}</span>
              )}
            </div>
            <div className="prop-creator-core__card-body">
              <strong>{cand.take_label}</strong>
              <span className="muted">{cand.provenance_label}</span>
              {cand.status === "complete" ? (
                <button
                  type="button"
                  className="primary"
                  data-testid="prop-creator-approve"
                  disabled={pc.busy}
                  onClick={() => void pc.approve(cand.id)}
                >
                  {approved ? "Using This Prop" : "Use This Prop"}
                </button>
              ) : null}
              {cand.status === "failed" ? (
                <button
                  type="button"
                  className="ghost"
                  data-testid="prop-creator-retry"
                  disabled={pc.busy}
                  onClick={() => void pc.retry(cand.id)}
                >
                  Retry
                </button>
              ) : null}
            </div>
          </article>
        );
      })}
    </div>
  );
}
