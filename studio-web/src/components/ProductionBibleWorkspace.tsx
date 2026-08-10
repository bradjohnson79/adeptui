import { useCallback, useEffect, useMemo, useState } from "react";
import { api, ApiError } from "../api";
import type {
  BibleAuditEvent,
  BibleDomainSummary,
  CoDirectorBible,
  CoDirectorBibleDiscoveryAsset,
  CoDirectorBibleDiscoveryGroup,
  CoDirectorBibleDiscoveryItem,
  CoDirectorBibleEntity,
  CoDirectorBibleFact,
  CoDirectorBibleImportPreview,
  CoDirectorBibleVersion,
} from "../api";
import type { Project } from "../types";
import { PanelHeading } from "./HelpTip";

type WorkspaceSection = "home" | "characters" | "locations" | "world" | "continuity" | "history";
type DraftStep = "review" | "choose" | "organize";
type DraftMode = "project" | "manual";

interface DraftState {
  mode: DraftMode;
  step: DraftStep;
  preview: CoDirectorBibleImportPreview;
  selectedEntityKeys: string[];
  selectedFactIndexes: number[];
}

interface ManualSeedForm {
  premise: string;
  visualTone: string;
  characters: string;
  locations: string;
  props: string;
}

const SECTION_LABELS: Record<WorkspaceSection, string> = {
  home: "Home",
  characters: "Characters",
  locations: "Locations",
  world: "World",
  continuity: "Continuity",
  history: "History",
};

const CATEGORY_BLURBS: Record<WorkspaceSection, string> = {
  home: "The trusted memory of this project.",
  characters: "Who lives in the canon.",
  locations: "Where the world comes alive.",
  world: "Story, style, props, and project truths.",
  continuity: "What must stay consistent.",
  history: "How the canon has evolved.",
};

function titleCaseLabel(value: string) {
  return value
    .replace(/[_-]+/g, " ")
    .replace(/\s+/g, " ")
    .trim()
    .replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function lifecycleBadge(status?: string) {
  if (!status || status === "draft") return null;
  const cls =
    status === "locked"
      ? "pill warn"
      : status === "approved"
        ? "pill ok"
        : status === "in_review"
          ? "pill"
          : "pill muted";
  return <span className={cls}>{titleCaseLabel(status)}</span>;
}

function parseNamesList(raw: string) {
  return raw
    .split(/\r?\n|,/)
    .map((item) => item.trim())
    .filter(Boolean);
}

function slugify(text: string, fallback: string) {
  return text.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-+|-+$/g, "") || fallback;
}

function dataString(value: unknown, key?: string) {
  if (!value || typeof value !== "object") return "";
  const record = value as Record<string, unknown>;
  const direct = key ? record[key] : record.description;
  if (typeof direct === "string" && direct.trim()) return direct.trim();
  const fallbackKeys = ["description", "summary", "appearanceSummary", "claim", "sourceTag"];
  for (const name of fallbackKeys) {
    if (typeof record[name] === "string" && String(record[name]).trim()) return String(record[name]).trim();
  }
  return "";
}

function dataArray<T>(value: unknown, key: string): T[] {
  if (!value || typeof value !== "object") return [];
  const candidate = (value as Record<string, unknown>)[key];
  return Array.isArray(candidate) ? (candidate as T[]) : [];
}

function entityReferenceAssets(entity: CoDirectorBibleEntity): CoDirectorBibleDiscoveryAsset[] {
  return dataArray<CoDirectorBibleDiscoveryAsset>(entity.data, "referenceAssets");
}

function entityNeedsReview(entity: CoDirectorBibleEntity) {
  if (!entity.data || typeof entity.data !== "object") return false;
  return Boolean((entity.data as Record<string, unknown>).needsReview);
}

function entityReasons(entity: CoDirectorBibleEntity) {
  return dataArray<string>(entity.data, "classificationReasons");
}

function entitySection(entity: CoDirectorBibleEntity): WorkspaceSection {
  if (entity.entityType === "character") return "characters";
  if (entity.entityType === "location") return "locations";
  if (
    ["continuity_state", "continuity_rule", "conflict_record", "production_decision", "canon_record"].includes(
      entity.entityType,
    )
  ) {
    return "continuity";
  }
  return "world";
}

function friendlyTypeLabel(entityType: string) {
  const labels: Record<string, string> = {
    project_profile: "Project Foundation",
    character: "Character",
    location: "Location",
    visual_style: "Visual Style",
    visual_language: "Visual Language",
    production_rule: "Production Rule",
    continuity_rule: "Continuity Rule",
    narrative_thread: "Story Thread",
    scene_fact: "Scene Fact",
    prop: "Prop",
    production_object: "Object",
    organization: "Organization",
    relationship: "Relationship",
    wardrobe: "Wardrobe",
    appearance_state: "Appearance",
    canon_record: "Story Fact",
    production_decision: "Creative Decision",
    story_arc: "Story Arc",
    story_beat: "Story Beat",
    timeline_entry: "Timeline Entry",
    reference_link: "Reference Asset",
    continuity_state: "Continuity Note",
    conflict_record: "Continuity Conflict",
  };
  return labels[entityType] || titleCaseLabel(entityType);
}

function buildManualPreview(project: Project, form: ManualSeedForm): CoDirectorBibleImportPreview {
  const entities: CoDirectorBibleEntity[] = [
    {
      entityType: "project_profile",
      entityKey: "project-profile",
      displayName: project.name || "Untitled Project",
      data: {
        name: project.name,
        description: form.premise.trim(),
        aspect: `${project.width}x${project.height}`,
        fps: project.fps,
      },
    },
  ];
  const facts: CoDirectorBibleFact[] = [];
  const discoveries: CoDirectorBibleDiscoveryGroup[] = [];

  const pushGroup = (id: string, title: string, description: string, items: CoDirectorBibleDiscoveryItem[]) => {
    if (items.length) discoveries.push({ id, title, description, items });
  };

  const foundationItems: CoDirectorBibleDiscoveryItem[] = [
    {
      id: "entity:project-profile",
      kind: "entity",
      title: project.name || "Untitled Project",
      subtitle: form.premise.trim() || "Project foundation",
      entityKey: "project-profile",
      entityType: "project_profile",
      included: true,
      needsReview: false,
      reasons: [],
      referenceAssets: [],
    },
  ];

  if (form.premise.trim()) {
    facts.push({
      factType: "story_fact",
      entityKey: "project-profile",
      statement: form.premise.trim(),
      data: { source: "manual" },
    });
  }

  if (form.visualTone.trim()) {
    entities.push({
      entityType: "visual_style",
      entityKey: "manual-visual-style",
      displayName: "Project look & feel",
      data: { description: form.visualTone.trim(), discoveryGroup: "visual-style" },
    });
  }

  const addNamedEntities = (raw: string, entityType: "character" | "location" | "prop") =>
    parseNamesList(raw).map((name, index) => ({
      entityType,
      entityKey: slugify(name, `${entityType}-${index + 1}`),
      displayName: name,
      data: { description: "", discoveryGroup: entityType === "prop" ? "props" : `${entityType}s` },
    }));

  const characterEntities = addNamedEntities(form.characters, "character");
  const locationEntities = addNamedEntities(form.locations, "location");
  const propEntities = addNamedEntities(form.props, "prop");
  entities.push(...characterEntities, ...locationEntities, ...propEntities);

  pushGroup("project-foundation", "Project Foundation", "The identity of the project.", foundationItems);
  if (form.visualTone.trim()) {
    pushGroup("visual-style", "Visual Style", "The creative look of the film.", [
      {
        id: "entity:manual-visual-style",
        kind: "entity",
        title: "Project look & feel",
        subtitle: form.visualTone.trim().slice(0, 180),
        entityKey: "manual-visual-style",
        entityType: "visual_style",
        included: true,
        needsReview: false,
        reasons: [],
        referenceAssets: [],
      },
    ]);
  }
  pushGroup(
    "characters",
    "Characters",
    "People who belong in the canon.",
    characterEntities.map((entity) => ({
      id: `entity:${entity.entityKey}`,
      kind: "entity",
      title: entity.displayName,
      subtitle: "Manual starter character",
      entityKey: entity.entityKey,
      entityType: entity.entityType,
      included: true,
      needsReview: false,
      reasons: [],
      referenceAssets: [],
    })),
  );
  pushGroup(
    "locations",
    "Locations",
    "Places the story returns to.",
    locationEntities.map((entity) => ({
      id: `entity:${entity.entityKey}`,
      kind: "entity",
      title: entity.displayName,
      subtitle: "Manual starter location",
      entityKey: entity.entityKey,
      entityType: entity.entityType,
      included: true,
      needsReview: false,
      reasons: [],
      referenceAssets: [],
    })),
  );
  pushGroup(
    "props",
    "Props & Objects",
    "Recurring physical details worth remembering.",
    propEntities.map((entity) => ({
      id: `entity:${entity.entityKey}`,
      kind: "entity",
      title: entity.displayName,
      subtitle: "Manual starter prop",
      entityKey: entity.entityKey,
      entityType: entity.entityType,
      included: true,
      needsReview: false,
      reasons: [],
      referenceAssets: [],
    })),
  );
  if (facts.length) {
    pushGroup("story", "Story Facts", "Key story truths and premise notes.", [
      {
        id: "fact:story-premise",
        kind: "fact",
        title: "Story premise",
        subtitle: facts[0].statement.slice(0, 180),
        factIndex: 0,
        included: true,
        needsReview: false,
        reasons: [],
        referenceAssets: [],
      },
    ]);
  }

  return {
    projectId: project.id,
    entities,
    facts,
    summary: `Prepared ${characterEntities.length} character(s), ${locationEntities.length} location(s), and ${propEntities.length} object(s) for Version 1.`,
    warnings: [],
    discoveries,
  };
}

function createDraft(preview: CoDirectorBibleImportPreview, mode: DraftMode): DraftState {
  return {
    mode,
    step: "review",
    preview,
    selectedEntityKeys: preview.entities.map((entity) => entity.entityKey),
    selectedFactIndexes: preview.facts.map((_, index) => index),
  };
}

function ReferenceAssetGrid({ assets }: { assets: CoDirectorBibleDiscoveryAsset[] }) {
  if (!assets.length) {
    return <p className="muted">No reference assets are attached yet.</p>;
  }
  return (
    <div
      style={{
        display: "grid",
        gridTemplateColumns: "repeat(auto-fill, minmax(160px, 1fr))",
        gap: "0.75rem",
      }}
    >
      {assets.map((asset) => (
        <a
          key={asset.assetId}
          href={api.assetUrl(asset.assetId)}
          target="_blank"
          rel="noreferrer"
          style={{
            border: "1px solid var(--border)",
            borderRadius: 12,
            overflow: "hidden",
            background: "var(--panel-2, rgba(255,255,255,0.03))",
            color: "inherit",
            textDecoration: "none",
          }}
        >
          {asset.kind === "image" ? (
            <img
              src={api.assetUrl(asset.assetId)}
              alt={asset.tag || asset.filename || "Reference asset"}
              style={{ width: "100%", aspectRatio: "1 / 1", objectFit: "cover", display: "block", background: "#111" }}
            />
          ) : (
            <div style={{ aspectRatio: "1 / 1", display: "grid", placeItems: "center", background: "#111" }}>
              <span className="muted">{titleCaseLabel(asset.kind)}</span>
            </div>
          )}
          <div style={{ padding: "0.75rem" }}>
            <strong style={{ display: "block" }}>{asset.tag || asset.filename || "Reference asset"}</strong>
            <span className="scene-meta">{titleCaseLabel(asset.kind)}</span>
          </div>
        </a>
      ))}
    </div>
  );
}

export function ProductionBibleWorkspace({
  project,
  onChange,
}: {
  project: Project;
  onChange?: () => Promise<void>;
}) {
  const [bible, setBible] = useState<CoDirectorBible | null>(null);
  const [summary, setSummary] = useState<BibleDomainSummary | null>(null);
  const [versions, setVersions] = useState<CoDirectorBibleVersion[]>([]);
  const [selectedVersion, setSelectedVersion] = useState<CoDirectorBibleVersion | null>(null);
  const [audit, setAudit] = useState<BibleAuditEvent[]>([]);
  const [section, setSection] = useState<WorkspaceSection>("home");
  const [selectedEntityKey, setSelectedEntityKey] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [notFound, setNotFound] = useState(false);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState("");
  const [draft, setDraft] = useState<DraftState | null>(null);
  const [showManualBuilder, setShowManualBuilder] = useState(false);
  const [search, setSearch] = useState("");
  const [manualSeed, setManualSeed] = useState<ManualSeedForm>({
    premise: "",
    visualTone: "",
    characters: "",
    locations: "",
    props: "",
  });

  const load = useCallback(async () => {
    setLoading(true);
    setNotFound(false);
    try {
      const loadedBible = await api.getBible(project.id);
      setBible(loadedBible);
      setSelectedVersion((current) =>
        current ? loadedBible.currentVersion?.versionNumber === current.versionNumber ? loadedBible.currentVersion : loadedBible.currentVersion : loadedBible.currentVersion,
      );
      const versionResponse = await api.listBibleVersions(project.id);
      setVersions(versionResponse.versions);
      try {
        setSummary(await api.getBibleSummary(project.id));
      } catch {
        setSummary(null);
      }
      try {
        setAudit((await api.listBibleAudit(project.id)).events);
      } catch {
        setAudit([]);
      }
    } catch (err) {
      if (err instanceof ApiError && err.code === "BIBLE_NOT_FOUND") {
        setNotFound(true);
        setBible(null);
        setSelectedVersion(null);
        setVersions([]);
        setSummary(null);
        setAudit([]);
      } else {
        setMsg(err instanceof Error ? err.message : "Failed to load Production Bible.");
      }
    } finally {
      setLoading(false);
    }
  }, [project.id]);

  useEffect(() => {
    void load();
  }, [load]);

  const startProjectDraft = async () => {
    setBusy(true);
    setMsg("");
    try {
      const preview = await api.previewBibleImport(project.id, { includeScenes: true, includeAssetsAsProps: true });
      setDraft(createDraft(preview, "project"));
      setShowManualBuilder(false);
    } catch (err) {
      setMsg(err instanceof Error ? err.message : "Could not prepare discoveries.");
    } finally {
      setBusy(false);
    }
  };

  const startManualDraft = () => {
    setShowManualBuilder(true);
    setDraft(null);
    setMsg("");
  };

  const buildManualDraft = () => {
    const preview = buildManualPreview(project, manualSeed);
    setDraft(createDraft(preview, "manual"));
    setShowManualBuilder(false);
    setMsg("");
  };

  const updateDraftEntity = (entityKey: string, patch: Partial<CoDirectorBibleEntity>) => {
    setDraft((current) => {
      if (!current) return current;
      const preview = {
        ...current.preview,
        entities: current.preview.entities.map((entity) =>
          entity.entityKey === entityKey ? { ...entity, ...patch, data: patch.data ?? entity.data } : entity,
        ),
        discoveries: current.preview.discoveries.map((group) => ({
          ...group,
          items: group.items.map((item) =>
            item.entityKey === entityKey && patch.displayName ? { ...item, title: patch.displayName } : item,
          ),
        })),
      };
      return { ...current, preview };
    });
  };

  const toggleDraftEntity = (entityKey: string) => {
    setDraft((current) => {
      if (!current) return current;
      const next = current.selectedEntityKeys.includes(entityKey)
        ? current.selectedEntityKeys.filter((key) => key !== entityKey)
        : [...current.selectedEntityKeys, entityKey];
      return { ...current, selectedEntityKeys: next };
    });
  };

  const toggleDraftFact = (factIndex: number) => {
    setDraft((current) => {
      if (!current) return current;
      const next = current.selectedFactIndexes.includes(factIndex)
        ? current.selectedFactIndexes.filter((value) => value !== factIndex)
        : [...current.selectedFactIndexes, factIndex];
      return { ...current, selectedFactIndexes: next };
    });
  };

  const confirmDraft = async () => {
    if (!draft) return;
    setBusy(true);
    setMsg("");
    try {
      const entities = draft.preview.entities.filter((entity) => draft.selectedEntityKeys.includes(entity.entityKey));
      const facts = draft.preview.facts.filter((_, index) => draft.selectedFactIndexes.includes(index));
      await api.confirmBibleImport(project.id, {
        entities,
        facts,
        summary:
          draft.mode === "manual"
            ? "Created Version 1 manually."
            : "Created Version 1 from project discoveries.",
        changeReason: draft.mode === "manual" ? "manual_seed" : "initial_import",
      });
      setDraft(null);
      setMsg("Version 1 is ready.");
      await load();
      await onChange?.();
    } catch (err) {
      setMsg(err instanceof Error ? err.message : "Could not create Version 1.");
    } finally {
      setBusy(false);
    }
  };

  const viewVersion = async (versionNumber: number) => {
    setBusy(true);
    try {
      const version = await api.getBibleVersion(project.id, versionNumber);
      setSelectedVersion(version);
      setSelectedEntityKey(null);
    } catch (err) {
      setMsg(err instanceof Error ? err.message : "Could not load that version.");
    } finally {
      setBusy(false);
    }
  };

  const exportBible = async () => {
    setBusy(true);
    try {
      const data = await api.exportBible(project.id);
      const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = `production-bible-${project.id.slice(0, 8)}.json`;
      link.click();
      URL.revokeObjectURL(url);
      setMsg("Bible export ready.");
    } catch (err) {
      setMsg(err instanceof Error ? err.message : "Could not export the Bible.");
    } finally {
      setBusy(false);
    }
  };

  const seedDemo = async () => {
    setBusy(true);
    try {
      const result = await api.seedDemoBible(project.id);
      setMsg(result.seeded ? "Example Bible loaded." : "This project already has a Bible.");
      await load();
      await onChange?.();
    } catch (err) {
      setMsg(err instanceof Error ? err.message : "Could not load the example Bible.");
    } finally {
      setBusy(false);
    }
  };

  const selectedEntity = useMemo(
    () => (selectedEntityKey ? (selectedVersion?.entities ?? []).find((entity) => entity.entityKey === selectedEntityKey) ?? null : null),
    [selectedEntityKey, selectedVersion],
  );

  const visibleEntities = selectedVersion?.entities ?? [];
  const storyFacts = selectedVersion?.facts ?? [];
  const searchTerm = search.trim().toLowerCase();

  const filteredEntities = useMemo(() => {
    const base =
      section === "home"
        ? visibleEntities
        : visibleEntities.filter((entity) => entitySection(entity) === section);
    if (!searchTerm) return base;
    return base.filter((entity) => {
      const haystack = [
        entity.displayName,
        entity.entityType,
        dataString(entity.data),
        ...entityReasons(entity),
      ]
        .join(" ")
        .toLowerCase();
      return haystack.includes(searchTerm);
    });
  }, [searchTerm, section, visibleEntities]);

  const filteredFacts = useMemo(() => {
    if (section !== "home" && section !== "world" && section !== "continuity") return [];
    if (!searchTerm) return storyFacts;
    return storyFacts.filter((fact) => `${fact.factType} ${fact.statement}`.toLowerCase().includes(searchTerm));
  }, [searchTerm, section, storyFacts]);

  const counts = useMemo(() => {
    const entityCounts = { characters: 0, locations: 0, world: 0, continuity: 0 };
    for (const entity of visibleEntities) {
      const group = entitySection(entity);
      if (group === "characters") entityCounts.characters += 1;
      else if (group === "locations") entityCounts.locations += 1;
      else if (group === "continuity") entityCounts.continuity += 1;
      else entityCounts.world += 1;
    }
    return entityCounts;
  }, [visibleEntities]);

  const reviewCounts = draft
    ? {
        entities: draft.selectedEntityKeys.length,
        facts: draft.selectedFactIndexes.length,
        review: draft.preview.discoveries.reduce(
          (sum, group) => sum + group.items.filter((item) => item.needsReview).length,
          0,
        ),
      }
    : null;

  const approveSelected = async () => {
    if (!selectedEntity?.stableId) return;
    setBusy(true);
    try {
      await api.approveBibleCharacter(project.id, selectedEntity.stableId);
      setMsg(`${selectedEntity.displayName} is now approved.`);
      await load();
    } catch (err) {
      setMsg(err instanceof Error ? err.message : "Could not approve this character.");
    } finally {
      setBusy(false);
    }
  };

  const lockSelected = async () => {
    if (!selectedEntity?.stableId) return;
    setBusy(true);
    try {
      await api.lockBibleCharacter(project.id, selectedEntity.stableId);
      setMsg(`${selectedEntity.displayName} is now locked.`);
      await load();
    } catch (err) {
      setMsg(err instanceof Error ? err.message : "Could not lock this character.");
    } finally {
      setBusy(false);
    }
  };

  if (loading) {
    return (
      <div className="page">
        <PanelHeading title="Production Bible" tip="The trusted memory of the project." />
        <p className="muted">Loading the trusted memory of this project…</p>
      </div>
    );
  }

  const renderDraftFlow = () => {
    if (!draft) return null;
    const stepNumber = { review: 1, choose: 2, organize: 3 }[draft.step];
    const entityMap = new Map(draft.preview.entities.map((entity) => [entity.entityKey, entity]));
    return (
      <div className="page bible-workspace" data-testid="bible-guided-creation">
        <PanelHeading
          title="Create Production Bible"
          tip="Shape what belongs, then create Version 1. Nothing becomes canon until you confirm it."
        />
        {msg ? <p className="pill">{msg}</p> : null}
        <div
          style={{
            display: "grid",
            gap: "0.75rem",
            gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))",
            marginBottom: "1rem",
          }}
        >
          <div className="card" style={{ padding: "1rem" }}>
            <strong>Step {stepNumber} of 3</strong>
            <p className="muted" style={{ margin: "0.35rem 0 0" }}>
              {draft.step === "review"
                ? "Review what the project already knows."
                : draft.step === "choose"
                  ? "Choose what belongs in the Bible."
                  : "Name and organize the pieces before Version 1."}
            </p>
          </div>
          <div className="card" style={{ padding: "1rem" }}>
            <strong>{reviewCounts?.entities ?? 0} entries selected</strong>
            <p className="muted" style={{ margin: "0.35rem 0 0" }}>
              {reviewCounts?.facts ?? 0} story facts · {reviewCounts?.review ?? 0} item(s) need review
            </p>
          </div>
        </div>

        {draft.step === "review" ? (
          <>
            <div
              className="card"
              style={{ padding: "1.1rem", borderRadius: 18, marginBottom: "1rem", background: "rgba(255,255,255,0.03)" }}
            >
              <h3 style={{ marginTop: 0 }}>Review discoveries</h3>
              <p style={{ marginBottom: "0.6rem" }}>{draft.preview.summary}</p>
              {draft.preview.warnings.map((warning) => (
                <p key={warning} className="pill warn" style={{ marginBottom: "0.5rem" }}>
                  {warning}
                </p>
              ))}
              <div
                style={{
                  display: "grid",
                  gap: "0.75rem",
                  gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))",
                  marginTop: "0.9rem",
                }}
              >
                {draft.preview.discoveries.map((group) => (
                  <div key={group.id} className="card" style={{ padding: "0.9rem" }}>
                    <strong>{group.title}</strong>
                    <p className="muted" style={{ margin: "0.35rem 0 0.5rem" }}>
                      {group.description}
                    </p>
                    <p className="scene-meta">
                      {group.items.length} {group.items.length === 1 ? "discovery" : "discoveries"}
                    </p>
                  </div>
                ))}
              </div>
            </div>
            <div className="row-actions">
              <button type="button" className="ghost" onClick={() => setDraft(null)}>
                Cancel
              </button>
              <button
                type="button"
                className="primary"
                data-testid="bible-next-choose"
                onClick={() => setDraft((current) => (current ? { ...current, step: "choose" } : current))}
              >
                Choose what belongs
              </button>
            </div>
          </>
        ) : null}

        {draft.step === "choose" ? (
          <>
            <div style={{ display: "grid", gap: "1rem" }}>
              {draft.preview.discoveries.map((group) => (
                <section key={group.id} className="card" style={{ padding: "1rem" }}>
                  <h3 style={{ marginTop: 0 }}>{group.title}</h3>
                  <p className="muted">{group.description}</p>
                  <div style={{ display: "grid", gap: "0.75rem" }}>
                    {group.items.map((item) => {
                      const checked =
                        item.kind === "entity"
                          ? draft.selectedEntityKeys.includes(String(item.entityKey))
                          : draft.selectedFactIndexes.includes(Number(item.factIndex));
                      return (
                        <label
                          key={item.id}
                          style={{
                            display: "grid",
                            gap: "0.35rem",
                            border: "1px solid var(--border)",
                            borderRadius: 14,
                            padding: "0.85rem",
                            background: checked ? "rgba(255,255,255,0.04)" : "transparent",
                          }}
                        >
                          <span style={{ display: "flex", alignItems: "center", gap: "0.6rem", flexWrap: "wrap" }}>
                            <input
                              type="checkbox"
                              checked={checked}
                              onChange={() =>
                                item.kind === "entity"
                                  ? toggleDraftEntity(String(item.entityKey))
                                  : toggleDraftFact(Number(item.factIndex))
                              }
                            />
                            <strong>{item.title}</strong>
                            {item.entityType ? <span className="pill muted">{friendlyTypeLabel(item.entityType)}</span> : null}
                            {item.needsReview ? <span className="pill warn">Needs review</span> : null}
                          </span>
                          {item.subtitle ? <span className="muted">{item.subtitle}</span> : null}
                          {item.referenceAssets.length ? (
                            <span className="scene-meta">
                              {item.referenceAssets.length} reference asset{item.referenceAssets.length === 1 ? "" : "s"}
                            </span>
                          ) : null}
                          {item.reasons.map((reason) => (
                            <span key={reason} className="muted">
                              {reason}
                            </span>
                          ))}
                        </label>
                      );
                    })}
                  </div>
                </section>
              ))}
            </div>
            <div className="row-actions" style={{ marginTop: "1rem" }}>
              <button
                type="button"
                className="ghost"
                onClick={() => setDraft((current) => (current ? { ...current, step: "review" } : current))}
              >
                Back
              </button>
              <button
                type="button"
                className="primary"
                data-testid="bible-next-organize"
                onClick={() => setDraft((current) => (current ? { ...current, step: "organize" } : current))}
              >
                Organize and confirm
              </button>
            </div>
          </>
        ) : null}

        {draft.step === "organize" ? (
          <>
            <div className="card" style={{ padding: "1rem", marginBottom: "1rem" }}>
              <h3 style={{ marginTop: 0 }}>Organize and confirm</h3>
              <p className="muted">
                Give each selected discovery the name you want the team to remember. Co-Director can propose changes later, but it never silently rewrites canon.
              </p>
              <div style={{ display: "grid", gap: "0.85rem" }}>
                {draft.selectedEntityKeys.map((entityKey) => {
                  const entity = entityMap.get(entityKey);
                  if (!entity) return null;
                  return (
                    <div
                      key={entityKey}
                      style={{
                        display: "grid",
                        gap: "0.45rem",
                        border: "1px solid var(--border)",
                        borderRadius: 14,
                        padding: "0.9rem",
                      }}
                    >
                      <span className="scene-meta">{friendlyTypeLabel(entity.entityType)}</span>
                      <input
                        type="text"
                        value={entity.displayName}
                        onChange={(event) => updateDraftEntity(entityKey, { displayName: event.target.value })}
                        style={{ maxWidth: 360 }}
                      />
                      {dataString(entity.data) ? <p className="muted">{dataString(entity.data)}</p> : null}
                      {entityReferenceAssets(entity).length ? (
                        <p className="scene-meta">
                          {entityReferenceAssets(entity).length} reference asset{entityReferenceAssets(entity).length === 1 ? "" : "s"}
                        </p>
                      ) : null}
                    </div>
                  );
                })}
                {draft.selectedFactIndexes.map((factIndex) => {
                  const fact = draft.preview.facts[factIndex];
                  if (!fact) return null;
                  return (
                    <div key={`fact-${factIndex}`} className="card" style={{ padding: "0.9rem" }}>
                      <span className="scene-meta">{titleCaseLabel(fact.factType)}</span>
                      <p style={{ margin: "0.35rem 0 0" }}>{fact.statement}</p>
                    </div>
                  );
                })}
              </div>
            </div>
            <div className="row-actions">
              <button
                type="button"
                className="ghost"
                onClick={() => setDraft((current) => (current ? { ...current, step: "choose" } : current))}
              >
                Back
              </button>
              <button
                type="button"
                className="primary"
                data-testid="bible-create-version-one"
                disabled={busy}
                onClick={() => void confirmDraft()}
              >
                {busy ? "Creating Version 1…" : "Create Version 1"}
              </button>
            </div>
          </>
        ) : null}
      </div>
    );
  };

  if (notFound) {
    if (draft) return renderDraftFlow();
    if (showManualBuilder) {
      return (
        <div className="page bible-workspace">
          <PanelHeading title="Start Production Bible Manually" tip="Create the first canon version from your own words." />
          {msg ? <p className="pill">{msg}</p> : null}
          <div className="card" style={{ padding: "1rem", display: "grid", gap: "0.9rem" }}>
            <label style={{ display: "grid", gap: "0.35rem" }}>
              <strong>Story premise</strong>
              <textarea
                value={manualSeed.premise}
                onChange={(event) => setManualSeed((current) => ({ ...current, premise: event.target.value }))}
                rows={4}
                placeholder="What is this project about?"
              />
            </label>
            <label style={{ display: "grid", gap: "0.35rem" }}>
              <strong>Visual style</strong>
              <textarea
                value={manualSeed.visualTone}
                onChange={(event) => setManualSeed((current) => ({ ...current, visualTone: event.target.value }))}
                rows={3}
                placeholder="Describe the look, mood, palette, and camera language."
              />
            </label>
            <label style={{ display: "grid", gap: "0.35rem" }}>
              <strong>Characters</strong>
              <textarea
                value={manualSeed.characters}
                onChange={(event) => setManualSeed((current) => ({ ...current, characters: event.target.value }))}
                rows={3}
                placeholder="One per line or comma separated"
              />
            </label>
            <label style={{ display: "grid", gap: "0.35rem" }}>
              <strong>Locations</strong>
              <textarea
                value={manualSeed.locations}
                onChange={(event) => setManualSeed((current) => ({ ...current, locations: event.target.value }))}
                rows={3}
                placeholder="One per line or comma separated"
              />
            </label>
            <label style={{ display: "grid", gap: "0.35rem" }}>
              <strong>Props & recurring objects</strong>
              <textarea
                value={manualSeed.props}
                onChange={(event) => setManualSeed((current) => ({ ...current, props: event.target.value }))}
                rows={3}
                placeholder="One per line or comma separated"
              />
            </label>
          </div>
          <div className="row-actions" style={{ marginTop: "1rem" }}>
            <button type="button" className="ghost" onClick={() => setShowManualBuilder(false)}>
              Back
            </button>
            <button type="button" className="primary" onClick={buildManualDraft}>
              Build starter Bible
            </button>
          </div>
        </div>
      );
    }

    return (
      <div className="page bible-workspace" data-testid="bible-empty-state">
        <PanelHeading title="Production Bible" tip="The trusted memory of the project." />
        {msg ? <p className="pill">{msg}</p> : null}
        <div
          className="card"
          style={{
            padding: "1.25rem",
            borderRadius: 20,
            background: "linear-gradient(180deg, rgba(255,255,255,0.04), rgba(255,255,255,0.02))",
          }}
        >
          <h2 style={{ marginTop: 0 }}>Build the trusted memory of your project</h2>
          <p style={{ maxWidth: 760 }}>
            The Production Bible keeps your characters, places, style, and story truths in one creative workspace so the team and Co-Director stay aligned from draft to delivery.
          </p>
          <div
            style={{
              display: "grid",
              gap: "0.75rem",
              gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))",
              margin: "1rem 0",
            }}
          >
            <div className="card" style={{ padding: "0.95rem" }}>
              <strong>Create from Project</strong>
              <p className="muted" style={{ marginBottom: 0 }}>
                Start from your current scenes, tagged assets, and project style, then shape what belongs.
              </p>
            </div>
            <div className="card" style={{ padding: "0.95rem" }}>
              <strong>How it helps</strong>
              <p className="muted" style={{ marginBottom: 0 }}>
                Gives every department one source of truth for canon, reference assets, continuity, and creative decisions.
              </p>
            </div>
          </div>
          <div className="row-actions" style={{ marginBottom: "1rem" }}>
            <button
              type="button"
              className="primary"
              data-testid="bible-create-from-project"
              disabled={busy}
              onClick={() => void startProjectDraft()}
            >
              {busy ? "Discovering…" : "Create from Project"}
            </button>
            <button
              type="button"
              className="ghost"
              data-testid="bible-start-manually"
              disabled={busy}
              onClick={startManualDraft}
            >
              Start Manually
            </button>
          </div>
          <details>
            <summary style={{ cursor: "pointer", fontWeight: 600 }}>More</summary>
            <div className="row-actions" style={{ marginTop: "0.75rem" }}>
              <button type="button" className="ghost" disabled={busy} onClick={() => void seedDemo()}>
                Load Example Bible
              </button>
            </div>
          </details>
        </div>
      </div>
    );
  }

  return (
    <div className="page bible-workspace">
      <PanelHeading
        title="Production Bible"
        tip="The trusted memory of the project. Co-Director can propose updates, but never silently change canon."
      />
      {msg ? <p className="pill">{msg}</p> : null}

      <div
        className="card"
        style={{
          padding: "1rem",
          marginBottom: "1rem",
          borderRadius: 18,
          background: "linear-gradient(180deg, rgba(255,255,255,0.04), rgba(255,255,255,0.02))",
        }}
      >
        <div
          style={{
            display: "grid",
            gap: "1rem",
            gridTemplateColumns: "minmax(240px, 1.6fr) minmax(220px, 1fr)",
            alignItems: "start",
          }}
        >
          <div>
            <h2 style={{ marginTop: 0, marginBottom: "0.35rem" }}>{project.name}</h2>
            <p className="muted" style={{ marginTop: 0 }}>
              {CATEGORY_BLURBS[section]}
            </p>
            <div className="row-actions" style={{ flexWrap: "wrap", marginTop: "0.75rem" }}>
              <span className="scene-meta">
                Version {selectedVersion?.versionNumber ?? "—"} of {bible?.versionCount ?? versions.length}
              </span>
              <span className="scene-meta">{summary?.health?.entityCount ?? visibleEntities.length} remembered entries</span>
              <span className="scene-meta">{storyFacts.length} story fact(s)</span>
            </div>
          </div>
          <div style={{ display: "grid", gap: "0.65rem" }}>
            <input
              type="search"
              value={search}
              onChange={(event) => setSearch(event.target.value)}
              placeholder="Search the Bible"
              aria-label="Search the Bible"
            />
            <div className="row-actions" style={{ flexWrap: "wrap" }}>
              <button type="button" className="ghost" disabled={busy} onClick={() => void exportBible()}>
                Export
              </button>
              <details>
                <summary style={{ cursor: "pointer" }}>More</summary>
                <div className="row-actions" style={{ marginTop: "0.5rem", flexWrap: "wrap" }}>
                  {versions.map((version) => (
                    <button
                      key={version.id}
                      type="button"
                      className={selectedVersion?.versionNumber === version.versionNumber ? "primary" : "ghost"}
                      onClick={() => void viewVersion(version.versionNumber)}
                    >
                      v{version.versionNumber}
                    </button>
                  ))}
                </div>
              </details>
            </div>
          </div>
        </div>
      </div>

      <nav className="row-actions" style={{ gap: "0.5rem", flexWrap: "wrap", marginBottom: "1rem" }}>
        {(Object.keys(SECTION_LABELS) as WorkspaceSection[]).map((id) => (
          <button
            key={id}
            type="button"
            className={section === id ? "primary" : "ghost"}
            onClick={() => {
              setSection(id);
              setSelectedEntityKey(null);
            }}
          >
            {SECTION_LABELS[id]}
          </button>
        ))}
      </nav>

      {section === "home" && !selectedEntity ? (
        <>
          <div
            style={{
              display: "grid",
              gap: "0.9rem",
              gridTemplateColumns: "repeat(auto-fit, minmax(210px, 1fr))",
              marginBottom: "1rem",
            }}
          >
            {[
              { id: "characters" as const, count: counts.characters },
              { id: "locations" as const, count: counts.locations },
              { id: "world" as const, count: counts.world + storyFacts.length },
              { id: "continuity" as const, count: (summary?.conflictCount ?? 0) + counts.continuity },
            ].map((card) => (
              <button
                key={card.id}
                type="button"
                className="card"
                style={{ padding: "1rem", textAlign: "left", borderRadius: 16 }}
                onClick={() => setSection(card.id)}
              >
                <strong>{SECTION_LABELS[card.id]}</strong>
                <p className="muted" style={{ margin: "0.35rem 0 0" }}>
                  {card.count} item{card.count === 1 ? "" : "s"}
                </p>
              </button>
            ))}
          </div>
          {(summary?.conflicts ?? []).length ? (
            <section className="card" style={{ padding: "1rem", marginBottom: "1rem" }}>
              <h3 style={{ marginTop: 0 }}>Continuity to watch</h3>
              {(summary?.conflicts ?? []).slice(0, 4).map((conflict, index) => (
                <p key={index} className="pill warn">
                  {(conflict as { description?: string }).description || "Potential continuity conflict"}
                </p>
              ))}
            </section>
          ) : null}
        </>
      ) : null}

      {selectedEntity ? (
        <section className="card" style={{ padding: "1rem", borderRadius: 18 }}>
          <div className="row-actions" style={{ justifyContent: "space-between", gap: "0.75rem", marginBottom: "0.75rem" }}>
            <button type="button" className="ghost" onClick={() => setSelectedEntityKey(null)}>
              Back to {SECTION_LABELS[entitySection(selectedEntity)]}
            </button>
            {selectedEntity.entityType === "character" ? (
              <div className="row-actions" style={{ gap: "0.5rem" }}>
                <button
                  type="button"
                  className="ghost"
                  disabled={busy || selectedEntity.lifecycleStatus === "locked"}
                  onClick={() => void approveSelected()}
                >
                  Approve
                </button>
                <button
                  type="button"
                  className="primary"
                  disabled={busy || selectedEntity.lifecycleStatus === "locked"}
                  onClick={() => void lockSelected()}
                >
                  Lock
                </button>
              </div>
            ) : null}
          </div>
          <h2 style={{ marginTop: 0, marginBottom: "0.35rem" }}>{selectedEntity.displayName}</h2>
          <div className="row-actions" style={{ gap: "0.5rem", flexWrap: "wrap", marginBottom: "0.75rem" }}>
            <span className="pill muted">{friendlyTypeLabel(selectedEntity.entityType)}</span>
            {lifecycleBadge(selectedEntity.lifecycleStatus)}
            {entityNeedsReview(selectedEntity) ? <span className="pill warn">Needs review</span> : null}
          </div>
          {dataString(selectedEntity.data) ? <p>{dataString(selectedEntity.data)}</p> : null}
          {entityReasons(selectedEntity).length ? (
            <div style={{ marginBottom: "1rem" }}>
              {entityReasons(selectedEntity).map((reason) => (
                <p key={reason} className="muted" style={{ margin: "0.3rem 0" }}>
                  {reason}
                </p>
              ))}
            </div>
          ) : null}
          <div
            style={{
              display: "grid",
              gap: "1rem",
              gridTemplateColumns: "minmax(0, 2fr) minmax(240px, 1fr)",
            }}
          >
            <div>
              <h3>Reference Assets</h3>
              <ReferenceAssetGrid assets={entityReferenceAssets(selectedEntity)} />
            </div>
            <div className="card" style={{ padding: "1rem" }}>
              <h3 style={{ marginTop: 0 }}>Canon status</h3>
              <p className="muted" style={{ marginBottom: "0.4rem" }}>
                Version {selectedVersion?.versionNumber ?? "—"} · {friendlyTypeLabel(selectedEntity.entityType)}
              </p>
              {selectedEntity.lifecycleStatus === "locked" ? (
                <p className="pill warn">Locked entries require a proposal before they change.</p>
              ) : (
                <p className="muted">Co-Director can propose edits, but you stay in control of approval.</p>
              )}
            </div>
          </div>
        </section>
      ) : section === "history" ? (
        <section className="card" style={{ padding: "1rem" }}>
          <h3 style={{ marginTop: 0 }}>Version history</h3>
          <div className="row-actions" style={{ flexWrap: "wrap", marginBottom: "1rem" }}>
            {versions.map((version) => (
              <button
                key={version.id}
                type="button"
                className={selectedVersion?.versionNumber === version.versionNumber ? "primary" : "ghost"}
                onClick={() => void viewVersion(version.versionNumber)}
              >
                Version {version.versionNumber}
              </button>
            ))}
          </div>
          {audit.length ? (
            <ul className="ms-list">
              {audit.map((event) => (
                <li key={event.id}>
                  <strong>{titleCaseLabel(event.eventType)}</strong>
                  <p className="muted" style={{ margin: "0.2rem 0" }}>
                    {event.summary}
                  </p>
                  <span className="scene-meta">{event.createdAt}</span>
                </li>
              ))}
            </ul>
          ) : (
            <p className="muted">No version history has been recorded yet.</p>
          )}
        </section>
      ) : (
        <section className="card" style={{ padding: "1rem" }}>
          <h3 style={{ marginTop: 0 }}>{SECTION_LABELS[section]}</h3>
          <p className="muted">{CATEGORY_BLURBS[section]}</p>
          {filteredEntities.length ? (
            <div style={{ display: "grid", gap: "0.85rem", gridTemplateColumns: "repeat(auto-fit, minmax(240px, 1fr))" }}>
              {filteredEntities.map((entity) => (
                <button
                  key={entity.stableId ?? entity.entityKey}
                  type="button"
                  className="card"
                  style={{ padding: "1rem", textAlign: "left", borderRadius: 16 }}
                  onClick={() => setSelectedEntityKey(entity.entityKey)}
                >
                  <strong>{entity.displayName}</strong>
                  <div className="row-actions" style={{ gap: "0.5rem", margin: "0.45rem 0", flexWrap: "wrap" }}>
                    <span className="scene-meta">{friendlyTypeLabel(entity.entityType)}</span>
                    {lifecycleBadge(entity.lifecycleStatus)}
                    {entityNeedsReview(entity) ? <span className="pill warn">Needs review</span> : null}
                  </div>
                  {dataString(entity.data) ? (
                    <p className="muted" style={{ margin: 0 }}>
                      {dataString(entity.data).slice(0, 180)}
                    </p>
                  ) : null}
                  {entityReferenceAssets(entity).length ? (
                    <p className="scene-meta" style={{ marginTop: "0.45rem" }}>
                      {entityReferenceAssets(entity).length} reference asset{entityReferenceAssets(entity).length === 1 ? "" : "s"}
                    </p>
                  ) : null}
                </button>
              ))}
            </div>
          ) : (
            <p className="muted">Nothing is showing here yet.</p>
          )}
          {filteredFacts.length ? (
            <div style={{ marginTop: "1rem" }}>
              <h4>Story facts</h4>
              <ul className="ms-list">
                {filteredFacts.map((fact, index) => (
                  <li key={`${fact.factType}-${index}`}>
                    <strong>{titleCaseLabel(fact.factType)}</strong>
                    <p className="muted" style={{ margin: "0.2rem 0 0" }}>
                      {fact.statement}
                    </p>
                  </li>
                ))}
              </ul>
            </div>
          ) : null}
        </section>
      )}
    </div>
  );
}
