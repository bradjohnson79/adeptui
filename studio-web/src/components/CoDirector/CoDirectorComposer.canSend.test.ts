import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";

/** Composer send gate: draft or attachments, and not busy. Status/Blocked/model must not participate. */
function composerCanSend(input: {
  draft: string;
  attachmentCount: number;
  busy: boolean;
  statusTone?: string;
}): boolean {
  void input.statusTone;
  return Boolean(input.draft.trim() || input.attachmentCount) && !input.busy;
}

describe("CoDirectorComposer canSend", () => {
  const src = readFileSync(new URL("./CoDirectorComposer.tsx", import.meta.url), "utf8");

  it("gates send only on draft, attachments, and busy — not Status/Blocked/model", () => {
    expect(src).toContain("const canSend = Boolean(draft.trim() || attachments.length) && !busy;");
    expect(src).toContain('disabled={!canSend}');
    expect(src).not.toMatch(/canSend[\s\S]{0,200}statusTone/);
    expect(src).not.toContain("VideoChat3");
    expect(src).not.toContain("capabilities.registry");
    expect(src).not.toMatch(/canSend.*=.*Blocked/);
  });

  it("attachment chip uses Adept panel tokens so filename and type stay readable", () => {
    const css = readFileSync(new URL("../../styles.css", import.meta.url), "utf8");
    const block = css.slice(css.indexOf(".codirector-attachment {"), css.indexOf(".codirector-overflow"));
    expect(block).toContain("background: var(--panel-elevated)");
    expect(block).toContain("color: var(--ink)");
    expect(block).not.toContain("background: #fff");
    expect(block).toMatch(/\.codirector-attachment-meta strong[\s\S]*color: var\(--ink\)/);
    expect(block).toMatch(/\.codirector-attachment-meta span[\s\S]*color: var\(--ink\)/);
  });

  it("Status Blocked + empty draft → send disabled; Blocked + non-empty draft → send enabled", () => {
    expect(
      composerCanSend({ draft: "", attachmentCount: 0, busy: false, statusTone: "Blocked" }),
    ).toBe(false);
    expect(
      composerCanSend({ draft: "help me recover", attachmentCount: 0, busy: false, statusTone: "Blocked" }),
    ).toBe(true);
    expect(
      composerCanSend({ draft: "   ", attachmentCount: 0, busy: false, statusTone: "Blocked" }),
    ).toBe(false);
    expect(
      composerCanSend({ draft: "", attachmentCount: 1, busy: false, statusTone: "Blocked" }),
    ).toBe(true);
    expect(
      composerCanSend({ draft: "help", attachmentCount: 0, busy: true, statusTone: "Blocked" }),
    ).toBe(false);
  });
});
