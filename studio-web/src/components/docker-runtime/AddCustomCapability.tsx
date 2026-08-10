import { useMemo, useState } from "react";
import { api } from "../../api";
import type { AddCustomCapabilitySource, RuntimeInstallationPlan } from "../../dockerRuntime/contracts";

const SOURCES: { id: AddCustomCapabilitySource; label: string }[] = [
  { id: "import_image", label: "Import Image" },
  { id: "compose", label: "Compose" },
  { id: "adept_package", label: "Adept Package" },
  { id: "comfy_workflow", label: "Build from Comfy Workflow" },
  { id: "register_existing", label: "Register Existing" },
];

const STAGES = [
  "Source",
  "Inspect",
  "Security",
  "Mapping",
  "Plan",
  "Validate",
  "Register",
] as const;

export function AddCustomCapability({ onRegistered }: { onRegistered?: () => void }) {
  const [source, setSource] = useState<AddCustomCapabilitySource>("import_image");
  const [stage, setStage] = useState(0);
  const [image, setImage] = useState("library/adept-custom-runtime:1.0.0");
  const [name, setName] = useState("Custom Runtime");
  const [workflowJson, setWorkflowJson] = useState('{"nodes":{}}');
  const [inspect, setInspect] = useState<Record<string, unknown> | null>(null);
  const [plan, setPlan] = useState<RuntimeInstallationPlan | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const canAdvance = useMemo(() => stage < STAGES.length - 1, [stage]);

  async function runInspect() {
    setBusy(true);
    setMessage(null);
    try {
      if (source === "comfy_workflow") {
        const wf = JSON.parse(workflowJson) as Record<string, unknown>;
        const report = await api.dockerRuntime.workflowInspect(wf);
        setInspect(report);
        if (report.mutatesCoreComfy) {
          setMessage("Blocked: workflow import must not mutate core Comfy.");
          return;
        }
      } else {
        setInspect({
          source,
          image,
          name,
          note: "Image/package will be validated by backend security policy.",
        });
      }
      setStage(1);
    } catch (e) {
      setMessage(e instanceof Error ? e.message : "Inspect failed");
    } finally {
      setBusy(false);
    }
  }

  async function runSecurityAndPlan() {
    setBusy(true);
    setMessage(null);
    try {
      const preview = await api.dockerRuntime.installPreview({ image, name, modality: "video" });
      setPlan(preview.plan);
      if (!preview.plan.security.ok) {
        setMessage(`Security blocked: ${preview.plan.security.blocked.join(", ")}`);
        setStage(2);
        return;
      }
      setStage(4);
    } catch (e) {
      setMessage(e instanceof Error ? e.message : "Plan failed");
    } finally {
      setBusy(false);
    }
  }

  async function register() {
    setBusy(true);
    setMessage(null);
    try {
      const result = await api.dockerRuntime.install({ image, name, modality: "video" });
      if (!result.ok || !result.result) {
        setMessage(result.error || "Install failed");
        return;
      }
      setStage(6);
      setMessage("Registered as user_added Docker Local — never auto-Certified.");
      onRegistered?.();
    } catch (e) {
      setMessage(e instanceof Error ? e.message : "Register failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="setup-component-section" data-testid="add-custom-capability" aria-labelledby="add-custom-capability-heading">
      <div className="setup-section-heading">
        <div>
          <h2 id="add-custom-capability-heading">Add Custom Capability</h2>
          <p>Isolated Docker runtimes only — never mutates core Comfy or certified model roots.</p>
        </div>
        <span>
          Stage {stage + 1}/{STAGES.length}: {STAGES[stage]}
        </span>
      </div>

      <ol className="setup-nav-strip" aria-label="Install stages">
        {STAGES.map((label, i) => (
          <li key={label} style={{ opacity: i === stage ? 1 : 0.55 }}>
            {i + 1}. {label}
          </li>
        ))}
      </ol>

      <div className="panel" style={{ display: "grid", gap: "0.75rem" }}>
        <label>
          Source
          <select
            data-testid="custom-capability-source"
            value={source}
            onChange={(e) => {
              setSource(e.target.value as AddCustomCapabilitySource);
              setStage(0);
            }}
          >
            {SOURCES.map((s) => (
              <option key={s.id} value={s.id}>
                {s.label}
              </option>
            ))}
          </select>
        </label>

        {source !== "comfy_workflow" ? (
          <>
            <label>
              Image (pinned tag required)
              <input data-testid="custom-capability-image" value={image} onChange={(e) => setImage(e.target.value)} />
            </label>
            <label>
              Display name
              <input data-testid="custom-capability-name" value={name} onChange={(e) => setName(e.target.value)} />
            </label>
          </>
        ) : (
          <label>
            Comfy workflow JSON
            <textarea
              data-testid="custom-capability-workflow"
              rows={8}
              value={workflowJson}
              onChange={(e) => setWorkflowJson(e.target.value)}
            />
          </label>
        )}

        <div style={{ display: "flex", gap: "0.5rem", flexWrap: "wrap" }}>
          <button type="button" disabled={busy} onClick={() => void runInspect()} data-testid="custom-capability-inspect">
            Inspect
          </button>
          <button type="button" disabled={busy || stage < 1} onClick={() => void runSecurityAndPlan()} data-testid="custom-capability-plan">
            Security + Plan
          </button>
          <button type="button" disabled={busy || !plan?.security.ok} onClick={() => void register()} data-testid="custom-capability-register">
            Validate & Register
          </button>
          {canAdvance ? (
            <button type="button" disabled={busy} onClick={() => setStage((s) => Math.min(s + 1, STAGES.length - 1))}>
              Next stage
            </button>
          ) : null}
        </div>

        {inspect ? (
          <pre data-testid="custom-capability-inspect-result" style={{ whiteSpace: "pre-wrap", fontSize: "0.85rem" }}>
            {JSON.stringify(inspect, null, 2)}
          </pre>
        ) : null}
        {plan ? (
          <pre data-testid="custom-capability-plan-result" style={{ whiteSpace: "pre-wrap", fontSize: "0.85rem" }}>
            {JSON.stringify(plan, null, 2)}
          </pre>
        ) : null}
        {message ? (
          <p className="setup-message" role="status" data-testid="custom-capability-message">
            {message}
          </p>
        ) : null}
      </div>
    </section>
  );
}
