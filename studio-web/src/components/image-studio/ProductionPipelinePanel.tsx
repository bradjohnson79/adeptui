import { useMemo, useState } from "react";
import { api } from "../../api";
import type {
  ImageGenerationPlan,
  ImagePipelineCandidateGroup,
  ImagePipelineDeploymentPreference,
  ImagePipelineQualityProfile,
  ProductionImageRequest,
} from "../../contracts/imagePipeline";
import { COLOR_GRADE_OPTIONS, DEFAULT_COLOR_GRADE, type ColorGradePresetId } from "../../contracts/colorGrades";

function qualityLabel(value: ImagePipelineQualityProfile): string {
  switch (value) {
    case "quick":
      return "Quick";
    case "enhanced":
      return "Enhanced";
    case "cinematic":
      return "Cinematic";
    case "studio-master":
      return "Studio Master";
    default:
      return value;
  }
}

function stagingLabel(value: string): string {
  switch (value) {
    case "poseCraft":
      return "Pose Guide";
    case "spatialMap":
      return "Scene Layout";
    default:
      return "Direct Render";
  }
}

function stagingTip(value: string): string {
  switch (value) {
    case "poseCraft":
      return "Use a pose guide first so character blocking stays readable before rendering.";
    case "spatialMap":
      return "Use scene layout guidance first so geography and camera clarity stay consistent.";
    default:
      return "This shot can go straight to image generation without extra staging help.";
  }
}

function readinessLabel(value: string): string {
  if (value === "ready") return "Ready";
  if (value === "blocked") return "Blocked";
  return "Needs Review";
}

type ProductionPipelinePanelProps = {
  projectId: string;
  prompt: string;
  purpose: string;
  referenceAssetIds: string[];
  deploymentPreference: ImagePipelineDeploymentPreference;
  allowApiDeployment: boolean;
  spatialMapId?: string;
  spatialMapVersion?: string;
  colorGradePreset?: ColorGradePresetId;
  onColorGradeChange?: (id: ColorGradePresetId) => void;
  hideTitle?: boolean;
};

export function ProductionPipelinePanel({
  projectId,
  prompt,
  purpose,
  referenceAssetIds,
  deploymentPreference,
  allowApiDeployment,
  spatialMapId,
  spatialMapVersion,
  colorGradePreset = DEFAULT_COLOR_GRADE,
  onColorGradeChange,
  hideTitle = false,
}: ProductionPipelinePanelProps) {
  const [qualityProfile, setQualityProfile] = useState<ImagePipelineQualityProfile>("enhanced");
  const [plan, setPlan] = useState<ImageGenerationPlan | null>(null);
  const [candidateGroup, setCandidateGroup] = useState<ImagePipelineCandidateGroup | null>(null);
  const [busy, setBusy] = useState(false);
  const [approving, setApproving] = useState(false);
  const [candidatesBusy, setCandidatesBusy] = useState(false);
  const [message, setMessage] = useState<string | null>(null);

  const promptSummary = useMemo(() => {
    const text = prompt.trim();
    if (!text) return "Describe the shot above to build a creative plan.";
    return text.length > 180 ? `${text.slice(0, 177)}...` : text;
  }, [prompt]);

  const planIsStale = !!plan && plan.request.prompt.trim() !== prompt.trim();
  const routeMode = plan?.modelRoute.deploymentTarget === "api" ? "API" : "Local";
  const routeNote =
    plan?.modelRoute.honestyNote ||
    (plan?.modelRoute.deploymentTarget === "api"
      ? "This route may use a paid API and needs clear approval."
      : "This route stays on a local setup for predictable cost.");

  async function preparePlan() {
    if (!prompt.trim()) {
      setMessage("Describe the shot first so the plan has something real to shape.");
      return;
    }
    setBusy(true);
    setMessage(null);
    try {
      const body: ProductionImageRequest = {
        projectId,
        prompt: prompt.trim(),
        purpose,
        qualityProfile,
        deploymentPreference,
        allowApiDeployment,
        referenceAssetIds,
        spatialMapPayload: spatialMapId
          ? {
              mapId: spatialMapId,
              mapVersion: spatialMapVersion || "",
            }
          : null,
      };
      const result = await api.imagePipeline.preparePlan(body);
      setPlan(result.plan);
      setCandidateGroup(null);
      setMessage(result.creatorPreview || "Plan prepared.");
    } catch (error: unknown) {
      setMessage(error instanceof Error ? error.message : String(error));
    } finally {
      setBusy(false);
    }
  }

  async function runCandidates() {
    if (!plan) return;
    setCandidatesBusy(true);
    setMessage(null);
    try {
      const generated = await api.imagePipeline.generateCandidates(projectId, plan.planId, {
        candidateCount: qualityProfile === "quick" ? 1 : 4,
      });
      let group = generated.group;
      try {
        const recommended = await api.imagePipeline.recommendCandidate(
          projectId,
          plan.planId,
          group.groupId,
        );
        group = recommended.group;
        setMessage(recommended.explanation || generated.message || "Candidates ready.");
      } catch {
        setMessage(generated.message || "Candidate slots prepared. Generation may still need approval.");
      }
      setCandidateGroup(group);
    } catch (error: unknown) {
      setMessage(error instanceof Error ? error.message : String(error));
    } finally {
      setCandidatesBusy(false);
    }
  }

  async function chooseCandidate(candidateId: string) {
    if (!plan || !candidateGroup) return;
    setCandidatesBusy(true);
    setMessage(null);
    try {
      const result = await api.imagePipeline.selectCandidate(
        projectId,
        plan.planId,
        candidateGroup.groupId,
        candidateId,
      );
      setCandidateGroup(result.group);
      setMessage("Candidate selected. Unselected options stay available.");
    } catch (error: unknown) {
      setMessage(error instanceof Error ? error.message : String(error));
    } finally {
      setCandidatesBusy(false);
    }
  }

  async function approveRoute() {
    if (!plan) return;
    setApproving(true);
    setMessage(null);
    try {
      const result = await api.imagePipeline.approvePlan(projectId, plan.planId, {
        kind: "deployment-route",
        approvedBy: "creator",
      });
      setPlan(result.plan);
      setMessage("Paid route approval recorded.");
    } catch (error: unknown) {
      setMessage(error instanceof Error ? error.message : String(error));
    } finally {
      setApproving(false);
    }
  }

  return (
    <section className={hideTitle ? "cis-plan-body" : "cis-card"} data-testid="image-pipeline-panel">
      {hideTitle ? null : <h2 className="cis-card__title">Image Plan</h2>}
      <p className="muted" style={{ marginTop: 0 }}>
        Shape the shot before you generate so the story beat, staging, and route are clear.
      </p>

      {message ? <p className="pill warn">{message}</p> : null}
      {planIsStale ? <p className="pill warn">The prompt changed. Prepare the plan again to refresh it.</p> : null}

      <div className="cis-row" style={{ alignItems: "end" }}>
        <div className="field" style={{ flex: 2 }}>
          <label>Prompt Summary</label>
          <div className="pill" style={{ justifyContent: "flex-start", whiteSpace: "normal" }}>
            {promptSummary}
          </div>
        </div>
        <div className="field">
          <label htmlFor="image-pipeline-quality">Quality</label>
          <select
            id="image-pipeline-quality"
            value={qualityProfile}
            onChange={(event) => setQualityProfile(event.target.value as ImagePipelineQualityProfile)}
          >
            <option value="quick">Quick</option>
            <option value="enhanced">Enhanced</option>
            <option value="cinematic">Cinematic</option>
            <option value="studio-master">Studio Master</option>
          </select>
        </div>
        <div className="field">
          <label htmlFor="image-pipeline-color-grade">Cinematic Color Grade</label>
          <select
            id="image-pipeline-color-grade"
            data-testid="cis-color-grade"
            value={colorGradePreset}
            onChange={(event) => onColorGradeChange?.(event.target.value as ColorGradePresetId)}
          >
            {COLOR_GRADE_OPTIONS.map((grade) => (
              <option key={grade.id} value={grade.id}>
                {grade.label}
              </option>
            ))}
          </select>
        </div>
        <div className="field">
          <button
            type="button"
            className="primary"
            onClick={() => void preparePlan()}
            disabled={busy || !prompt.trim()}
            data-testid="image-pipeline-prepare"
          >
            {busy ? "Preparing..." : "Prepare Plan"}
          </button>
        </div>
      </div>

      {plan ? (
        <>
          <div
            className="cis-row"
            data-testid="image-pipeline-creative-summary"
            style={{ marginTop: "0.9rem", alignItems: "stretch" }}
          >
            <div className="field" style={{ flex: 1 }}>
              <label>Scene Purpose</label>
              <div className="pill" style={{ justifyContent: "flex-start", whiteSpace: "normal" }}>
                {plan.creativeDirection.scenePurpose}
              </div>
            </div>
            <div className="field" style={{ flex: 1 }}>
              <label>Mood</label>
              <div className="pill">{plan.creativeDirection.mood}</div>
            </div>
            <div className="field" style={{ flex: 1 }}>
              <label>Audience Focus</label>
              <div className="pill" style={{ justifyContent: "flex-start", whiteSpace: "normal" }}>
                {plan.creativeDirection.audienceFocus.join(", ")}
              </div>
            </div>
            <div className="field" style={{ flex: 1 }}>
              <label>Visual Priority</label>
              <div className="pill" style={{ justifyContent: "flex-start", whiteSpace: "normal" }}>
                {plan.creativeDirection.visualPriority}
              </div>
            </div>
          </div>

          <div className="cis-row" style={{ marginTop: "0.9rem", alignItems: "stretch" }}>
            <div className="field" style={{ flex: 1 }} data-testid="image-pipeline-staging">
              <label>Staging Recommendation</label>
              <div className="pill" style={{ justifyContent: "flex-start", whiteSpace: "normal" }}>
                <strong>{stagingLabel(plan.controlPackage.stagingRecommendation)}</strong>
                <span style={{ marginLeft: 8 }}>{stagingTip(plan.controlPackage.stagingRecommendation)}</span>
              </div>
            </div>
            <div className="field" style={{ flex: 1 }}>
              <label>Model Route</label>
              <div className="pill" style={{ justifyContent: "flex-start", whiteSpace: "normal" }}>
                <strong>
                  {routeMode} · {plan.modelRoute.modelFamily}
                </strong>
                <span style={{ marginLeft: 8 }}>{routeNote}</span>
              </div>
              {plan.modelRoute.requiresApproval ? (
                <button
                  type="button"
                  className="ghost"
                  onClick={() => void approveRoute()}
                  disabled={approving}
                  style={{ marginTop: "0.55rem" }}
                >
                  {approving ? "Approving..." : "Approve Paid Route"}
                </button>
              ) : null}
            </div>
          </div>

          <div className="cis-row" style={{ marginTop: "0.9rem", alignItems: "stretch" }}>
            <div className="field" style={{ flex: 1 }} data-testid="image-pipeline-readiness">
              <label>Readiness</label>
              <div className="pill" style={{ justifyContent: "flex-start", whiteSpace: "normal" }}>
                <strong>{readinessLabel(plan.readiness)}</strong>
                <span style={{ marginLeft: 8 }}>
                  {plan.readinessReasons[0] || "The plan is ready for the next creator review step."}
                </span>
              </div>
            </div>
            <div className="field" style={{ flex: 1 }}>
              <label>Plan Path</label>
              <div className="pill" style={{ justifyContent: "flex-start", whiteSpace: "normal" }}>
                {plan.stages.map((stage) => stage.label).join(" -> ")}
              </div>
            </div>
          </div>

          <div className="cis-row" style={{ marginTop: "0.9rem", alignItems: "end" }}>
            <div className="field" style={{ flex: 1 }}>
              <label>Current Profile</label>
              <div className="pill">{qualityLabel(plan.request.qualityProfile)}</div>
            </div>
            <div className="field" style={{ flex: 1 }}>
              <label>Primary Summary</label>
              <div className="pill" style={{ justifyContent: "flex-start", whiteSpace: "normal" }}>
                {plan.previewSummary}
              </div>
            </div>
            <div className="field">
              <button
                type="button"
                className="primary"
                onClick={() => void runCandidates()}
                disabled={candidatesBusy || plan.readiness === "blocked"}
                data-testid="image-pipeline-generate-candidates"
              >
                {candidatesBusy ? "Working..." : "Prepare Candidates"}
              </button>
            </div>
            <div className="field">
              <button type="button" className="ghost" disabled title="Timeline handoff is not wired yet.">
                Send to Timeline
              </button>
            </div>
          </div>

          {candidateGroup ? (
            <div className="field" style={{ marginTop: "0.9rem" }} data-testid="image-pipeline-candidates">
              <label>Candidates</label>
              <div className="cis-row" style={{ flexWrap: "wrap", gap: "0.5rem" }}>
                {candidateGroup.candidates.map((candidate) => {
                  const selected = candidateGroup.selectedCandidateId === candidate.candidateId;
                  const recommended = candidateGroup.recommendedCandidateId === candidate.candidateId;
                  return (
                    <button
                      key={candidate.candidateId}
                      type="button"
                      className={selected ? "primary" : "ghost"}
                      data-testid={`image-pipeline-candidate-${candidate.candidateId}`}
                      onClick={() => void chooseCandidate(candidate.candidateId)}
                      disabled={candidatesBusy}
                      title={candidate.status}
                    >
                      {candidate.label || candidate.candidateId}
                      {recommended ? " · Suggested" : ""}
                      {selected ? " · Selected" : ""}
                    </button>
                  );
                })}
              </div>
              {candidateGroup.explanation ? (
                <p className="muted" data-testid="image-pipeline-recommend-reason">
                  {candidateGroup.explanation}
                </p>
              ) : null}
            </div>
          ) : null}

          <details style={{ marginTop: "0.9rem" }}>
            <summary>Advanced</summary>
            <div className="field" style={{ marginTop: "0.75rem" }}>
              <label>Creative Direction Packet</label>
              <pre style={{ overflow: "auto", maxHeight: 220, margin: 0 }}>
                {JSON.stringify(plan.creativeDirection, null, 2)}
              </pre>
            </div>
          </details>
        </>
      ) : null}
    </section>
  );
}
