import { useEditor, EditorContent } from "@tiptap/react";
import StarterKit from "@tiptap/starter-kit";
import Underline from "@tiptap/extension-underline";
import TextAlign from "@tiptap/extension-text-align";
import { useCallback, useEffect, useRef, useState } from "react";
import { api, ApiError } from "../../api";
import { StoryDocumentEditor, type StoryDocumentHandle } from "../story/StoryDocumentEditor";
import { defaultStoryTitle } from "../story/canonicalStory";
import type { Project } from "../../types";
import type { EditorTab } from "../../workspacePrefs";
import { IndentKeys, IndentParagraph } from "./richTextExtensions";
import { elementsToHtml, isBlankHtml } from "./legacyHtml";
import { sanitizeHtml } from "./sanitizeHtml";
import {
  conflictReloadState,
  RECOVERY_RESTORED_MESSAGE,
  RECOVERY_RESTORE_FAILED_MESSAGE,
  shouldOfferRecovery,
  type ScriptwriterBundle,
} from "./recovery";
import { resolveLinkSceneId } from "./sceneLink";
import { ScriptTitleEditor } from "./ScriptTitleEditor";
import type { SaveState, ScriptDocument, StudioView, WritingMode } from "./types";
import "./scriptwriter.css";

function resolveInitialHtml(doc: Partial<ScriptDocument> | null | undefined): string {
  if (doc?.contentHtml && !isBlankHtml(doc.contentHtml)) return doc.contentHtml;
  if (doc?.elements && doc.elements.length > 0) return elementsToHtml(doc.elements);
  return "<p></p>";
}

type NavScene = {
  sceneHeadingId?: string;
  sceneNumber?: string;
  heading?: string;
  location?: string;
  timeOfDay?: string;
  estimatedPages?: number;
  productionStatus?: string;
};

/**
 * Script Writer Standard — screenplay + native Story document.
 *
 * Script owns scenes, screenplay text, add/remove/reorder, revisions, and the
 * screenplay title. Story is a formatted project document on the same canvas;
 * it reads and writes the canonical story_entries row shared with Co-Director
 * Story Express. The Story button never leaves this workspace.
 */
export function ScriptwriterStudio({
  project,
  onActiveDocumentId,
  onActiveSceneChange,
}: {
  project: Project;
  onChange?: () => Promise<void>;
  onGo: (tab: EditorTab) => void;
  onActiveDocumentId?: (documentId: string | undefined) => void;
  /** Reports the selected script scene (sceneHeadingId) so Co-Director gains
   * current-scene awareness without manual tagging. */
  onActiveSceneChange?: (sceneHeadingId: string | null) => void;
}) {
  const [doc, setDoc] = useState<ScriptDocument | null>(null);
  const [nav, setNav] = useState<NavScene[]>([]);
  const [stats, setStats] = useState<Record<string, unknown>>({});
  const [continuity, setContinuity] = useState<Array<Record<string, unknown>>>([]);
  const [bibleCandidates, setBibleCandidates] = useState<Array<Record<string, unknown>>>([]);
  const [bibleProposals, setBibleProposals] = useState<Array<Record<string, unknown>>>([]);
  const [revisions, setRevisions] = useState<Array<Record<string, unknown>>>([]);
  const [saveState, setSaveState] = useState<SaveState>("saved");
  const [storySaveState, setStorySaveState] = useState<SaveState>("saved");
  const [storyTitle, setStoryTitle] = useState("");
  const storyHandleRef = useRef<StoryDocumentHandle | null>(null);
  const [mode, setMode] = useState<WritingMode>("standard");
  const [view, setView] = useState<StudioView>("script");
  const [message, setMessage] = useState<string | null>(null);
  const [analysis, setAnalysis] = useState<Record<string, unknown> | null>(null);
  const [proposal, setProposal] = useState<Record<string, unknown> | null>(null);
  const [timelinePrep, setTimelinePrep] = useState<Record<string, unknown> | null>(null);
  const [activeSceneId, setActiveSceneIdState] = useState<string | null>(null);
  // CDX-058: explicit project-scene selection for Link to Scene (no scenes[0]).
  const [linkSceneId, setLinkSceneId] = useState<string | null>(null);
  const [importText, setImportText] = useState("");
  const [findText, setFindText] = useState("");
  const [replaceText, setReplaceText] = useState("");
  const [compareA, setCompareA] = useState("");
  const [compareB, setCompareB] = useState("");
  const [compareResult, setCompareResult] = useState<unknown[] | null>(null);
  // Creator-First progressive disclosure: power tools live behind More tools.
  const [moreToolsOpen, setMoreToolsOpen] = useState(false);
  const saveTimer = useRef<number | null>(null);
  const hydrating = useRef(false);
  const latestRevisionRef = useRef<number | null>(null);
  const latestDocIdRef = useRef<string | null>(null);

  const setActiveSceneId = useCallback(
    (id: string | null) => {
      setActiveSceneIdState(id);
      onActiveSceneChange?.(id);
    },
    [onActiveSceneChange],
  );

  const applyBundle = useCallback(
    (bundle: Awaited<ReturnType<typeof api.scriptwriter.studio>>) => {
      const d = bundle.document as unknown as ScriptDocument;
      setDoc(d);
      latestRevisionRef.current = d.revision;
      latestDocIdRef.current = d.id;
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

  const setDocTracked = useCallback((d: ScriptDocument) => {
    setDoc(d);
    latestRevisionRef.current = d.revision;
    latestDocIdRef.current = d.id;
  }, []);

  useEffect(() => () => {
    onActiveDocumentId?.(undefined);
    onActiveSceneChange?.(null);
  }, [onActiveDocumentId, onActiveSceneChange]);

  const load = useCallback(async () => {
    const bundle = await api.scriptwriter.studio(project.id);
    applyBundle(bundle);
    return bundle.document as unknown as ScriptDocument;
  }, [project.id, applyBundle]);

  const editor = useEditor({
    extensions: [
      StarterKit.configure({ paragraph: false }),
      IndentParagraph,
      Underline,
      TextAlign.configure({ types: ["heading", "paragraph"] }),
      IndentKeys,
    ],
    content: "<p></p>",
    onUpdate: ({ editor: ed }) => {
      if (hydrating.current || !latestDocIdRef.current) return;
      setSaveState("unsaved");
      if (saveTimer.current) window.clearTimeout(saveTimer.current);
      saveTimer.current = window.setTimeout(() => {
        void (async () => {
          const docId = latestDocIdRef.current;
          if (!docId) return;
          try {
            setSaveState("saving");
            const html = sanitizeHtml(ed.getHTML());
            const res = await api.scriptwriter.autosave(project.id, docId, {
              html,
              expectedRevision: latestRevisionRef.current ?? undefined,
            });
            const d = res.document as unknown as ScriptDocument;
            setDocTracked(d);
            setSaveState((res.saveState as SaveState) || "saved");
          } catch (e) {
            if (e instanceof ApiError && e.status === 400 && (e.code === "SCRIPT_CONFLICT" || (e.message || "").includes("CONFLICT"))) {
              try {
                const fresh = await api.scriptwriter.studio(project.id);
                const d = fresh.document as unknown as ScriptDocument;
                setDocTracked(d);
                if (editor) {
                  hydrating.current = true;
                  editor.commands.setContent(resolveInitialHtml(d));
                  hydrating.current = false;
                }
                // CDX-055: the backend keeps the client's unsaved edit in the
                // recovery payload — surface the restore affordance instead of
                // silently dropping the in-progress edit.
                const reload = conflictReloadState(fresh as unknown as ScriptwriterBundle);
                setSaveState(reload.saveState);
                setMessage(reload.message);
              } catch {
                setSaveState("save_failed");
                setMessage("Save failed: document was updated elsewhere and reload also failed. Please refresh the page.");
              }
            } else {
              setSaveState("save_failed");
              setMessage(e instanceof Error ? e.message : "Save failed");
            }
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
        editor.commands.setContent(resolveInitialHtml(d));
        hydrating.current = false;
      })
      .catch((e: Error) => setMessage(e.message));
  }, [load, editor]);

  const refreshNav = async () => {
    const bundle = await api.scriptwriter.studio(project.id);
    applyBundle(bundle);
  };

  const syncEditorFromDoc = (d: ScriptDocument) => {
    if (!editor) return;
    hydrating.current = true;
    editor.commands.setContent(resolveInitialHtml(d));
    hydrating.current = false;
  };

  // CDX-055: reapply the server-kept unsaved edit from the recovery payload.
  const restoreRecovery = async () => {
    const docId = latestDocIdRef.current;
    if (!docId) return;
    try {
      const res = await api.scriptwriter.restoreRecovery(project.id, docId);
      const d = res.document as unknown as ScriptDocument;
      setDocTracked(d);
      syncEditorFromDoc(d);
      setSaveState("saved");
      setMessage(RECOVERY_RESTORED_MESSAGE);
      await refreshNav();
    } catch {
      setSaveState("save_failed");
      setMessage(RECOVERY_RESTORE_FAILED_MESSAGE);
    }
  };

  // ── Script title (canonical document metadata) ─────────────────────────
  const renameTitle = async (next: string) => {
    const docId = latestDocIdRef.current;
    if (!docId) throw new Error("save_failed");
    const res = await api.scriptwriter.renameTitle(project.id, docId, next);
    const d = res.document as unknown as ScriptDocument;
    setDocTracked(d);
  };

  const renameStoryTitle = async (next: string) => {
    const handle = storyHandleRef.current;
    if (!handle) throw new Error("save_failed");
    await handle.rename(next);
    setStoryTitle(next.trim() || defaultStoryTitle(project.name));
  };

  // ── Scene management (canonical script scene model) ────────────────────
  const insertScene = async () => {
    if (!doc) return;
    const previousIds = new Set(nav.map((s) => s.sceneHeadingId));
    const res = await api.scriptwriter.insertScene(project.id, doc.id, {
      heading: "INT. NEW LOCATION - DAY",
      afterSceneId: activeSceneId ?? undefined,
    });
    const d = res.document as unknown as ScriptDocument;
    setDocTracked(d);
    syncEditorFromDoc(d);
    await refreshNav();
    // Select the newly inserted scene (the nav id that was not there before).
    const fresh = await api.scriptwriter.studio(project.id);
    const freshNav = (fresh.navigator || []) as NavScene[];
    const added = freshNav.find((s) => s.sceneHeadingId && !previousIds.has(s.sceneHeadingId));
    if (added?.sceneHeadingId) setActiveSceneId(added.sceneHeadingId);
    setMessage("Scene added. Rename it by editing its heading in the page.");
  };

  const removeScene = async () => {
    if (!doc || !activeSceneId) return;
    const target = nav.find((s) => s.sceneHeadingId === activeSceneId);
    const label = target?.heading || "this scene";
    if (!window.confirm(`Remove ${label}? You can undo this.`)) return;
    const res = await api.scriptwriter.deleteScene(project.id, doc.id, activeSceneId);
    const d = res.document as unknown as ScriptDocument;
    setDocTracked(d);
    syncEditorFromDoc(d);
    setActiveSceneId(null);
    await refreshNav();
    setMessage("Scene removed.");
  };

  const moveSceneBy = async (sceneHeadingId: string, delta: number) => {
    if (!doc) return;
    const idx = nav.findIndex((s) => s.sceneHeadingId === sceneHeadingId);
    if (idx < 0) return;
    const toIndex = idx + delta;
    if (toIndex < 0 || toIndex >= nav.length) return;
    const res = await api.scriptwriter.moveScene(project.id, doc.id, sceneHeadingId, toIndex);
    const d = res.document as unknown as ScriptDocument;
    setDocTracked(d);
    syncEditorFromDoc(d);
    await refreshNav();
  };

  const undo = async () => {
    if (!doc) return;
    const res = await api.scriptwriter.undo(project.id, doc.id);
    const d = res.document as unknown as ScriptDocument;
    setDocTracked(d);
    syncEditorFromDoc(d);
    await refreshNav();
  };

  // ── Revisions (first-class; Compare folded in) ─────────────────────────
  const createRevision = async () => {
    if (!doc) return;
    const res = await api.scriptwriter.createRevision(project.id, doc.id, {
      name: `Blue ${new Date().toISOString().slice(0, 10)}`,
      color: "Blue",
    });
    setDoc(res.document as unknown as ScriptDocument);
    await refreshNav();
    setMessage("Revision created.");
  };

  const restoreRevisionById = async (revisionId: string) => {
    if (!doc) return;
    if (!window.confirm("Restore this revision? The current script is replaced — you can undo.")) return;
    const res = await api.scriptwriter.restoreRevision(project.id, doc.id, revisionId);
    const d = res.document as unknown as ScriptDocument;
    setDocTracked(d);
    syncEditorFromDoc(d);
    await refreshNav();
    setMessage("Revision restored.");
  };

  const runCompare = async () => {
    if (!doc || !compareA || !compareB) return;
    const res = await api.scriptwriter.compareRevisions(project.id, doc.id, compareA, compareB);
    setCompareResult(res.changed || []);
  };

  // ── More tools (relocated power — nothing here is primary chrome) ──────
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
    setDocTracked(d);
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
    setDocTracked(d);
    syncEditorFromDoc(d);
    setImportText("");
    await refreshNav();
  };

  const linkScene = async () => {
    if (!doc || !activeSceneId) return;
    // CDX-058: bind the SELECTED project scene, never project.scenes[0].
    const sceneId = resolveLinkSceneId(project.scenes, linkSceneId);
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
    setDocTracked(d);
    syncEditorFromDoc(d);
    setMessage(`Search/replace applied for “${findText}”.`);
  };

  const proposeBible = async () => {
    if (!doc) return;
    const res = await api.scriptwriter.proposeBible(project.id, doc.id);
    setBibleProposals(res.proposals || []);
    setMessage(`${(res.proposals || []).length} Bible proposal(s) created (not auto-applied).`);
  };

  const shellClass = [
    "sw-studio",
    mode === "focus" ? "is-focus" : "",
    view === "story" ? "is-story" : "",
  ]
    .filter(Boolean)
    .join(" ");

  const toolbarSave = view === "story" ? storySaveState : saveState;

  return (
    <div className={shellClass} data-testid="scriptwriter-studio">
      <div className="sw-toolbar" data-testid="scriptwriter-toolbar">
        <span className="sw-toolbar__title">
          {view === "story" ? (
            <ScriptTitleEditor
              title={storyTitle}
              onRename={renameStoryTitle}
              testId="scriptwriter-story-title"
              defaultTitle={defaultStoryTitle(project.name)}
              ariaLabel="Story title"
            />
          ) : (
            <ScriptTitleEditor title={doc?.title || ""} onRename={renameTitle} testId="scriptwriter-title" />
          )}
        </span>
        <button type="button" className={view === "script" ? "primary" : "ghost"} data-testid="scriptwriter-view-script" onClick={() => setView("script")}>
          Script
        </button>
        <button
          type="button"
          className={view === "story" ? "primary" : "ghost"}
          data-testid="scriptwriter-story"
          onClick={() => setView("story")}
          title="Open the story document — synopsis, treatment, arcs, and world notes"
        >
          Story
        </button>
        {view !== "story" ? (
          <>
            <button type="button" className="ghost" data-testid="scriptwriter-insert-scene" onClick={() => void insertScene()} title="Add a new scene after the selected one">
              Add Scene
            </button>
            <button
              type="button"
              className="ghost"
              data-testid="scriptwriter-remove-scene"
              disabled={!activeSceneId}
              onClick={() => void removeScene()}
              title="Remove the selected scene (you can undo)"
            >
              Remove Scene
            </button>
            <button type="button" className={view === "revisions" ? "primary" : "ghost"} data-testid="scriptwriter-revisions" onClick={() => setView("revisions")} title="Snapshot, restore and compare versions of your script">
              Revisions
            </button>
          </>
        ) : null}
        {view !== "story" ? (
          <>
        <button type="button" className="ghost" data-testid="scriptwriter-undo" onClick={() => void undo()} title="Undo the last scene or version change (for typing, use Ctrl+Z while writing)">
          Undo
        </button>
        <button
          type="button"
          className="ghost"
          data-testid="scriptwriter-redo"
          onClick={() => editor?.chain().focus().redo().run()}
          disabled={!editor?.can().redo()}
          title="Redo typing in the editor (scene and version changes can't be redone yet)"
        >
          Redo
        </button>
          </>
        ) : null}
        <button type="button" className={mode === "focus" ? "primary" : "ghost"} data-testid="scriptwriter-focus" onClick={() => setMode((m) => (m === "focus" ? "standard" : "focus"))} title="Hide the side panels so you can write">
          Focus
        </button>
        <span className="sw-toolbar__save" data-testid="scriptwriter-save-state">
          {toolbarSave.replace("_", " ")}
          {view !== "story" && stats.pagesEstimated != null ? ` · ~${String(stats.pagesEstimated)} est. pages` : ""}
        </span>
        {shouldOfferRecovery(saveState) ? (
          <button
            type="button"
            className="ghost sw-toolbar__restore"
            data-testid="scriptwriter-restore-recovery"
            onClick={() => void restoreRecovery()}
          >
            Restore my unsaved changes
          </button>
        ) : null}
      </div>

      <div className="sw-body">
        <aside className="sw-nav" data-testid="scriptwriter-navigator" aria-label="Script navigator" hidden={view === "story"}>
          <p className="eyebrow">Scenes</p>
          {nav.map((s, i) => (
            <div className="sw-nav__row" key={s.sceneHeadingId}>
              <button
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
              <span className="sw-nav__reorder">
                <button
                  type="button"
                  className="ghost"
                  data-testid={`scriptwriter-nav-up-${s.sceneHeadingId}`}
                  disabled={i === 0}
                  onClick={() => void moveSceneBy(s.sceneHeadingId || "", -1)}
                  title="Move scene up"
                >
                  ↑
                </button>
                <button
                  type="button"
                  className="ghost"
                  data-testid={`scriptwriter-nav-down-${s.sceneHeadingId}`}
                  disabled={i === nav.length - 1}
                  onClick={() => void moveSceneBy(s.sceneHeadingId || "", 1)}
                  title="Move scene down"
                >
                  ↓
                </button>
              </span>
            </div>
          ))}
          {!nav.length ? <p className="muted">No scenes yet — write a heading or Add Scene.</p> : null}
        </aside>

        <main className="sw-page-wrap" data-testid="scriptwriter-page">
          {view === "script" ? (
            <div className="sw-page" aria-label="Screenplay page">
              <div className="sw-richtext-toolbar" data-testid="scriptwriter-richtext-toolbar">
                <button type="button" className="sw-rt-btn" onClick={() => editor?.chain().focus().toggleBold().run()} disabled={!editor?.can().toggleBold()} title="Bold">B</button>
                <button type="button" className="sw-rt-btn" onClick={() => editor?.chain().focus().toggleItalic().run()} disabled={!editor?.can().toggleItalic()} title="Italic">I</button>
                <button type="button" className="sw-rt-btn" onClick={() => editor?.chain().focus().toggleUnderline().run()} disabled={!editor?.can().toggleUnderline()} title="Underline">U</button>
                <span className="sw-rt-sep" />
                <button type="button" className={editor?.isActive("heading", { level: 1 }) ? "sw-rt-btn is-active" : "sw-rt-btn"} onClick={() => editor?.chain().focus().toggleHeading({ level: 1 }).run()} title="Heading 1">H1</button>
                <button type="button" className={editor?.isActive("heading", { level: 2 }) ? "sw-rt-btn is-active" : "sw-rt-btn"} onClick={() => editor?.chain().focus().toggleHeading({ level: 2 }).run()} title="Heading 2">H2</button>
                <span className="sw-rt-sep" />
                <button type="button" className={editor?.isActive("bulletList") ? "sw-rt-btn is-active" : "sw-rt-btn"} onClick={() => editor?.chain().focus().toggleBulletList().run()} title="Bullet list">•</button>
                <button type="button" className={editor?.isActive("orderedList") ? "sw-rt-btn is-active" : "sw-rt-btn"} onClick={() => editor?.chain().focus().toggleOrderedList().run()} title="Numbered list">1.</button>
                <span className="sw-rt-sep" />
                <button type="button" className={editor?.isActive("textAlign", { textAlign: "left" }) ? "sw-rt-btn is-active" : "sw-rt-btn"} onClick={() => editor?.chain().focus().setTextAlign("left").run()} title="Align left">⯇</button>
                <button type="button" className={editor?.isActive("textAlign", { textAlign: "center" }) ? "sw-rt-btn is-active" : "sw-rt-btn"} onClick={() => editor?.chain().focus().setTextAlign("center").run()} title="Align center">≣</button>
                <button type="button" className={editor?.isActive("textAlign", { textAlign: "right" }) ? "sw-rt-btn is-active" : "sw-rt-btn"} onClick={() => editor?.chain().focus().setTextAlign("right").run()} title="Align right">⯈</button>
                <span className="sw-rt-sep" />
                <button type="button" className="sw-rt-btn" onClick={() => editor?.chain().focus().undo().run()} disabled={!editor?.can().undo()} title="Undo typing">↶</button>
                <button type="button" className="sw-rt-btn" onClick={() => editor?.chain().focus().redo().run()} disabled={!editor?.can().redo()} title="Redo typing">↷</button>
              </div>
              <EditorContent editor={editor} data-testid="scriptwriter-editor" />
            </div>
          ) : null}
          {view === "story" ? (
            <StoryDocumentEditor
              projectId={project.id}
              projectName={project.name}
              source="scriptwriter"
              onSaveState={setStorySaveState}
              onTitleChange={setStoryTitle}
              onReady={(handle) => {
                storyHandleRef.current = handle;
              }}
            />
          ) : null}
          {view === "revisions" ? (
            <div className="sw-page sw-revisions" data-testid="scriptwriter-revisions-view">
              <p className="eyebrow">Revisions</p>
              <p className="muted">
                Snapshots of your script. Create one before big changes; Restore goes back; Compare shows what changed.
              </p>
              <button type="button" className="primary" data-testid="scriptwriter-create-revision" onClick={() => void createRevision()}>
                Create revision
              </button>
              <ul className="sw-revisions__list" data-testid="scriptwriter-revisions-list">
                {revisions.map((r) => (
                  <li key={String(r.id)}>
                    <strong>{String(r.name)}</strong> <span className="muted">({String(r.color)} · rev {String(r.revision ?? "—")})</span>{" "}
                    <button
                      type="button"
                      className="ghost"
                      data-testid={`scriptwriter-revision-restore-${String(r.id)}`}
                      onClick={() => void restoreRevisionById(String(r.id))}
                    >
                      Restore
                    </button>
                  </li>
                ))}
                {!revisions.length ? <li className="muted">No revisions yet.</li> : null}
              </ul>

              <p className="eyebrow" style={{ marginTop: "1rem" }}>
                Compare revisions
              </p>
              <div data-testid="scriptwriter-compare">
                <label>
                  Revision A
                  <select value={compareA} onChange={(e) => setCompareA(e.target.value)} data-testid="scriptwriter-compare-a">
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
                  <select value={compareB} onChange={(e) => setCompareB(e.target.value)} data-testid="scriptwriter-compare-b">
                    <option value="">—</option>
                    {revisions.map((r) => (
                      <option key={String(r.id)} value={String(r.id)}>
                        {String(r.name)}
                      </option>
                    ))}
                  </select>
                </label>
                <button type="button" data-testid="scriptwriter-compare-run" onClick={() => void runCompare()}>
                  Compare
                </button>
                <pre data-testid="scriptwriter-compare-result">{compareResult ? JSON.stringify(compareResult.slice(0, 20), null, 2) : "No comparison yet"}</pre>
              </div>
            </div>
          ) : null}
        </main>

        <aside className="sw-inspector" data-testid="scriptwriter-inspector" aria-label="Script inspector" hidden={view === "story"}>
          <button
            type="button"
            className="ghost sw-inspector__toggle"
            data-testid="scriptwriter-more-tools"
            onClick={() => setMoreToolsOpen((v) => !v)}
            aria-expanded={moreToolsOpen}
          >
            {moreToolsOpen ? "▾ More tools" : "▸ More tools"}
          </button>
          {!moreToolsOpen ? (
            <p className="muted">Scene analysis, linking, Timeline prep, export, import and search live here when you need them.</p>
          ) : null}

          {moreToolsOpen ? (
            <>
              <div className="row-actions">
                <label className="sw-link-scene-picker" data-testid="scriptwriter-link-scene-picker">
                  <span>Link to project scene</span>
                  <select
                    value={linkSceneId || ""}
                    onChange={(e) => setLinkSceneId(e.target.value || null)}
                    data-testid="scriptwriter-link-scene-select"
                  >
                    <option value="">{project.scenes.length ? "First scene (default)" : "No project scenes"}</option>
                    {project.scenes.map((s) => (
                      <option key={s.id} value={s.id}>
                        {s.name || s.id}
                      </option>
                    ))}
                  </select>
                </label>
                <button type="button" data-testid="scriptwriter-analyze" onClick={() => void analyze()}>
                  Analyze scene
                </button>
                <button type="button" data-testid="scriptwriter-propose-dialogue" onClick={() => void acceptDialogueProposal()}>
                  Propose dialogue polish
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
            </>
          ) : null}
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
    </div>
  );
}
