import { useCallback, useEffect, useRef, useState } from "react";
import { api, type CoDirectorProposal } from "../../api";
import { Button } from "../ui";
import type { ContentTab } from "./CoDirectorNavDrawer";
import { CONTENT_NAV } from "./navEntries";
import { ProjectWikiPanel } from "./ProjectWikiPanel";
import { NotesPanel } from "./NotesPanel";
import { CastingPanel } from "./CastingPanel";
import { StoryEntryEditor } from "../story/StoryEntryEditor";
import { SceneReadinessMatrix } from "./SceneReadinessMatrix";
import { useCoDirectorSession } from "./CoDirectorSession";
import { AgentWorkSurface } from "./AgentWorkSurface/AgentWorkSurface";
import { isAgentWork } from "./AgentWorkSurface/types";
import { CoDirectorEmptyState } from "./cards";
import { CoDirectorProposalCard } from "./CoDirectorProposalCard";
import { EnvironmentReferenceSheetPanel } from "./EnvironmentReferenceSheetPanel";
import { SceneCreatorPanel } from "./SceneCreator/SceneCreatorPanel";
import { PlanWorkspacePanel } from "./plans";
import { ProjectRetrievalPanel, RETRIEVAL_TOOL_SETS } from "./retrieval";
import { LibraryMediaGrid } from "./library/LibraryMediaGrid";
import { ScriptwriterInlineEditor } from "./scriptwriter/ScriptwriterInlineEditor";
import { CharacterCompactView } from "./characters/CharacterCompactView";
import { SpatialMapPanel } from "./SpatialMap/SpatialMapPanel";
import {
  CoDirectorDevelopmentPanel,
  CoDirectorPitchLaunchPanel,
  CoDirectorVisionPanel,
} from "./CoDirectorPartnershipPanels";

function useActiveProjectPlan(projectId: string) {
  const [loading, setLoading] = useState(true);
  const [plan, setPlan] = useState<Record<string, any> | null>(null);
  const [status, setStatus] = useState<string>("not_created");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!projectId) {
      setPlan(null);
      setStatus("not_created");
      setError(null);
      setLoading(false);
      return;
    }
    let cancelled = false;
    setLoading(true);
    setError(null);
    void (async () => {
      try {
        const active = await api.getCoDirectorActivePlan(projectId);
        if (cancelled) return;
        const activePlanId = String(active.plan?.planId || "");
        if (!activePlanId) {
          setPlan(null);
          setStatus(active.status || "not_created");
          setLoading(false);
          return;
        }
        const resolved = await api.getCoDirectorProjectPlanById(projectId, activePlanId);
        if (cancelled) return;
        setPlan(resolved.plan || null);
        setStatus(resolved.status || "active");
        setLoading(false);
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : String(err));
          setPlan(null);
          setLoading(false);
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [projectId]);

  return { loading, plan, status, error };
}

function StageList({ projectId }: { projectId: string }) {
  const { loading, plan, error } = useActiveProjectPlan(projectId);
  const [loaded, setLoaded] = useState(false);
  const steps = Array.isArray(plan?.steps) ? (plan?.steps as Array<Record<string, any>>) : [];

  useEffect(() => {
    setLoaded(!loading);
  }, [loading]);

  if (!loaded) {
    return <p className="muted">Loading plan…</p>;
  }

  if (error) {
    return (
      <CoDirectorEmptyState
        testId="codirector-production-error"
        title="Production plan unavailable"
        description={error}
      />
    );
  }

  if (!plan) {
    return (
      <CoDirectorEmptyState
        testId="codirector-production-empty"
        title="No active production plan"
        description="The active plan will appear here as soon as one is created."
      />
    );
  }

  return (
    <div data-testid="codirector-stage-list">
      <div className="codirector-content-card">
        <p className="eyebrow">Active plan</p>
        <h3 style={{ marginTop: 0 }}>{String(plan.title || "Production Plan")}</h3>
        <p className="muted">State: {String(plan.state || "draft").replace(/_/g, " ")}</p>
      </div>
      {steps.length ? (
        <ol className="codirector-stage-list">
          {steps.map((step, index) => {
            const state = String(step.state || step.status || "pending");
            return (
              <li key={String(step.stepId || index)} data-status={state} aria-current={state === "in_progress" ? "step" : undefined}>
                <span>{String(step.title || `Step ${index + 1}`)}</span>
                <span className="status">{state.replace(/_/g, " ")}</span>
              </li>
            );
          })}
        </ol>
      ) : (
        <CoDirectorEmptyState
          testId="codirector-production-steps-empty"
          title="Plan steps are still empty"
          description="This plan exists, but no creator-facing steps have been saved yet."
        />
      )}
    </div>
  );
}

function ApprovalsList({ projectId }: { projectId: string }) {
  const {
    proposals: sessionProposals,
    proposalActingId,
    approveProposal,
    rejectProposal,
    requestProposalRevision,
    cancelProposal,
    productionCapable,
  } = useCoDirectorSession();
  const [remote, setRemote] = useState<CoDirectorProposal[] | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    api
      .listProposals(projectId)
      .then((res) => {
        if (!cancelled) {
          setRemote(res.proposals || []);
          setLoading(false);
        }
      })
      .catch(() => {
        if (!cancelled) {
          setRemote(null);
          setLoading(false);
        }
      });
    return () => {
      cancelled = true;
    };
  }, [projectId]);

  const proposals =
    (remote && remote.length ? remote : null) ??
    sessionProposals.filter((p) => p.projectId === projectId || !p.projectId);

  if (loading && !proposals.length) {
    return <p className="muted">Loading approvals…</p>;
  }

  const pending = proposals.filter(
    (p) => p.status === "pending" || p.status === "revision_requested" || p.status === "executing",
  );

  if (!pending.length) {
    return (
      <CoDirectorEmptyState
        testId="codirector-approvals-empty"
        kind="no-results"
        title="No approvals are waiting."
        description="Co-Director will place proposed production changes here before applying them."
      />
    );
  }

  return (
    <div data-testid="codirector-approvals-panel" className="codirector-approval-list">
      {pending.map((proposal) => (
        <CoDirectorProposalCard
          key={proposal.id}
          proposal={proposal}
          busy={proposalActingId === proposal.id}
          productionCapable={productionCapable}
          onApprove={() => void approveProposal(proposal.id)}
          onReject={(note) => void rejectProposal(proposal.id, note)}
          onRequestRevision={(note) => void requestProposalRevision(proposal.id, note)}
          onCancel={() => void cancelProposal(proposal.id)}
        />
      ))}
    </div>
  );
}

type FoundationPillar = {
  status: string;
  exists: boolean;
  last_updated: string | null;
  item_count: number;
};

type FoundationStatus = {
  story: FoundationPillar;
  script: FoundationPillar;
  storyboard?: FoundationPillar;
  characters: FoundationPillar;
  ready_for_timeline: boolean;
  missing_pillars: string[];
};

function pillarLabel(pillar: FoundationPillar, isCount: boolean): string {
  if (!pillar.exists) return "Not Started";
  if (isCount) {
    return pillar.item_count > 0 ? String(pillar.item_count) : "Not Started";
  }
  const status = (pillar.status || "").replace(/_/g, " ").trim();
  if (!status) return "Ready";
  return status.charAt(0).toUpperCase() + status.slice(1);
}

function FoundationStatusBar({
  projectId,
  onPillarSelect,
  onGoTab,
}: {
  projectId: string;
  onPillarSelect: (tab: ContentTab) => void;
  onGoTab?: (tab: string, extra?: Record<string, string>) => void;
}) {
  const [status, setStatus] = useState<FoundationStatus | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!projectId) {
      setStatus(null);
      setLoading(false);
      return;
    }
    let cancelled = false;
    setLoading(true);
    api
      .foundationStatus(projectId)
      .then((res) => {
        if (!cancelled) {
          setStatus(res as FoundationStatus);
          setLoading(false);
        }
      })
      .catch(() => {
        if (!cancelled) {
          setStatus(null);
          setLoading(false);
        }
      });
    return () => {
      cancelled = true;
    };
  }, [projectId]);

  if (loading || !status) {
    return null;
  }

  const pillars: { key: keyof Pick<FoundationStatus, "story" | "script" | "characters">; label: string; tab: ContentTab; isCount: boolean }[] = [
    { key: "story", label: "Story", tab: "story", isCount: false },
    { key: "script", label: "Script", tab: "scriptwriter", isCount: false },
    { key: "characters", label: "Characters", tab: "characters", isCount: true },
  ];

  return (
    <div className="codirector-content-card" data-testid="codirector-foundation-status" style={{ marginBottom: "0.5rem" }}>
      <p className="eyebrow" style={{ margin: 0 }}>Project Foundation</p>
      <div style={{ display: "flex", flexWrap: "wrap", gap: "0.5rem", marginTop: "0.35rem" }}>
        {pillars.map((p) => {
          const pillar = status[p.key];
          const label = pillarLabel(pillar, p.isCount);
          const ready = pillar.exists && (p.isCount ? pillar.item_count > 0 : true);
          return (
            <button
              key={p.key}
              type="button"
              data-testid={`codirector-foundation-${p.key}`}
              onClick={() => {
                if (p.tab === "characters" && onGoTab) {
                  onGoTab("characters");
                } else {
                  onPillarSelect(p.tab);
                }
              }}
              style={{
                display: "inline-flex",
                flexDirection: "column",
                alignItems: "flex-start",
                padding: "0.3rem 0.5rem",
                background: ready ? "color-mix(in srgb, var(--accent, #4a8) 14%, transparent)" : "transparent",
                border: "1px solid color-mix(in srgb, currentColor 18%, transparent)",
                borderRadius: "0.35rem",
                cursor: "pointer",
                minWidth: "5.5rem",
              }}
            >
              <span style={{ fontSize: "0.7rem", opacity: 0.8 }}>{p.label}</span>
              <span style={{ fontSize: "0.8rem", fontWeight: 600 }}>{label}</span>
            </button>
          );
        })}
      </div>
    </div>
  );
}

export function CoDirectorProjectContent({
  tab,
  onTabChange,
  onGoTab,
}: {
  tab: ContentTab;
  onTabChange: (tab: ContentTab) => void;
  onGoTab?: (tab: string, extra?: Record<string, string>) => void;
}) {
  const { uiContext, messages, activity, activeExecution } = useCoDirectorSession();
  const projectId = uiContext.projectId || "";
  const lastUserMessageId = [...messages].reverse().find((message) => message.role === "user")?.id || "";
  const wikiRefreshToken = `${uiContext.projectName || ""}:${lastUserMessageId}:${messages.length}:${activity?.wikiRefreshNonce || 0}`;
  const [openGroup, setOpenGroup] = useState<string | null>(null);
  const [castingFocus, setCastingFocus] = useState<string | null>(null);
  const [menuPos, setMenuPos] = useState<{ top: number; left: number } | null>(null);
  const storyTriggerRef = useRef<HTMLDivElement>(null);
  const productionTriggerRef = useRef<HTMLDivElement>(null);

  const handleTabChange = useCallback(
    (id: ContentTab) => {
      onTabChange(id);
    },
    [onTabChange],
  );

  useEffect(() => {
    if (!openGroup) return;
    const handleMouseDown = (e: MouseEvent) => {
      const target = e.target as Node;
      const triggerEl = document.querySelector(`[data-testid="codirector-content-group-${openGroup}"]`)?.parentElement;
      const menuEl = document.querySelector(`[data-testid="codirector-content-group-menu-${openGroup}"]`);
      if (triggerEl && !triggerEl.contains(target) && menuEl && !menuEl.contains(target)) {
        setOpenGroup(null);
        setMenuPos(null);
      }
    };
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        setOpenGroup(null);
        setMenuPos(null);
      }
    };
    document.addEventListener("mousedown", handleMouseDown);
    document.addEventListener("keydown", handleKeyDown);
    return () => {
      document.removeEventListener("mousedown", handleMouseDown);
      document.removeEventListener("keydown", handleKeyDown);
    };
  }, [openGroup]);

  return (
    <aside className="codirector-workspace-content" aria-label="Project Content" data-testid="codirector-project-content">
      <div className="codirector-content-tabs" role="tablist" aria-label="Project content sections">
        {CONTENT_NAV.map((item) => {
          if (item.kind === "tab") {
            return (
              <Button
                key={item.id}
                role="tab"
                aria-selected={tab === item.id}
                variant="compact"
                className={tab === item.id ? "is-selected" : undefined}
                data-testid={`codirector-content-tab-${item.id}`}
                onClick={() => { handleTabChange(item.id); setOpenGroup(null); setMenuPos(null); }}
              >
                {item.label}
              </Button>
            );
          }
          const childActive = item.children.some((c) => c.id === tab);
          const expanded = openGroup === item.id;
          return (
            <div
              key={item.id}
              ref={item.id === "story" ? storyTriggerRef : productionTriggerRef}
              style={{ position: "relative", display: "inline-flex" }}
            >
              <Button
                role="tab"
                aria-selected={childActive}
                aria-haspopup="menu"
                aria-expanded={expanded}
                variant="compact"
                className={childActive ? "is-selected" : undefined}
                data-testid={`codirector-content-group-${item.id}`}
                onClick={(e) => {
                  if (openGroup === item.id) {
                    setOpenGroup(null);
                    setMenuPos(null);
                  } else {
                    const rect = e.currentTarget.getBoundingClientRect();
                    setMenuPos({ top: rect.bottom, left: rect.left });
                    setOpenGroup(item.id);
                  }
                }}
              >
                {item.label} ▾
              </Button>
              {expanded && menuPos ? (
                <div
                  role="menu"
                  data-testid={`codirector-content-group-menu-${item.id}`}
                  style={{
                    position: "fixed",
                    top: menuPos.top,
                    left: menuPos.left,
                    zIndex: 1000,
                    minWidth: "10rem",
                    padding: "0.35rem",
                    background: "var(--panel, #1a1f2a)",
                    border: "1px solid color-mix(in srgb, currentColor 18%, transparent)",
                    borderRadius: "0.4rem",
                  }}
                >
                  {item.children.map((child) => (
                    <Button
                      key={child.id}
                      role="menuitem"
                      variant="compact"
                      data-testid={`codirector-content-tab-${child.id}`}
                      className={tab === child.id ? "is-selected" : undefined}
                      onClick={() => {
                        handleTabChange(child.id);
                        setOpenGroup(null);
                        setMenuPos(null);
                      }}
                      style={{ display: "block", width: "100%", textAlign: "left" }}
                    >
                      {child.label}
                    </Button>
                  ))}
                </div>
              ) : null}
            </div>
          );
        })}
      </div>
      <div
        className="codirector-content-body"
        role="tabpanel"
        style={{ position: "relative" }}
      >
        <div
          className={
            isAgentWork(activeExecution)
              ? "project-pane-content project-pane--dimmed"
              : "project-pane-content"
          }
        >
        {tab === "wiki" && (
          <div data-testid="codirector-content-wiki">
            <h3 style={{ marginTop: 0, fontSize: "0.95rem" }}>
              {uiContext.projectName || "No Project Selected"}
            </h3>
            {projectId ? (
              <>
                <FoundationStatusBar projectId={projectId} onPillarSelect={handleTabChange} onGoTab={onGoTab} />
                <ProjectWikiPanel
                  projectId={projectId}
                  refreshToken={wikiRefreshToken}
                  wikiUiMessage={activity?.wikiUiMessage || null}
                  wikiVerification={activity?.wikiVerification || null}
                  onOpenCasting={(name) => {
                    setCastingFocus(name);
                    onTabChange("casting");
                  }}
                />
              </>
            ) : (
              <p className="muted">Select a project to open the Project Wiki.</p>
            )}
          </div>
        )}
        {tab === "story" && (
          <div data-testid="codirector-content-story">
            {projectId ? (
              <StoryEntryEditor projectId={projectId} embedded />
            ) : (
              <p className="muted">Select a project to write your Story.</p>
            )}
          </div>
        )}
        {tab === "notes" && (
          <div data-testid="codirector-content-notes">
            {projectId ? (
              <NotesPanel projectId={projectId} />
            ) : (
              <p className="muted">Select a project to open Notes.</p>
            )}
          </div>
        )}
        {tab === "casting" && (
          <div data-testid="codirector-content-casting">
            {projectId ? (
              <CastingPanel projectId={projectId} focusCharacter={castingFocus} />
            ) : (
              <p className="muted">Select a project to open Casting.</p>
            )}
          </div>
        )}
        {tab === "scriptwriter" && (
          <div data-testid="codirector-content-scriptwriter">
            {projectId ? (
              <ScriptwriterInlineEditor
                projectId={projectId}
                onOpenFull={() => onGoTab?.("scriptwriter")}
              />
            ) : (
              <p className="muted">Select a project to open Script Writer.</p>
            )}
          </div>
        )}
        {tab === "characters" && (
          <div data-testid="codirector-content-characters">
            {projectId ? (
              <CharacterCompactView
                projectId={projectId}
                onOpenFull={(characterId) =>
                  onGoTab?.(
                    "characters",
                    characterId ? { characterId, returnWorkspace: "codirector" } : { returnWorkspace: "codirector" },
                  )
                }
              />
            ) : (
              <p className="muted">Select a project to open Character Creator.</p>
            )}
          </div>
        )}
        {tab === "spatial_map" && (
          <div data-testid="codirector-content-spatial-map">
            {projectId ? (
              <SpatialMapPanel projectId={projectId} onGoTab={onGoTab} />
            ) : (
              <CoDirectorEmptyState
                testId="codirector-spatial-map-empty"
                title="No Project Selected"
                description="Select a project to open Spatial Map."
              />
            )}
          </div>
        )}
        {tab === "scene_creator" && (
          <div data-testid="codirector-content-scene-creator">
            {projectId ? (
              <SceneCreatorPanel projectId={projectId} onGoTab={onGoTab} />
            ) : (
              <CoDirectorEmptyState title="No Project Selected" description="Select a project to open Scene Creator." />
            )}
          </div>
        )}
        {tab === "library" && (
          <div data-testid="codirector-content-library">
            {projectId ? (
              <LibraryMediaGrid projectId={projectId} onGoTab={onGoTab} />
            ) : (
              <CoDirectorEmptyState
                testId="codirector-library-empty"
                title="Project library"
                description="Select a project to browse library assets."
              />
            )}
          </div>
        )}
        {tab === "production" &&
          (projectId ? (
            <StageList projectId={projectId} />
          ) : (
            <CoDirectorEmptyState title="No Project Selected" description="Select a project to view stages." />
          ))}
        {tab === "plans" && (
          <div data-testid="codirector-content-plans">
            {projectId ? (
              <>
                <SceneReadinessMatrix projectId={projectId} />
                <EnvironmentReferenceSheetPanel projectId={projectId} />
                <PlanWorkspacePanel projectId={projectId} />
                <ProjectRetrievalPanel
                  projectId={projectId}
                  tools={RETRIEVAL_TOOL_SETS.plans}
                  emptyTitle="No stored plans or proposals"
                  emptyDescription="Plans and proposals are listed from the same stores Approvals uses."
                  testId="codirector-retrieval-plans"
                />
              </>
            ) : (
              <CoDirectorEmptyState
                testId="codirector-plans-empty"
                title="No active plan"
                description="Select a project to view durable production plans."
              />
            )}
          </div>
        )}
        {tab === "bible" && (
          <div data-testid="codirector-content-bible">
            {projectId ? (
              <ProjectRetrievalPanel
                projectId={projectId}
                tools={RETRIEVAL_TOOL_SETS.bible}
                emptyTitle="No Production Bible"
                emptyDescription="Bible summary appears when a Production Bible exists for this project."
                testId="codirector-retrieval-bible"
              />
            ) : (
              <CoDirectorEmptyState
                title="Production Bible"
                description="Select a project to retrieve Bible records."
              />
            )}
          </div>
        )}
        {tab === "approvals" &&
          (projectId ? (
            <ApprovalsList projectId={projectId} />
          ) : (
            <CoDirectorEmptyState title="No Project Selected" description="Select a project to review approvals." />
          ))}
        {tab === "jobs" &&
          (projectId ? (
            <ProjectRetrievalPanel
              projectId={projectId}
              tools={RETRIEVAL_TOOL_SETS.jobs}
              emptyTitle="No jobs"
              emptyDescription="Jobs appear when executive or render jobs exist. Progress is never invented."
              testId="codirector-retrieval-jobs"
            />
          ) : (
            <CoDirectorEmptyState
              testId="codirector-jobs-empty"
              kind="unavailable"
              title="Jobs"
              description="Select a project to inspect jobs."
            />
          ))}
        {tab === "development" && <CoDirectorDevelopmentPanel />}
        {tab === "vision" && <CoDirectorVisionPanel />}
        {tab === "pitch" && <CoDirectorPitchLaunchPanel />}
        </div>
        {isAgentWork(activeExecution) && (
          <div
            className="agent-operation-overlay"
            role="dialog"
            aria-label="Co-Director working"
            data-testid="agent-operation-overlay"
          >
            <AgentWorkSurface />
          </div>
        )}
      </div>
    </aside>
  );
}
