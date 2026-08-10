import { useEditor, EditorContent } from "@tiptap/react";
import StarterKit from "@tiptap/starter-kit";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { api } from "../../api";
import type { Project } from "../../types";
import type { EditorTab } from "../../workspacePrefs";
import { docJsonToElements, elementsToDocJson, ScreenplayKeys, ScreenplayParagraph } from "./screenplayExtension";
import type { SaveState, ScriptDocument, StudioView, WritingMode } from "./types";
import "./scriptwriter.css";

type NavScene = {
  sceneHeadingId?: string;
  sceneNumber?: string;
  heading?: string;
  location?: string;
  timeOfDay?: string;
  estimatedPages?: number;
  productionStatus?: string;
};

export function ScriptwriterStudio({
  project,
  onGo,
  onActiveDocumentId,
}: {
  project: Project;
  onChange?: () => Promise<void>;
  onGo: (tab: EditorTab) => void;
  onActiveDocumentId?: (documentId: string | undefined) => void;
}) {
  const [doc, setDoc] = useState<ScriptDocument | null>(null);
  const [nav, setNav] = useState<NavScene[]>([]);
  const [stats, setStats] = useState<Record<string, unknown>>({});
  const [continuity, setContinuity] = useState<Array<Record<string, unknown>>>([]);
  const [bibleCandidates, setBibleCandidates] = useState<Array<Record<string, unknown>>>([]);
  const [bibleProposals, setBibleProposals] = useState<Array<Record<string, unknown>>>([]);
  const [revisions, setRevisions] = useState<Array<Record<string, unknown>>>([]);
  const [saveState, setSaveState] = useState<SaveState>("saved");
  const [mode, setMode] = useState<WritingMode>("standard");
  const [view, setView] = useState<StudioView>("script");
  const [message, setMessage] = useState<string | null>(null);
  const [analysis, setAnalysis] = useState<Record<string, unknown> | null>(null);
  const [proposal, setProposal] = useState<Record<string, unknown> | null>(null);
  const [timelinePrep, setTimelinePrep] = useState<Record<string, unknown> | null>(null);
  const [activeSceneId, setActiveSceneId] = useState<string | null>(null);
  const [commandOpen, setCommandOpen] = useState(false);
  const [commandQuery, setCommandQuery] = useState("");
  const [importText, setImportText] = useState("");
  const [findText, setFindText] = useState("");
  const [replaceText, setReplaceText] = useState("");
  const [compareA, setCompareA] = useState("");
  const [compareB, setCompareB] = useState("");
  const [compareResult, setCompareResult] = useState<unknown[] | null>(null);
  const [codirectorOpen, setCodirectorOpen] = useState(true);
  const saveTimer = useRef<number | null>(null);
  const hydrating = useRef(false);

  const applyBundle = useCallback(
    (bundle: Awaited<ReturnType<typeof api.scriptwriter.studio>>) => {
      const d = bundle.document as unknown as ScriptDocument;
      setDoc(d);
      onActiveDocumentId?.(d.id);
      setNav((bundle.navigator || []) as NavScene[]);
      setStats(bundle.stats || {});
      setContinuity(bundle.continuity || []);
      setBibleCandidates(bundle.bibleCandidates || []);
      setRevisions(bundle.revisions || []);
      if (bundle.recovery) setSaveState("recovery_available");
    },
    [onActiveDocumentId],
  );

  useEffect(() => () => onActiveDocumentId?.(undefined), [onActiveDocumentId]);

  const load = useCallback(async () => {
    const bundle = await api.scriptwriter.studio(project.id);
    applyBundle(bundle);
    return bundle.document as unknown as ScriptDocument;
  }, [project.id, applyBundle]);

  const editor = useEditor({
    extensions: [
      StarterKit.configure({ paragraph: false }),
      ScreenplayParagraph,
      ScreenplayKeys,
    ],
    content: elementsToDocJson([]),
    onUpdate: ({ editor: ed }) => {
      if (hydrating.current || !doc) return;
      setSaveState("unsaved");
      if (saveTimer.current) window.clearTimeout(saveTimer.current);
      saveTimer.current = window.setTimeout(() => {
        void (async () => {
          try {
            setSaveState("saving");
            const elements = docJsonToElements(ed.getJSON() as { content?: Array<Record<string, unknown>> });
            const res = await api.scriptwriter.autosave(project.id, doc.id, {
              elements,
              expectedRevision: doc.revision,
            });
            setDoc(res.document as unknown as ScriptDocument);
            setSaveState((res.saveState as SaveState) || "saved");
          } catch (e) {
            setSaveState("save_failed");
            setMessage(e instanceof Error ? e.message : "Save failed");
          }
        })();
      }, 700);
    },
  });

  useEffect(() => {
    void load()
      .then((d) => {
        if (!editor) return;
        hydrating.current = true;
        editor.commands.setContent(elementsToDocJson(d.elements || []));
        hydrating.current = false;
      })
      .catch((e: Error) => setMessage(e.message));
  }, [load, editor]);

  useEffect(() => {
    const onKey = (ev: KeyboardEvent) => {
      if ((ev.ctrlKey || ev.metaKey) && ev.key.toLowerCase() === "k") {
        ev.preventDefault();
        setCommandOpen(true);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  const refreshNav = async () => {
    const bundle = await api.scriptwriter.studio(project.id);
    applyBundle(bundle);
  };

  const syncEditorFromDoc = (d: ScriptDocument) => {
    if (!editor) return;
    hydrating.current = true;
    editor.commands.setContent(elementsToDocJson(d.elements || []));
    hydrating.current = false;
  };

  const insertScene = async () => {
    if (!doc) return;
    const res = await api.scriptwriter.insertScene(project.id, doc.id, {
      heading: "INT. NEW LOCATION - DAY",
    });
    const d = res.document as unknown as ScriptDocument;
    setDoc(d);
    syncEditorFromDoc(d);
    await refreshNav();
  };

  const undo = async () => {
    if (!doc) return;
    const res = await api.scriptwriter.undo(project.id, doc.id);
    const d = res.document as unknown as ScriptDocument;
    setDoc(d);
    syncEditorFromDoc(d);
    await refreshNav();
  };

  const analyze = async () => {
    if (!doc || !activeSceneId) {
      setMessage("Select a scene in the navigator first.");
      return;
    }
    const res = await api.scriptwriter.analyzeScene(project.id, doc.id, activeSceneId);
    setAnalysis(res.analysis);
    setProposal({
      op: "replace",
      elementId: activeSceneId,
      text: String((res.analysis as { scenePurpose?: string }).scenePurpose || ""),
      previewOnly: true,
      kind: "analyze_scene",
    });
  };

  const acceptDialogueProposal = async () => {
    if (!doc || !activeSceneId) return;
    // Find first dialogue in scene via elements
    const els = doc.elements || [];
    let inScene = false;
    let dialogueId: string | null = null;
    let dialogueText = "";
    for (const el of els) {
      if (el.id === activeSceneId) inScene = true;
      else if (el.type === "scene_heading" && inScene) break;
      if (inScene && el.type === "dialogue") {
        dialogueId = el.id;
        dialogueText = el.text;
        break;
      }
    }
    if (!dialogueId) {
      setMessage("No dialogue in selected scene to revise.");
      return;
    }
    const revised = dialogueText.replace(/\s+/g, " ").trim() + (dialogueText.endsWith(".") ? "" : ".");
    const pending = {
      op: "replace",
      elementId: dialogueId,
      text: revised,
      note: "Co-Director proposed dialogue polish — requires accept.",
    };
    setProposal(pending);
  };

  const applyProposal = async () => {
    if (!doc || !proposal || proposal.previewOnly) {
      setMessage("Proposal is analysis-only or missing.");
      return;
    }
    const res = await api.scriptwriter.applyProposal(project.id, doc.id, proposal);
    const d = res.document as unknown as ScriptDocument;
    setDoc(d);
    syncEditorFromDoc(d);
    setProposal(null);
    setMessage("Co-Director proposal applied via transaction.");
  };

  const prepareTimeline = async () => {
    if (!doc || !activeSceneId) return;
    const res = await api.scriptwriter.prepareTimeline(project.id, doc.id, activeSceneId);
    setTimelinePrep(res.proposal);
  };

  const applyTimeline = async () => {
    if (!doc || !activeSceneId || !timelinePrep) return;
    await api.scriptwriter.applyTimelineMetadata(project.id, doc.id, activeSceneId, timelinePrep);
    setMessage("Timeline preparation metadata applied (no clips auto-generated).");
    await refreshNav();
  };

  const createRevision = async () => {
    if (!doc) return;
    const res = await api.scriptwriter.createRevision(project.id, doc.id, {
      name: `Blue ${new Date().toISOString().slice(0, 10)}`,
      color: "Blue",
    });
    setDoc(res.document as unknown as ScriptDocument);
    await refreshNav();
    setMessage("Revision set created.");
  };

  const runCompare = async () => {
    if (!doc || !compareA || !compareB) return;
    const res = await api.scriptwriter.compareRevisions(project.id, doc.id, compareA, compareB);
    setCompareResult(res.changed || []);
    setView("compare");
  };

  const exportFountain = async () => {
    if (!doc) return;
    const res = await api.scriptwriter.exportFountain(project.id, doc.id);
    const blob = new Blob([res.fountain], { type: "text/plain" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `${doc.title || "script"}.fountain`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const exportPdf = async () => {
    if (!doc) return;
    const res = await api.scriptwriter.exportPdf(project.id, doc.id);
    setMessage(res.ok ? `PDF exported: ${res.path}` : String(res.error?.message || "PDF export failed"));
  };

  const doImport = async () => {
    if (!doc || !importText.trim()) return;
    const res = await api.scriptwriter.importText(project.id, doc.id, importText);
    const d = res.document as unknown as ScriptDocument;
    setDoc(d);
    syncEditorFromDoc(d);
    setImportText("");
    await refreshNav();
  };

  const convertBeats = async () => {
    if (!doc) return;
    const res = await api.scriptwriter.convertOutline(project.id, doc.id, [
      { title: "OPENING IMAGE", description: "Establish world and tone." },
      { title: "INCITING INCIDENT", description: "Disrupt the status quo." },
    ]);
    const d = res.document as unknown as ScriptDocument;
    setDoc(d);
    syncEditorFromDoc(d);
    await refreshNav();
  };

  const linkScene = async () => {
    if (!doc || !activeSceneId) return;
    const sceneId = project.scenes[0]?.id;
    if (!sceneId) {
      setMessage("No project scene available to link.");
      return;
    }
    await api.scriptwriter.linkScene(project.id, doc.id, activeSceneId, sceneId);
    setMessage(`Linked script scene to project scene ${sceneId.slice(0, 8)}`);
    await refreshNav();
  };

  const runSearchReplace = async () => {
    if (!doc || !findText) return;
    const res = await api.scriptwriter.searchReplace(project.id, doc.id, {
      find: findText,
      replace: replaceText,
    });
    const d = res.document as unknown as ScriptDocument;
    setDoc(d);
    syncEditorFromDoc(d);
    setMessage(`Search/replace applied for “${findText}”.`);
  };

  const proposeBible = async () => {
    if (!doc) return;
    const res = await api.scriptwriter.proposeBible(project.id, doc.id);
    setBibleProposals(res.proposals || []);
    setMessage(`${(res.proposals || []).length} Bible proposal(s) created (not auto-applied).`);
  };

  const commands = useMemo(
    () =>
      [
        { id: "insert", label: "Insert scene", run: () => void insertScene() },
        { id: "undo", label: "Undo last transaction", run: () => void undo() },
        { id: "analyze", label: "Analyze current scene", run: () => void analyze() },
        { id: "focus", label: "Toggle Focus Mode", run: () => setMode((m) => (m === "focus" ? "standard" : "focus")) },
        { id: "revision", label: "Create revision", run: () => void createRevision() },
        { id: "timeline", label: "Prepare scene for Timeline", run: () => void prepareTimeline() },
        { id: "export-f", label: "Export Fountain", run: () => void exportFountain() },
        { id: "export-p", label: "Export PDF", run: () => void exportPdf() },
        { id: "cd", label: "Open Co-Director panel", run: () => setCodirectorOpen(true) },
      ].filter((c) => c.label.toLowerCase().includes(commandQuery.toLowerCase())),
    [commandQuery, doc, activeSceneId],
  );

  const shellClass = [
    "sw-studio",
    mode === "focus" || mode === "distraction-free" ? "is-focus" : "",
    mode === "distraction-free" ? "is-distraction" : "",
    mode === "dialogue" ? "is-dialogue" : "",
  ]
    .filter(Boolean)
    .join(" ");

  return (
    <div className={shellClass} data-testid="scriptwriter-studio">
      <div className="sw-toolbar" data-testid="scriptwriter-toolbar">
        <span className="sw-toolbar__title">{doc?.title || "Scriptwriter Studio"}</span>
        <button type="button" className={view === "script" ? "primary" : "ghost"} onClick={() => setView("script")}>
          Script
        </button>
        <button type="button" className={view === "outline" ? "primary" : "ghost"} onClick={() => setView("outline")}>
          Outline
        </button>
        <button type="button" className={view === "cards" ? "primary" : "ghost"} onClick={() => setView("cards")}>
          Cards
        </button>
        <button type="button" className={view === "beats" ? "primary" : "ghost"} onClick={() => setView("beats")}>
          Beats
        </button>
        <button type="button" className={view === "compare" ? "primary" : "ghost"} onClick={() => setView("compare")}>
          Compare
        </button>
        <button type="button" className={view === "storyboard" ? "primary" : "ghost"} onClick={() => setView("storyboard")}>
          Storyboard
        </button>
        <button type="button" className="ghost" data-testid="scriptwriter-insert-scene" onClick={() => void insertScene()}>
          Insert scene
        </button>
        <button type="button" className="ghost" data-testid="scriptwriter-undo" onClick={() => void undo()}>
          Undo
        </button>
        <button type="button" className="ghost" data-testid="scriptwriter-focus" onClick={() => setMode((m) => (m === "focus" ? "standard" : "focus"))}>
          Focus
        </button>
        <button type="button" className="ghost" onClick={() => setMode("dialogue")}>
          Dialogue focus
        </button>
        <button type="button" className="ghost" onClick={() => setMode("production")}>
          Production
        </button>
        <button type="button" className="ghost" data-testid="scriptwriter-command" onClick={() => setCommandOpen(true)}>
          Command
        </button>
        <button type="button" className="ghost" onClick={() => onGo("timeline")}>
          Timeline
        </button>
        <span className="sw-toolbar__save" data-testid="scriptwriter-save-state">
          {saveState.replace("_", " ")}
          {stats.pagesEstimated != null ? ` · ~${String(stats.pagesEstimated)} est. pages` : ""}
        </span>
      </div>

      <div className="sw-body">
        <aside className="sw-nav" data-testid="scriptwriter-navigator" aria-label="Script navigator">
          <p className="eyebrow">Scenes</p>
          {nav.map((s) => (
            <button
              key={s.sceneHeadingId}
              type="button"
              className={activeSceneId === s.sceneHeadingId ? "sw-nav__item is-active" : "sw-nav__item"}
              data-testid={`scriptwriter-nav-${s.sceneHeadingId}`}
              onClick={() => setActiveSceneId(s.sceneHeadingId || null)}
            >
              <strong>
                {s.sceneNumber || "—"} · {s.heading}
              </strong>
              <div className="muted">
                {s.location} {s.timeOfDay} · ~{s.estimatedPages}p · {s.productionStatus}
              </div>
            </button>
          ))}
          <p className="eyebrow" style={{ marginTop: "0.75rem" }}>
            Revisions
          </p>
          {revisions.map((r) => (
            <div key={String(r.id)} className="muted">
              {String(r.name)} ({String(r.color)})
            </div>
          ))}
        </aside>

        <main className="sw-page-wrap" data-testid="scriptwriter-page">
          {view === "script" ? (
            <div className="sw-page" aria-label="Screenplay page">
              <EditorContent editor={editor} data-testid="scriptwriter-editor" />
            </div>
          ) : null}
          {view === "cards" ? (
            <div className="sw-cards" data-testid="scriptwriter-cards">
              {nav.map((s) => (
                <div key={s.sceneHeadingId} className="sw-card">
                  <strong>
                    {s.sceneNumber} {s.heading}
                  </strong>
                  <p className="muted">
                    {s.location} · {s.productionStatus}
                  </p>
                </div>
              ))}
            </div>
          ) : null}
          {view === "outline" || view === "beats" ? (
            <div data-testid="scriptwriter-outline">
              <p className="eyebrow">{view === "beats" ? "Beat sheet" : "Outline"}</p>
              <ul>
                {nav.map((s) => (
                  <li key={s.sceneHeadingId}>
                    {s.sceneNumber}. {s.heading}
                  </li>
                ))}
              </ul>
              <button type="button" className="primary" data-testid="scriptwriter-convert-beats" onClick={() => void convertBeats()}>
                Convert sample beats to scenes
              </button>
            </div>
          ) : null}
          {view === "compare" ? (
            <div data-testid="scriptwriter-compare">
              <label>
                Revision A
                <select value={compareA} onChange={(e) => setCompareA(e.target.value)}>
                  <option value="">—</option>
                  {revisions.map((r) => (
                    <option key={String(r.id)} value={String(r.id)}>
                      {String(r.name)}
                    </option>
                  ))}
                </select>
              </label>
              <label>
                Revision B
                <select value={compareB} onChange={(e) => setCompareB(e.target.value)}>
                  <option value="">—</option>
                  {revisions.map((r) => (
                    <option key={String(r.id)} value={String(r.id)}>
                      {String(r.name)}
                    </option>
                  ))}
                </select>
              </label>
              <button type="button" onClick={() => void runCompare()}>
                Compare
              </button>
              <pre>{compareResult ? JSON.stringify(compareResult.slice(0, 20), null, 2) : "No comparison yet"}</pre>
            </div>
          ) : null}
          {view === "storyboard" ? (
            <div data-testid="scriptwriter-storyboard-view">
              <p className="eyebrow">Storyboard view</p>
              <p className="muted">
                Storyboard panels remain linked to legacy segments during migration. Open the dedicated Storyboard
                workspace for panel editing.
              </p>
              <button type="button" className="primary" onClick={() => onGo("script")}>
                Open Storyboard workspace
              </button>
            </div>
          ) : null}
        </main>

        <aside className="sw-inspector" data-testid="scriptwriter-inspector" aria-label="Script inspector">
          <p className="eyebrow">Inspector</p>
          <div className="row-actions">
            <button type="button" data-testid="scriptwriter-analyze" onClick={() => void analyze()}>
              Analyze scene
            </button>
            <button type="button" data-testid="scriptwriter-propose-dialogue" onClick={() => void acceptDialogueProposal()}>
              Propose dialogue polish
            </button>
            <button type="button" data-testid="scriptwriter-create-revision" onClick={() => void createRevision()}>
              Create revision
            </button>
            <button type="button" data-testid="scriptwriter-link-scene" onClick={() => void linkScene()}>
              Link to Scene
            </button>
            <button type="button" data-testid="scriptwriter-timeline-prep" onClick={() => void prepareTimeline()}>
              Prepare Timeline
            </button>
            <button type="button" data-testid="scriptwriter-export-fountain" onClick={() => void exportFountain()}>
              Export Fountain
            </button>
            <button type="button" data-testid="scriptwriter-export-pdf" onClick={() => void exportPdf()}>
              Export PDF
            </button>
          </div>

          {codirectorOpen ? (
            <div className="sw-proposal" data-testid="scriptwriter-codirector-panel">
              <strong>Co-Director</strong>
              <p className="muted">Proposals never auto-apply.</p>
              {analysis ? <pre style={{ whiteSpace: "pre-wrap" }}>{JSON.stringify(analysis, null, 2)}</pre> : null}
              {proposal ? (
                <>
                  <pre data-testid="scriptwriter-proposal">{JSON.stringify(proposal, null, 2)}</pre>
                  {!proposal.previewOnly ? (
                    <button type="button" className="primary" data-testid="scriptwriter-apply-proposal" onClick={() => void applyProposal()}>
                      Accept proposal
                    </button>
                  ) : (
                    <p className="muted">Analysis preview — no mutation.</p>
                  )}
                </>
              ) : null}
            </div>
          ) : null}

          {timelinePrep ? (
            <div className="sw-proposal" data-testid="scriptwriter-timeline-proposal">
              <strong>Timeline preparation</strong>
              <pre style={{ whiteSpace: "pre-wrap", fontSize: "0.7rem" }}>{JSON.stringify(timelinePrep, null, 2)}</pre>
              <button type="button" className="primary" data-testid="scriptwriter-timeline-apply" onClick={() => void applyTimeline()}>
                Apply metadata
              </button>
            </div>
          ) : null}

          <p className="eyebrow">Bible candidates</p>
          <ul data-testid="scriptwriter-bible-candidates">
            {bibleCandidates.map((c, i) => (
              <li key={i}>
                {String(c.kind)}: {String(c.name)}{" "}
                <button
                  type="button"
                  data-testid={`scriptwriter-bible-reject-${i}`}
                  onClick={() => setBibleCandidates((prev) => prev.filter((_, j) => j !== i))}
                >
                  Reject
                </button>
              </li>
            ))}
          </ul>
          <button type="button" className="primary" data-testid="scriptwriter-bible-propose" onClick={() => void proposeBible()}>
            Propose Bible updates
          </button>
          {bibleProposals.length ? (
            <pre data-testid="scriptwriter-bible-proposals">{JSON.stringify(bibleProposals, null, 2)}</pre>
          ) : null}
          <p className="muted">Proposals only — Production Bible never silent-writes.</p>

          <p className="eyebrow">Search / Replace</p>
          <input
            value={findText}
            onChange={(e) => setFindText(e.target.value)}
            placeholder="Find"
            data-testid="scriptwriter-find"
          />
          <input
            value={replaceText}
            onChange={(e) => setReplaceText(e.target.value)}
            placeholder="Replace"
            data-testid="scriptwriter-replace"
          />
          <button type="button" data-testid="scriptwriter-search-replace" onClick={() => void runSearchReplace()}>
            Replace all
          </button>

          <p className="eyebrow">Continuity</p>
          <ul>
            {continuity.slice(0, 5).map((c, i) => (
              <li key={i}>
                [{String(c.severity)}] {String(c.message)}
              </li>
            ))}
          </ul>

          <p className="eyebrow">Import Fountain</p>
          <textarea
            rows={4}
            value={importText}
            onChange={(e) => setImportText(e.target.value)}
            data-testid="scriptwriter-import-text"
            placeholder="Paste Fountain…"
          />
          <button type="button" data-testid="scriptwriter-import" onClick={() => void doImport()}>
            Import
          </button>
        </aside>
      </div>

      <div className="sw-status" data-testid="scriptwriter-status">
        <span>Rev {doc?.revision ?? "—"}</span>
        <span>Scenes {String(stats.scenes ?? nav.length)}</span>
        <span>Words {String(stats.words ?? "—")}</span>
        <span>Pagination: estimated</span>
        <span>Mode: {mode}</span>
        {message ? <span data-testid="scriptwriter-message">{message}</span> : null}
      </div>

      {commandOpen ? (
        <div className="sw-command" data-testid="scriptwriter-command-palette" role="dialog" aria-label="Command palette">
          <input
            autoFocus
            value={commandQuery}
            onChange={(e) => setCommandQuery(e.target.value)}
            placeholder="Search commands…"
            data-testid="scriptwriter-command-input"
          />
          <ul>
            {commands.map((c) => (
              <li key={c.id}>
                <button
                  type="button"
                  onClick={() => {
                    c.run();
                    setCommandOpen(false);
                    setCommandQuery("");
                  }}
                >
                  {c.label}
                </button>
              </li>
            ))}
          </ul>
          <button type="button" className="ghost" onClick={() => setCommandOpen(false)}>
            Close
          </button>
        </div>
      ) : null}
    </div>
  );
}
