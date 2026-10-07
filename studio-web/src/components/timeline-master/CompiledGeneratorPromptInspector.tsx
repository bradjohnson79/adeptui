import { useEffect, useState } from "react";
import { api } from "../../api";

const UNAVAILABLE = "generator-specific prompting unavailable";

type CompilePreview = {
  ok?: boolean;
  status?: string;
  message?: string | null;
  generatorId?: string;
  profileId?: string | null;
  dialect?: string | null;
  compiledPrompt?: string;
  negativePrompt?: string;
  warnings?: string[];
};

export function CompiledGeneratorPromptInspector({
  generatorId,
  scenePrompt,
  projectId,
  sceneId,
}: {
  generatorId: string;
  scenePrompt: string;
  projectId?: string;
  sceneId?: string;
}) {
  const [preview, setPreview] = useState<CompilePreview | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    const gid = (generatorId || "").trim();
    let cancelled = false;
    if (!gid) {
      setPreview({
        ok: false,
        status: "GENERATOR_KNOWLEDGE_UNAVAILABLE",
        message: UNAVAILABLE,
        compiledPrompt: "",
      });
      return;
    }
    const timer = window.setTimeout(() => {
      setBusy(true);
      void api
        .compileGeneratorPromptPreview({
          generatorId: gid,
          userPrompt: scenePrompt || "",
          projectId,
          sceneId,
          mode: "image_to_video",
          mediaType: "video",
        })
        .then((body) => {
          if (!cancelled) setPreview(body);
        })
        .catch(() => {
          if (!cancelled) {
            setPreview({
              ok: false,
              status: "GENERATOR_KNOWLEDGE_UNAVAILABLE",
              message: UNAVAILABLE,
              compiledPrompt: "",
            });
          }
        })
        .finally(() => {
          if (!cancelled) setBusy(false);
        });
    }, 250);
    return () => {
      cancelled = true;
      window.clearTimeout(timer);
    };
  }, [generatorId, scenePrompt, projectId, sceneId]);

  const unavailable = !preview?.ok;
  const compiled = (preview?.compiledPrompt || "").trim();

  return (
    <div className="field" data-testid="timeline-compiled-generator-prompt">
      <span>Prompt Preview</span>
      <p className="scene-meta" data-testid="timeline-compiled-generator-prompt-generator">
        {generatorId || "no generator"}
        {preview?.profileId ? ` · profile ${preview.profileId}` : ""}
        {preview?.dialect ? ` · ${preview.dialect}` : ""}
        {busy ? " · compiling…" : ""}
      </p>
      {unavailable || !compiled ? (
        <p className="scene-meta" data-testid="timeline-compiled-generator-prompt-unavailable">
          {preview?.message || UNAVAILABLE}
        </p>
      ) : (
        <textarea
          readOnly
          rows={5}
          value={compiled}
          aria-label="Prompt Preview compiled generator prompt"
          data-testid="timeline-compiled-generator-prompt-text"
        />
      )}
      {(preview?.warnings || []).length ? (
        <ul className="scene-meta" data-testid="timeline-compiled-generator-prompt-warnings">
          {(preview?.warnings || []).slice(0, 6).map((w) => (
            <li key={w}>{w}</li>
          ))}
        </ul>
      ) : null}
    </div>
  );
}
