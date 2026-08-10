import { useEffect, useState } from "react";
import { api } from "../api";
import { StudioChrome } from "./dashboard/StudioChrome";

type Entry = {
  id: string;
  source: string;
  sourceKey: string;
  displayName: string;
  classification: string;
  installAction: string | null;
};

export default function ModelRadarWorkspace() {
  const [enabled, setEnabled] = useState<boolean | null>(null);
  const [entries, setEntries] = useState<Entry[]>([]);
  const [selected, setSelected] = useState<string>("");
  const [compat, setCompat] = useState<Record<string, unknown> | null>(null);
  const [sandboxId, setSandboxId] = useState<string>("");
  const [planId, setPlanId] = useState<string>("");
  const [planStatus, setPlanStatus] = useState<string>("");
  const [msg, setMsg] = useState<string>("");
  const [projectId, setProjectId] = useState<string>("");

  useEffect(() => {
    let cancelled = false;
    (async () => {
      const health = await api.health();
      if (cancelled) return;
      const on = Boolean(health?.operator?.modelRadarEnabled);
      setEnabled(on);
      if (!on) return;
      const reg = await api.m28RadarRegistry();
      if (!cancelled) setEntries(reg.entries || []);
    })().catch((e) => setMsg(String(e)));
    return () => {
      cancelled = true;
    };
  }, []);

  if (enabled === null) {
    return (
      <div className="app-shell atmosphere" data-testid="model-radar-loading">
        <StudioChrome variant="home" />
        <div className="page">Loading…</div>
      </div>
    );
  }
  if (!enabled) {
    return (
      <div className="app-shell atmosphere" data-testid="model-radar-unavailable">
        <StudioChrome variant="home" />
        <div className="page">
          <h1 className="ds-type-h1">Model Radar unavailable</h1>
          <p className="ds-type-helper">Enable STUDIO_FEATURE_MODEL_RADAR_V1 to use this workspace.</p>
        </div>
      </div>
    );
  }

  const refresh = async () => {
    const reg = await api.m28RadarRegistry();
    setEntries(reg.entries || []);
  };

  return (
    <div className="app-shell atmosphere" data-testid="model-radar-page">
      <StudioChrome
        variant="home"
        breadcrumbs={[{ label: "Home" }, { label: "Tools" }, { label: "Model Radar" }]}
      />
      <div className="page model-radar-page">
      <h1 className="ds-type-h1">Model Radar</h1>
      <p className="ds-type-helper">Discover, classify, evaluate, and sandbox models (fixture-capable).</p>
      <div className="row" style={{ gap: 8, flexWrap: "wrap" }}>
        <button
          type="button"
          data-testid="discovery-hf-btn"
          onClick={async () => {
            await api.m28RadarDiscover("huggingface");
            await refresh();
            setMsg("HF discovery complete");
          }}
        >
          Discover Hugging Face
        </button>
        <button
          type="button"
          data-testid="discovery-gh-btn"
          onClick={async () => {
            await api.m28RadarDiscover("github");
            await refresh();
            setMsg("GitHub discovery complete");
          }}
        >
          Discover GitHub
        </button>
        <input
          data-testid="project-id-input"
          placeholder="Project ID for approve"
          value={projectId}
          onChange={(e) => setProjectId(e.target.value)}
        />
      </div>

      <section style={{ marginTop: 16 }}>
        <h2>Registry</h2>
        <ul data-testid="registry-list">
          {entries.map((e) => (
            <li key={e.id} data-testid={`registry-item-${e.id}`}>
              <label>
                <input
                  type="radio"
                  name="entry"
                  checked={selected === e.id}
                  onChange={() => setSelected(e.id)}
                />{" "}
                {e.displayName} · {e.classification}
                {e.installAction ? "" : " · no install"}
              </label>
            </li>
          ))}
        </ul>
      </section>

      <div className="row" style={{ gap: 8, flexWrap: "wrap", marginTop: 12 }}>
        <button
          type="button"
          data-testid="watchlist-add"
          disabled={!selected}
          onClick={async () => {
            await api.m28WatchlistAdd(selected, projectId || undefined);
            setMsg("Added to watchlist");
          }}
        >
          Add to watchlist
        </button>
        <button
          type="button"
          data-testid="compat-run"
          disabled={!selected}
          onClick={async () => {
            const res = await api.m28CompatEvaluate(selected);
            setCompat(res);
            setMsg(`Compat: ${res.verdict}`);
          }}
        >
          Evaluate compatibility
        </button>
        <button
          type="button"
          data-testid="sandbox-create"
          onClick={async () => {
            const sb = await api.m28SandboxCreate("Radar Sandbox");
            setSandboxId(sb.id);
            setMsg(`Sandbox ${sb.id}`);
          }}
        >
          Create sandbox
        </button>
        <button
          type="button"
          data-testid="sandbox-plan"
          disabled={!sandboxId || !selected}
          onClick={async () => {
            const plan = await api.m28SandboxPlan(sandboxId, selected);
            setPlanId(plan.id);
            setPlanStatus(plan.status);
            setMsg(`Plan ${plan.id} ${plan.status}`);
          }}
        >
          Generate plan
        </button>
        <button
          type="button"
          data-testid="sandbox-reject"
          disabled={!planId}
          onClick={async () => {
            const plan = await api.m28SandboxPlanReject(planId);
            setPlanStatus(plan.status);
            setMsg("Plan rejected");
          }}
        >
          Reject plan
        </button>
        <button
          type="button"
          data-testid="sandbox-approve"
          disabled={!planId || !projectId}
          onClick={async () => {
            const plan = await api.m28SandboxPlanApprove(planId, projectId);
            setPlanStatus(plan.status);
            setMsg(`Plan approved job=${plan.job?.id || ""}`);
          }}
        >
          Approve plan
        </button>
      </div>

      {compat && (
        <pre data-testid="compat-result">{JSON.stringify(compat, null, 2)}</pre>
      )}
      <p data-testid="radar-status">
        sandbox={sandboxId || "none"} plan={planId || "none"} status={planStatus || "n/a"}
      </p>
      {msg && <p data-testid="radar-msg">{msg}</p>}

      <SandboxPanel sandboxId={sandboxId} projectId={projectId} />
      <ShotProfilePanel projectId={projectId} />
      <RecipePanel projectId={projectId} />
      </div>
    </div>
  );
}

function SandboxPanel({ sandboxId, projectId }: { sandboxId: string; projectId: string }) {
  const [info, setInfo] = useState<string>("");
  if (!sandboxId) return null;
  return (
    <section data-testid="sandbox-panel" style={{ marginTop: 24 }}>
      <h2>Sandbox</h2>
      <div className="row" style={{ gap: 8, flexWrap: "wrap" }}>
        <button type="button" data-testid="sandbox-start" onClick={async () => {
          await api.m28SandboxStart(sandboxId); setInfo("started");
        }}>Start</button>
        <button type="button" data-testid="sandbox-health" onClick={async () => {
          const h = await api.m28SandboxHealth(sandboxId); setInfo(JSON.stringify(h));
        }}>Health</button>
        <button type="button" data-testid="sandbox-detect" onClick={async () => {
          const d = await api.m28SandboxDetect(sandboxId); setInfo(JSON.stringify(d));
        }}>Detect</button>
        <button type="button" data-testid="sandbox-validate" onClick={async () => {
          const v = await api.m28SandboxValidate(sandboxId); setInfo(JSON.stringify(v));
        }}>Validate</button>
        <button type="button" data-testid="sandbox-stop" onClick={async () => {
          await api.m28SandboxStop(sandboxId); setInfo("stopped");
        }}>Stop</button>
        <button type="button" data-testid="sandbox-restart" onClick={async () => {
          await api.m28SandboxRestart(sandboxId); setInfo("restarted");
        }}>Restart</button>
        <button type="button" data-testid="sandbox-remove" onClick={async () => {
          const r = await api.m28SandboxRemove(sandboxId); setInfo(JSON.stringify(r));
        }}>Remove</button>
        <button type="button" data-testid="promote-create" onClick={async () => {
          const p = await api.m28PromoteCreate(sandboxId); setInfo(`promote:${p.id}:${p.status}`);
          (window as unknown as { __m28PromoteId?: string }).__m28PromoteId = p.id;
        }}>Promotion proposal</button>
        <button type="button" data-testid="promote-reject" onClick={async () => {
          const id = (window as unknown as { __m28PromoteId?: string }).__m28PromoteId;
          if (!id) return;
          const p = await api.m28PromoteReject(id); setInfo(`rejected:${p.status}`);
        }}>Reject promote</button>
        <button type="button" data-testid="promote-approve" disabled={!projectId} onClick={async () => {
          const id = (window as unknown as { __m28PromoteId?: string }).__m28PromoteId;
          if (!id) return;
          const p = await api.m28PromoteApprove(id, projectId); setInfo(`approved:${p.status}`);
        }}>Approve promote</button>
      </div>
      <pre data-testid="sandbox-info">{info}</pre>
    </section>
  );
}

function ShotProfilePanel({ projectId }: { projectId: string }) {
  const [profileId, setProfileId] = useState("");
  const [mode, setMode] = useState<"guided" | "professional">("guided");
  if (!projectId) return null;
  return (
    <section data-testid="shot-profile-panel" style={{ marginTop: 24 }}>
      <h2>Shot Profile</h2>
      <div className="row" style={{ gap: 8, flexWrap: "wrap" }}>
        <button type="button" data-testid="shot-profile-create" onClick={async () => {
          const p = await api.m28ShotProfileCreate(projectId, "E2E Profile");
          setProfileId(p.id);
        }}>Create</button>
        <button type="button" data-testid="shot-profile-save" disabled={!profileId} onClick={async () => {
          await api.m28ShotProfileSave(profileId, {
            lighting: { template: "soft_key", key: 0.8, fill: 0.3, rim: 0.2, intensity: 0.9, temperature: 5200, softness: 0.5 },
            atmosphere: { blueHaze: 0.2 },
            grade: { template: "neutral", contrast: 0.15, saturation: 0.05 },
          }, mode);
        }}>Save</button>
        <button type="button" data-testid="shot-profile-mode-guided" onClick={() => setMode("guided")}>Guided</button>
        <button type="button" data-testid="shot-profile-mode-pro" onClick={() => setMode("professional")}>Professional</button>
        <button type="button" data-testid="shot-profile-depth" disabled={!profileId} onClick={async () => {
          await api.m28ShotProfileDepth(profileId, [
            { id: "s1", camera: { distance: 2.5 } },
            { id: "s2", camera: { elevation: 10 } },
          ], ["s1"]);
        }}>Apply selected depth</button>
        <button type="button" data-testid="shot-profile-associate" disabled={!profileId} onClick={async () => {
          await api.m28ShotProfileAssociate(profileId, "sb-shot-1", "tl-item-1");
        }}>Associate</button>
        <button type="button" data-testid="recipe-run-from-profile" disabled={!profileId} onClick={async () => {
          const r = await api.m28RecipeCreate(projectId, "From profile");
          await api.m28RecipeRun(r.id);
        }}>Run recipe</button>
      </div>
      <p data-testid="shot-profile-id">{profileId || "none"}</p>
    </section>
  );
}

function RecipePanel({ projectId }: { projectId: string }) {
  const [recipeId, setRecipeId] = useState("");
  if (!projectId) return null;
  return (
    <section data-testid="recipe-panel" style={{ marginTop: 24 }}>
      <h2>Production Recipe</h2>
      <button type="button" data-testid="recipe-run" onClick={async () => {
        const r = await api.m28RecipeCreate(projectId, "E2E Recipe");
        setRecipeId(r.id);
        await api.m28RecipeRun(r.id);
      }}>Run recipe</button>
      <p data-testid="recipe-id">{recipeId || "none"}</p>
    </section>
  );
}
