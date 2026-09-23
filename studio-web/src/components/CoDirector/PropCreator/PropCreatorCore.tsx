/**
 * PropCreatorCore — Express + Standard views over usePropCreator.
 * Express stays the Co-Director stack. Standard is a Production shell over the same blocks.
 */
import { useCallback, useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { api } from "../../../api";
import type { CreatorDeletePreview } from "../../creators/creatorProfileDelete";
import { CreatorProfileDeleteModal } from "../../creators/CreatorProfileDeleteModal";
import { CHARACTER_STYLE_OPTIONS } from "../../character/types";
import { GeneratorPlanPanel } from "../../generators/GeneratorPlanPanel";
import "../../generators/generatorSource.css";
import { CharacterReferenceAssetPicker } from "../characters/CharacterReferenceAssetPicker";
import { candidateHasValidAsset, visiblePrimaryPreviewAssetId } from "./propApproval";
import { PropAssetPreview } from "./PropAssetPreview";
import { PropReferenceSheetModal } from "./PropReferenceSheetModal";
import { candidateStatusLabel, plannedCandidateCount, propGenerateBlockReason } from "./propGenerator";
import { candidateErrorMessage, candidateIsFailed, plannedProgress, promptCanonicalPropTag } from "./types";
import { PROP_GLOBAL_SCOPE_HELP, groupScopeItems, scopeLabel } from "../../../creatorScope";
import { GlobalScopeField } from "../../creator/GlobalScopeField";
import { PROP_PROFILE_SAVED_NOTICE, usePropCreator, type PropCreatorVariant } from "./usePropCreator";
import { loadPropUsage, type PropUsageCounts } from "./propUsage";
import "../../character/characterCore.css";
import "./propCreator.css";
import { PropAdvancedPanel } from "./PropAdvancedPanel";

export type PropCreatorCoreProps = {
  projectId: string;
  variant: PropCreatorVariant;
  onGoTab?: (tab: string, extra?: Record<string, string>) => void;
};

export function PropCreatorCore({ projectId, variant, onGoTab }: PropCreatorCoreProps) {
  const { t } = useTranslation("propCreator");
  const pc = usePropCreator(projectId);
  const [deletePreview, setDeletePreview] = useState<CreatorDeletePreview | null>(null);
  const [deleteModalOpen, setDeleteModalOpen] = useState(false);
  const [deleting, setDeleting] = useState(false);

  const handleDeleteClick = useCallback(async () => {
    if (!pc.prop || pc.busy) return;
    try {
      const preview = await pc.getDeletePreview();
      if (preview) {
        setDeletePreview(preview);
        setDeleteModalOpen(true);
      }
    } catch {
      /* pc.error is set by the hook; modal simply won't open */
    }
  }, [pc]);

  const handleConfirmDelete = useCallback(async () => {
    if (!deletePreview) return;
    setDeleting(true);
    try {
      const ok = await pc.remove({
        confirmCrossProject: deletePreview.isGlobal && deletePreview.usageCount > 0,
      });
      if (ok) {
        setDeleteModalOpen(false);
        setDeletePreview(null);
      } else {
        const updated = await pc.getDeletePreview();
        setDeletePreview(updated ?? null);
      }
    } catch {
      /* error surfaced through pc.error */
    } finally {
      setDeleting(false);
    }
  }, [deletePreview, pc]);

  if (pc.loading) {
    return <p className="muted" data-testid="prop-creator-loading">{t("loading")}</p>;
  }
  const deleteProps = {
    preview: deletePreview,
    modalOpen: deleteModalOpen,
    deleting,
    onDeleteClick: handleDeleteClick,
    onConfirmDelete: handleConfirmDelete,
    onCloseDeleteModal: () => {
      if (!deleting) {
        setDeleteModalOpen(false);
        setDeletePreview(null);
      }
    },
  };
  if (variant === "standard") {
    return <StandardLayout projectId={projectId} pc={pc} deleteProps={deleteProps} />;
  }
  return <ExpressLayout projectId={projectId} pc={pc} deleteProps={deleteProps} onGoTab={onGoTab} />;
}

type DeleteProps = {
  preview: CreatorDeletePreview | null;
  modalOpen: boolean;
  deleting: boolean;
  onDeleteClick: () => void;
  onConfirmDelete: () => void;
  onCloseDeleteModal: () => void;
};

function ExpressLayout({
  projectId,
  pc,
  deleteProps,
  onGoTab,
}: {
  projectId: string;
  pc: ReturnType<typeof usePropCreator>;
  deleteProps: DeleteProps;
  onGoTab?: (tab: string, extra?: Record<string, string>) => void;
}) {
  const [expressMode, setExpressMode] = useState<"standard" | "advanced">("standard");
  useEffect(() => {
    const mode = String(pc.prop?.mode || "").trim().toLowerCase();
    if (mode === "advanced") setExpressMode("advanced");
    if (mode === "standard" || mode === "basic") setExpressMode("standard");
  }, [pc.prop?.id, pc.prop?.mode]);
  return (
    <section className="prop-creator-core" data-testid="prop-creator-panel">
      <div className="prop-creator-core__tabs" role="tablist" aria-label="Prop creator mode">
        <button
          type="button"
          role="tab"
          className={expressMode === "standard" ? "prop-creator-core__tab is-on" : "prop-creator-core__tab"}
          data-testid="prop-creator-tab-standard"
          aria-selected={expressMode === "standard"}
          onClick={() => setExpressMode("standard")}
        >
          Standard Prop
        </button>
        <button
          type="button"
          role="tab"
          className={expressMode === "advanced" ? "prop-creator-core__tab is-on" : "prop-creator-core__tab"}
          data-testid="prop-creator-tab-advanced"
          aria-selected={expressMode === "advanced"}
          onClick={() => setExpressMode("advanced")}
        >
          Advanced Prop
        </button>
      </div>
      {expressMode === "standard" ? (
        <>
          <div className="character-core__section" data-testid="prop-creator-section-saved">
            <h3 className="character-core__section-title">Saved Prop</h3>
            <SavedPropBlock pc={pc} projectId={projectId} onDelete={deleteProps.onDeleteClick} deleting={deleteProps.deleting} />
          </div>
          <div className="character-core__section" data-testid="prop-creator-section-name-style">
            <h3 className="character-core__section-title">Name / Style</h3>
            <NameStyleBlock pc={pc} />
          </div>
          <div className="character-core__section" data-testid="prop-creator-section-description">
            <h3 className="character-core__section-title">Description</h3>
            <DescriptionBlock pc={pc} />
          </div>
          <div className="character-core__section" data-testid="prop-creator-section-reference">
            <h3 className="character-core__section-title">Reference</h3>
            <ReferenceBlock projectId={projectId} pc={pc} />
          </div>
          <div className="character-core__section" data-testid="prop-creator-section-generator">
            <h3 className="character-core__section-title">Generator</h3>
            <GeneratorBlock projectId={projectId} pc={pc} />
          </div>
          <div className="character-core__section" data-testid="prop-creator-section-actions">
            <h3 className="character-core__section-title">Actions</h3>
            <ActionsBlock pc={pc} />
            <StatusBlock pc={pc} />
          </div>
          <div className="character-core__section" data-testid="prop-creator-section-results">
            <h3 className="character-core__section-title">Results</h3>
            <CandidateGrid pc={pc} />
          </div>
          <CreatorProfileDeleteModal
            open={deleteProps.modalOpen}
            entityType="prop"
            preview={deleteProps.preview}
            deleting={deleteProps.deleting}
            onClose={deleteProps.onCloseDeleteModal}
            onConfirm={() => void deleteProps.onConfirmDelete()}
          />
        </>
      ) : (
        <>
          <div className="character-core__section" data-testid="prop-creator-section-saved-advanced">
            <h3 className="character-core__section-title">Saved Prop</h3>
            <SavedPropBlock pc={pc} projectId={projectId} onDelete={deleteProps.onDeleteClick} deleting={deleteProps.deleting} />
          </div>
          <div className="character-core__section">
            <h3 className="character-core__section-title">Name</h3>
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
            <GlobalScopeField
              testId="prop-creator-global"
              checked={pc.isGlobal}
              onChange={pc.setIsGlobal}
              helpText={PROP_GLOBAL_SCOPE_HELP}
            />
          </div>
          <div className="character-core__section">
            <h3 className="character-core__section-title">Advanced Prop</h3>
            <PropAdvancedPanel
              projectId={projectId}
              propId={pc.prop?.id}
              name={pc.name}
              initialProp={pc.prop}
              tagDisplay={promptCanonicalPropTag(pc.prop, pc.name) || undefined}
              onGoTab={onGoTab}
            />
          </div>
          <CreatorProfileDeleteModal
            open={deleteProps.modalOpen}
            entityType="prop"
            preview={deleteProps.preview}
            deleting={deleteProps.deleting}
            onClose={deleteProps.onCloseDeleteModal}
            onConfirm={() => void deleteProps.onConfirmDelete()}
          />
        </>
      )}
    </section>
  );
}

function StandardLayout({
  projectId,
  pc,
  deleteProps,
}: {
  projectId: string;
  pc: ReturnType<typeof usePropCreator>;
  deleteProps: DeleteProps;
}) {
  const previewId = visiblePrimaryPreviewAssetId(pc.prop);
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
        <SavedPropBlock pc={pc} projectId={projectId} layout="list" onDelete={deleteProps.onDeleteClick} deleting={deleteProps.deleting} />
      </aside>
      <div className="prop-creator-standard__preview" data-testid="prop-creator-preview">
        {previewId ? (
          <PropAssetPreview
            assetId={previewId}
            projectId={projectId}
            alt="Approved prop"
            testId="prop-creator-preview-image"
            unavailableLabel="Primary candidate unavailable"
          />
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
          <ActionsBlock pc={pc} />
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
      <CreatorProfileDeleteModal
        open={deleteProps.modalOpen}
        entityType="prop"
        preview={deleteProps.preview}
        deleting={deleteProps.deleting}
        onClose={deleteProps.onCloseDeleteModal}
        onConfirm={() => void deleteProps.onConfirmDelete()}
      />
    </div>
  );
}

function SavedPropBlock({
  pc,
  projectId,
  layout = "select",
  onDelete,
  deleting,
}: {
  pc: ReturnType<typeof usePropCreator>;
  projectId: string;
  layout?: "select" | "list";
  onDelete?: () => void;
  deleting?: boolean;
}) {
  const props = pc.workspace?.props || [];
  const grouped = groupScopeItems(props, projectId);
  if (layout === "list") {
    const approved = props.filter((p) => Boolean(p.approved_asset_id));
    const drafts = props.filter((p) => !p.approved_asset_id);
    return (
      <div className="prop-creator-standard__browser-list">
        <button type="button" className="ghost" data-testid="prop-creator-new" onClick={() => pc.newProp()}>
          Create New
        </button>
        <button
          type="button"
          className="danger"
          data-testid="prop-creator-delete"
          disabled={!pc.prop?.id || pc.busy || deleting}
          onClick={() => onDelete?.()}
        >
          Delete Prop
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
        <select
          data-testid="prop-creator-saved-select"
          value={pc.prop?.id || ""}
          onChange={(e) => {
            if (e.target.value) void pc.selectProp(e.target.value);
          }}
          aria-label="Saved Prop"
        >
          <option value="">{props.length ? "Choose a saved Prop" : "No saved Props yet"}</option>
          {grouped.project.length ? (
            <optgroup label="Project">
              {grouped.project.map((p) => (
                <option key={p.id} value={p.id}>
                  {scopeLabel(`${p.display_label || p.tag}${p.approved_asset_id ? "" : " (Draft)"}`, p, projectId)}
                </option>
              ))}
            </optgroup>
          ) : null}
          {grouped.global.length ? (
            <optgroup label="Global">
              {grouped.global.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.display_label || p.tag}
                  {p.approved_asset_id ? "" : " (Draft)"}
                </option>
              ))}
            </optgroup>
          ) : null}
        </select>
      </label>
      <button type="button" className="ghost" data-testid="prop-creator-new" onClick={() => pc.newProp()}>
        Create New
      </button>
      <button
        type="button"
        className="danger"
        data-testid="prop-creator-delete"
        disabled={!pc.prop?.id || pc.busy || deleting}
        onClick={() => onDelete?.()}
      >
        Delete Prop
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
        {pc.nameCollision ? (
          <div className="prop-creator-core__name-collision" data-testid="prop-creator-name-collision">
            <p>{pc.nameCollision.name} already exists in this project.</p>
            <button type="button" className="ghost" data-testid="prop-creator-open-existing" onClick={() => void pc.selectProp(pc.nameCollision!.id)}>
              Open Existing
            </button>
            <button type="button" className="ghost" data-testid="prop-creator-choose-name" onClick={() => pc.setName("")}>
              Choose Another Name
            </button>
          </div>
        ) : null}
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
      <GlobalScopeField
        testId="prop-creator-global"
        checked={pc.isGlobal}
        onChange={pc.setIsGlobal}
        helpText={PROP_GLOBAL_SCOPE_HELP}
      />
    </div>
  );
}

function DescriptionBlock({ pc }: { pc: ReturnType<typeof usePropCreator> }) {
  return (
    <div>
      <textarea
        className="prop-creator-core__prompt"
        data-testid="prop-creator-description"
        value={pc.description}
        onChange={(e) => pc.setDescription(e.target.value)}
        placeholder="What is this prop? Shape, material, color, important details."
        aria-label="Description"
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
    <div className="character-core__reference" data-testid="prop-creator-reference">
      {refId ? (
        <div className="character-core__reference-preview">
          <img src={api.assetUrl(refId)} alt="Prop reference" data-testid="prop-creator-reference-thumb" />
        </div>
      ) : null}
      <div className="character-core__reference-actions">
        <button
          type="button"
          className="character-core__button"
          data-testid="prop-creator-reference-library"
          onClick={() => setPickerOpen(true)}
        >
          {refId ? "Change from Library" : "Add from Library"}
        </button>
        <button
          type="button"
          className="character-core__button"
          data-testid="prop-creator-reference-upload"
          onClick={() => fileRef.current?.click()}
        >
          Upload
        </button>
        {refId ? (
          <button
            type="button"
            className="character-core__button"
            data-testid="prop-creator-reference-remove"
            onClick={() => void pc.setReference(null)}
          >
            Remove
          </button>
        ) : null}
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
        sectionLabel=""
        testId="prop-generator-panel"
        value={pc.plan}
        onChange={pc.setPlan}
      />
    </div>
  );
}

function ActionsBlock({
  pc,
}: {
  pc: ReturnType<typeof usePropCreator>;
}) {
  const { t } = useTranslation(["propCreator", "common"]);
  const lookFileRef = useRef<HTMLInputElement>(null);
  const progress = plannedProgress(pc.prop?.candidates || [], plannedCandidateCount(pc.plan));
  const blockReason = propGenerateBlockReason({
    name: pc.name,
    plan: pc.plan,
    busy: false,
  });
  const canGenerate = !blockReason && !pc.busy;
  const showProgress = true; // ORDER 16: always show idle standing-by vs generating title
  return (
    <div className="character-core__generate">
      {showProgress ? (
        <div className="character-core__progress" data-testid="prop-creator-progress">
          <div className="character-core__progress-head">
            <span className="character-core__progress-title" data-testid="prop-creator-progress-title">
              {pc.generating ? "Generating Prop Images" : "Prop Creator Generator ready/standing by"}
            </span>
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
        <button
          type="button"
          className="ghost"
          data-testid="prop-creator-upload-look"
          disabled={pc.busy || !pc.name.trim()}
          onClick={() => lookFileRef.current?.click()}
        >
          Upload
        </button>
        <input
          ref={lookFileRef}
          type="file"
          accept="image/png,image/jpeg,image/webp,image/gif,image/bmp,image/tiff,.png,.jpg,.jpeg,.webp,.gif,.bmp,.tif,.tiff"
          hidden
          data-testid="prop-creator-upload-look-input"
          onChange={(e) => {
            const file = e.target.files?.[0];
            e.target.value = "";
            if (file) void pc.uploadLook(file);
          }}
        />
        <button type="button" className="ghost" data-testid="prop-creator-save" disabled={pc.busy || !pc.name.trim()} onClick={() => void pc.save()}>
          {t("propCreator:save")}
        </button>
        <button type="button" className="ghost" data-testid="prop-creator-reset" onClick={() => pc.reset()}>
          Reset
        </button>
      </div>
      {blockReason ? (
        <p className="character-core__hint" data-testid="prop-creator-generate-reason">
          {blockReason}
        </p>
      ) : null}
      {pc.uploadError ? (
        <p className="prop-creator-core__error" role="alert" data-testid="prop-creator-upload-error">
          {pc.uploadError}
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
      <p>Placements: {usage ? `${usage.spatial} placement${usage.spatial === 1 ? "" : "s"}` : "…"}</p>
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
  const [prsOpen, setPrsOpen] = useState(false);
  const prsAssetId = String(pc.prop?.prs_asset_id || pc.prop?.prsAssetId || "").trim();
  const prsTag = promptCanonicalPropTag(pc.prop);

  if (!candidates.length) return null;
  return (
    <>
    <div className="prop-creator-core__candidates" data-testid="prop-creator-result-grid">
      {candidates.map((cand) => {
        const approved = cand.asset_id && cand.asset_id === pc.prop?.approved_asset_id;
        const statusLabel = candidateStatusLabel(cand.status);
        const failed = candidateIsFailed(cand);
        const failMessage = failed ? candidateErrorMessage(cand) : "";
        const canOpenPrs = Boolean(approved && prsAssetId);
        return (
          <article
            key={cand.id}
            className={approved ? "prop-creator-core__card is-approved" : "prop-creator-core__card"}
            data-testid="prop-creator-result-card"
            data-status={cand.status}
          >
            <div className="prop-creator-core__thumb">
              {candidateHasValidAsset(cand) ? (
                <PropAssetPreview
                  assetId={cand.asset_id!}
                  projectId={pc.projectId}
                  alt={cand.take_label}
                  testId="prop-creator-result-image"
                  unavailableLabel="Look unavailable"
                  onClick={canOpenPrs ? () => setPrsOpen(true) : undefined}
                  clickableHint={canOpenPrs ? "Open Prop Reference Sheet" : undefined}
                />
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
              <span className="muted">
                {cand.origin === "uploaded" ? "Uploaded" : cand.provenance_label}
              </span>
              <span className="muted" data-testid="prop-creator-result-status">{statusLabel}</span>
              {candidateHasValidAsset(cand) ? (
                <button
                  type="button"
                  className="character-core__button primary"
                  data-testid="prop-creator-approve"
                  disabled={pc.busy}
                  onClick={() => void pc.approve(cand.id)}
                >
                  {approved ? "Using This Prop" : "Use This Prop"}
                </button>
              ) : null}
              {candidateHasValidAsset(cand) && approved ? (
                <button
                  type="button"
                  className="character-core__button"
                  data-testid="prop-creator-create-prs"
                  disabled={pc.busy}
                  onClick={() => void pc.composeReferenceSheet()}
                >
                  {prsAssetId ? "Regenerate Prop Reference Sheet" : "Create Prop Reference Sheet"}
                </button>
              ) : null}
              {prsAssetId && approved ? (
                <div className="prop-creator-core__tag-row" data-testid="prop-creator-prs-tag">
                  <code>{prsTag}</code>
                  <button
                    type="button"
                    className="character-core__button"
                    data-testid="prop-creator-copy-tag"
                    onClick={() => {
                      if (prsTag) void navigator.clipboard.writeText(prsTag);
                    }}
                  >
                    Copy %tag
                  </button>
                </div>
              ) : null}
              {candidateHasValidAsset(cand) ? (
                <button
                  type="button"
                  className="character-core__button"
                  data-testid="prop-creator-save-image"
                  onClick={() => {
                    const url = api.assetUrl(cand.asset_id!, undefined, pc.projectId);
                    window.open(url, "_blank", "noopener,noreferrer");
                  }}
                >
                  Save Image
                </button>
              ) : null}
              {failed ? (
                <button
                  type="button"
                  className="character-core__button"
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
    <PropReferenceSheetModal
      open={prsOpen}
      assetId={prsAssetId}
      projectId={pc.projectId}
      title={prsTag ? `Prop Reference Sheet · ${prsTag}` : "Prop Reference Sheet"}
      onClose={() => setPrsOpen(false)}
    />
    </>
  );
}

