import { useEffect, useState } from "react";
import { api } from "../../api";
import { UnifiedMediaCard, type MediaCard } from "./UnifiedMediaCard";
import { ApprovalCenterPanel } from "./ApprovalCenterPanel";
import { ProductionPlanPanel } from "./ProductionPlanPanel";

type Stage = string;

const STAGES: Stage[] = [
  "idea",
  "discovery",
  "treatment",
  "screenplay",
  "previs",
  "production",
  "post",
  "delivery",
];

/**
 * M2.14 three-pane unified workspace (flag-gated by parent).
 * Left: stage-adaptive nav | Center: structured conversation | Right: collapsible inspector
 */
export function UnifiedExperienceWorkspace({
  projectId,
  enabled,
}: {
  projectId: string;
  enabled: boolean;
}) {
  const [inspectorOpen, setInspectorOpen] = useState(true);
  const [stage, setStage] = useState<Stage>("idea");
  const [status, setStatus] = useState<Record<string, unknown> | null>(null);
  const [media, setMedia] = useState<MediaCard[]>([]);
  const [expanded, setExpanded] = useState<MediaCard | null>(null);
  const [primaryAction, setPrimaryAction] = useState("Start idea-first discovery");
  const [messages, setMessages] = useState<string[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!enabled) return;
    let cancelled = false;
    (async () => {
      try {
        const s = await api.m214Status();
        if (cancelled) return;
        setStatus(s);
        if (s.enabled) {
          const session = await api.m214Session(projectId);
          if (cancelled) return;
          setStage((session.stage as { stage?: string })?.stage || "idea");
          setPrimaryAction(String(session.primaryNextAction || primaryAction));
          const m = await api.m214Media(projectId);
          if (cancelled) return;
          setMedia((m.items as MediaCard[]) || []);
        }
      } catch (e) {
        if (!cancelled) setError(e instanceof Error ? e.message : "Failed to load M2.14");
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [enabled, projectId]);

  if (!enabled) return null;

  async function runIdea() {
    setError(null);
    const res = await api.m214Idea({
      projectId,
      idea: "A hitchhiker waits under sodium light as a stranger slows down.",
      preferredFormat: "short scene",
    });
    setStage(res.stage || "discovery");
    setMessages((prev) => [
      ...prev,
      `Storyteller discovery (${res.mode}): ${(res.questions || []).join(" | ")}`,
      `Format guidance: ${res.formatGuidance}`,
      `[honesty: ${res.honesty}]`,
    ]);
    setPrimaryAction("Answer Storyteller questions");
  }

  async function runHitchhiker() {
    setError(null);
    const res = await api.m214HitchhikerSmoke({ projectId });
    setMedia(res.cards || []);
    setMessages((prev) => [
      ...prev,
      "Hitchhiker smoke media created — all cards labeled MOCKED/FIXTURE.",
      "No fake 3D preview fabricated.",
    ]);
    setPrimaryAction("Review mocked media cards");
  }

  return (
    <div className="m214-workspace" data-testid="m214-unified-workspace" role="region" aria-label="Unified Co-Director workspace">
      <aside className="m214-nav" aria-label="Project stage navigation">
        <p className="eyebrow">Stage</p>
        <nav>
          <ul>
            {STAGES.map((s) => (
              <li key={s}>
                <button
                  type="button"
                  className={s === stage ? "active" : ""}
                  aria-current={s === stage ? "step" : undefined}
                  onClick={async () => {
                    setStage(s);
                    await api.m214Stage({ projectId, stage: s });
                  }}
                >
                  {s}
                </button>
              </li>
            ))}
          </ul>
        </nav>
        <p className="m214-flag" data-testid="m214-flag-badge">
          Flag: {status?.enabled ? "ON" : "OFF"} (default OFF)
        </p>
      </aside>

      <section className="m214-center" aria-label="Structured conversation">
        <header>
          <h2>Co-Director Unified Experience</h2>
          <p className="m214-primary-action" data-testid="m214-primary-action">
            Next: {primaryAction}
          </p>
        </header>
        <div className="m214-actions">
          <button type="button" onClick={runIdea} data-testid="m214-idea-first">
            Idea-first discovery
          </button>
          <button type="button" onClick={runHitchhiker} data-testid="m214-hitchhiker">
            Hitchhiker smoke (mocked)
          </button>
        </div>
        {error && (
          <p role="alert" className="m214-error">
            {error}
          </p>
        )}
        <ol className="m214-conversation" aria-live="polite">
          {messages.map((m, i) => (
            <li key={i} className="m214-card">
              {m}
            </li>
          ))}
        </ol>
        <div className="m214-media-rail" aria-label="Media cards">
          {media.map((card) => (
            <UnifiedMediaCard key={card.id} card={card} onExpand={() => setExpanded(card)} />
          ))}
        </div>
      </section>

      {inspectorOpen && (
        <aside className="m214-inspector" aria-label="Inspector">
          <button
            type="button"
            className="m214-collapse"
            aria-expanded={inspectorOpen}
            onClick={() => setInspectorOpen(false)}
          >
            Collapse inspector
          </button>
          <ProductionPlanPanel projectId={projectId} />
          <ApprovalCenterPanel projectId={projectId} />
        </aside>
      )}
      {!inspectorOpen && (
        <button type="button" className="m214-expand-inspector" onClick={() => setInspectorOpen(true)}>
          Open inspector
        </button>
      )}

      {expanded && (
        <div
          className="m214-media-modal"
          role="dialog"
          aria-modal="true"
          aria-label={`Expanded ${expanded.kind}`}
          data-testid="m214-media-modal"
        >
          <button type="button" onClick={() => setExpanded(null)} autoFocus>
            Close
          </button>
          <h3>{expanded.title}</h3>
          <p>
            Kind: {expanded.kind} · Honesty: <strong>{expanded.honesty}</strong>
          </p>
          {expanded.kind === "environment_preview" && (
            <p>M2.13 preview when available — no fake 3D.</p>
          )}
        </div>
      )}
    </div>
  );
}
