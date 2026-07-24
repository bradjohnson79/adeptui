import { useState } from "react";
import { DEFAULT_POLICIES, type ActionCategory, type PermissionPolicy } from "../../codirector/types";
import { useCoDirectorSession } from "./CoDirectorSession";
import type { PromptMode } from "./types";

export function CoDirectorOverflowMenu() {
  const {
    overflowPanel,
    setOverflowPanel,
    promptMode,
    setPromptMode,
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
  } = useCoDirectorSession();
  const [testing, setTesting] = useState(false);

  if (overflowPanel === "none") return null;

  return (
    <div className="codirector-overflow" role="menu" aria-label="Co-Director options">
      <div className="codirector-overflow-nav">
        {(
          [
            ["options", "Options"],
            ["provider", "Model"],
            ["knowledge", "Knowledge"],
            ["access", "Access"],
            ["audit", "Audit"],
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
          <div className="codirector-filter-chips">
            {(["creative", "structured", "model", "advanced"] as PromptMode[]).map((mode) => (
              <button
                key={mode}
                type="button"
                className={promptMode === mode ? "primary" : ""}
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
            Include project knowledge
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
        </div>
      )}

      {overflowPanel === "provider" && (
        <div className="codirector-overflow-body">
          <p className="eyebrow">Model & provider</p>
          <p>
            {providerStatus}
            {providerHealth?.reachable ? " ✓" : ""}
          </p>
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
