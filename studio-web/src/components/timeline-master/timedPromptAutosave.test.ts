import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";

describe("Timed Prompt autosave + Inspector authority", () => {
  it("Timed Prompt modal persists text via useDraftField without requiring OK", () => {
    const modal = readFileSync(new URL("./TimedPromptEditorModal.tsx", import.meta.url), "utf8");
    expect(modal).toContain('from "./useDraftField"');
    expect(modal).toContain("useDraftField(liveText, persistText");
    expect(modal).toContain("onPersist");
    expect(modal).toContain("production_prompt: null");
    expect(modal).toContain('data-testid="timeline-timed-prompt-text"');
    expect(modal).toContain("textField.flush()");
    expect(modal).toContain("void onPersist({ text, production_prompt: null })");
  });

  it("DirectorTracks wires modal onPersist to persistPromptEdit without closing", () => {
    const tracks = readFileSync(new URL("../DirectorTracks.tsx", import.meta.url), "utf8");
    expect(tracks).toContain("persistPromptEdit");
    expect(tracks).toContain("onPersist={persistTimedPromptPatch}");
    expect(tracks).toContain("if (opts?.close) setEditingPromptId(null)");
    expect(tracks).toContain("await persistPromptEdit(id, patch, { close: true })");
  });

  it("Inspector Prompt Clip edits Master promptSegments with debounced draft", () => {
    const inspector = readFileSync(new URL("./TimelineInspector.tsx", import.meta.url), "utf8");
    expect(inspector).toContain("persistPromptSegText");
    expect(inspector).toContain('useDraftField(selectedPrompt?.text || "", persistPromptSegText');
    expect(inspector).toContain("production_prompt: null");
    expect(inspector).toContain('data-testid="timeline-prompt-instruction"');
    expect(inspector).toContain('data-testid="timed-prompt-authority-hint"');
    expect(inspector).toContain("patchMasterPrompt");
    expect(inspector).not.toContain("Legacy director prompt_segments are adapter only");
  });

  it("useDraftField flushes pending edits on idle, blur, and unmount", () => {
    const draft = readFileSync(new URL("./useDraftField.ts", import.meta.url), "utf8");
    expect(draft).toContain("flushRef.current()");
    expect(draft).toContain("idleMs");
    expect(draft).toContain("return { value, onChange, onFocus, onBlur, flush, isDirty }");
  });

  it("DirectorTracks persists Timed Prompts through Master helpers", () => {
    const tracks = readFileSync(new URL("../DirectorTracks.tsx", import.meta.url), "utf8");
    expect(tracks).toContain("flattenMasterPrompts");
    expect(tracks).toContain("patchMasterPrompt");
    expect(tracks).toContain("promptWriteTail");
    expect(tracks).toContain("promptWriteSegs");
    expect(tracks).toContain("subscribeShellTimelineSnapshot");
    expect(tracks).not.toMatch(/strip.*subject|replace\([^)]*subject\s*\d/i);
  });

  it("Prompt Name uses local draft + idle/blur commit (no per-keystroke Timeline patch)", () => {
    const editor = readFileSync(new URL("./TimedPromptReferenceBindingsEditor.tsx", import.meta.url), "utf8");
    expect(editor).toContain("draftNames");
    expect(editor).toContain("PROMPT_NAME_IDLE_MS");
    expect(editor).toContain("commitPromptName");
    expect(editor).toContain("onPromptNameChange");
    expect(editor).toContain("onPromptNameBlur");
    expect(editor).toContain("onValidationError");
    // Must not patch prompt_name on every keystroke path.
    expect(editor).toMatch(/onChange=\{\(event\) => onPromptNameChange/);
    expect(editor).not.toMatch(/onChange=\{\(event\) => patchRow\(index, \{ prompt_name:/);
  });

  it("Timed Prompt modal accepts binding drafts even when validation error is set", () => {
    const modal = readFileSync(new URL("./TimedPromptEditorModal.tsx", import.meta.url), "utf8");
    expect(modal).toContain("onValidationError={setBindingError}");
    expect(modal).toContain("validateTimedPromptNameBindings");
    expect(modal).toContain("bindingsEditorRef.current?.flush()");
    // Must not freeze draft updates behind if (!error).
    expect(modal).not.toMatch(/if \(!error\) setDraft/);
  });

  it("Inspector persists nameBindings only on committed onChange (not keystroke)", () => {
    const inspector = readFileSync(new URL("./TimelineInspector.tsx", import.meta.url), "utf8");
    expect(inspector).toContain("onValidationError={setTokenError}");
    expect(inspector).toContain("Prompt Name commits only");
  });

  it("useTimelineEditorModal does not re-focus when focus is already inside the modal", () => {
    const hook = readFileSync(new URL("./useTimelineEditorModal.ts", import.meta.url), "utf8");
    expect(hook).toContain("onCancelRef");
    expect(hook).toContain("alreadyInside");
    expect(hook).toContain("justOpened");
    // onCancel identity must not re-run the focus effect
    expect(hook).toMatch(/\}, \[initialSelector, open\]\);/);
    expect(hook).not.toMatch(/\}, \[initialSelector, onCancel, open\]\);/);
  });

  it("DirectorTracks passes stable Timed Prompt modal cancel/persist/commit callbacks", () => {
    const tracks = readFileSync(new URL("../DirectorTracks.tsx", import.meta.url), "utf8");
    expect(tracks).toContain("closeTimedPromptModal");
    expect(tracks).toContain("onCancel={closeTimedPromptModal}");
    expect(tracks).toContain("onPersist={persistTimedPromptPatch}");
    expect(tracks).toContain("onCommit={commitTimedPromptPatch}");
    expect(tracks).not.toContain("onCancel={() => setEditingPromptId(null)}");
    // Rules of Hooks: stable Timed Prompt callbacks must be declared before scene/tl early returns.
    const hooksAt = tracks.indexOf("const closeTimedPromptModal = useCallback");
    const earlyScene = tracks.indexOf("if (!scene) {");
    const earlyTl = tracks.indexOf("if (!tl) {");
    expect(hooksAt).toBeGreaterThan(-1);
    expect(hooksAt).toBeLessThan(earlyScene);
    expect(hooksAt).toBeLessThan(earlyTl);
    expect(tracks).toContain("editingPromptIdRef");
    expect(tracks).toContain("persistPromptEditRef");
  });

});
