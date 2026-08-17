import { useEffect, useState, type ReactNode } from "react";
import { api } from "../../api";
import "./prompt-intelligence.css";
import "./prompt-intelligence-v2.css";

export type PromptIntelligenceDomain = "image" | "video" | "audio" | "voice" | "music" | "sfx";

type Props = {
  creatorPrompt: string;
  domain?: PromptIntelligenceDomain;
  providerId?: string | null;
  modelId?: string | null;
  engineId?: string | null;
  negativePrompt?: string;
  projectId?: string;
  sceneId?: string;
  /** Called when Apply succeeds with the final provider prompt + full record. */
  onApply?: (payload: { finalProviderPrompt: string; record: Record<string, unknown> }) => void;
  compact?: boolean;
  /** Artist-facing layout for Cinematic Image Generator (no debug chrome). */
  artistLayout?: boolean;
  /** Optional accordion summary for artist layout. */
  onArtistStatusChange?: (status: string) => void;
  /** Optional quality meter host rendered below the action row. */
  qualitySlot?: ReactNode;
};

const DEFAULT_MODULES = {
  productionRefinement: true,
  cinematicRefinement: true,
  motionRefinement: true,
  audioRefinement: true,
  characterContinuity: true,
  providerOptimization: true,
  languageModules: ["en"] as string[],
};

export function PromptIntelligencePanel({
  creatorPrompt,
  domain = "video",
  providerId,
  modelId,
  engineId,
  negativePrompt,
  projectId,
  sceneId,
  onApply,
  compact = false,
  artistLayout = false,
  onArtistStatusChange,
  qualitySlot,
}: Props) {
  const [open, setOpen] = useState(!compact || artistLayout);
  const [production, setProduction] = useState(true);
  const [providerOpt, setProviderOpt] = useState(true);
  const [chineseOn, setChineseOn] = useState(false);
  const [balance, setBalance] = useState<"subtle" | "balanced" | "strong">("balanced");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [recommendation, setRecommendation] = useState<string | null>(null);
  const [record, setRecord] = useState<Record<string, unknown> | null>(null);
  const [refined, setRefined] = useState("");
  const [chinese, setChinese] = useState("");
  const [finalPrompt, setFinalPrompt] = useState("");
  const [overridden, setOverridden] = useState(false);
  const [scores, setScores] = useState<{
    overall: number;
    dimensions: Record<string, number>;
    recommendations: Array<{ code: string; message: string; severity: string }>;
  } | null>(null);
  const [strategyMode, setStrategyMode] = useState<"manual" | "recommend" | "automatic_certified">("recommend");
  const [strategyRec, setStrategyRec] = useState<Record<string, unknown> | null>(null);
  const [axes, setAxes] = useState<{
    promptQuality: number;
    providerCompatibility: number;
    recommendedStrategyConfidence: number;
  } | null>(null);

  useEffect(() => {
    if (!artistLayout || !onArtistStatusChange) return;
    const modeLabel =
      strategyMode === "manual" ? "Manual" : strategyMode === "automatic_certified" ? "Certified Auto" : "Co-Director";
    onArtistStatusChange(chineseOn ? `${modeLabel} · English + Chinese` : modeLabel);
  }, [artistLayout, strategyMode, chineseOn, onArtistStatusChange]);

  const modulesEnabled = {
    ...DEFAULT_MODULES,
    productionRefinement: production,
    cinematicRefinement: production,
    motionRefinement: production && domain === "video",
    audioRefinement: production && ["audio", "music", "sfx", "voice"].includes(domain),
    providerOptimization: providerOpt,
    languageModules: chineseOn ? ["en", "zh"] : ["en"],
  };

  const bodyBase = (opts?: { forceGenerated?: boolean }) => {
    const forceGenerated = Boolean(opts?.forceGenerated);
    const isOverride = forceGenerated ? false : overridden;
    return {
      creatorPrompt,
      domain,
      providerId: providerId || undefined,
      modelId: modelId || undefined,
      engineId: engineId || undefined,
      negativePrompt: negativePrompt || undefined,
      modulesEnabled,
      languageBalance: balance,
      projectId,
      sceneId,
      manuallyOverridden: isOverride,
      existingFinalPrompt: isOverride ? finalPrompt : undefined,
      strategyMode,
      projectPrefs: { strategyMode, minConfidence: "medium" },
      category: "general",
    };
  };

  const runEnhance = async (opts?: { forceGenerated?: boolean }) => {
    if (!creatorPrompt.trim()) {
      setError("Enter a creator prompt first.");
      return;
    }
    const forceGenerated = Boolean(opts?.forceGenerated);
    setBusy(true);
    setError(null);
    try {
      const payload = bodyBase({ forceGenerated });
      const [enhanced, analyzed] = await Promise.all([
        api.promptIntelligence.enhance(payload),
        api.promptIntelligence.analyze(payload),
      ]);
      const rec = (enhanced.record || {}) as Record<string, unknown>;
      setRecord(rec);
      setRecommendation(enhanced.profileRecommendation || null);
      const recStrategy =
        (enhanced as { strategyRecommendation?: Record<string, unknown> }).strategyRecommendation ||
        (analyzed as { strategyRecommendation?: Record<string, unknown> }).strategyRecommendation ||
        null;
      setStrategyRec(recStrategy);
      const a2 =
        (enhanced as { analyzerV2?: Record<string, number> }).analyzerV2 ||
        (analyzed as { analyzerV2?: Record<string, number> }).analyzerV2;
      if (a2) {
        setAxes({
          promptQuality: Number(a2.promptQuality || 0),
          providerCompatibility: Number(a2.providerCompatibility || 0),
          recommendedStrategyConfidence: Number(a2.recommendedStrategyConfidence || 0),
        });
      }
      if (forceGenerated || !overridden) {
        setOverridden(false);
        setRefined(String(rec.refinedEnglishPrompt || ""));
        setChinese(String((rec.languageEnhancements as Record<string, string> | undefined)?.zh || rec.chineseEnhancement || ""));
        // Never silent-apply uncertified bilingual — only fill preview fields
        setFinalPrompt(String(rec.finalProviderPrompt || ""));
        if (
          strategyMode === "automatic_certified" &&
          recStrategy?.appliedAutomatically &&
          String(recStrategy.status || "").startsWith("certified_")
        ) {
          // Explicit certified auto path still leaves Final previewable; user confirms Apply
          setChineseOn(String(recStrategy.strategy || "").startsWith("bilingual"));
        }
      }
      if (analyzed.qualityReport) {
        setScores({
          overall: analyzed.qualityReport.overall,
          dimensions: analyzed.qualityReport.dimensions || {},
          recommendations: analyzed.qualityReport.recommendations || [],
        });
      }
      if (!enhanced.ok && enhanced.error) {
        setError(String((enhanced.error as { message?: string }).message || "Enhancement used English-only fallback."));
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "Prompt Intelligence failed.");
    } finally {
      setBusy(false);
    }
  };

  const apply = () => {
    if (!finalPrompt.trim()) return;
    const nextRecord = {
      ...(record || {}),
      creatorPrompt,
      originalPrompt: creatorPrompt,
      refinedEnglishPrompt: refined,
      languageEnhancements: { ...((record?.languageEnhancements as object) || {}), zh: chinese },
      chineseEnhancement: chinese,
      finalProviderPrompt: finalPrompt,
      manuallyOverridden: overridden,
      modulesEnabled,
      languageBalance: balance,
    };
    onApply?.({ finalProviderPrompt: finalPrompt, record: nextRecord });
  };

  const resetGenerated = () => {
    void runEnhance({ forceGenerated: true });
  };

  return (
    <div
      className={`prompt-intelligence-panel${artistLayout ? " prompt-intelligence-panel--artist" : ""}`}
      data-testid="prompt-intelligence-panel"
    >
      {!artistLayout ? (
        <button
          type="button"
          className="ghost prompt-intelligence-panel__toggle"
          aria-expanded={open}
          data-testid="prompt-intelligence-toggle"
          onClick={() => setOpen((v) => !v)}
        >
          Prompt Intelligence {open ? "▾" : "▸"}
        </button>
      ) : null}
      {open ? (
        <div className="prompt-intelligence-panel__body">
          {artistLayout ? (
            <div className="cis-pi-strategy" role="radiogroup" aria-label="Prompt Intelligence mode">
              {(
                [
                  ["manual", "Manual"],
                  ["recommend", "Co-Director"],
                  ["automatic_certified", "Certified Auto"],
                ] as const
              ).map(([value, label]) => (
                <label key={value}>
                  <input
                    type="radio"
                    name="cis-pi-strategy"
                    checked={strategyMode === value}
                    data-testid={`prompt-intelligence-strategy-mode-${value}`}
                    onChange={() => setStrategyMode(value)}
                  />
                  {label}
                </label>
              ))}
            </div>
          ) : (
            <div className="prompt-intelligence-panel__balance" role="group" aria-label="Strategy mode">
              <span className="eyebrow">Strategy mode</span>
              {(["manual", "recommend", "automatic_certified"] as const).map((m) => (
                <button
                  key={m}
                  type="button"
                  className={strategyMode === m ? "primary" : "ghost"}
                  data-testid={`prompt-intelligence-strategy-mode-${m}`}
                  onClick={() => setStrategyMode(m)}
                >
                  {m === "automatic_certified" ? "Auto (certified only)" : m}
                </button>
              ))}
            </div>
          )}

          <div className="prompt-intelligence-panel__toggles" role="group" aria-label="Prompt Intelligence modules">
            <label>
              <input type="checkbox" checked={production} onChange={(e) => setProduction(e.target.checked)} />
              {artistLayout ? "Production refinement" : "Refine for production"}
            </label>
            <label>
              <input type="checkbox" checked={providerOpt} onChange={(e) => setProviderOpt(e.target.checked)} />
              Optimize for selected model
            </label>
            <label>
              <input
                type="checkbox"
                checked={chineseOn}
                data-testid="prompt-intelligence-chinese"
                onChange={(e) => setChineseOn(e.target.checked)}
              />
              {artistLayout ? "English + Chinese enhancement" : "Add English + Chinese enhancement"}
            </label>
          </div>

          {chineseOn ? (
            <div className="prompt-intelligence-panel__balance" role="group" aria-label="Language balance">
              <span className="eyebrow">Language Balance</span>
              {(["subtle", "balanced", "strong"] as const).map((b) => (
                <button
                  key={b}
                  type="button"
                  className={balance === b ? "primary" : "ghost"}
                  data-testid={`prompt-intelligence-balance-${b}`}
                  onClick={() => setBalance(b)}
                  title={b === "strong" ? "Advanced / experimental until benchmarked" : undefined}
                >
                  {b === "strong" ? "Strong (advanced)" : b[0].toUpperCase() + b.slice(1)}
                </button>
              ))}
            </div>
          ) : null}

          {!artistLayout && recommendation ? (
            <p className="prompt-intelligence-panel__reco" data-testid="prompt-intelligence-recommendation">
              {recommendation}
            </p>
          ) : null}

          {!artistLayout && strategyRec ? (
            <p className="prompt-intelligence-panel__strategy-banner" data-testid="prompt-intelligence-strategy-rec">
              Recommended strategy: {String(strategyRec.strategy)} · {String(strategyRec.status)} ·{" "}
              {String(strategyRec.confidence)} — {String(strategyRec.reason)}
              {strategyRec.appliedAutomatically ? " (certified auto preview)" : " (not auto-applied)"}
            </p>
          ) : null}

          {!artistLayout && axes ? (
            <div className="prompt-intelligence-panel__axes" data-testid="prompt-intelligence-axes-v2">
              <span>Prompt Quality: {axes.promptQuality}</span>
              <span>Provider Compatibility: {axes.providerCompatibility}</span>
              <span>Strategy Confidence: {axes.recommendedStrategyConfidence}</span>
            </div>
          ) : null}

          {!artistLayout && scores ? (
            <div className="prompt-intelligence-panel__scores" data-testid="prompt-intelligence-scores">
              <strong>Prompt Analysis · {scores.overall} / 100</strong>
              <ul>
                {Object.entries(scores.dimensions).map(([k, v]) => (
                  <li key={k}>
                    {k}: {v}%
                  </li>
                ))}
              </ul>
              {scores.recommendations.slice(0, 3).map((r) => (
                <p key={r.code} className="muted">
                  {r.message}
                </p>
              ))}
            </div>
          ) : null}

          <div className="row-actions prompt-intelligence-panel__actions">
            <button type="button" className="primary" disabled={busy || !creatorPrompt.trim()} data-testid="prompt-intelligence-preview" onClick={() => void runEnhance()}>
              {busy ? "Working…" : artistLayout ? "Preview" : "Preview Enhanced Prompt"}
            </button>
            <button type="button" className="primary" disabled={!finalPrompt.trim()} data-testid="prompt-intelligence-apply" onClick={apply}>
              Apply
            </button>
            <button type="button" disabled={busy || !record} onClick={() => void runEnhance()}>
              Regenerate
            </button>
            <button type="button" disabled={!overridden && !record} data-testid="prompt-intelligence-reset" onClick={resetGenerated}>
              Reset
            </button>
            <button
              type="button"
              disabled={!record}
              data-testid="prompt-intelligence-use-english"
              onClick={() => {
                setChineseOn(false);
                setChinese("");
                setFinalPrompt(refined || creatorPrompt);
                setOverridden(true);
              }}
            >
              Use English Only
            </button>
          </div>

          {qualitySlot}
          {artistLayout && scores ? (
            <div className="cis-quality" data-testid="prompt-intelligence-scores">
              <div className="cis-quality__label">
                <span>
                  Prompt Quality · <strong>{scores.overall >= 80 ? "Excellent" : scores.overall >= 60 ? "Strong" : "Needs work"}</strong>
                </span>
                <span>{scores.overall} / 100</span>
              </div>
              <div className="cis-quality__bar" aria-hidden>
                <span style={{ width: `${Math.max(4, Math.min(100, scores.overall))}%` }} />
              </div>
              <div className="cis-quality__ready">
                {scores.overall >= 75 ? "Ready for Production" : "Refine the shot description, then Preview again."}
              </div>
            </div>
          ) : null}

          {error ? <p className="error">{error}</p> : null}
          {overridden ? (
            <p className="pill" data-testid="prompt-intelligence-override-banner">
              Manual override active — regenerate will not replace the Final Provider Prompt until you Reset.
            </p>
          ) : null}

          {record || finalPrompt ? (
            <div className="prompt-intelligence-panel__preview" data-testid="prompt-intelligence-preview-sections">
              {!artistLayout ? (
                <>
                  <label>
                    Original
                    <textarea readOnly value={creatorPrompt} rows={2} data-testid="prompt-intelligence-original" />
                  </label>
                  <label>
                    Refined English
                    <textarea
                      value={refined}
                      rows={3}
                      data-testid="prompt-intelligence-refined"
                      onChange={(e) => {
                        setRefined(e.target.value);
                        if (!overridden) {
                          setFinalPrompt(
                            chinese ? `${e.target.value.trim()}\n${chinese}`.trim() : e.target.value.trim(),
                          );
                        }
                      }}
                    />
                  </label>
                  <label>
                    Chinese Enhancement
                    <textarea
                      value={chinese}
                      rows={2}
                      data-testid="prompt-intelligence-chinese-text"
                      onChange={(e) => {
                        setChinese(e.target.value);
                        if (!overridden) {
                          setFinalPrompt(
                            e.target.value.trim()
                              ? `${refined.trim()}\n${e.target.value.trim()}`.trim()
                              : refined.trim(),
                          );
                        }
                      }}
                    />
                  </label>
                </>
              ) : null}
              <label>
                {artistLayout ? "Enhanced Prompt" : "Final Provider Prompt"}
                <textarea
                  value={finalPrompt}
                  rows={artistLayout ? 5 : 4}
                  data-testid="prompt-intelligence-final"
                  onChange={(e) => {
                    setFinalPrompt(e.target.value);
                    setOverridden(true);
                  }}
                />
              </label>
            </div>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}
