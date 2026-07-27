# -*- coding: utf-8 -*-
"""Emit M2.14 frontend workspace components (UTF-8)."""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "studio-web" / "src" / "components" / "CoDirector"
E2E = ROOT / "studio-web" / "e2e"


def w(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not text.endswith("\n"):
        text += "\n"
    path.write_text(text, encoding="utf-8", newline="\n")
    print("wrote", path.relative_to(ROOT))


WORKSPACE = r'''import { useEffect, useState } from "react";
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
'''

MEDIA_CARD = r'''export type MediaCard = {
  id: string;
  kind: string;
  title: string;
  honesty?: string;
  groupKey?: string;
  status?: string;
  payload?: Record<string, unknown>;
};

export function UnifiedMediaCard({
  card,
  onExpand,
}: {
  card: MediaCard;
  onExpand: () => void;
}) {
  const honesty = card.honesty || "mocked";
  return (
    <article
      className="m214-media-card"
      data-testid={`m214-media-${card.kind}`}
      data-honesty={honesty}
    >
      <header>
        <span className="m214-media-kind">{card.kind}</span>
        <span className={`m214-honesty m214-honesty-${honesty}`} aria-label={`Honesty ${honesty}`}>
          {honesty.toUpperCase()}
        </span>
      </header>
      <p>{card.title}</p>
      <button type="button" onClick={onExpand}>
        Expand
      </button>
    </article>
  );
}
'''

APPROVAL = r'''import { useEffect, useState } from "react";
import { api } from "../../api";

export function ApprovalCenterPanel({ projectId }: { projectId: string }) {
  const [data, setData] = useState<Record<string, unknown> | null>(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      const res = await api.m214Approvals({
        projectId,
        pending: {
          story: { status: "pending", items: [{ id: "story-1", label: "Storyteller handoff" }] },
          media: { status: "pending", items: [{ id: "media-1", label: "Mocked hitchhiker card" }] },
        },
      });
      if (!cancelled) setData(res);
    })();
    return () => {
      cancelled = true;
    };
  }, [projectId]);

  return (
    <section className="m214-approval-center" data-testid="m214-approval-center" aria-label="Approval Center">
      <h3>Approval Center</h3>
      <p>Pending: {String(data?.pendingCount ?? "…")}</p>
      <p className="m214-primary-action">{String(data?.primaryNextAction || "")}</p>
      <ul>
        {((data?.categories as Array<{ category: string; status: string }>) || []).map((c) => (
          <li key={c.category}>
            <span className={`m214-status m214-status-${c.status}`} aria-label={`${c.category} ${c.status}`}>
              {c.category}: {c.status}
            </span>
          </li>
        ))}
      </ul>
      <p className="eyebrow">No silent approvals</p>
    </section>
  );
}
'''

PLAN = r'''import { useEffect, useState } from "react";
import { api } from "../../api";

export function ProductionPlanPanel({ projectId }: { projectId: string }) {
  const [data, setData] = useState<Record<string, unknown> | null>(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      const res = await api.m214Plan(projectId);
      if (!cancelled) setData(res);
    })();
    return () => {
      cancelled = true;
    };
  }, [projectId]);

  const stages = (data?.stages as Array<{ id: string; status: string }>) || [];

  return (
    <section className="m214-plan" data-testid="m214-production-plan" aria-label="Production plan">
      <h3>Production plan</h3>
      <ol>
        {stages.map((s) => (
          <li key={s.id} data-status={s.status} aria-current={s.status === "current" ? "step" : undefined}>
            {s.id}
            <span className={`m214-status m214-status-${s.status}`}> {s.status}</span>
          </li>
        ))}
      </ol>
    </section>
  );
}
'''

CSS = r'''/* M2.14 Unified Experience — additive styles */
.m214-workspace {
  display: grid;
  grid-template-columns: minmax(160px, 200px) 1fr minmax(220px, 280px);
  gap: 0.75rem;
  min-height: 420px;
  padding: 0.75rem;
  background: linear-gradient(160deg, #1a1f24 0%, #243038 55%, #1c252b 100%);
  color: #e8eef2;
  border-radius: 8px;
}
.m214-nav ul { list-style: none; padding: 0; margin: 0; }
.m214-nav button {
  width: 100%;
  text-align: left;
  background: transparent;
  border: 0;
  color: inherit;
  padding: 0.35rem 0.5rem;
  cursor: pointer;
}
.m214-nav button.active { background: rgba(255,255,255,0.08); font-weight: 600; }
.m214-center { min-width: 0; }
.m214-primary-action { font-weight: 600; }
.m214-conversation { list-style: none; padding: 0; }
.m214-card {
  margin: 0.4rem 0;
  padding: 0.6rem 0.75rem;
  background: rgba(0,0,0,0.2);
  border-left: 3px solid #6fa8c4;
}
.m214-media-rail { display: flex; flex-wrap: wrap; gap: 0.5rem; margin-top: 0.75rem; }
.m214-media-card {
  width: 140px;
  padding: 0.5rem;
  background: rgba(255,255,255,0.04);
  border: 1px solid rgba(255,255,255,0.12);
}
.m214-honesty-mocked { color: #e6c07b; }
.m214-honesty-fixture { color: #8ec7a0; }
.m214-honesty-real { color: #9fd0ff; }
.m214-inspector { border-left: 1px solid rgba(255,255,255,0.1); padding-left: 0.75rem; }
.m214-media-modal {
  position: fixed;
  inset: 10% 15%;
  background: #141a1f;
  border: 1px solid rgba(255,255,255,0.2);
  padding: 1rem;
  z-index: 40;
}
.m214-status-pending::before { content: "● "; color: #e6c07b; }
.m214-status-none::before { content: "○ "; color: #8899a6; }
.m214-status-current::before { content: "▶ "; }
.m214-error { color: #f0a0a0; }
@media (max-width: 900px) {
  .m214-workspace { grid-template-columns: 1fr; }
}
'''

E2E_SPEC = r'''import { test, expect } from "@playwright/test";

/**
 * Focused M2.14 Playwright smoke (section 53).
 * Requires STUDIO_FEATURE_CODIRECTOR_UNIFIED_EXPERIENCE_V1=true in the API env.
 */
test.describe("M2.14 Unified Experience", () => {
  test("workspace renders three-pane shell when flag on", async ({ page }) => {
    await page.goto("/codirector");
    const ws = page.getByTestId("m214-unified-workspace");
    // When flag off, workspace is not rendered — soft skip
    if ((await ws.count()) === 0) {
      test.skip(true, "M2.14 flag off in this environment");
    }
    await expect(ws).toBeVisible();
    await expect(page.getByTestId("m214-flag-badge")).toContainText("Flag:");
    await expect(page.getByTestId("m214-approval-center")).toBeVisible();
    await expect(page.getByTestId("m214-production-plan")).toBeVisible();
  });

  test("hitchhiker mocked media labeled", async ({ page }) => {
    await page.goto("/codirector");
    const btn = page.getByTestId("m214-hitchhiker");
    if ((await btn.count()) === 0) {
      test.skip(true, "M2.14 flag off in this environment");
    }
    await btn.click();
    await expect(page.getByTestId("m214-media-image")).toContainText("MOCKED");
  });
});
'''


def main() -> None:
    w(WEB / "UnifiedExperienceWorkspace.tsx", WORKSPACE)
    w(WEB / "UnifiedMediaCard.tsx", MEDIA_CARD)
    w(WEB / "ApprovalCenterPanel.tsx", APPROVAL)
    w(WEB / "ProductionPlanPanel.tsx", PLAN)
    w(WEB / "m214-unified.css", CSS)
    w(E2E / "m214-unified-experience.spec.ts", E2E_SPEC)
    print("ui emit complete")


if __name__ == "__main__":
    main()
