import { useEffect, useMemo, useRef, useState } from "react";
import { api, type CoDirectorProjectWiki, type ProjectWikiEntry, type ProjectWikiSection } from "../../api";
import { Button } from "../ui";
import { CoDirectorEmptyState, CoDirectorErrorState } from "./cards";
import { CompiledWikiReader } from "./wiki/CompiledWikiReader";
function stripHtml(text: string): string {
  return text.replace(/<[^>]+>/g, "").trim();
}

type SectionSpec = {
  key: keyof CoDirectorProjectWiki["sections"];
  label: string;
};

const SECTION_ORDER: SectionSpec[] = [
  { key: "knownDetails", label: "Known Details" },
  { key: "creativeFoundation", label: "Creative Foundation" },
  { key: "characters", label: "Characters" },
  { key: "worldAndSetting", label: "World & Setting" },
  { key: "storyAndEpisodes", label: "Story & Episodes" },
  { key: "visualIdentity", label: "Visual Identity" },
  { key: "productionDecisions", label: "Production Decisions" },
  { key: "openQuestions", label: "Open Questions" },
  { key: "references", label: "References" },
];

type ExportFormat = "pdf" | "html";
type ExportPrefs = {
  exportTitle: string;
  includeCover: boolean;
  includeToc: boolean;
  includeOpenQuestions: boolean;
  includeUnresolved: boolean;
  includeImages: boolean;
  includeAudioVideo: boolean;
  includeProductionMetadata: boolean;
  sectionsMode: "all" | "selected";
  selectedSections: string[];
  sizeMode: "optimized" | "original" | "wiki_only" | "text_only";
};

const DEFAULT_EXPORT_PREFS: ExportPrefs = {
  exportTitle: "",
  includeCover: true,
  includeToc: true,
  includeOpenQuestions: true,
  includeUnresolved: true,
  includeImages: true,
  includeAudioVideo: true,
  includeProductionMetadata: true,
  sectionsMode: "all",
  selectedSections: [],
  sizeMode: "optimized",
};

function exportPrefsKey(projectId: string) {
  return `adept_codirector_wiki_export_${projectId}`;
}

function loadExportPrefs(projectId: string): ExportPrefs {
  try {
    const raw = localStorage.getItem(exportPrefsKey(projectId));
    if (!raw) return DEFAULT_EXPORT_PREFS;
    return { ...DEFAULT_EXPORT_PREFS, ...(JSON.parse(raw) as Partial<ExportPrefs>) };
  } catch {
    return DEFAULT_EXPORT_PREFS;
  }
}

function persistExportPrefs(projectId: string, prefs: ExportPrefs) {
  try {
    localStorage.setItem(exportPrefsKey(projectId), JSON.stringify(prefs));
  } catch {
    /* ignore */
  }
}

function downloadBlob(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  link.click();
  URL.revokeObjectURL(url);
}

function stateLabel(entry: ProjectWikiEntry) {
  if (entry.state === "confirmed") return "Confirmed";
  if (entry.state === "proposed") return "Inferred / Learning";
  if (entry.state === "approved") return "Approved";
  if (entry.state === "rejected") return "Rejected";
  if (entry.state === "superseded") return "Superseded";
  if (entry.state === "reference-only") return "Reference only";
  return "Unresolved";
}

function tocExpandedKey(projectId: string) {
  return `adept_wiki_toc_expanded_${projectId}`;
}

function renderSection(
  key: string,
  label: string,
  section: ProjectWikiSection,
  selectedId: string | null,
  onSelect: (id: string) => void,
) {
  return (
    <section
      key={key}
      id={`wiki-section-${key}`}
      className="codirector-content-card codirector-project-wiki-section"
      data-testid={`project-wiki-${key}`}
    >
      <h4>{label}</h4>
      {section.summary ? <p className="muted">{section.summary}</p> : null}
      {section.entries.length ? (
        <ul className="codirector-project-wiki-list">
          {section.entries.map((entry) => (
            <li
              key={entry.id}
              id={`wiki-entry-${entry.id}`}
              data-state={entry.state}
              data-selected={selectedId === entry.id ? "true" : "false"}
              className={selectedId === entry.id ? "is-selected" : undefined}
              onClick={() => onSelect(entry.id)}
              style={{ cursor: "pointer" }}
            >
              <span className="codirector-project-wiki-entry-state" data-testid={`wiki-entry-state-${entry.state}`}>
                {stateLabel(entry)}
              </span>
              <span>{entry.text}</span>
            </li>
          ))}
        </ul>
      ) : (
        <p className="muted">{section.emptyState || "Nothing here yet."}</p>
      )}
    </section>
  );
}

export function ProjectWikiPanel({
  projectId,
  refreshToken,
  wikiUiMessage,
  wikiVerification,
  onOpenCasting,
  onGoTab,
}: {
  projectId: string;
  refreshToken: string;
  wikiUiMessage?: string | null;
  wikiVerification?: { persistenceState?: string; presentationState?: string; finalState?: string; error?: string | null } | null;
  onOpenCasting?: (characterName: string) => void;
  onGoTab?: (tab: string, extra?: Record<string, string>) => void;
}) {
  const [loading, setLoading] = useState(true);
  const [wiki, setWiki] = useState<CoDirectorProjectWiki | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [exportOpen, setExportOpen] = useState(false);
  const [exportFormat, setExportFormat] = useState<ExportFormat>("pdf");
  const [exportBusy, setExportBusy] = useState(false);
  const [exportPrefs, setExportPrefs] = useState<ExportPrefs>(() => loadExportPrefs(projectId));
  const [manualBump, setManualBump] = useState(0);
  const [selectedEntryId, setSelectedEntryId] = useState<string | null>(null);
  const [wikiBusy, setWikiBusy] = useState(false);
  const [actionMessage, setActionMessage] = useState<string | null>(null);
  const [storySummaryBusy, setStorySummaryBusy] = useState(false);
  const [diagnosticSummary, setDiagnosticSummary] = useState<string | null>(null);
  const [reorgOpen, setReorgOpen] = useState(false);
  const [reorgDomains, setReorgDomains] = useState<Record<string, boolean>>({
    characters: true,
    locations: true,
    story: true,
    world: true,
    timeline: true,
    wardrobe: true,
    props: true,
    visual: true,
    audio: true,
    assets: true,
    canon: true,
  });
  const [reorgStage, setReorgStage] = useState<string | null>(null);
  const [reorgSummary, setReorgSummary] = useState<string[] | null>(null);
  const [reorgJobId, setReorgJobId] = useState<string | null>(null);
  const [reorgSpecialists, setReorgSpecialists] = useState<string[]>([]);
  // Refine Wiki — creator correction state.
  const [refineOpen, setRefineOpen] = useState(false);
  const [refineInstruction, setRefineInstruction] = useState("");
  const [refineBusy, setRefineBusy] = useState(false);
  const [refinePreview, setRefinePreview] = useState<Record<string, unknown> | null>(null);
  const [refineResult, setRefineResult] = useState<{ lines: string[]; correctionId: string } | null>(null);
  const [currentPage, setCurrentPage] = useState<{ pageId: string; pageType?: string; title?: string } | null>(null);
  const [tocOpen, setTocOpen] = useState(() => {
    try {
      return localStorage.getItem(tocExpandedKey(projectId)) !== "0";
    } catch {
      return true;
    }
  });

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    void api
      .getCoDirectorProjectWiki(projectId)
      .then((next) => {
        if (!cancelled) {
          setWiki(next);
          setLoading(false);
        }
      })
      .catch((err) => {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : String(err));
          setLoading(false);
        }
      });
    return () => {
      cancelled = true;
    };
  }, [projectId, refreshToken, manualBump]);

  // Auto-refetch when wiki verification newly reaches VERIFIED / VISIBLE.
  const lastAutoRefreshKey = useRef<string>("");
  useEffect(() => {
    const final = wikiVerification?.finalState || wikiVerification?.presentationState || "";
    const persistence = wikiVerification?.persistenceState || "";
    const key = `${final}|${persistence}`;
    const ready =
      final === "VERIFIED" ||
      final === "VISIBLE" ||
      persistence === "VERIFIED" ||
      wikiVerification?.presentationState === "VISIBLE";
    if (!ready || key === lastAutoRefreshKey.current) return;
    lastAutoRefreshKey.current = key;
    setManualBump((n) => n + 1);
  }, [
    wikiVerification?.finalState,
    wikiVerification?.presentationState,
    wikiVerification?.persistenceState,
  ]);

  const runRebuild = async () => {
    setWikiBusy(true);
    setActionMessage(null);
    try {
      const result = await api.rebuildCoDirectorProjectWiki(projectId);
      const states = (result.verification?.states || {}) as {
        PERSISTED?: boolean;
        VERIFIED?: boolean;
        VISIBLE?: boolean;
      };
      if (result.ok && states.PERSISTED && !states.VISIBLE) {
        setActionMessage(
          String(result.verification?.recoveryMessage || "") ||
            "The project notes were saved, but the Wiki panel did not refresh.",
        );
      } else if (!result.ok) {
        setActionMessage(result.error || "The Wiki update failed.");
      } else {
        setActionMessage(
          result.wikiHasContent
            ? `Wiki rebuilt with ${result.extractedCandidates ?? 0} notes from the conversation.`
            : "Rebuild finished — add more story details in chat to grow the Wiki.",
        );
      }
      setManualBump((n) => n + 1);
    } catch (err) {
      setActionMessage(err instanceof Error ? err.message : "The Wiki update failed.");
    } finally {
      setWikiBusy(false);
    }
  };

  const runDiagnostic = async () => {
    setWikiBusy(true);
    setDiagnosticSummary(null);
    try {
      const result = await api.diagnoseCoDirectorProjectWiki(projectId);
      if (!result.ok) {
        setDiagnosticSummary(result.error || "Diagnostic could not run.");
        return;
      }
      const counts = result.wikiSectionCounts || {};
      const parts = Object.entries(counts)
        .filter(([, n]) => (n || 0) > 0)
        .map(([k, n]) => `${k}: ${n}`);
      setDiagnosticSummary(
        [
          result.wikiHasContent ? "Wiki has content." : "Wiki is still empty.",
          `Messages: ${result.userMessageCount ?? 0}`,
          `Knowledge notes: ${result.knowledgeEntryCount ?? 0}`,
          parts.length ? `Sections — ${parts.join(", ")}` : "No section entries yet.",
        ].join(" "),
      );
    } catch (err) {
      setDiagnosticSummary(err instanceof Error ? err.message : "Diagnostic could not run.");
    } finally {
      setWikiBusy(false);
    }
  };

  const runReorganize = async () => {
    setWikiBusy(true);
    setReorgStage("Reviewing Wiki structure");
    setReorgSummary(null);
    setActionMessage(null);
    try {
      const domains = Object.entries(reorgDomains)
        .filter(([, on]) => on)
        .map(([k]) => k);
      const result = await api.reorganizeCoDirectorProjectWiki(projectId, {
        domains,
        useSpecialists: true,
        preserveLockedCanon: true,
        createUndoSnapshot: true,
      });
      if (!result.ok) {
        setActionMessage(result.error || "Reorganization failed.");
        setReorgStage(null);
        return;
      }
      const job = result.job;
      setReorgJobId(job?.id || null);
      setReorgStage(job?.stage || result.stages?.[result.stages.length - 1] || "Complete");
      setReorgSummary(job?.summaryLines || []);
      setReorgSpecialists(result.specialistsActivated || []);
      setReorgOpen(false);
      setManualBump((n) => n + 1);
    } catch (err) {
      setActionMessage(err instanceof Error ? err.message : "Reorganization failed.");
      setReorgStage(null);
    } finally {
      setWikiBusy(false);
    }
  };

  const runUndoReorganize = async () => {
    if (!reorgJobId) return;
    setWikiBusy(true);
    try {
      const result = await api.undoCoDirectorWikiReorganize(projectId, reorgJobId);
      if (!result.ok) {
        setActionMessage(result.error || "Undo failed.");
        return;
      }
      setReorgSummary(null);
      setReorgStage(null);
      setActionMessage("Previous Wiki revision restored.");
      setManualBump((n) => n + 1);
    } catch (err) {
      setActionMessage(err instanceof Error ? err.message : "Undo failed.");
    } finally {
      setWikiBusy(false);
    }
  };

  // --- Refine Wiki handlers ---
  const openRefine = (instruction = "") => {
    setRefineInstruction(instruction);
    setRefinePreview(null);
    setRefineResult(null);
    setRefineOpen(true);
  };

  const refineTarget = () => {
    if (!currentPage) return undefined;
    return {
      pageId: currentPage.pageId,
      pageType: currentPage.pageType,
      label: currentPage.title,
    };
  };

  const runRefinePreview = async () => {
    if (!refineInstruction.trim()) return;
    setRefineBusy(true);
    setRefinePreview(null);
    setActionMessage(null);
    try {
      const result = await api.previewCoDirectorWikiCorrection(
        projectId,
        refineInstruction.trim(),
        refineTarget(),
      );
      if (!result.ok) {
        setActionMessage("Co-Director could not prepare a preview.");
        return;
      }
      setRefinePreview(result.preview);
    } catch (err) {
      setActionMessage(err instanceof Error ? err.message : "Preview failed.");
    } finally {
      setRefineBusy(false);
    }
  };

  const runRefineApply = async () => {
    const previewId = refinePreview?.previewId as string | undefined;
    if (!previewId) return;
    setRefineBusy(true);
    try {
      const result = await api.applyCoDirectorWikiCorrection(projectId, previewId);
      if (!result.ok) {
        setActionMessage("The refinement could not be applied.");
        return;
      }
      const lines = (result.summaryLines as string[] | undefined) || [];
      const correction = (result.correction as Record<string, unknown> | undefined) || {};
      setRefineResult({ lines, correctionId: String(correction.id || "") });
      setRefinePreview(null);
      setRefineInstruction("");
      setManualBump((n) => n + 1);
    } catch (err) {
      setActionMessage(err instanceof Error ? err.message : "Apply failed.");
    } finally {
      setRefineBusy(false);
    }
  };

  const runRefineUndo = async () => {
    if (!refineResult?.correctionId) return;
    setRefineBusy(true);
    try {
      const result = await api.undoCoDirectorWikiCorrection(projectId, refineResult.correctionId);
      if (!result.ok) {
        setActionMessage("Undo failed.");
        return;
      }
      setRefineResult(null);
      setActionMessage("Refinement undone — previous Wiki restored.");
      setManualBump((n) => n + 1);
    } catch (err) {
      setActionMessage(err instanceof Error ? err.message : "Undo failed.");
    } finally {
      setRefineBusy(false);
    }
  };

  useEffect(() => {
    setExportPrefs(loadExportPrefs(projectId));
  }, [projectId]);

  const populated = useMemo(() => {
    if (!wiki) return [];
    return SECTION_ORDER.map(({ key, label }) => {
      const section = wiki.sections[key];
      const count = section?.entries?.length || 0;
      return { key: String(key), label, section, count };
    }).filter((s) => s.count > 0);
  }, [wiki]);

  const sections = useMemo(() => {
    return populated.map(({ key, label, section }) =>
      renderSection(key, label, section, selectedEntryId, setSelectedEntryId),
    );
  }, [populated, selectedEntryId]);

  const selectedEntry = useMemo(() => {
    if (!wiki || !selectedEntryId) return null;
    for (const key of Object.keys(wiki.sections) as (keyof CoDirectorProjectWiki["sections"])[]) {
      const found = wiki.sections[key]?.entries?.find((e) => e.id === selectedEntryId);
      if (found) {
        return { entry: found, sectionKey: String(key) };
      }
    }
    return null;
  }, [wiki, selectedEntryId]);

  const updatePrefs = (patch: Partial<ExportPrefs>) => {
    setExportPrefs((prev) => {
      const next = { ...prev, ...patch };
      persistExportPrefs(projectId, next);
      return next;
    });
  };

  const runExport = async (format: ExportFormat) => {
    if (!wiki) return;
    setExportBusy(true);
    setError(null);
    try {
      const body = {
        ...exportPrefs,
        exportTitle: exportPrefs.exportTitle || wiki.title,
      };
      const file =
        format === "pdf"
          ? await api.exportCoDirectorProjectWikiPdf(projectId, body)
          : await api.exportCoDirectorProjectWikiHtml(projectId, body);
      downloadBlob(file.blob, file.filename);
      setExportOpen(false);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setExportBusy(false);
    }
  };

  if (loading) {
    return (
      <p className="muted" data-testid="project-wiki-loading">
        Loading Project Wiki…
      </p>
    );
  }

  if (error) {
    return <CoDirectorErrorState testId="project-wiki-error" title="Project Wiki unavailable" description={error} />;
  }

  if (!wiki) {
    return <CoDirectorEmptyState testId="project-wiki-empty" title="Project Wiki" description="No project wiki is available yet." />;
  }

  const persistenceOk =
    wikiVerification?.persistenceState === "VERIFIED" || wikiVerification?.persistenceState === "PERSISTED";
  const showRefreshHint = Boolean(wikiUiMessage && persistenceOk);
  const showRetryHint = Boolean(wikiUiMessage && wikiVerification?.persistenceState === "FAILED");

  const wikiActions = (
    <div className="row" style={{ gap: "0.35rem", flexWrap: "wrap", marginBottom: "0.5rem" }}>
      <Button
        compact
        variant="primary"
        disabled={wikiBusy}
        data-testid="project-wiki-refine"
        title="Tell Co-Director what is wrong, missing, misplaced, duplicated, or should be rewritten."
        onClick={() => openRefine()}
      >
        Refine Wiki
      </Button>
      <Button
        compact
        disabled={wikiBusy}
        data-testid="project-wiki-rebuild"
        onClick={() => void runRebuild()}
      >
        {wikiBusy ? "Working…" : "Rebuild Wiki from conversation"}
      </Button>
      <Button
        compact
        variant="ghost"
        disabled={wikiBusy}
        data-testid="project-wiki-diagnostic"
        onClick={() => void runDiagnostic()}
      >
        Run Wiki diagnostic
      </Button>
      <Button
        compact
        variant="ghost"
        disabled={wikiBusy}
        data-testid="project-wiki-reorganize"
        onClick={() => {
          setReorgOpen(true);
          setReorgSummary(null);
        }}
      >
        Reorganize Wiki
      </Button>
    </div>
  );

  const reorgDomainLabels: { key: string; label: string }[] = [
    { key: "characters", label: "Characters and relationships" },
    { key: "locations", label: "Locations and sets" },
    { key: "story", label: "Story, episodes, and scenes" },
    { key: "world", label: "World and lore" },
    { key: "timeline", label: "Timeline and continuity" },
    { key: "wardrobe", label: "Wardrobe and props" },
    { key: "props", label: "Props (detailed)" },
    { key: "visual", label: "Visual and audio references" },
    { key: "audio", label: "Audio references" },
    { key: "assets", label: "Scripts and production assets" },
    { key: "canon", label: "Canon states and conflicts" },
  ];

  const reorgPanel = reorgOpen ? (
    <div className="codirector-action-card" data-testid="project-wiki-reorganize-dialog" role="dialog" aria-label="Reorganize Project Wiki">
      <h3 style={{ marginTop: 0 }}>Reorganize Project Wiki</h3>
      <p>
        Co-Director will review the current Wiki, use its professional production specialists, and reorganize any
        misplaced, duplicated, incomplete, or poorly catalogued information.
      </p>
      <div className="codirector-project-wiki-export-grid" data-testid="project-wiki-reorganize-scopes">
        {reorgDomainLabels.map((d) => (
          <label key={d.key}>
            <input
              type="checkbox"
              checked={Boolean(reorgDomains[d.key])}
              onChange={(e) => setReorgDomains((prev) => ({ ...prev, [d.key]: e.target.checked }))}
            />{" "}
            {d.label}
          </label>
        ))}
      </div>
      <div className="row" style={{ marginTop: "0.75rem", gap: "0.35rem" }}>
        <Button compact disabled={wikiBusy} data-testid="project-wiki-reorganize-confirm" onClick={() => void runReorganize()}>
          {wikiBusy ? "Reorganizing…" : "Reorganize Wiki"}
        </Button>
        <Button compact variant="ghost" disabled={wikiBusy} onClick={() => setReorgOpen(false)}>
          Cancel
        </Button>
      </div>
    </div>
  ) : null;

  const reorgProgress = reorgStage ? (
    <p className="muted" data-testid="project-wiki-reorganize-stage">
      {reorgStage}
      {reorgSpecialists.length ? ` · Specialists: ${reorgSpecialists.slice(0, 6).join(", ")}` : ""}
    </p>
  ) : null;

  const reorgResult = reorgSummary?.length ? (
    <div className="codirector-content-card" data-testid="project-wiki-reorganize-summary">
      <h4 style={{ marginTop: 0 }}>Wiki Reorganized</h4>
      <ul>
        {reorgSummary.map((line) => (
          <li key={line}>{line}</li>
        ))}
      </ul>
      <div className="row" style={{ gap: "0.35rem", flexWrap: "wrap" }}>
        <Button compact variant="ghost" data-testid="project-wiki-reorganize-review" onClick={() => setManualBump((n) => n + 1)}>
          Review Changes
        </Button>
        <Button compact variant="ghost" data-testid="project-wiki-reorganize-conflicts" onClick={() => setManualBump((n) => n + 1)}>
          View Conflicts
        </Button>
        <Button compact variant="ghost" data-testid="project-wiki-reorganize-open" onClick={() => setManualBump((n) => n + 1)}>
          Open Reorganized Wiki
        </Button>
        <Button
          compact
          variant="ghost"
          disabled={!reorgJobId || wikiBusy}
          data-testid="project-wiki-reorganize-undo"
          onClick={() => void runUndoReorganize()}
        >
          Undo Reorganization
        </Button>
      </div>
    </div>
  ) : null;

  // --- Refine Wiki overlay ---
  const refineContextLabel = currentPage?.title
    ? `Refining: ${currentPage.title}`
    : "Refining: Whole Wiki";
  const previewChanges = (refinePreview?.proposedChanges as Array<Record<string, unknown>> | undefined) || [];
  const clarification = (refinePreview?.clarificationQuestion as string | undefined) || null;

  const refinePanel = refineOpen ? (
    <div
      className="codirector-action-card"
      data-testid="project-wiki-refine-dialog"
      role="dialog"
      aria-label="Refine Project Wiki"
    >
      <h3 style={{ marginTop: 0 }}>Refine Project Wiki</h3>
      <p className="muted" data-testid="project-wiki-refine-context" style={{ marginTop: 0 }}>
        {refineContextLabel}
      </p>
      {!refineResult ? (
        <>
          <p>
            Tell Co-Director what is wrong, missing, misplaced, duplicated, or should be rewritten.
          </p>
          <textarea
            data-testid="project-wiki-refine-input"
            value={refineInstruction}
            onChange={(e) => {
              setRefineInstruction(e.target.value);
              setRefinePreview(null);
            }}
            placeholder='For example: "Gakona is a location, not a character." or "Merge Barnes and Special Agent Barnes."'
            rows={4}
            style={{ width: "100%", resize: "vertical" }}
          />
          {clarification ? (
            <p className="muted" data-testid="project-wiki-refine-clarification" style={{ marginTop: "0.5rem" }}>
              {clarification}
            </p>
          ) : null}
          {refinePreview && !clarification ? (
            <div
              className="codirector-content-card"
              data-testid="project-wiki-refine-preview"
              style={{ marginTop: "0.75rem" }}
            >
              <h4 style={{ marginTop: 0 }}>Proposed Wiki Changes</h4>
              <ul>
                {previewChanges.map((c, i) => (
                  <li key={i} data-testid={`project-wiki-refine-change-${i}`}>
                    <strong>{String(c.area || "Wiki")}:</strong> {String(c.description || "")}
                  </li>
                ))}
              </ul>
            </div>
          ) : null}
          <div className="row" style={{ marginTop: "0.75rem", gap: "0.35rem", flexWrap: "wrap" }}>
            {!refinePreview || clarification ? (
              <Button
                compact
                variant="primary"
                disabled={refineBusy || !refineInstruction.trim()}
                data-testid="project-wiki-refine-preview-btn"
                onClick={() => void runRefinePreview()}
              >
                {refineBusy ? "Preparing…" : "Preview Changes"}
              </Button>
            ) : (
              <>
                <Button
                  compact
                  variant="primary"
                  disabled={refineBusy}
                  data-testid="project-wiki-refine-apply"
                  onClick={() => void runRefineApply()}
                >
                  {refineBusy ? "Applying…" : "Apply Refinement"}
                </Button>
                <Button
                  compact
                  variant="ghost"
                  disabled={refineBusy}
                  data-testid="project-wiki-refine-modify"
                  onClick={() => setRefinePreview(null)}
                >
                  Modify Instruction
                </Button>
              </>
            )}
            <Button
              compact
              variant="ghost"
              disabled={refineBusy}
              data-testid="project-wiki-refine-cancel"
              onClick={() => setRefineOpen(false)}
            >
              Cancel
            </Button>
          </div>
        </>
      ) : (
        <>
          <h4 style={{ marginTop: 0 }}>Wiki refined</h4>
          <ul data-testid="project-wiki-refine-result">
            {(refineResult.lines.length ? refineResult.lines : ["Refinement applied."]).map((line) => (
              <li key={line}>{line}</li>
            ))}
          </ul>
          <div className="row" style={{ gap: "0.35rem", flexWrap: "wrap" }}>
            <Button
              compact
              variant="ghost"
              data-testid="project-wiki-refine-review"
              onClick={() => {
                setRefineOpen(false);
                setManualBump((n) => n + 1);
              }}
            >
              Review Changes
            </Button>
            <Button
              compact
              variant="ghost"
              disabled={refineBusy}
              data-testid="project-wiki-refine-undo"
              onClick={() => void runRefineUndo()}
            >
              Undo
            </Button>
          </div>
        </>
      )}
    </div>
  ) : null;

  // Small persistent beta disclaimer with a subtle Refine Wiki link.
  const wikiFooter = (
    <p
      className="muted"
      data-testid="project-wiki-disclaimer"
      style={{ fontSize: "0.78rem", marginTop: "1rem", opacity: 0.8 }}
    >
      Co-Director can make mistakes. Adept UI is currently in beta. Review and edit important project
      details.{" "}
      <button
        type="button"
        data-testid="project-wiki-disclaimer-refine"
        onClick={() => openRefine()}
        style={{
          background: "none",
          border: "none",
          color: "var(--accent, #6cb6ff)",
          cursor: "pointer",
          padding: 0,
          fontSize: "inherit",
          textDecoration: "underline",
        }}
      >
        Refine Wiki
      </button>
    </p>
  );

  const hasCompiled = Boolean(wiki.compiledPages && wiki.compiledPages.length);

  if (!wiki.hasContent && populated.length === 0 && !hasCompiled) {
    return (
      <div data-testid="codirector-project-wiki-shell">
        {wikiActions}
        {reorgPanel}
        {refinePanel}
        {reorgProgress}
        {reorgResult}
        {actionMessage ? (
          <p className="muted" data-testid="project-wiki-action-message">
            {actionMessage}
          </p>
        ) : null}
        {diagnosticSummary ? (
          <p className="muted" data-testid="project-wiki-diagnostic-summary">
            {diagnosticSummary}
          </p>
        ) : null}
        {wikiUiMessage ? (
          <p className="muted" data-testid="project-wiki-ui-message">
            {wikiUiMessage}{" "}
            {showRefreshHint ? (
              <Button compact variant="ghost" data-testid="project-wiki-refresh" onClick={() => setManualBump((n) => n + 1)}>
                Refresh Wiki
              </Button>
            ) : null}
            {showRetryHint ? (
              <span data-testid="project-wiki-retry-hint"> Retry documentation from the conversation.</span>
            ) : null}
          </p>
        ) : null}
        <CoDirectorEmptyState
          testId="project-wiki-empty"
          title="Project Wiki"
          description={
            wiki.emptyState ||
            "Learning in progress… nothing is treated as canon without support from your conversation. You can rebuild from the conversation anytime."
          }
        />
        {wikiFooter}
      </div>
    );
  }

  if (hasCompiled) {
    return (
      <div className="codirector-project-wiki" data-testid="codirector-project-wiki">
        {wikiActions}
        {reorgPanel}
        {refinePanel}
        {reorgProgress}
        {reorgResult}
        {actionMessage ? (
          <p className="muted" data-testid="project-wiki-action-message">
            {actionMessage}
          </p>
        ) : null}
        <CompiledWikiReader
          wiki={wiki}
          onOpenCasting={onOpenCasting}
          onPageChange={(page) =>
            setCurrentPage(page ? { pageId: page.pageId, pageType: page.pageType, title: page.title } : null)
          }
          onRefineStorySummary={async () => {
            if (storySummaryBusy) return;
            setStorySummaryBusy(true);
            setActionMessage("Refining Story Summary with Co-Director…");
            try {
              await api.refineCoDirectorStorySummary(projectId);
              setActionMessage("Story Summary refined.");
              setManualBump((n) => n + 1);
            } catch (err) {
              setActionMessage(`Refine failed: ${err instanceof Error ? err.message : String(err)}`);
            } finally {
              setStorySummaryBusy(false);
            }
          }}
          onDevelopStory={() => {
            setActionMessage("Add more story details in chat — Co-Director will expand the summary automatically.");
          }}
          onCorrect={(page) => {
            setCurrentPage({ pageId: page.pageId, pageType: page.pageType, title: page.title });
            openRefine();
          }}
        />
        {(() => {
          const se = wiki.storyEntries;
          if (!se?.length) return null;
          return (
            <div className="wiki-section" data-testid="wiki-story-entries">
              <h3>Story</h3>
              {se.map((entry, i) => (
                <details key={entry.entryId || i} className="wiki-story-entry" data-testid={`wiki-story-entry-${i}`}>
                  <summary className="wiki-story-entry__title">
                    {entry.title || "Untitled"}
                    {entry.entryType !== "project_story" && entry.entryType ? (
                      <span className="wiki-story-entry__type">({entry.entryType})</span>
                    ) : null}
                  </summary>
                  {entry.logline && (
                    <div className="wiki-story-entry__section">
                      <strong>Logline</strong>
                      <p>{stripHtml(entry.logline)}</p>
                    </div>
                  )}
                  {entry.shortSummary && (
                    <div className="wiki-story-entry__section">
                      <strong>Short Summary</strong>
                      <p>{stripHtml(entry.shortSummary)}</p>
                    </div>
                  )}
                  {entry.longSummary && (
                    <div className="wiki-story-entry__section">
                      <strong>Long Summary</strong>
                      <p>{stripHtml(entry.longSummary)}</p>
                    </div>
                  )}
                </details>
              ))}
            </div>
          );
        })()}
        {(() => {
          const cp = wiki.characterProfiles;
          if (!cp?.length) return null;
          return (
            <div className="wiki-section" data-testid="wiki-character-profiles">
              <h3>Characters</h3>
              <div className="wiki-character-grid">
                {cp.map((char, i) => (
                  <div key={char.profileId || i} className="wiki-character-card" data-testid={`wiki-character-card-${i}`}>
                    <div className="wiki-character-card__header">
                      {char.approvedCastingImageAssetId ? (
                        <img
                          src={`/api/assets/${char.approvedCastingImageAssetId}/file`}
                          alt={char.name}
                          className="wiki-character-card__image"
                          onError={(e) => { (e.target as HTMLImageElement).style.display = "none"; }}
                        />
                      ) : (
                        <div className="wiki-character-card__placeholder">
                          <span>{char.name?.charAt(0)?.toUpperCase() || "?"}</span>
                        </div>
                      )}
                      <div className="wiki-character-card__info">
                        <h4>{char.name}</h4>
                        {char.role && <span className="wiki-character-card__role">{char.role}</span>}
                      </div>
                    </div>
                    {char.description && (
                      <p className="wiki-character-card__description">{char.description}</p>
                    )}
                    {char.personality?.keywords?.length > 0 && (
                      <div className="wiki-character-card__keywords">
                        {(char.personality as any).keywords.map((kw: string, ki: number) => (
                          <span key={ki} className="wiki-character-card__keyword">{kw}</span>
                        ))}
                      </div>
                    )}
                    {char.apparentAge || char.speciesOrType ? (
                      <div className="wiki-character-card__details">
                        {char.apparentAge && <span>Age: {char.apparentAge}</span>}
                        {char.speciesOrType && <span>Species: {char.speciesOrType}</span>}
                      </div>
                    ) : null}
                    <div className="wiki-character-card__actions">
                      <button type="button" className="ghost" onClick={() => onGoTab?.("characters", { characterId: char.profileId })}>
                        Open Character
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          );
        })()}
      {(wiki.suggestedCharacters || []).length > 0 && (
        <div className="wiki-section" data-testid="wiki-suggested-characters">
          <details>
            <summary>Suggested Characters ({(wiki.suggestedCharacters || []).length})</summary>
            {(wiki.suggestedCharacters || []).map((sc, i) => (
              <p key={i} className="muted">
                &ldquo;{sc.suggestedName}&rdquo; &mdash; Create a Character Profile?
              </p>
            ))}
          </details>

        </div>
      )}
        {wikiFooter}
      </div>
    );
  }

  const tocNodes =
    wiki.professionalToc && wiki.professionalToc.length
      ? wiki.professionalToc
      : wiki.toc && wiki.toc.length
        ? wiki.toc.map((t) => ({ ...t, children: undefined as undefined }))
        : populated.map((s) => ({ key: s.key, label: s.label, count: s.count, children: undefined }));

  return (
    <div className="codirector-project-wiki" data-testid="codirector-project-wiki">
      {wikiActions}
      {reorgPanel}
      {refinePanel}
      {reorgProgress}
      {reorgResult}
      {actionMessage ? (
        <p className="muted" data-testid="project-wiki-action-message">
          {actionMessage}
        </p>
      ) : null}
      {diagnosticSummary ? (
        <p className="muted" data-testid="project-wiki-diagnostic-summary">
          {diagnosticSummary}
        </p>
      ) : null}
      {wikiUiMessage ? (
        <p className="muted" data-testid="project-wiki-ui-message">
          {wikiUiMessage}{" "}
          {showRefreshHint || persistenceOk ? (
            <Button compact variant="ghost" data-testid="project-wiki-refresh" onClick={() => setManualBump((n) => n + 1)}>
              Refresh Wiki
            </Button>
          ) : null}
        </p>
      ) : null}
      <nav
        className="codirector-content-card codirector-project-wiki-toc"
        data-testid="project-wiki-toc"
        aria-label="Wiki table of contents"
      >
        <div className="row" style={{ justifyContent: "space-between", alignItems: "center" }}>
          <p className="eyebrow" style={{ margin: 0 }}>
            Table of Contents
          </p>
          <Button
            variant="ghost"
            compact
            data-testid="project-wiki-toc-toggle"
            onClick={() => {
              setTocOpen((v) => {
                const next = !v;
                try {
                  localStorage.setItem(tocExpandedKey(projectId), next ? "1" : "0");
                } catch {
                  /* ignore */
                }
                return next;
              });
            }}
          >
            {tocOpen ? "Hide" : "Show"}
          </Button>
        </div>
        {tocOpen ? (
          <ul style={{ listStyle: "none", padding: 0, margin: "0.5rem 0 0" }}>
            {tocNodes.map((s) => (
              <li key={s.key} style={{ marginBottom: "0.35rem" }}>
                <a
                  href={`#wiki-section-${s.key}`}
                  data-testid={`project-wiki-toc-${s.key}`}
                  onClick={(e) => {
                    e.preventDefault();
                    const legacy =
                      {
                        projectOverview: "knownDetails",
                        story: "creativeFoundation",
                        characters: "characters",
                        episodesAndScenes: "storyAndEpisodes",
                        worldAndLore: "worldAndSetting",
                        locationsAndSets: "worldAndSetting",
                        timelineAndContinuity: "storyAndEpisodes",
                        visualDevelopment: "visualIdentity",
                        audioAndPerformance: "creativeFoundation",
                        scriptsAndDevelopment: "productionDecisions",
                        production: "productionDecisions",
                        references: "references",
                      }[s.key] || s.key;
                    document.getElementById(`wiki-section-${legacy}`)?.scrollIntoView({ behavior: "smooth" });
                  }}
                >
                  {s.label} ({s.count})
                </a>
                {"children" in s && Array.isArray(s.children) && s.children.length ? (
                  <ul style={{ listStyle: "none", paddingLeft: "0.85rem", margin: "0.2rem 0 0" }} data-testid={`project-wiki-toc-children-${s.key}`}>
                    {s.children.slice(0, 12).map((child) => (
                      <li key={String(child.id || child.label)} style={{ fontSize: "0.8rem", marginBottom: "0.15rem" }}>
                        <button
                          type="button"
                          className="codirector-wiki-toc-entity"
                          data-testid={child.id ? `project-wiki-toc-entity-${child.id}` : undefined}
                          data-canon={child.canonState || "INFERRED"}
                          onClick={() => {
                            if (child.id) {
                              setSelectedEntryId(String(child.id));
                              document.getElementById(`wiki-entry-${child.id}`)?.scrollIntoView({ behavior: "smooth", block: "nearest" });
                            }
                          }}
                          style={{
                            background: "transparent",
                            border: "none",
                            padding: 0,
                            color: "inherit",
                            cursor: child.id ? "pointer" : "default",
                            textAlign: "left",
                          }}
                        >
                          <span>{child.label}</span>
                          {child.canonState ? (
                            <span
                              className="codirector-project-wiki-entry-state"
                              data-testid={`wiki-canon-badge-${String(child.canonState).toLowerCase()}`}
                              style={{ marginLeft: "0.35rem", fontSize: "0.7rem" }}
                            >
                              {child.canonState}
                            </span>
                          ) : null}
                        </button>
                      </li>
                    ))}
                  </ul>
                ) : null}
              </li>
            ))}
          </ul>
        ) : null}
      </nav>
      <div className="codirector-content-card">
        <div className="row" style={{ justifyContent: "space-between", alignItems: "center" }}>
          <p className="eyebrow">Overview</p>
          <div style={{ position: "relative" }}>
            <Button variant="ghost" compact data-testid="project-wiki-export-trigger" onClick={() => setExportOpen((v) => !v)}>
              Export
            </Button>
            {exportOpen ? (
              <div className="codirector-action-card" style={{ position: "absolute", right: 0, top: "2.2rem", zIndex: 3, minWidth: "12rem" }}>
                <div className="row">
                  <Button variant="ghost" compact data-testid="project-wiki-export-pdf" onClick={() => setExportFormat("pdf")}>
                    Export as PDF
                  </Button>
                  <Button variant="ghost" compact data-testid="project-wiki-export-html" onClick={() => setExportFormat("html")}>
                    Export as Offline HTML
                  </Button>
                </div>
              </div>
            ) : null}
          </div>
        </div>
        <h3 style={{ marginTop: 0 }}>{wiki.title}</h3>
        <p>{wiki.overview || "Your project notes are beginning to take shape."}</p>
      </div>
      {exportOpen ? (
        <div className="codirector-action-card" role="dialog" aria-label="Export Project Wiki" data-testid="project-wiki-export-dialog">
          <h3>Export Project Wiki</h3>
          <p className="muted">Choose what to include in your export.</p>
          <label>
            Export title
            <input
              value={exportPrefs.exportTitle}
              onChange={(e) => updatePrefs({ exportTitle: e.target.value })}
              placeholder={wiki.title}
            />
          </label>
          <label>
            Size mode
            <select value={exportPrefs.sizeMode} onChange={(e) => updatePrefs({ sizeMode: e.target.value as ExportPrefs["sizeMode"] })}>
              <option value="optimized">Optimized</option>
              <option value="original">Original Quality</option>
              <option value="wiki_only">Wiki Only</option>
              <option value="text_only">Text Only</option>
            </select>
          </label>
          <div className="codirector-project-wiki-export-grid">
            <label><input type="checkbox" checked={exportPrefs.includeCover} onChange={(e) => updatePrefs({ includeCover: e.target.checked })} /> Cover page</label>
            <label><input type="checkbox" checked={exportPrefs.includeToc} onChange={(e) => updatePrefs({ includeToc: e.target.checked })} /> Table of contents</label>
            <label><input type="checkbox" checked={exportPrefs.includeOpenQuestions} onChange={(e) => updatePrefs({ includeOpenQuestions: e.target.checked })} /> Open questions</label>
            <label><input type="checkbox" checked={exportPrefs.includeUnresolved} onChange={(e) => updatePrefs({ includeUnresolved: e.target.checked })} /> Unresolved items</label>
            <label><input type="checkbox" checked={exportPrefs.includeImages} onChange={(e) => updatePrefs({ includeImages: e.target.checked })} /> Supporting images</label>
            <label><input type="checkbox" checked={exportPrefs.includeAudioVideo} onChange={(e) => updatePrefs({ includeAudioVideo: e.target.checked })} /> Audio and video</label>
            <label><input type="checkbox" checked={exportPrefs.includeProductionMetadata} onChange={(e) => updatePrefs({ includeProductionMetadata: e.target.checked })} /> Production metadata</label>
          </div>
          <label>
            Sections
            <select value={exportPrefs.sectionsMode} onChange={(e) => updatePrefs({ sectionsMode: e.target.value as ExportPrefs["sectionsMode"] })}>
              <option value="all">Current Wiki</option>
              <option value="selected">Selected sections</option>
            </select>
          </label>
          {exportPrefs.sectionsMode === "selected" ? (
            <div className="codirector-project-wiki-export-grid">
              {SECTION_ORDER.map((section) => {
                const checked = exportPrefs.selectedSections.includes(String(section.key));
                return (
                  <label key={section.key}>
                    <input
                      type="checkbox"
                      checked={checked}
                      onChange={(e) =>
                        updatePrefs({
                          selectedSections: e.target.checked
                            ? [...exportPrefs.selectedSections, String(section.key)]
                            : exportPrefs.selectedSections.filter((item) => item !== String(section.key)),
                        })
                      }
                    />
                    {section.label}
                  </label>
                );
              })}
            </div>
          ) : null}
          <div className="row">
            <Button variant="ghost" compact onClick={() => setExportOpen(false)}>
              Cancel
            </Button>
            <Button
              variant="primary"
              compact
              disabled={exportBusy}
              data-testid={`project-wiki-run-export-${exportFormat}`}
              onClick={() => void runExport(exportFormat)}
            >
              {exportBusy ? "Exporting…" : exportFormat === "pdf" ? "Export as PDF" : "Export as Offline HTML"}
            </Button>
          </div>
        </div>
      ) : null}
      <div
        className="codirector-project-wiki-layout"
        style={{ display: "grid", gridTemplateColumns: selectedEntry ? "minmax(0, 1fr) 14rem" : "1fr", gap: "0.75rem" }}
      >
        <div>{sections}</div>
        {selectedEntry ? (
          <aside
            className="codirector-content-card"
            data-testid="project-wiki-context-panel"
            style={{ alignSelf: "start", position: "sticky", top: "0.5rem" }}
          >
            <p className="eyebrow" style={{ marginTop: 0 }}>
              Note details
            </p>
            <p data-testid="project-wiki-context-state">
              Status: {stateLabel(selectedEntry.entry)}
              {selectedEntry.entry.inferred === true
                ? " (Inferred)"
                : selectedEntry.entry.inferred === false
                  ? " (Confirmed)"
                  : ""}
            </p>
            <p className="muted" data-testid="project-wiki-context-section">
              Section: {selectedEntry.sectionKey}
            </p>
            {selectedEntry.entry.sourceMessageId ? (
              <p className="muted" data-testid="project-wiki-context-source">
                Source: conversation note
              </p>
            ) : (
              <p className="muted">Source: project library / notes</p>
            )}
            <p className="muted" data-testid="project-wiki-context-updated">
              Last wiki update: {wiki.updatedAt || "—"}
            </p>
            <Button compact variant="ghost" onClick={() => setSelectedEntryId(null)}>
              Close
            </Button>
          </aside>
        ) : null}
      </div>
      {(wiki.storyEntries || []).length > 0 && (
        <div className="wiki-section" data-testid="wiki-story-entries">
          <h3>Story</h3>
          {(wiki.storyEntries || []).map((entry, i) => (
            <details key={entry.entryId || i} className="wiki-story-entry" data-testid={`wiki-story-entry-${i}`}>
              <summary className="wiki-story-entry__title">
                {entry.title || "Untitled"}
                {entry.entryType !== "project_story" && entry.entryType ? (
                  <span className="wiki-story-entry__type">({entry.entryType})</span>
                ) : null}
              </summary>
              {entry.logline && (
                <div className="wiki-story-entry__section">
                  <strong>Logline</strong>
                  <p>{entry.logline}</p>
                </div>
              )}
              {entry.shortSummary && (
                <div className="wiki-story-entry__section">
                  <strong>Short Summary</strong>
                  <p>{entry.shortSummary}</p>
                </div>
              )}
              {entry.longSummary && (
                <div className="wiki-story-entry__section">
                  <strong>Long Summary</strong>
                  <p>{entry.longSummary}</p>
                </div>
              )}
            </details>
          ))}
        </div>
      )}
      {(wiki.characterProfiles || []).length > 0 && (
        <div className="wiki-section" data-testid="wiki-character-profiles">
          <h3>Characters</h3>
          <div className="wiki-character-grid">
            {(wiki.characterProfiles || []).map((char, i) => (
              <div key={char.profileId || i} className="wiki-character-card" data-testid={`wiki-character-card-${i}`}>
                <div className="wiki-character-card__header">
                  {char.approvedCastingImageAssetId ? (
                    <img
                      src={`/api/assets/${char.approvedCastingImageAssetId}/file`}
                      alt={char.name}
                      className="wiki-character-card__image"
                      onError={(e) => { (e.target as HTMLImageElement).style.display = "none"; }}
                    />
                  ) : (
                    <div className="wiki-character-card__placeholder">
                      <span>{char.name?.charAt(0)?.toUpperCase() || "?"}</span>
                    </div>
                  )}
                  <div className="wiki-character-card__info">
                    <h4>{char.name}</h4>
                    {char.role && <span className="wiki-character-card__role">{char.role}</span>}
                  </div>
                </div>
                {char.description && (
                  <p className="wiki-character-card__description">{char.description}</p>
                )}
                {(char.personality as any)?.keywords?.length > 0 && (
                  <div className="wiki-character-card__keywords">
                    {(char.personality as any).keywords.map((kw: string, ki: number) => (
                      <span key={ki} className="wiki-character-card__keyword">{kw}</span>
                    ))}
                  </div>
                )}
                {char.apparentAge || char.speciesOrType ? (
                  <div className="wiki-character-card__details">
                    {char.apparentAge && <span>Age: {char.apparentAge}</span>}
                    {char.speciesOrType && <span>Species: {char.speciesOrType}</span>}
                  </div>
                ) : null}
                <div className="wiki-character-card__actions">
                  <button type="button" className="ghost" onClick={() => onGoTab?.("characters", { characterId: char.profileId })}>
                    Open Character
                  </button>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
      {(() => {
        const sc = wiki.suggestedCharacters;
        if (!sc?.length) return null;
        return (
          <div className="wiki-section" data-testid="wiki-suggested-characters">
            <details>
              <summary>Suggested Characters ({sc.length})</summary>
              {sc.map((s, i) => (
                <p key={i} className="muted">
                  &ldquo;{s.suggestedName}&rdquo; &mdash; Create a Character Profile?
                </p>
              ))}
            </details>
          </div>
        );
      })()}
      {wikiFooter}
    </div>
  );
}

