import { useEffect, useMemo, useRef, useState } from "react";
import { api, type CoDirectorBible } from "../../api";
import type { Asset, Project } from "../../types";
import { PanelHeading } from "../HelpTip";
import { Button } from "../ui";
import "./brand-studio.css";
import {
  BACKGROUND_OPTIONS,
  CAMPAIGN_TYPES,
  COMPOSITION_OPTIONS,
  FORMAT_OPTIONS,
  RESULT_LANES,
  TYPOGRAPHY_TEMPLATES,
  VISUAL_DIRECTIONS,
  assetLabel,
  buildBrandCheck,
  collectBrandResults,
  parseBrandStudioState,
  pickBrandImages,
  serializeBrandStudioState,
  upsertQueuedResults,
  type BrandStudioCampaign,
  type ResultLane,
} from "./brandStudioModel";

function slugify(value: string) {
  return value.toLowerCase().replace(/[^a-z0-9]+/g, "-");
}

function pullText(record: Record<string, unknown>, keys: string[]) {
  for (const key of keys) {
    const value = record[key];
    if (typeof value === "string" && value.trim()) return value.trim();
  }
  return "";
}

function extractPalette(...blocks: string[]) {
  const matches = blocks
    .flatMap((block) => Array.from(block.matchAll(/#(?:[0-9a-fA-F]{6})\b/g)).map((match) => match[0]))
    .slice(0, 6);
  return Array.from(new Set(matches));
}

function buildBibleImport(campaign: BrandStudioCampaign, bible: CoDirectorBible): BrandStudioCampaign {
  const version = bible.currentVersion;
  if (!version) return campaign;
  const entities = version.entities || [];
  const facts = version.facts || [];
  const projectProfile = entities.find((entity) => entity.entityType === "project_profile");
  const visualEntities = entities.filter((entity) => ["visual_style", "visual_language", "production_rule"].includes(entity.entityType));
  const propEntity = entities.find((entity) => ["prop", "production_object"].includes(entity.entityType));
  const styleNotes = visualEntities
    .map((entity) => pullText(entity.data || {}, ["description", "summary", "appearanceSummary", "claim"]))
    .filter(Boolean)
    .slice(0, 4)
    .join(" ");
  const factText = facts.map((fact) => fact.statement || "").join(" ");
  const profileSummary = projectProfile ? pullText(projectProfile.data || {}, ["description", "summary"]) : "";
  const palette = extractPalette(version.summary || "", profileSummary, styleNotes, factText);
  return {
    ...campaign,
    brandKit: {
      ...campaign.brandKit,
      source: "production_bible",
      bibleSummary: [version.summary, profileSummary].filter(Boolean).join(" ").trim(),
      styleNotes: [campaign.brandKit.styleNotes, styleNotes].filter(Boolean).join(" ").trim(),
      productName: campaign.brandKit.productName || propEntity?.displayName || "",
      colorPalette: palette.length ? palette : campaign.brandKit.colorPalette,
      inheritedEntityKeys: entities.slice(0, 24).map((entity) => entity.entityKey),
      inheritedAt: new Date().toISOString(),
    },
  };
}

function formatLaneLabel(value: ResultLane) {
  if (value === "concepts") return "Concepts";
  if (value === "variations") return "Variations";
  if (value === "formats") return "Formats";
  return "Approved";
}

function EmptyLockState({
  title,
  body,
  actionLabel,
  onAction,
}: {
  title: string;
  body: string;
  actionLabel: string;
  onAction: () => void;
}) {
  return (
    <div className="brand-studio__empty-lock">
      <strong>{title}</strong>
      <p>{body}</p>
      <Button variant="secondary" onClick={onAction}>
        {actionLabel}
      </Button>
    </div>
  );
}

function AssetChoiceCard({
  title,
  subtitle,
  asset,
  selected,
  onSelect,
}: {
  title: string;
  subtitle: string;
  asset: Asset;
  selected: boolean;
  onSelect: (assetId: string) => void;
}) {
  return (
    <button
      type="button"
      className={`brand-studio__asset-card${selected ? " is-selected" : ""}`}
      onClick={() => onSelect(asset.id)}
      data-testid={`${slugify(title)}-${asset.id}`}
    >
      <span className="brand-studio__asset-thumb">
        <img src={api.assetUrl(asset.id)} alt={assetLabel(asset)} loading="lazy" />
      </span>
      <span className="brand-studio__asset-meta">
        <strong>{assetLabel(asset)}</strong>
        <span>{subtitle}</span>
      </span>
    </button>
  );
}

export function BrandStudioWorkspace({
  project,
  onChange,
}: {
  project: Project;
  onChange?: () => Promise<void>;
}) {
  const [state, setState] = useState(() => parseBrandStudioState(project));
  const [saveState, setSaveState] = useState<"idle" | "saving" | "saved" | "error">("idle");
  const [msg, setMsg] = useState("");
  const [busy, setBusy] = useState(false);
  const [bibleBusy, setBibleBusy] = useState(false);
  const initialized = useRef(false);
  const assets = useMemo(() => pickBrandImages(project), [project]);
  const campaign = state.activeCampaign;
  const heroPreview = useMemo(() => {
    const all = collectBrandResults(project, campaign, state.results);
    return all.find((item) => item.lane === "approved") || all[0] || null;
  }, [campaign, project, state.results]);
  const brandCheck = useMemo(() => buildBrandCheck(campaign), [campaign]);
  const groupedResults = useMemo(() => collectBrandResults(project, campaign, state.results), [campaign, project, state.results]);

  useEffect(() => {
    setState(parseBrandStudioState(project));
    initialized.current = false;
  }, [project.id]);

  const persistState = async (nextState: typeof state) => {
    try {
      setSaveState("saving");
      await api.updateProject(project.id, {
        settings_json: serializeBrandStudioState(project.settings_json, nextState),
      } as Partial<Project>);
      setSaveState("saved");
    } catch (error) {
      console.error(error);
      setSaveState("error");
    }
  };

  useEffect(() => {
    if (!initialized.current) {
      initialized.current = true;
      return;
    }
    const handle = window.setTimeout(async () => {
      await persistState(state);
    }, 300);
    return () => window.clearTimeout(handle);
  }, [project.id, project.settings_json, state]);

  const patchCampaign = (patch: Partial<BrandStudioCampaign>) => {
    setState((current) => ({
      ...current,
      activeCampaign: {
        ...current.activeCampaign,
        ...patch,
      },
    }));
  };

  const patchBrandKit = (patch: Partial<BrandStudioCampaign["brandKit"]>) => {
    setState((current) => ({
      ...current,
      activeCampaign: {
        ...current.activeCampaign,
        brandKit: {
          ...current.activeCampaign.brandKit,
          ...patch,
        },
      },
    }));
  };

  const saveColorPalette = (raw: string) => {
    patchBrandKit({
      colorPalette: raw
        .split(/[\n,]+/)
        .map((value) => value.trim())
        .filter(Boolean),
    });
  };

  const scrollBrandKit = () => {
    document.getElementById("brand-kit-section")?.scrollIntoView({ behavior: "smooth", block: "start" });
  };

  const buildRunPayload = (format: string, lane: ResultLane) => ({
    toolId: "brand.studio",
    prompt: campaign.brief,
    requiredWording: campaign.brandKit.requiredWording,
    brandColors: campaign.brandKit.colorPalette,
    logoAssetIds: campaign.brandKit.logoAssetId ? [campaign.brandKit.logoAssetId] : [],
    productAssetIds: campaign.brandKit.productAssetId ? [campaign.brandKit.productAssetId] : [],
    campaignName: campaign.name,
    campaignType: campaign.campaignType,
    visualDirection: campaign.visualDirection,
    composition: campaign.composition,
    background: campaign.background,
    format,
    campaignFormats: campaign.campaignFormats,
    typographyTemplate: campaign.typographyTemplate,
    productName: campaign.brandKit.productName,
    styleNotes: campaign.brandKit.styleNotes,
    bibleSummary: campaign.brandKit.bibleSummary,
    resultLane: lane,
    confirmPaidCloud: false,
  });

  const run = async () => {
    setBusy(true);
    setMsg("");
    try {
      const formats = Array.from(new Set([campaign.heroFormat, ...campaign.campaignFormats])).slice(0, 4);
      const queued: Array<{ assetId?: string; jobId?: string; lane: ResultLane; format: string; title: string }> = [];
      for (const format of formats) {
        const lane = format === campaign.heroFormat ? campaign.resultLane : "formats";
        const res = await api.runGenerationTool(project.id, buildRunPayload(format, lane));
        queued.push({
          assetId: res.assetId,
          jobId: res.jobId,
          lane,
          format,
          title: `${campaign.name} · ${format}`,
        });
      }
      const nextState = {
        ...state,
        activeCampaign: {
          ...state.activeCampaign,
          lastGeneratedAt: new Date().toISOString(),
        },
        results: upsertQueuedResults(state.results, queued),
      };
      setState(nextState);
      await persistState(nextState);
      setMsg(`Queued ${queued.length} brand-safe ${queued.length === 1 ? "visual" : "visuals"} with preserved locks.`);
      await onChange?.();
    } catch (e) {
      setMsg(e instanceof Error ? e.message : "Brand generate failed");
    } finally {
      setBusy(false);
    }
  };

  const importFromBible = async () => {
    setBibleBusy(true);
    setMsg("");
    try {
      const bible = await api.getBible(project.id);
      if (!bible.currentVersion) {
        setMsg("Production Bible is empty. Start a Brand Kit from this project library, or seed canon first.");
        return;
      }
      const nextState = {
        ...state,
        activeCampaign: buildBibleImport(state.activeCampaign, bible),
      };
      setState(nextState);
      await persistState(nextState);
      setMsg("Production Bible guidance imported as read-only brand direction.");
    } catch (error) {
      setMsg(error instanceof Error ? error.message : "Production Bible import failed");
    } finally {
      setBibleBusy(false);
    }
  };

  const createProposal = async () => {
    setBusy(true);
    setMsg("");
    try {
      const proposal = await api.proposeCoDirectorToolCall(project.id, {
        toolId: "propose_brand_generate",
        arguments: {
          campaignName: campaign.name,
          prompt: campaign.brief,
          requiredWording: campaign.brandKit.requiredWording,
          campaignType: campaign.campaignType,
          visualDirection: campaign.visualDirection,
          composition: campaign.composition,
          background: campaign.background,
          format: campaign.heroFormat,
          logoAssetId: campaign.brandKit.logoAssetId || undefined,
          productAssetId: campaign.brandKit.productAssetId || undefined,
          brandColors: campaign.brandKit.colorPalette.join(", "),
          typographyTemplate: campaign.typographyTemplate,
          productName: campaign.brandKit.productName,
          styleNotes: campaign.brandKit.styleNotes,
          bibleSummary: campaign.brandKit.bibleSummary,
          resultLane: campaign.resultLane,
        },
        createdBy: "user",
      });
      const nextState = {
        ...state,
        activeCampaign: {
          ...state.activeCampaign,
          latestProposalId: proposal.id,
        },
      };
      setState(nextState);
      await persistState(nextState);
      setMsg("Co-Director proposal created. Review and approve it before any canon-adjacent brand mutation.");
    } catch (error) {
      setMsg(error instanceof Error ? error.message : "Proposal could not be created");
    } finally {
      setBusy(false);
    }
  };

  const toggleApproved = (assetId: string) => {
    const ids = new Set(campaign.approvedAssetIds);
    if (ids.has(assetId)) ids.delete(assetId);
    else ids.add(assetId);
    const nextState = {
      ...state,
      activeCampaign: {
        ...state.activeCampaign,
        approvedAssetIds: [...ids],
      },
      results: state.results.map((result) =>
        result.assetId === assetId
          ? ({
              ...result,
              lane: (ids.has(assetId) ? "approved" : "formats") as ResultLane,
            })
          : result,
      ),
    };
    setState(nextState);
    void persistState(nextState);
  };

  const lockSummaryReady =
    campaign.brandKit.logoAssetId ||
    campaign.brandKit.productAssetId ||
    campaign.brandKit.requiredWording ||
    campaign.brandKit.bibleSummary;

  return (
    <div className="page brand-studio" data-testid="brand-studio">
      <PanelHeading
        title="Brand Studio"
        tip="Build creator-friendly campaigns with locked brand ingredients, visual direction, and grouped outputs. Canon stays proposal-gated whenever a change would affect the Production Bible."
      />
      <div className="brand-studio__hero">
        <div>
          <h2>{campaign.name}</h2>
          <p>
            Preview first, advanced second. Build a campaign canvas, lock the ingredients that matter, and generate
            brand-safe artwork into this project&apos;s library only.
          </p>
        </div>
        <div className="brand-studio__status-cluster">
          <span className="pill" data-testid="brand-save-status">
            {saveState === "saving"
              ? "Saving campaign"
              : saveState === "saved"
                ? "Campaign saved"
                : saveState === "error"
                  ? "Save needs retry"
                  : "Campaign ready"}
          </span>
          <span className="pill">
            Brand Check {brandCheck.ready}/{brandCheck.total}
          </span>
        </div>
      </div>

      <div className="brand-studio__shell">
        <section className="brand-studio__preview">
          <div
            className="brand-studio__canvas"
            style={{
              background: `linear-gradient(140deg, ${campaign.brandKit.colorPalette[0] || "#0f172a"} 0%, ${
                campaign.brandKit.colorPalette[1] || "#111827"
              } 100%)`,
            }}
          >
            <div className="brand-studio__canvas-copy">
              <span className="brand-studio__eyebrow">Campaign Canvas</span>
              <h3>{CAMPAIGN_TYPES.find((item) => item.id === campaign.campaignType)?.label || "Brand Campaign"}</h3>
              <p>{campaign.brief}</p>
              <div className="brand-studio__canvas-pills">
                <span>{campaign.heroFormat}</span>
                <span>{campaign.composition}</span>
                <span>{campaign.background}</span>
                <span>{VISUAL_DIRECTIONS.find((item) => item.id === campaign.visualDirection)?.label}</span>
              </div>
            </div>
            <div className="brand-studio__canvas-preview">
              {heroPreview?.assetId ? (
                <img src={api.assetUrl(heroPreview.assetId)} alt={heroPreview.title} loading="lazy" />
              ) : (
                <div className="brand-studio__canvas-empty">
                  <strong>Preview will bloom here.</strong>
                  <span>Generate concepts, variations, and campaign formats once your brand locks feel right.</span>
                </div>
              )}
            </div>
          </div>

          {!lockSummaryReady ? (
            <div className="brand-studio__empty-state">
              <h3>Start your Brand Kit</h3>
              <p>
                Choose visual locks from this project library, or inherit tone and canon guidance from the Production
                Bible without mutating it.
              </p>
              <div className="brand-studio__empty-actions">
                <Button variant="primary" onClick={scrollBrandKit}>
                  Create Brand Kit
                </Button>
                <Button variant="secondary" onClick={() => void importFromBible()} loading={bibleBusy} data-testid="brand-import-bible">
                  Import from Production Bible
                </Button>
              </div>
            </div>
          ) : null}

          <div className="brand-studio__check card">
            <div className="brand-studio__section-head">
              <div>
                <span className="brand-studio__eyebrow">Brand Check</span>
                <h3>Compliance summary</h3>
              </div>
              <p>Every lock stays reassuring, visible, and tied to this open project library.</p>
            </div>
            <div className="brand-studio__check-grid">
              {brandCheck.items.map((item) => (
                <article key={item.label} className={`brand-studio__check-item${item.ok ? " is-ready" : ""}`}>
                  <strong>{item.label}</strong>
                  <span>{item.ok ? "Ready" : "Needs love"}</span>
                  <p>{item.note}</p>
                </article>
              ))}
            </div>
          </div>

          <div className="brand-studio__gallery card" data-testid="brand-gallery">
            <div className="brand-studio__section-head">
              <div>
                <span className="brand-studio__eyebrow">Results Gallery</span>
                <h3>Concepts, variations, formats, approved</h3>
              </div>
              <p>Outputs stay grouped by creative intent so reviews feel like a campaign wall, not a file dump.</p>
            </div>
            <div className="brand-studio__gallery-stack">
              {RESULT_LANES.map((lane) => {
                const entries = groupedResults.filter((item) => item.lane === lane);
                return (
                  <section key={lane} className="brand-studio__gallery-lane">
                    <header>
                      <h4>{formatLaneLabel(lane)}</h4>
                      <span>{entries.length}</span>
                    </header>
                    {entries.length ? (
                      <div className="brand-studio__gallery-grid">
                        {entries.map((entry) => (
                          <article key={entry.id} className="brand-studio__result-card">
                            <div className="brand-studio__result-thumb">
                              {entry.assetId ? (
                                <img src={api.assetUrl(entry.assetId)} alt={entry.title} loading="lazy" />
                              ) : (
                                <div className="brand-studio__result-placeholder">Queued</div>
                              )}
                            </div>
                            <div className="brand-studio__result-meta">
                              <strong>{entry.title}</strong>
                              <span>{entry.format}</span>
                              <span>{entry.status === "queued" ? "Queued for render" : "In project library"}</span>
                            </div>
                            {entry.assetId ? (
                              <Button
                                variant={campaign.approvedAssetIds.includes(entry.assetId) ? "primary" : "secondary"}
                                compact
                                onClick={() => toggleApproved(entry.assetId as string)}
                              >
                                {campaign.approvedAssetIds.includes(entry.assetId) ? "Approved" : "Mark approved"}
                              </Button>
                            ) : null}
                          </article>
                        ))}
                      </div>
                    ) : (
                      <p className="brand-studio__lane-empty">Nothing here yet. Generate a campaign set to begin.</p>
                    )}
                  </section>
                );
              })}
            </div>
          </div>
        </section>

        <aside className="brand-studio__controls">
          <div className="card brand-studio__card">
            <div className="brand-studio__section-head">
              <div>
                <span className="brand-studio__eyebrow">Creative Direction</span>
                <h3>Campaign canvas</h3>
              </div>
              <p>Guide the intent in human language, then let the tooling hold the technical contract.</p>
            </div>

            <label className="brand-studio__field">
              <span>Campaign name</span>
              <input value={campaign.name} onChange={(e) => patchCampaign({ name: e.target.value })} />
            </label>

            <div className="brand-studio__visual-grid">
              {CAMPAIGN_TYPES.map((item) => (
                <button
                  key={item.id}
                  type="button"
                  className={`brand-studio__choice-card${campaign.campaignType === item.id ? " is-selected" : ""}`}
                  onClick={() => patchCampaign({ campaignType: item.id })}
                  data-testid={`brand-campaign-type-${item.id}`}
                >
                  <strong>{item.label}</strong>
                  <span>{item.blurb}</span>
                </button>
              ))}
            </div>

            <label className="brand-studio__field">
              <span>Creative brief</span>
              <textarea
                rows={5}
                value={campaign.brief}
                onChange={(e) => patchCampaign({ brief: e.target.value })}
                data-testid="brand-brief"
                placeholder="Describe the campaign, the feeling, the product story, and what the viewer should feel."
              />
            </label>
          </div>

          <div className="card brand-studio__card" id="brand-kit-section">
            <div className="brand-studio__section-head">
              <div>
                <span className="brand-studio__eyebrow">Brand Kit</span>
                <h3>Visual locks that feel trustworthy</h3>
              </div>
              <p>No raw asset IDs, no dead empty selectors. Choose what must stay recognizable.</p>
            </div>

            <label className="brand-studio__field">
              <span>Locked wording</span>
              <input
                value={campaign.brandKit.requiredWording}
                onChange={(e) => patchBrandKit({ requiredWording: e.target.value, source: "manual" })}
                placeholder="Headline, offer, tagline, or required legal copy"
                data-testid="brand-required-wording"
              />
            </label>

            <label className="brand-studio__field">
              <span>Brand colors</span>
              <textarea
                rows={2}
                value={campaign.brandKit.colorPalette.join(", ")}
                onChange={(e) => saveColorPalette(e.target.value)}
                placeholder="#0d9488, #f8fafc, #111827"
              />
            </label>

            <label className="brand-studio__field">
              <span>Product name</span>
              <input
                value={campaign.brandKit.productName}
                onChange={(e) => patchBrandKit({ productName: e.target.value })}
                placeholder="Hero product or collection"
              />
            </label>

            <label className="brand-studio__field">
              <span>Typography feel</span>
              <input
                value={campaign.brandKit.typography}
                onChange={(e) => patchBrandKit({ typography: e.target.value })}
                placeholder="Elegant serif with soft luxury spacing"
              />
            </label>

            <label className="brand-studio__field">
              <span>Style notes</span>
              <textarea
                rows={3}
                value={campaign.brandKit.styleNotes}
                onChange={(e) => patchBrandKit({ styleNotes: e.target.value })}
                placeholder="Lighting, texture, brand personality, shelf presence, styling cues..."
              />
            </label>

            <div className="brand-studio__palette">
              {campaign.brandKit.colorPalette.map((color) => (
                <span key={color} style={{ background: color }} title={color}>
                  {color}
                </span>
              ))}
            </div>

            <div className="brand-studio__lock-sections">
              <section>
                <div className="brand-studio__lock-head">
                  <strong>Logo lock</strong>
                  <span>Choose from this project library</span>
                </div>
                {assets.length ? (
                  <div className="brand-studio__asset-grid">
                    {assets.slice(0, 8).map((asset) => (
                      <AssetChoiceCard
                        key={`logo-${asset.id}`}
                        title="brand-logo-lock"
                        subtitle="Use as logo reference"
                        asset={asset}
                        selected={campaign.brandKit.logoAssetId === asset.id}
                        onSelect={(assetId) => patchBrandKit({ logoAssetId: assetId, source: "library" })}
                      />
                    ))}
                  </div>
                ) : (
                  <EmptyLockState
                    title="Create Brand Kit"
                    body="Add images to this project library first so Brand Studio has a logo or emblem to protect."
                    actionLabel="Open library workflow"
                    onAction={scrollBrandKit}
                  />
                )}
              </section>

              <section>
                <div className="brand-studio__lock-head">
                  <strong>Product / packaging lock</strong>
                  <span>Keep hero silhouettes and packaging cues stable</span>
                </div>
                {assets.length ? (
                  <div className="brand-studio__asset-grid">
                    {assets.slice(0, 8).map((asset) => (
                      <AssetChoiceCard
                        key={`product-${asset.id}`}
                        title="brand-product-lock"
                        subtitle="Use as product reference"
                        asset={asset}
                        selected={campaign.brandKit.productAssetId === asset.id}
                        onSelect={(assetId) => patchBrandKit({ productAssetId: assetId, source: "library" })}
                      />
                    ))}
                  </div>
                ) : (
                  <EmptyLockState
                    title="Import from Production Bible"
                    body="Pull approved story and style guidance while you gather visual references for the package itself."
                    actionLabel="Import Bible guidance"
                    onAction={() => void importFromBible()}
                  />
                )}
              </section>
            </div>

            <div className="brand-studio__inline-actions">
              <Button variant="secondary" onClick={() => void importFromBible()} loading={bibleBusy}>
                Import from Production Bible
              </Button>
              {campaign.brandKit.bibleSummary ? <span className="pill">Read-only canon guidance loaded</span> : null}
            </div>
            {campaign.brandKit.bibleSummary ? <p className="brand-studio__bible-note">{campaign.brandKit.bibleSummary}</p> : null}
          </div>

          <div className="card brand-studio__card">
            <div className="brand-studio__section-head">
              <div>
                <span className="brand-studio__eyebrow">Visual Direction</span>
                <h3>Shape the image language</h3>
              </div>
              <p>Keep the creative choices tactile: direction, composition, background, format, and finishing template.</p>
            </div>

            <div className="brand-studio__visual-grid">
              {VISUAL_DIRECTIONS.map((item) => (
                <button
                  key={item.id}
                  type="button"
                  className={`brand-studio__choice-card${campaign.visualDirection === item.id ? " is-selected" : ""}`}
                  onClick={() => patchCampaign({ visualDirection: item.id })}
                  data-testid={`brand-direction-${item.id}`}
                >
                  <strong>{item.label}</strong>
                  <span>{item.blurb}</span>
                </button>
              ))}
            </div>

            <div className="brand-studio__chip-row">
              {COMPOSITION_OPTIONS.map((item) => (
                <Button
                  key={item}
                  variant={campaign.composition === item ? "primary" : "secondary"}
                  compact
                  onClick={() => patchCampaign({ composition: item })}
                >
                  {item}
                </Button>
              ))}
            </div>

            <div className="brand-studio__chip-row">
              {BACKGROUND_OPTIONS.map((item) => (
                <Button
                  key={item}
                  variant={campaign.background === item ? "primary" : "secondary"}
                  compact
                  onClick={() => patchCampaign({ background: item })}
                >
                  {item}
                </Button>
              ))}
            </div>

            <div className="brand-studio__chip-row">
              {FORMAT_OPTIONS.map((item) => (
                <Button
                  key={item}
                  variant={campaign.heroFormat === item ? "primary" : "secondary"}
                  compact
                  onClick={() => patchCampaign({ heroFormat: item })}
                  data-testid={`brand-format-${slugify(item)}`}
                >
                  {item}
                </Button>
              ))}
            </div>

            <div className="brand-studio__section-head brand-studio__subhead">
              <div>
                <span className="brand-studio__eyebrow">Campaign Sets</span>
                <h3>Multi-format generation</h3>
              </div>
              <p>Choose the delivery mix you want generated around the hero concept.</p>
            </div>

            <div className="brand-studio__formats-grid">
              {FORMAT_OPTIONS.map((item) => {
                const selected = campaign.campaignFormats.includes(item);
                return (
                  <button
                    key={item}
                    type="button"
                    className={`brand-studio__format-card${selected ? " is-selected" : ""}`}
                    onClick={() =>
                      patchCampaign({
                        campaignFormats: selected
                          ? campaign.campaignFormats.filter((format) => format !== item)
                          : [...campaign.campaignFormats, item],
                      })
                    }
                    data-testid={`brand-campaign-set-${slugify(item)}`}
                  >
                    <strong>{item}</strong>
                    <span>{selected ? "Included in set" : "Tap to include"}</span>
                  </button>
                );
              })}
            </div>

            <label className="brand-studio__field">
              <span>Typography finishing template</span>
              <select
                value={campaign.typographyTemplate}
                onChange={(e) => patchCampaign({ typographyTemplate: e.target.value })}
              >
                {TYPOGRAPHY_TEMPLATES.map((item) => (
                  <option key={item} value={item}>
                    {item}
                  </option>
                ))}
              </select>
            </label>

            <label className="brand-studio__field">
              <span>Generate into gallery lane</span>
              <select
                value={campaign.resultLane}
                onChange={(e) => patchCampaign({ resultLane: e.target.value as ResultLane })}
              >
                {RESULT_LANES.filter((lane) => lane !== "approved").map((lane) => (
                  <option key={lane} value={lane}>
                    {formatLaneLabel(lane)}
                  </option>
                ))}
              </select>
            </label>

            <details className="brand-studio__advanced" data-testid="brand-advanced">
              <summary>Advanced</summary>
              <label className="brand-studio__field">
                <span>Extra finishing notes</span>
                <textarea
                  rows={3}
                  value={campaign.advancedNotes}
                  onChange={(e) => patchCampaign({ advancedNotes: e.target.value })}
                  placeholder="Safe margins, lockup placement, legal footer, export notes, alternate headline guidance..."
                />
              </label>
              <p className="brand-studio__advanced-note">
                Advanced stays collapsed by default. Creator-first controls live above; technical details stay tucked
                away until needed.
              </p>
            </details>
          </div>

          <div className="card brand-studio__card">
            <div className="brand-studio__section-head">
              <div>
                <span className="brand-studio__eyebrow">Generate</span>
                <h3>Brand-safe artwork</h3>
              </div>
              <p>Generation is always non-destructive. Originals stay untouched, and every output lands in this project library.</p>
            </div>
            <div className="brand-studio__inline-actions">
              <Button variant="primary" disabled={busy} loading={busy} onClick={() => void run()} data-testid="brand-generate">
                Generate artwork
              </Button>
              <Button variant="secondary" disabled={busy} onClick={() => void createProposal()} data-testid="brand-propose">
                Create Co-Director proposal
              </Button>
            </div>
            <p className="brand-studio__advanced-note">
              Production Bible inheritance is read-only here. If a future brand change would mutate canon, it should be
              reviewed through an approval proposal rather than applied silently.
            </p>
          </div>
        </aside>
      </div>
      {msg && <p className="pill">{msg}</p>}
    </div>
  );
}
