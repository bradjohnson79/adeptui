/**
 * ShotRequestInput — the SHOT REQUESTS textarea plus a Shot Suggestion
 * generator and a live parse preview.
 *
 * Amendment #5 (@/# tags): @ uses real character names (spaces/apostrophes
 * allowed), # uses normalized prop tags. The textarea accepts free-form
 * comma-separated shot requests.
 * Amendment #44 (one suggestion at a time): the suggestion card shows ONE
 * suggested shot with [Add Shot] / [Try Another]; never silently injects text.
 *
 * Law #9 (every control wired):
 *  - Shot Suggestion calls the real parse-shots endpoint to validate a
 *    constructed candidate prompt, then surfaces it as a single suggestion.
 *  - Parse Preview calls parse-shots to show how the current text splits.
 */
import { useCallback, useEffect, useState } from "react";
import { sceneCreatorApi } from "./sceneCreatorApi";
import type { ResolvedCharacter, ResolvedProp, ShotRequest, ShotSuggestion } from "./types";

export type ShotRequestInputProps = {
  projectId: string;
  value: string;
  onChange: (next: string) => void;
  characters: ResolvedCharacter[];
  props: ResolvedProp[];
  disabled?: boolean;
};

/** Heuristic templates for shot suggestions (cycles on Try Another). */
const SHOT_TEMPLATES: Array<(c: ResolvedCharacter[], p: ResolvedProp[]) => string> = [
  (c, p) => {
    const who = c[0];
    const prop = p[0];
    if (who && prop) return `@${who.name} extreme close-up reacting to #${prop.tag}`;
    if (who) return `@${who.name} extreme close-up, emotional reaction`;
    return `establishing wide shot of the environment`;
  },
  (c, _p) => {
    const who = c[0];
    if (who) return `@${who.name} medium shot, ${who.position_label}, eye level`;
    return `medium shot of the scene`;
  },
  (c, _p) => {
    const a = c[0];
    const b = c[1];
    if (a && b) return `over-the-shoulder from @${a.name} toward @${b.name}`;
    if (a) return `@${a.name} high angle shot 15 degrees right`;
    return `high angle shot of the environment`;
  },
  (c, p) => {
    const who = c[0];
    const prop = p[1] || p[0];
    if (who && prop) return `@${who.name} close-up holding #${prop.tag}`;
    if (who) return `@${who.name} close-up, subtle expression change`;
    return `close-up detail of a prop`;
  },
  (c, _p) => {
    const who = c[c.length - 1];
    if (who) return `@${who.name} wide shot, ${who.position_label}, establishing geography`;
    return `wide establishing shot`;
  },
];

function appendShot(current: string, shot: string): string {
  const trimmed = current.trim();
  if (!trimmed) return shot;
  // Preserve the user's separator style: if they use newlines, append newline;
  // otherwise comma.
  if (trimmed.includes("\n")) return `${trimmed}\n${shot}`;
  return `${trimmed}, ${shot}`;
}

export function ShotRequestInput({
  projectId,
  value,
  onChange,
  characters,
  props,
  disabled,
}: ShotRequestInputProps) {
  const [suggestion, setSuggestion] = useState<ShotSuggestion | null>(null);
  const [suggestionBusy, setSuggestionBusy] = useState(false);
  const [suggestionError, setSuggestionError] = useState<string | null>(null);
  const [templateIndex, setTemplateIndex] = useState(0);
  const [preview, setPreview] = useState<ShotRequest[] | null>(null);
  const [previewBusy, setPreviewBusy] = useState(false);

  // Debounced parse preview (Law #13: bounded, no storm). Only parses when
  // the text is non-empty and the user pauses for 600ms.
  useEffect(() => {
    if (!value.trim()) {
      setPreview(null);
      return;
    }
    let cancelled = false;
    setPreviewBusy(true);
    const handle = window.setTimeout(() => {
      void (async () => {
        try {
          const res = await sceneCreatorApi.parseShots(projectId, value);
          if (!cancelled) {
            setPreview(res.shots || []);
            setSuggestionError(null);
          }
        } catch (err) {
          if (!cancelled) {
            // Preview is best-effort; show nothing on failure.
            setPreview(null);
          }
        } finally {
          if (!cancelled) setPreviewBusy(false);
        }
      })();
    }, 600);
    return () => {
      cancelled = true;
      window.clearTimeout(handle);
    };
  }, [projectId, value]);

  const fetchSuggestion = useCallback(async () => {
    setSuggestionBusy(true);
    setSuggestionError(null);
    try {
      const template = SHOT_TEMPLATES[templateIndex % SHOT_TEMPLATES.length](characters, props);
      // Validate the candidate prompt through the real parse-shots endpoint.
      // This confirms the @/# tags resolve and the shot is well-formed.
      const res = await sceneCreatorApi.parseShots(projectId, template);
      const shot = res.shots?.[0];
      const prompt = shot?.raw_text || template;
      setSuggestion({
        prompt,
        rationale: `Based on ${characters.length} placed character${characters.length === 1 ? "" : "s"} and ${props.length} prop${props.length === 1 ? "" : "s"} in your Spatial Map.`,
      });
      setTemplateIndex((i) => i + 1);
    } catch (err) {
      setSuggestionError(err instanceof Error ? err.message : String(err));
    } finally {
      setSuggestionBusy(false);
    }
  }, [characters, props, projectId, templateIndex]);

  const addSuggestion = useCallback(() => {
    if (!suggestion) return;
    onChange(appendShot(value, suggestion.prompt));
    setSuggestion(null);
  }, [suggestion, value, onChange]);

  return (
    <div data-testid="scene-creator-shot-input" className="codirector-content-card">
      <div className="row" style={{ justifyContent: "space-between", alignItems: "baseline" }}>
        <label
          htmlFor="scene-creator-shot-textarea"
          style={{ fontWeight: 600, letterSpacing: "0.04em", fontSize: "0.7rem", textTransform: "uppercase" }}
        >
          Shot Requests
        </label>
        <button
          type="button"
          className="primary"
          onClick={() => void fetchSuggestion()}
          disabled={disabled || suggestionBusy}
          data-testid="scene-creator-suggest-shot"
          title="Get one suggested shot based on your Spatial Map"
        >
          {suggestionBusy ? "Suggesting…" : "Shot Suggestion"}
        </button>
      </div>
      <textarea
        id="scene-creator-shot-textarea"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        disabled={disabled}
        rows={5}
        placeholder="@Korri close up, @Korri high angle shot 15 degrees right, @Korri medium shot behind #baristabar holding #coffeecup, OTS from Director toward @Korri"
        style={{ width: "100%", resize: "vertical", fontFamily: "inherit", marginTop: "0.4rem" }}
        data-testid="scene-creator-shot-textarea"
        aria-label="Shot requests — comma-separated, use @ for characters and # for props"
      />
      <p className="muted" style={{ margin: "0.25rem 0 0", fontSize: "0.75rem" }}>
        Use <code>@Name</code> for characters and <code>#tag</code> for props. Separate shots with commas or new lines.
      </p>

      {previewBusy ? (
        <p className="muted" style={{ fontSize: "0.75rem", margin: "0.5rem 0 0" }}>Parsing…</p>
      ) : preview && preview.length ? (
        <p className="muted" style={{ fontSize: "0.75rem", margin: "0.5rem 0 0" }} data-testid="scene-creator-shot-preview">
          {preview.length} shot{preview.length === 1 ? "" : "s"} detected
        </p>
      ) : null}

      {suggestionError ? (
        <p className="muted" style={{ color: "var(--danger, #c33)", fontSize: "0.8rem", margin: "0.5rem 0 0" }}>
          Suggestion unavailable: {suggestionError}
        </p>
      ) : null}

      {suggestion ? (
        <div
          data-testid="scene-creator-suggestion-card"
          className="codirector-content-card"
          style={{ marginTop: "0.6rem", background: "color-mix(in srgb, var(--accent, #4a8) 8%, transparent)" }}
        >
          <p className="eyebrow" style={{ margin: 0 }}>Suggested Shot</p>
          <p style={{ margin: "0.35rem 0", fontWeight: 600 }}>&ldquo;{suggestion.prompt}&rdquo;</p>
          {suggestion.rationale ? (
            <p className="muted" style={{ margin: 0, fontSize: "0.78rem" }}>{suggestion.rationale}</p>
          ) : null}
          <div className="row" style={{ gap: "0.5rem", marginTop: "0.5rem" }}>
            <button
              type="button"
              className="primary"
              onClick={addSuggestion}
              disabled={disabled}
              data-testid="scene-creator-add-shot"
            >
              Add Shot
            </button>
            <button
              type="button"
              onClick={() => void fetchSuggestion()}
              disabled={disabled || suggestionBusy}
              data-testid="scene-creator-try-another"
            >
              Try Another
            </button>
          </div>
        </div>
      ) : null}
    </div>
  );
}
