import { useState } from "react";
import { DEFAULT_POLICIES, type ActionCategory, type PermissionPolicy } from "../../codirector/types";
import { useCoDirectorSession } from "./CoDirectorSession";
import { PromptIntelligencePanel } from "./PromptIntelligencePanel";
import { PromptIntelligenceBenchmarkDashboard } from "./PromptIntelligenceBenchmarkDashboard";
import { CoDirectorStatusPanel } from "./CoDirectorStatusPanel";
import { CoDirectorInitiativeDial } from "./CoDirectorInitiativeDial";
import type { CollaborationMode, CoDirectorActivityPreference, PromptMode } from "./types";

const COLLABORATION_MODES: { id: CollaborationMode; label: string }[] = [
  { id: "explore", label: "Explore" },
  { id: "critique", label: "Critique" },
  { id: "compare", label: "Compare" },
  { id: "refine", label: "Refine" },
  { id: "decide", label: "Decide" },
  { id: "review", label: "Review" },
  { id: "execute", label: "Execute" },
  { id: "teach", label: "Teach" },
];

function loadCollaborationMode(): CollaborationMode {
  try {
    const raw = window.localStorage.getItem("codirector.collaborationMode");
    if (COLLABORATION_MODES.some((mode) => mode.id === raw)) {
      return raw as CollaborationMode;
    }
  } catch {
    /* ignore */
  }
  return "explore";
}

export function CoDirectorOverflowMenu() {
  const {
    overflowPanel,
    setOverflowPanel,
    promptMode,
    setPromptMode,
    activityPreference,
    setActivityPreference,
    uiContext,
    includeProjectKnowledge,
    setIncludeProjectKnowledge,
    compilePrompt,
    busy,
    providerStatus,
    providerModel,
    providerHealth,
    selectedModelId,
    setSelectedModelId,
    refreshProviderHealth,
    reconnect,
    showReconnectAction,
    runtimeState,
    runtimeChip,
    clearConversation,
    expandToFullScreen,
    displayMode,
    policies,
    setPolicies,
    kbModels,
    kbDoc,
    loadKnowledge,
    loadKnowledgeDoc,
    audit,
    refreshAudit,
    plan,
    openStatusPanel,
  } = useCoDirectorSession();
  const [testing, setTesting] = useState(false);
  const [collaborationMode, setCollaborationMode] = useState<CollaborationMode>(() => loadCollaborationMode());
  const projectTypeLabel = uiContext?.primaryProjectType?.replace(/_/g, " ") || "custom";

  if (overflowPanel === "none") return null;

  return (
    <div
      id="codirector-overflow-panel"
      className="codirector-overflow"
      role="region"
      aria-label="Co-Director options"
      data-testid="codirector-overflow-panel"
    >
      <div className="codirector-overflow-nav">
        {(
          [
            ["options", "Options"],
            ["provider", "Model"],
            ["promptBench", "PI Benchmarks"],
            ["knowledge", "Knowledge"],
            ["access", "Access"],
            ["audit", "Audit"],
            ["status", "Status"],
            ...(plan ? [["plan", "Active plan"] as const] : []),
          ] as const
        ).map(([id, label]) => (
          <button
            key={id}
            type="button"
            className={overflowPanel === id ? "primary" : "ghost"}
            onClick={() => {
              setOverflowPanel(id);
              if (id === "knowledge") void loadKnowledge();
              if (id === "audit") refreshAudit();
              if (id === "status") void openStatusPanel();
            }}
          >
            {label}
          </button>
        ))}
        <button type="button" className="ghost" onClick={() => setOverflowPanel("none")}>
          Close
        </button>
      </div>

      {overflowPanel === "options" && (
        <div className="codirector-overflow-body">
          <p className="eyebrow">Response style</p>
          <div className="codirector-filter-chips" role="group" aria-label="Response style">
            {(["creative", "structured", "model", "advanced"] as PromptMode[]).map((mode) => (
              <button
                key={mode}
                type="button"
                className={promptMode === mode ? "primary is-active" : ""}
                aria-pressed={promptMode === mode}
                onClick={() => setPromptMode(mode)}
              >
                {mode}
              </button>
            ))}
          </div>
          <label className="codirector-check">
            <input
              type="checkbox"
              checked={includeProjectKnowledge}
              onChange={(e) => setIncludeProjectKnowledge(e.target.checked)}
            />
            <span>Include project knowledge</span>
          </label>
          <CoDirectorInitiativeDial compact />
          <p className="eyebrow" style={{ marginTop: "0.85rem" }}>
            Working style
          </p>
          <p className="muted" style={{ margin: "0 0 0.4rem", fontSize: "0.85rem" }}>
            Project format: <strong data-testid="codirector-domain-badge">{projectTypeLabel}</strong>
          </p>
          <div className="codirector-filter-chips" role="group" aria-label="Working style">
            {COLLABORATION_MODES.map((mode) => (
              <button
                key={mode.id}
                type="button"
                className={collaborationMode === mode.id ? "primary is-active" : ""}
                aria-pressed={collaborationMode === mode.id}
                data-testid={`codirector-collab-mode-${mode.id}`}
                onClick={() => {
                  setCollaborationMode(mode.id);
                  try {
                    window.localStorage.setItem("codirector.collaborationMode", mode.id);
                  } catch {
                    /* ignore */
                  }
                }}
              >
                {mode.label}
              </button>
            ))}
          </div>
          <label
            className="codirector-check"
            style={{ flexDirection: "column", alignItems: "flex-start", gap: "0.3rem" }}
          >
            <span>Show Co-Director Activity</span>
            <select
              value={activityPreference}
              onChange={(e) => setActivityPreference(e.target.value as CoDirectorActivityPreference)}
            >
              <option value="always">Always</option>
              <option value="longer_tasks">Only for longer tasks</option>
              <option value="hidden">Hidden</option>
            </select>
          </label>
          <div className="row-actions">
            <button type="button" disabled={busy} onClick={() => void compilePrompt()}>
              Compile prompt
            </button>
            <button
              type="button"
              onClick={() => {
                if (window.confirm("Clear this conversation? This cannot be undone.")) {
                  clearConversation();
                }
              }}
            >
              Clear conversation
            </button>
            {displayMode === "popup" && (
              <button type="button" onClick={() => expandToFullScreen()}>
                Open full screen
              </button>
            )}
          </div>
          <PromptIntelligencePanel
            creatorPrompt=""
            domain="video"
            compact
            onApply={({ finalProviderPrompt }) => {
              // Soft handoff: copy into clipboard-friendly toast via alert when no host bind.
              window.dispatchEvent(
                new CustomEvent("adept-prompt-intelligence-apply", {
                  detail: { finalProviderPrompt },
                }),
              );
            }}
          />
          <p className="muted" style={{ fontSize: "0.72rem" }}>
            Open Timeline / Image / Video / Audio generators and use Prompt Intelligence there with the active prompt, or paste a prompt into those panels after Preview.
          </p>
        </div>
      )}

      {overflowPanel === "promptBench" && (
        <div className="codirector-overflow-body" data-testid="codirector-prompt-bench-overflow">
          <PromptIntelligenceBenchmarkDashboard />
        </div>
      )}

      {overflowPanel === "provider" && (
        <div className="codirector-overflow-body">
          <p className="eyebrow">Model & provider</p>
          <p data-testid="codirector-runtime-status">
            {runtimeChip || providerStatus}
            {providerHealth?.reachable ? " ✓" : ""}
          </p>
          <p className="muted">State: {runtimeState}</p>
          {(providerHealth?.testOnly || providerHealth?.honesty === "mocked") && (
            <p className="muted" data-testid="codirector-test-only-provider">
              Test-only mock provider — not a production connection.
            </p>
          )}
          {providerHealth?.endpoint && <p className="muted">Endpoint: {providerHealth.endpoint}</p>}
          {providerModel && <p className="muted">Active model: {providerModel}</p>}
          {!providerHealth?.reachable && providerHealth?.message && (
            <p className="muted">{providerHealth.message}</p>
          )}
          {!!providerHealth?.models?.length && (
            <label className="codirector-check" style={{ flexDirection: "column", alignItems: "flex-start", gap: "0.3rem" }}>
              Model
              <select
                value={selectedModelId || providerHealth.selectedModel || ""}
                onChange={(e) => setSelectedModelId(e.target.value || null)}
                data-testid="codirector-model-select"
              >
                {providerHealth.models.map((m) => (
                  <option key={m.id} value={m.id}>
                    {m.name || m.id}
                  </option>
                ))}
              </select>
            </label>
          )}
          <div className="row-actions">
            <button
              type="button"
              disabled={testing}
              onClick={async () => {
                setTesting(true);
                try {
                  await refreshProviderHealth();
                } finally {
                  setTesting(false);
                }
              }}
            >
              {testing ? "Testing…" : "Refresh / Test"}
            </button>
            {showReconnectAction ? (
              <button type="button" data-testid="codirector-reconnect-options" onClick={() => void reconnect()}>
                Reconnect
              </button>
            ) : null}
          </div>
        </div>
      )}

      {overflowPanel === "knowledge" && (
        <div className="codirector-overflow-body">
          <p className="eyebrow">Prompt Knowledge</p>
          <p className="muted">Models, camera, motion, negatives — retrieved by compile.</p>
          {!kbModels.length ? (
            <p className="scene-meta">No models loaded.</p>
          ) : (
            kbModels.map((m) => (
              <button key={m.id} type="button" onClick={() => void loadKnowledgeDoc(m.id)}>
                {m.label || m.id}
              </button>
            ))
          )}
          {kbDoc && <pre className="explain-panel">{kbDoc}</pre>}
        </div>
      )}

      {overflowPanel === "access" && (
        <div className="codirector-overflow-body">
          <p className="eyebrow">Permission policies</p>
          {(Object.keys(DEFAULT_POLICIES) as ActionCategory[]).map((cat) => (
            <div key={cat} className="permission-row">
              <span>{cat}</span>
              <select
                value={policies[cat]}
                onChange={(e) => {
                  const next = { ...policies, [cat]: e.target.value as PermissionPolicy };
                  setPolicies(next);
                }}
              >
                <option value="always_allow">Always allow</option>
                <option value="ask_once">Ask once</option>
                <option value="always_ask">Always ask</option>
                <option value="never">Never</option>
              </select>
            </div>
          ))}
        </div>
      )}

      {overflowPanel === "audit" && (
        <ul className="activity-feed codirector-overflow-body">
          {!audit.length && <li className="muted">No Co-Director actions yet.</li>}
          {audit.map((a) => (
            <li key={a.id}>
              <span className="scene-meta">{new Date(a.at).toLocaleString()}</span>
              <span>
                {a.ok ? "✓" : "✗"} {a.label} {a.detail ? `— ${a.detail}` : ""}
              </span>
            </li>
          ))}
        </ul>
      )}

      {overflowPanel === "status" && <CoDirectorStatusPanel />}

      {overflowPanel === "plan" && plan && (
        <div className="codirector-overflow-body">
          <p className="eyebrow">Active plan</p>
          <p>
            <strong>{plan.title}</strong>
          </p>
          <p className="muted">{plan.intention}</p>
          <p className="muted">Use the inline plan controls in the conversation to approve or run steps.</p>
        </div>
      )}
    </div>
  );
}
