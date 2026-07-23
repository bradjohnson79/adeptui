import { useEffect, useRef, useState } from "react";
import { api } from "../api";
import type { Project, SceneSetup } from "../types";
import { HelpTip } from "./HelpTip";

type Msg = { role: "user" | "assistant"; content: string };

const QUICK = [
  {
    label: "Build scene",
    mode: "setup" as const,
    text: "Build a complete scene setup for the selected scene: choose engine, duration, write prompts, and place available @tagged images into start/middle/end slots.",
  },
  {
    label: "How do I start?",
    mode: "guide" as const,
    text: "I'm new here. Walk me through creating my first multi-scene video in Adept UI Video Studio.",
  },
  {
    label: "Write a prompt",
    mode: "prompt" as const,
    text: "Write a strong motion prompt for the selected scene using available @tags if any.",
  },
  {
    label: "LTX vs WAN",
    mode: "guide" as const,
    text: "When should I use LTX 2.3 vs WAN 2.2 on a scene?",
  },
];

function summarizeSetup(s: SceneSetup): string[] {
  const lines: string[] = [];
  if (s.summary) lines.push(s.summary);
  if (s.engine) {
    const labels: Record<string, string> = {
      ltx: "LTX 2.3",
      wan: "WAN 2.2",
      fal_seedance: "Seedance 2.0 (fal)",
      fal_kling: "Kling (fal)",
      fal_veo: "Veo 3.1 (fal)",
      fal_runway: "Runway (fal)",
    };
    lines.push(`Engine: ${labels[s.engine] || s.engine}`);
  }
  if (s.duration_sec != null) lines.push(`Duration: ${s.duration_sec}s`);
  if (s.media_mode) lines.push(`Track: ${s.media_mode}`);
  if (s.preset) lines.push(`Preset: ${s.preset}`);
  if (s.global_prompt) lines.push(`Global look: ${s.global_prompt.slice(0, 80)}${s.global_prompt.length > 80 ? "…" : ""}`);
  if (s.prompt) lines.push(`Prompt: ${s.prompt.slice(0, 100)}${s.prompt.length > 100 ? "…" : ""}`);
  if (s.prompt_segments?.length) lines.push(`Prompt segments: ${s.prompt_segments.length}`);
  if (s.image_slots) {
    const slots = Object.entries(s.image_slots)
      .filter(([, v]) => v)
      .map(([k, v]) => `${k}=${v}`)
      .join(", ");
    if (slots) lines.push(`Images: ${slots}`);
  }
  if (s.audio_ref) lines.push(`Audio: ${s.audio_ref}`);
  if (s.sfx?.length) lines.push(`SFX clips: ${s.sfx.length}`);
  return lines.length ? lines : ["Scene setup ready to apply"];
}

export function AssistantPanel({
  project,
  sceneId,
  onApplyPrompt,
  onAppliedSetup,
}: {
  project?: Project | null;
  sceneId?: string;
  onApplyPrompt?: (prompt: string) => void;
  onAppliedSetup?: () => void;
}) {
  const [open, setOpen] = useState(false);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [applying, setApplying] = useState(false);
  const [status, setStatus] = useState("Checking Ollama…");
  const [messages, setMessages] = useState<Msg[]>([
    {
      role: "assistant",
      content:
        "Hi — I'm the Adept Assistant for Adept UI Video Studio. I can build a full scene setup (engine, prompts, image slots), write prompts, and guide you through Director, @tags, and renders. Ask me to “build the scene” or tap Build scene.",
    },
  ]);
  const [suggested, setSuggested] = useState<string | null>(null);
  const [setup, setSetup] = useState<SceneSetup | null>(null);
  const [applyNote, setApplyNote] = useState<string | null>(null);
  const endRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    api.assistantHealth()
      .then((h) => {
        if (!h.ollama_reachable) setStatus("Ollama offline");
        else setStatus(`Local · ${h.model}`);
      })
      .catch(() => setStatus("Assistant unavailable"));
  }, []);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, open, setup]);

  const send = async (text: string, mode: "chat" | "prompt" | "guide" | "setup" = "chat") => {
    const trimmed = text.trim();
    if (!trimmed || busy) return;
    setBusy(true);
    setSuggested(null);
    setSetup(null);
    setApplyNote(null);
    const next = [...messages, { role: "user" as const, content: trimmed }];
    setMessages(next);
    setInput("");
    try {
      const res = await api.assistantChat({
        messages: next.map((m) => ({ role: m.role, content: m.content })),
        project_id: project?.id,
        scene_id: sceneId,
        mode,
      });
      setMessages([...next, { role: "assistant", content: res.reply }]);
      if (res.scene_setup) setSetup(res.scene_setup);
      else if (res.suggested_prompt) setSuggested(res.suggested_prompt);
    } catch (err) {
      setMessages([
        ...next,
        {
          role: "assistant",
          content: `I couldn't reach the local model. ${err instanceof Error ? err.message : String(err)}`,
        },
      ]);
    } finally {
      setBusy(false);
    }
  };

  const applySetup = async () => {
    if (!setup || !project?.id || !sceneId || applying) return;
    setApplying(true);
    setApplyNote(null);
    try {
      const res = await api.assistantApplySetup({
        project_id: project.id,
        scene_id: sceneId,
        setup,
      });
      const note =
        (res.applied.length ? `Applied: ${res.applied.join(", ")}` : "Nothing changed") +
        (res.warnings.length ? `\nWarnings: ${res.warnings.join("; ")}` : "");
      setApplyNote(note);
      setMessages((m) => [...m, { role: "assistant", content: note }]);
      setSetup(null);
      onAppliedSetup?.();
    } catch (err) {
      setApplyNote(err instanceof Error ? err.message : String(err));
    } finally {
      setApplying(false);
    }
  };

  return (
    <>
      <button className="assistant-fab" onClick={() => setOpen((v) => !v)} title="Adept Assistant">
        {open ? "Close" : "Assistant"}
      </button>
      {open && (
        <aside className="assistant-panel">
          <div className="assistant-head">
            <div>
              <div className="panel-heading-title">
                <strong>Adept Assistant</strong>
                <HelpTip text="Local Ollama helper: write prompts, build full scene setups, and guide you through Director, @tags, and renders." />
              </div>
              <div className="scene-meta">{status}</div>
            </div>
            <button className="ghost" onClick={() => setOpen(false)}>
              ×
            </button>
          </div>
          <div className="assistant-quick">
            {QUICK.map((q) => (
              <button key={q.label} disabled={busy} onClick={() => send(q.text, q.mode)}>
                {q.label}
              </button>
            ))}
          </div>
          <div className="assistant-messages">
            {messages.map((m, i) => (
              <div key={i} className={`assistant-msg ${m.role}`}>
                {m.content}
              </div>
            ))}
            <div ref={endRef} />
          </div>
          {setup && (
            <div className="assistant-apply">
              <div className="scene-meta">Proposed scene setup — confirm to apply</div>
              <ul className="assistant-setup-list">
                {summarizeSetup(setup).map((line, i) => (
                  <li key={i}>{line}</li>
                ))}
              </ul>
              {!project?.id || !sceneId ? (
                <div className="scene-meta">Open a project and select a scene to apply.</div>
              ) : (
                <div className="row-actions">
                  <button className="ghost" disabled={applying} onClick={() => setSetup(null)}>
                    Dismiss
                  </button>
                  <button className="primary" disabled={applying} onClick={applySetup}>
                    {applying ? "Applying…" : "Apply to selected scene"}
                  </button>
                </div>
              )}
            </div>
          )}
          {suggested && onApplyPrompt && !setup && (
            <div className="assistant-apply">
              <div className="scene-meta">Suggested prompt ready</div>
              <button
                className="primary"
                onClick={() => {
                  onApplyPrompt(suggested);
                  setSuggested(null);
                }}
              >
                Apply prompt to selected scene
              </button>
            </div>
          )}
          {applyNote && !setup && <div className="assistant-apply scene-meta">{applyNote}</div>}
          <form
            className="assistant-input"
            onSubmit={(e) => {
              e.preventDefault();
              const mode = /build|set\s*up|setup|configure|assemble/i.test(input)
                ? "setup"
                : /prompt|rewrite|write/i.test(input)
                  ? "prompt"
                  : "chat";
              send(input, mode);
            }}
          >
            <textarea
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder="e.g. Build a rainy night chase with @hero on start…"
              rows={3}
              disabled={busy}
            />
            <div className="row-actions">
              <button type="button" disabled={busy} onClick={() => send(input, "setup")}>
                Build scene
              </button>
              <button type="button" disabled={busy} onClick={() => send(input, "prompt")}>
                Prompt help
              </button>
              <button className="primary" type="submit" disabled={busy || !input.trim()}>
                {busy ? "Thinking…" : "Send"}
              </button>
            </div>
          </form>
        </aside>
      )}
    </>
  );
}
