/**
 * PropCreatorCore — Express + Standard views over usePropCreator.
 * Express stays the Co-Director stack. Standard is a Production shell over the same blocks.
 */
import { useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { api } from "../../../api";
import { CHARACTER_STYLE_OPTIONS } from "../../character/types";
import { GeneratorPlanPanel } from "../../generators/GeneratorPlanPanel";
import "../../generators/generatorSource.css";
import { CharacterReferenceAssetPicker } from "../characters/CharacterReferenceAssetPicker";
import { candidateStatusLabel, plannedCandidateCount, propGenerateBlockReason } from "./propGenerator";
import { candidateErrorMessage, candidateIsFailed, plannedProgress } from "./types";
import { PROP_PROFILE_SAVED_NOTICE, usePropCreator, type PropCreatorVariant } from "./usePropCreator";
import { loadPropUsage, type PropUsageCounts } from "./propUsage";
import "./propCreator.css";

export type PropCreatorCoreProps = {
  projectId: string;
  variant: PropCreatorVariant;
  onGoTab?: (tab: string, extra?: Record<string, string>) => void;
};

export function PropCreatorCore({ projectId, variant }: PropCreatorCoreProps) {
  const { t } = useTranslation("propCreator");
  const pc = usePropCreator(projectId);
  if (pc.loading) {
    return <p className="muted" data-testid="prop-creator-loading">{t("loading")}</p>;
  }
  if (variant === "standard") {
    return <StandardLayout projectId={projectId} pc={pc} />;
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
      <GeneratorBlock projectId={projectId} pc={pc} />
      <ActionsBlock pc={pc} />
      <StatusBlock pc={pc} />
      <CandidateGrid pc={pc} />
    </section>
  );
}

function StandardLayout({
  projectId,
  pc,
}: {
  projectId: string;
  pc: ReturnType<typeof usePropCreator>;
}) {
  const previewId =
    pc.prop?.approved_asset_id ||
    pc.prop?.candidates.find((c) => c.status === "complete" && c.asset_id)?.asset_id;
  const [usage, setUsage] = useState<PropUsageCounts | null>(null);

  useEffect(() => {
    const propId = pc.prop?.id;
    if (!propId) {
      setUsage(null);
      return;
    }
    let cancelled = false;
    void loadPropUsage(projectId, propId).then((next) => {
      if (!cancelled) setUsage(next);
    });
    return () => {
      cancelled = true;
    };
  }, [projectId, pc.prop?.id]);

  return (
    <div className="prop-creator-standard" data-testid="prop-creator-standard">
      <aside className="prop-creator-standard__browser" data-testid="prop-creator-browser">
        <SavedPropBlock pc={pc} layout="list" />
      </aside>
      <div className="prop-creator-standard__preview" data-testid="prop-creator-preview">
        {previewId ? (
          <img src={api.assetUrl(previewId)} alt="Approved prop" data-testid="prop-creator-preview-image" />
        ) : (
          <p className="muted">Generate a look, then approve one to see it here.</p>
        )}
      </div>
      <aside className="prop-creator-standard__inspector" data-testid="prop-creator-inspector">
        <details className="prop-creator-standard__accordion" open>
          <summary>Name / Style</summary>
          <NameStyleBlock pc={pc} />
        </details>
        <details className="prop-creator-standard__accordion" open>
          <summary>Description</summary>
          <DescriptionBlock pc={pc} />
        </details>
        <details className="prop-creator-standard__accordion" open>
          <summary>Reference</summary>
          <ReferenceBlock projectId={projectId} pc={pc} />
        </details>
        <details className="prop-creator-standard__accordion" open>
          <summary>Generator</summary>
          <GeneratorBlock projectId={projectId} pc={pc} />
        </details>
        <details className="prop-creator-standard__accordion" open>
          <summary>Actions</summary>
          <ActionsBlock pc={pc} usage={usage} />
        </details>
        <details className="prop-creator-standard__accordion" open>
          <summary>Status</summary>
          <StatusBlock pc={pc} />
        </details>
        <details className="prop-creator-standard__accordion">
          <summary>Identity History</summary>
          <IdentityHistoryBlock pc={pc} />
        </details>
        <details className="prop-creator-standard__accordion">
          <summary>Usage</summary>
          <UsageBlock usage={usage} hasProp={Boolean(pc.prop)} />
        </details>
      </aside>
      <div className="prop-creator-standard__strip" data-testid="prop-creator-take-strip">
        <CandidateGrid pc={pc} />
      </div>
    </div>
  );
}

function SavedPropBlock({
  pc,
  layout = "select",
}: {
  pc: ReturnType<typeof usePropCreator>;
  layout?: "select" | "list";
}) {
  const props = pc.workspace?.props || [];
  if (layout === "list") {
    const approved = props.filter((p) => Boolean(p.approved_asset_id));
    const drafts = props.filter((p) => !p.approved_asset_id);
    return (
      <div className="prop-creator-standard__browser-list">
        <button type="button" className="ghost" data-testid="prop-creator-new" onClick={() => pc.newProp()}>
          Create New
        </button>
        <p className="prop-creator-core__label">Approved</p>
        {approved.length ? (
          approved.map((p) => (
            <button
              key={p.id}
              type="button"
              className={p.id === pc.prop?.id ? "prop-creator-core__chip is-on" : "prop-creator-core__chip"}
              data-testid="prop-creator-browser-item"
              onClick={() => void pc.selectProp(p.id)}
            >
              {p.display_label || p.tag}
            </button>
          ))
        ) : (
          <p className="muted">No approved Props yet</p>
        )}
        <p className="prop-creator-core__label">Drafts</p>
        {drafts.length ? (
          drafts.map((p) => (
            <button
              key={p.id}
              type="button"
              className={
                p.id === pc.prop?.id
                  ? "prop-creator-core__chip is-on is-draft"
                  : "prop-creator-core__chip is-draft"
              }
              data-testid="prop-creator-browser-item"
              onClick={() => void pc.selectProp(p.id)}
            >
              {p.display_label || p.tag} (Draft)
            </button>
          ))
        ) : (
          <p className="muted">No drafts</p>
        )}
      </div>
    );
  }
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
      <label className="character-core__checkbox">
        <input
          type="checkbox"
          data-testid="prop-use-as-identity"
          checked={pc.useAsIdentity}
          disabled={pc.busy || !refId}
          onChange={(e) => pc.setUseAsIdentity(e.target.checked)}
        />
        <span>
          Use as Prop Identity{" "}
          <span
            className="character-core__tip"
            title="Use this image as the prop's look, without AI generation. Save to set it as the identity. The existing reference asset is reused — no copy, no generate."
          >
            (?)
          </span>
        </span>
      </label>
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

function GeneratorBlock({
  projectId,
  pc,
}: {
  projectId: string;
  pc: ReturnType<typeof usePropCreator>;
}) {
  const hasReference = !!pc.prop?.reference_asset_id;
  return (
    <div data-testid="prop-creator-generators">
      <GeneratorPlanPanel
        projectId={projectId}
        visualStyle={pc.visualStyle}
        hasReference={hasReference}
        disabled={pc.busy}
        purpose="prop"
        textModeLabel="Description Guided"
        imageNoun="Prop Image"
        imageNounPlural="Prop Images"
        sectionLabel="Generator"
        testId="prop-generator-panel"
        value={pc.plan}
        onChange={pc.setPlan}
      />
    </div>
  );
}

function deleteConfirmMessage(usage?: PropUsageCounts | null): string | undefined {
  if (!usage) return undefined;
  const place = usage.spatial === 1 ? "placement" : "placements";
  const shot = usage.shots === 1 ? "shot" : "shots";
  return `Remove this Prop profile? Used on ${usage.spatial} Spatial ${place} and ${usage.shots} Scene ${shot}. Placements will be unlinked. Library images stay.`;
}

function ActionsBlock({
  pc,
  usage,
}: {
  pc: ReturnType<typeof usePropCreator>;
  usage?: PropUsageCounts | null;
}) {
  const { t } = useTranslation(["propCreator", "common"]);
  const progress = plannedProgress(pc.prop?.candidates || [], plannedCandidateCount(pc.plan));
  const blockReason = propGenerateBlockReason({
    name: pc.name,
    plan: pc.plan,
    busy: false,
  });
  const canGenerate = !blockReason && !pc.busy;
  const showProgress = pc.generating || progress.total > 0;
  return (
    <div className="character-core__generate">
      {showProgress ? (
        <div className="character-core__progress" data-testid="prop-creator-progress">
          <div className="character-core__progress-head">
            <span className="character-core__progress-title">Generating Prop Images</span>
            <span className="character-core__progress-pct" data-testid="prop-creator-progress-pct">
              {progress.percent}%
            </span>
          </div>
          <div
            className="character-core__progress-track"
            role="progressbar"
            aria-valuenow={progress.percent}
            aria-valuemin={0}
            aria-valuemax={100}
          >
            <div className="character-core__progress-fill" style={{ width: `${progress.percent}%` }} />
          </div>
          <p className="character-core__progress-label" data-testid="prop-creator-progress-label">
            {progress.done} of {progress.total}
          </p>
        </div>
      ) : null}
      <div className="prop-creator-core__row">
        <button
          type="button"
          className="character-core__button primary"
          data-testid="prop-creator-generate"
          disabled={!canGenerate}
          title={blockReason || undefined}
          onClick={() => void pc.generate()}
        >
          {pc.generating ? t("propCreator:generating") : t("propCreator:generateImages")}
        </button>
        <button type="button" className="ghost" data-testid="prop-creator-save" disabled={pc.busy || !pc.name.trim()} onClick={() => void pc.save()}>
          {t("propCreator:save")}
        </button>
        <button type="button" className="ghost" data-testid="prop-creator-reset" onClick={() => pc.reset()}>
          Reset
        </button>
        <button
          type="button"
          className="ghost"
          data-testid="prop-creator-delete"
          disabled={!pc.prop || pc.busy}
          onClick={() => void pc.remove(deleteConfirmMessage(usage))}
        >
          Delete
        </button>
      </div>
      {blockReason ? (
        <p className="character-core__hint" data-testid="prop-creator-generate-reason">
          {blockReason}
        </p>
      ) : null}
    </div>
  );
}

function StatusBlock({ pc }: { pc: ReturnType<typeof usePropCreator> }) {
  return (
    <>
      {pc.error ? (
        <p className="prop-creator-core__error" role="alert" data-testid="prop-creator-error">
          {pc.error}
        </p>
      ) : null}
      {pc.notice ? (
        <p
          className={pc.notice === PROP_PROFILE_SAVED_NOTICE ? "prop-creator-core__notice" : "prop-creator-core__notice is-info"}
          role="status"
          aria-live="polite"
          data-testid="prop-creator-notice"
        >
          {pc.notice}
        </p>
      ) : null}
    </>
  );
}

function IdentityHistoryBlock({ pc }: { pc: ReturnType<typeof usePropCreator> }) {
  const prop = pc.prop;
  if (!prop) {
    return <p className="muted">Save a Prop to see look history.</p>;
  }
  const candidates = prop.candidates || [];
  return (
    <div data-testid="prop-creator-identity-history">
      <p className="muted">
        Current identity: {prop.approved_asset_id ? "approved look" : "none yet"}
      </p>
      <p className="muted">Created: {formatTs(prop.created_at)}</p>
      <p className="muted">Updated: {formatTs(prop.updated_at)}</p>
      {candidates.length ? (
        <ul className="prop-creator-standard__history">
          {candidates.map((cand) => (
            <li key={cand.id}>
              <strong>{cand.take_label}</strong>
              {" — "}
              {cand.provenance_label}
              {" · "}
              {candidateStatusLabel(cand.status)}
              {" · "}
              {cand.conditioning === "reference_conditioned" ? "Reference Conditioned" : "Description Guided"}
              {cand.asset_id === prop.approved_asset_id ? " · current identity" : ""}
            </li>
          ))}
        </ul>
      ) : (
        <p className="muted">No generated looks yet.</p>
      )}
    </div>
  );
}

function UsageBlock({ usage, hasProp }: { usage: PropUsageCounts | null; hasProp: boolean }) {
  if (!hasProp) {
    return <p className="muted">Select a Prop to see where it is used.</p>;
  }
  return (
    <div data-testid="prop-creator-usage">
      <p>Spatial Map: {usage ? `${usage.spatial} placement${usage.spatial === 1 ? "" : "s"}` : "…"}</p>
      <p>Scene shots: {usage ? `${usage.shots} shot${usage.shots === 1 ? "" : "s"}` : "…"}</p>
      <p className="muted">Timeline: not available</p>
    </div>
  );
}

function formatTs(value?: string) {
  if (!value) return "—";
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString();
}

function CandidateGrid({ pc }: { pc: ReturnType<typeof usePropCreator> }) {
  const candidates = pc.prop?.candidates || [];
  if (!candidates.length) return null;
  return (
    <div className="prop-creator-core__candidates" data-testid="prop-creator-result-grid">
      {candidates.map((cand) => {
        const approved = cand.asset_id && cand.asset_id === pc.prop?.approved_asset_id;
        const statusLabel = candidateStatusLabel(cand.status);
        const failed = candidateIsFailed(cand);
        const failMessage = failed ? candidateErrorMessage(cand) : "";
        return (
          <article
            key={cand.id}
            className={approved ? "prop-creator-core__card is-approved" : "prop-creator-core__card"}
            data-testid="prop-creator-result-card"
            data-status={cand.status}
          >
            <div className="prop-creator-core__thumb">
              {cand.asset_id && cand.status === "complete" ? (
                <img src={api.assetUrl(cand.asset_id)} alt={cand.take_label} data-testid="prop-creator-result-image" />
              ) : failed ? (
                <span className="muted" data-testid="prop-creator-result-failed">
                  Failed
                  {failMessage ? (
                    <span data-testid="prop-creator-result-failed-msg">{failMessage}</span>
                  ) : null}
                </span>
              ) : (
                <span className="muted" data-testid="prop-creator-result-generating">Generating</span>
              )}
            </div>
            <div className="prop-creator-core__card-body">
              <strong>{cand.take_label}</strong>
              <span className="muted">{cand.provenance_label}</span>
              <span className="muted" data-testid="prop-creator-result-status">{statusLabel}</span>
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
              {failed ? (
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
