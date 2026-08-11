import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../api";
import type { Project } from "../types";
import { PanelHeading } from "./HelpTip";
import { Button } from "./ui";
import { useOpenCoDirector } from "./CoDirector";
import { VoiceStudioWorkspace } from "./VoiceStudioWorkspace";
import { IdentityRegistryWorkspace } from "./continuity/IdentityRegistryWorkspace";

type TabId =
  | "overview"
  | "gates"
  | "visual"
  | "sheet"
  | "closeups"
  | "poses"
  | "expressions"
  | "skin"
  | "hair"
  | "wardrobe"
  | "props"
  | "voiceStudio"
  | "voice"
  | "voicePerformance"
  | "personality"
  | "emotion"
  | "motion"
  | "relationships"
  | "prompts"
  | "performance"
  | "identityRegistry"
  | "continuity"
  | "versions"
  | "assets";

const TABS: { id: TabId; label: string }[] = [
  { id: "overview", label: "Overview" },
  { id: "gates", label: "Visual Gates" },
  { id: "visual", label: "Visual Identity" },
  { id: "sheet", label: "Character Sheet" },
  { id: "closeups", label: "Close-Ups" },
  { id: "poses", label: "Poses" },
  { id: "expressions", label: "Expressions" },
  { id: "skin", label: "Skin" },
  { id: "hair", label: "Hair" },
  { id: "wardrobe", label: "Wardrobe" },
  { id: "props", label: "Props / Accessories" },
  { id: "personality", label: "Personality" },
  { id: "motion", label: "Motion" },
  { id: "voiceStudio", label: "Voice Studio" },
  { id: "emotion", label: "Emotion" },
  { id: "performance", label: "Performance Bible" },
  { id: "relationships", label: "Relationships" },
  { id: "prompts", label: "Prompt Package" },
  { id: "identityRegistry", label: "Approved Look" },
  { id: "continuity", label: "Continuity" },
  { id: "versions", label: "Versions" },
  { id: "assets", label: "Generated Assets" },
];

const REQUIRED_ROLES = [
  "full_body_front",
  "full_body_side_left",
  "full_body_back",
  "closeup_front",
  "closeup_side_left",
  "closeup_back",
];

/** Role → Character Profile tab mapping for generated visual-sheet assets. */
const TAB_ROLES: Partial<Record<TabId, string[]>> = {
  sheet: [
    "hero_portrait",
    "full_body_front",
    "full_body_side_left",
    "full_body_side_right",
    "full_body_back",
    "turnaround_sheet",
    "scale_reference",
  ],
  closeups: [
    "closeup_front",
    "closeup_side_left",
    "closeup_side_right",
    "closeup_back",
    "neutral_portrait",
    "hero_portrait",
  ],
  poses: ["pose_sheet", "hands_reference", "feet_reference"],
  expressions: ["expression_sheet"],
  skin: ["skin_closeup"],
  hair: ["hair_front", "hair_side", "hair_back"],
  wardrobe: ["wardrobe_reference"],
  props: ["prop_reference", "accessory_reference"],
};

const ROLE_LABELS: Record<string, string> = {
  hero_portrait: "Hero portrait",
  full_body_front: "Full body · front",
  full_body_side_left: "Full body · left",
  full_body_side_right: "Full body · right",
  full_body_back: "Full body · back",
  turnaround_sheet: "Turnaround sheet",
  scale_reference: "Scale reference",
  closeup_front: "Close-up · front",
  closeup_side_left: "Close-up · left",
  closeup_side_right: "Close-up · right",
  closeup_back: "Close-up · back",
  neutral_portrait: "Neutral portrait",
  pose_sheet: "Pose sheet",
  hands_reference: "Hands",
  feet_reference: "Feet",
  expression_sheet: "Expression sheet",
  skin_closeup: "Skin close-up",
  hair_front: "Hair · front",
  hair_side: "Hair · side",
  hair_back: "Hair · back",
  wardrobe_reference: "Wardrobe reference",
  prop_reference: "Prop reference",
  accessory_reference: "Accessory reference",
};

function ReferenceRoleGallery({
  title,
  roles,
  refs,
  requiredRoles = [],
  emptyHint,
}: {
  title: string;
  roles: string[];
  refs: any[];
  requiredRoles?: string[];
  emptyHint?: string;
}) {
  const byRole = new Map<string, any[]>();
  for (const r of refs) {
    const role = String(r.reference_role || "");
    if (!roles.includes(role)) continue;
    const list = byRole.get(role) || [];
    list.push(r);
    byRole.set(role, list);
  }
  const required = new Set(requiredRoles);
  const missing = roles.filter((role) => required.has(role) && !byRole.has(role));

  return (
    <div data-testid="character-reference-gallery" style={{ marginBottom: "1rem" }}>
      <h3 style={{ marginBottom: "0.35rem" }}>{title}</h3>
      <p className="muted" style={{ fontSize: "0.85rem", marginTop: 0 }}>
        Generated Character Creator images appear here by reference role — not only under Visual Gates.
      </p>
      {missing.length > 0 && (
        <p className="muted" data-testid="character-gallery-missing" style={{ fontSize: "0.85rem" }}>
          Still missing: {missing.join(", ")}
        </p>
      )}
      <div
        className="library-grid"
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fill, minmax(160px, 1fr))",
          gap: "0.75rem",
          marginTop: "0.75rem",
        }}
      >
        {roles.map((role) => {
          const items = byRole.get(role) || [];
          const primary = items[0];
          return (
            <div
              key={role}
              className="recent-asset-card"
              data-testid={`character-ref-card-${role}`}
              style={{
                border: "1px solid var(--border, #333)",
                borderRadius: 8,
                overflow: "hidden",
                background: "var(--panel-2, rgba(255,255,255,0.03))",
              }}
            >
              <div className="recent-asset-thumb" style={{ aspectRatio: "1", background: "#1a1a1a" }}>
                {primary?.asset_id ? (
                  <a href={api.assetUrl(primary.asset_id)} target="_blank" rel="noreferrer">
                    <img
                      src={api.assetUrl(primary.asset_id)}
                      alt={ROLE_LABELS[role] || role}
                      style={{ width: "100%", height: "100%", objectFit: "cover", display: "block" }}
                    />
                  </a>
                ) : (
                  <div
                    className="muted"
                    style={{
                      height: "100%",
                      display: "grid",
                      placeItems: "center",
                      fontSize: "0.8rem",
                      padding: "0.5rem",
                      textAlign: "center",
                    }}
                  >
                    {required.has(role) ? "Required · missing" : "No asset yet"}
                  </div>
                )}
              </div>
              <div style={{ padding: "0.45rem 0.55rem" }}>
                <div style={{ fontSize: "0.85rem", fontWeight: 600 }}>{ROLE_LABELS[role] || role}</div>
                <div className="scene-meta" style={{ fontSize: "0.72rem", wordBreak: "break-all" }}>
                  {primary?.asset_id
                    ? `${items.length > 1 ? `${items.length} · ` : ""}${String(primary.asset_id).slice(0, 8)}…`
                    : emptyHint || "Generate Visual Sheet or attach"}
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

const CHARACTER_GENERATE_VARIANTS = [
  { id: "front", role: "full_body_front", label: "Front", promptSuffix: "full body front view, neutral pose" },
  { id: "side", role: "full_body_side_left", label: "Side", promptSuffix: "full body left side profile" },
  { id: "rear", role: "full_body_back", label: "Rear", promptSuffix: "full body back view" },
  {
    id: "expression",
    role: "closeup_front",
    label: "Expression",
    promptSuffix: "facial expression close-up, front facing",
  },
  {
    id: "costume",
    role: "full_body_front",
    label: "Costume",
    promptSuffix: "alternate costume variant, full body front",
  },
] as const;

/**
 * M3.3 Character Profile workspace — canonical identity (not Avatar Studio metadata).
 */
export function CharacterProfileWorkspace({
  project,
  onChange,
  initialTab,
  initialCharacterId,
  initialIdentityId,
  returnWorkspace,
}: {
  project: Project;
  onChange?: () => Promise<void>;
  initialTab?: TabId;
  initialCharacterId?: string;
  initialIdentityId?: string;
  returnWorkspace?: string;
}) {
  const navigate = useNavigate();
  const openCoDirector = useOpenCoDirector();
  const [tab, setTab] = useState<TabId>(() => {
    if (initialTab === "voice" || initialTab === "voicePerformance") return "voiceStudio";
    return initialTab || "overview";
  });
  const [items, setItems] = useState<any[]>([]);
  const [selectedId, setSelectedId] = useState<string>(initialCharacterId || "");
  const [profile, setProfile] = useState<any | null>(null);
  const [refs, setRefs] = useState<any[]>([]);
  const [msg, setMsg] = useState("");
  const [busy, setBusy] = useState(false);
  const [name, setName] = useState("New Character");
  const [roleLabel, setRoleLabel] = useState("");
  const [attachRole, setAttachRole] = useState("full_body_front");
  const [attachAssetId, setAttachAssetId] = useState("");
  const [genPrompt, setGenPrompt] = useState("");
  const [bridgeRefs, setBridgeRefs] = useState(true);

  const selected = useMemo(() => items.find((i) => i.id === selectedId) || profile, [items, selectedId, profile]);

  const refreshList = async () => {
    const res = await api.listCharacterProfiles(project.id);
    setItems(res.items || []);
    if (!selectedId && res.items?.[0]?.id) setSelectedId(res.items[0].id);
  };

  const refreshSelected = async (id: string) => {
    if (!id) return;
    // Visual-sheet GET heals roleAssets → references before list returns.
    await api.getCharacterVisualSheet(project.id, id).catch(() => null);
    const [p, r] = await Promise.all([
      api.getCharacterProfile(project.id, id),
      api.listCharacterReferences(project.id, id),
    ]);
    setProfile(p);
    setRefs(r.items || []);
  };

  useEffect(() => {
    refreshList().catch((e) => setMsg(e instanceof Error ? e.message : String(e)));
  }, [project.id]);

  useEffect(() => {
    if (selectedId) refreshSelected(selectedId).catch(console.error);
  }, [selectedId, project.id]);

  useEffect(() => {
    if (!initialTab) return;
    if (initialTab === "voice" || initialTab === "voicePerformance") setTab("voiceStudio");
    else setTab(initialTab);
  }, [initialTab]);

  useEffect(() => {
    if (initialCharacterId) setSelectedId(initialCharacterId);
  }, [initialCharacterId]);

  useEffect(() => {
    if (!selectedId) return;
    try {
      sessionStorage.setItem("adept_selected_character", selectedId);
      window.dispatchEvent(new CustomEvent("adept:selected-character", { detail: { characterId: selectedId } }));
    } catch {
      /* ignore */
    }
  }, [selectedId]);

  useEffect(() => {
    const onOpenVoice = (ev: Event) => {
      const detail = (ev as CustomEvent<{ tab?: string; characterId?: string }>).detail || {};
      if (detail.characterId) setSelectedId(detail.characterId);
      if (detail.tab === "voicePerformance" || detail.tab === "voice" || detail.tab === "voiceStudio") {
        setTab("voiceStudio");
      } else if (detail.tab === "identityRegistry") setTab("identityRegistry");
    };
    window.addEventListener("adept:open-character-voice", onOpenVoice);
    return () => window.removeEventListener("adept:open-character-voice", onOpenVoice);
  }, []);

  const create = async () => {
    setBusy(true);
    setMsg("");
    try {
      const created = await api.createCharacterProfile(project.id, { name, role: roleLabel });
      setSelectedId(created.id);
      await refreshList();
      await onChange?.();
      setMsg(`Created draft Character Profile “${created.name}”.`);
      if (returnWorkspace === "voicestudio" && created?.id) {
        try {
          sessionStorage.setItem("adept_selected_character", created.id);
          const url = new URL(window.location.href);
          url.searchParams.set("workspace", "voicestudio");
          url.searchParams.set("characterId", created.id);
          url.searchParams.delete("returnWorkspace");
          window.history.pushState({}, "", url.toString());
          window.dispatchEvent(new PopStateEvent("popstate"));
        } catch {
          /* ignore */
        }
      }
    } catch (e) {
      setMsg(e instanceof Error ? e.message : "Create failed");
    } finally {
      setBusy(false);
    }
  };

  const attach = async () => {
    if (!selectedId || !attachAssetId) return;
    setBusy(true);
    try {
      await api.attachCharacterReference(project.id, selectedId, {
        asset_id: attachAssetId,
        reference_role: attachRole,
      });
      await refreshSelected(selectedId);
      setMsg(`Attached ${attachRole}`);
    } catch (e) {
      setMsg(e instanceof Error ? e.message : "Attach failed");
    } finally {
      setBusy(false);
    }
  };

  const bridgeReferenceIds = async (): Promise<string[]> => {
    if (!bridgeRefs || !selectedId) return [];
    const ids: string[] = [];
    for (const r of refs.slice(0, 4)) {
      if (!r.asset_id) continue;
      try {
        const bridged = await api.imageProductBridgeReference(project.id, {
          assetId: r.asset_id,
          role: r.reference_role || "character",
          displayName: `${profile?.name || "Character"} · ${r.reference_role}`,
          identityRegistryRef: selectedId,
        });
        if (bridged?.referenceId) ids.push(bridged.referenceId);
      } catch {
        /* optional bridge */
      }
    }
    return ids;
  };

  const generateVariant = async (variant: (typeof CHARACTER_GENERATE_VARIANTS)[number]) => {
    if (!selectedId || !profile) return;
    setBusy(true);
    setMsg("");
    try {
      const referenceIds = await bridgeReferenceIds();
      const extra = genPrompt.trim();
      const subject = [profile.name, variant.promptSuffix, extra].filter(Boolean).join(", ");
      const res = await api.imageProductGenerate(project.id, {
        presetId: "builtin-character-sheet",
        purpose: "character_sheet",
        subject,
        prompt: subject,
        referenceIds,
        tag: `${String(profile.name || "char").replace(/\s+/g, "_").toLowerCase()}_${variant.id}`,
        creativeContext: { objective: "character_sheet", characterId: selectedId },
      });
      setMsg(`Queued ${variant.label} · job ${res.jobId || "?"}`);
      await onChange?.();
    } catch (e) {
      setMsg(e instanceof Error ? e.message : "Generate failed");
    } finally {
      setBusy(false);
    }
  };

  const saveSkinHair = async () => {
    if (!selectedId || !profile) return;
    setBusy(true);
    try {
      const updated = await api.patchCharacterProfile(project.id, selectedId, {
        skin: profile.skin || {},
        hair: profile.hair || {},
        personality: profile.personality || {},
        performance: profile.performance || {},
        motion: profile.motion || {},
        emotion: profile.emotion || {},
        relationships: profile.relationships || [],
      });
      setProfile(updated);
      setMsg("Saved skin / hair / personality / performance / emotion / motion / relationships.");
    } catch (e) {
      setMsg(e instanceof Error ? e.message : "Save failed");
    } finally {
      setBusy(false);
    }
  };

  const seedKorri = async () => {
    setBusy(true);
    setMsg("");
    try {
      const created = await api.seedKorriCanon(project.id);
      setSelectedId(created.id);
      await refreshList();
      await refreshSelected(created.id);
      setMsg("Seeded Korri from korri.v1 canon (black twin ponytails, purple eyes, handmade wardrobe).");
    } catch (e) {
      setMsg(e instanceof Error ? e.message : "Seed Korri failed");
    } finally {
      setBusy(false);
    }
  };

  const promoteIdentity = async () => {
    if (!selectedId) return;
    setBusy(true);
    try {
      const res = await api.promoteCharacterIdentity(project.id, selectedId, "owner");
      await refreshSelected(selectedId);
      setMsg(
        `Promoted: VisualIdentity=${res.visualIdentityId || "—"} Bible=${res.bibleStableId || "—"} PromptPackage frozen.`,
      );
    } catch (e) {
      setMsg(e instanceof Error ? e.message : "Promote failed");
    } finally {
      setBusy(false);
    }
  };

  const coverage = profile?.coverage;
  const present = new Set((coverage?.present_roles || refs.map((r) => r.reference_role)) as string[]);

  return (
    <div className="page" data-testid="character-profile-workspace">
      <PanelHeading
        title="Character Profile"
        tip="Canonical Character Identity System for this project. Generated sheets, voice, and assets stay in this project’s Library — never a new project per image."
      />
      {returnWorkspace === "codirector" ? (
        <div className="row-actions" style={{ marginBottom: "0.75rem" }}>
          <Button
            variant="ghost"
            data-testid="character-back-to-codirector"
            onClick={() => {
              // Re-open the Co-Director session (it is an overlay, not a routed
              // workspace) and return to the project landing page.
              openCoDirector();
              navigate(`/project/${project.id}`);
            }}
          >
            ← Back to Co-Director
          </Button>
        </div>
      ) : null}
      <p className="scene-meta">
        All generations for this character stay in this project’s Library. Creating a profile or sheet never opens a new project.
      </p>
      {msg && (
        <p className="pill" data-testid="character-profile-msg">
          {msg}
        </p>
      )}

      <div className="row-actions" style={{ gap: "0.75rem", marginBottom: "1rem", flexWrap: "wrap" }}>
        <input value={name} onChange={(e) => setName(e.target.value)} placeholder="Character name" data-testid="character-name-input" />
        <input value={roleLabel} onChange={(e) => setRoleLabel(e.target.value)} placeholder="Role" />
        <Button variant="primary" disabled={busy} onClick={() => void create()} data-testid="character-create">
          Create Character Profile
        </Button>
        <Button disabled={busy} onClick={() => void seedKorri()} data-testid="character-seed-korri">
          Seed Korri (canon v1)
        </Button>
        <Button disabled={busy || !selectedId} onClick={() => void promoteIdentity()} data-testid="character-promote">
          Promote to Identity / Bible / Prompts
        </Button>
        <select
          value={selectedId}
          onChange={(e) => setSelectedId(e.target.value)}
          data-testid="character-select"
        >
          <option value="">Select character…</option>
          {items.map((i) => (
            <option key={i.id} value={i.id}>
              {i.name} ({i.status})
            </option>
          ))}
        </select>
      </div>

      {selected && (
        <>
          <nav className="row-actions" style={{ flexWrap: "wrap", gap: "0.35rem", marginBottom: "1rem" }} data-testid="character-tabs">
            {TABS.map((t) => (
              <button
                key={t.id}
                type="button"
                className={tab === t.id ? "primary" : "ghost"}
                onClick={() => setTab(t.id)}
                data-testid={`character-tab-${t.id}`}
              >
                {t.label}
              </button>
            ))}
          </nav>

          {tab === "overview" && (
            <section className="panel" data-testid="character-overview">
              <h3>{profile?.name || selected.name}</h3>
              <p className="muted">
                Status: {coverage?.status || profile?.status} · Coverage score:{" "}
                {Math.round(Number(coverage?.score || 0) * 100)}% · Version: {profile?.active_version_id || "—"}
              </p>
              <p>
                Active wardrobe: {profile?.active_wardrobe_id || "none"} · Active voice:{" "}
                {profile?.active_voice_profile_id || "none"}
              </p>
              <div className="character-overview__fields">
                <label className="character-overview__field">
                  <span>Bio &amp; Personality</span>
                  <textarea
                    rows={4}
                    data-testid="character-overview-bio"
                    placeholder="Who is this character? Temperament, motivations, background…"
                    value={profile?.description || ""}
                    onChange={async (e) => {
                      if (!selectedId || !profile) return;
                      try {
                        const updated = await api.patchCharacterProfile(project.id, selectedId, { description: e.target.value });
                        setProfile(updated);
                      } catch (err) {
                        setMsg(err instanceof Error ? err.message : "Save failed");
                      }
                    }}
                  />
                </label>
                <label className="character-overview__field">
                  <span>Visual Description</span>
                  <textarea
                    rows={4}
                    data-testid="character-overview-visual-desc"
                    placeholder="Visual appearance: age, facial features, hair, eyes, build, clothing…"
                    value={profile?.visual_description || ""}
                    onChange={async (e) => {
                      if (!selectedId || !profile) return;
                      try {
                        const updated = await api.patchCharacterProfile(project.id, selectedId, { visual_description: e.target.value });
                        setProfile(updated);
                      } catch (err) {
                        setMsg(err instanceof Error ? err.message : "Save failed");
                      }
                    }}
                  />
                </label>
                <label className="character-overview__field">
                  <span>Visual Style</span>
                  <select
                    data-testid="character-overview-style"
                    value={profile?.visual_style || ""}
                    onChange={async (e) => {
                      if (!selectedId || !profile) return;
                      try {
                        const updated = await api.patchCharacterProfile(project.id, selectedId, { visual_style: e.target.value });
                        setProfile(updated);
                      } catch (err) {
                        setMsg(err instanceof Error ? err.message : "Save failed");
                      }
                    }}
                  >
                    <option value="">Default cinematic</option>
                    <option value="live_action">Live Action</option>
                    <option value="anime">Anime</option>
                    <option value="realistic_anime">Realistic Anime</option>
                    <option value="stylized_3d_animation">Stylized 3D</option>
                    <option value="stop_motion">Stop Motion</option>
                    <option value="claymation">Claymation</option>
                    <option value="graphic_novel">Comic / Graphic Novel</option>
                    <option value="watercolor">Watercolor</option>
                    <option value="oil_painting">Oil Painting</option>
                    <option value="documentary_realism">Photorealistic</option>
                  </select>
                </label>
              </div>
              {(coverage?.missing_roles || []).length > 0 && (
                <div data-testid="character-missing-guidance">
                  <h4>Missing required references</h4>
                  <ul>
                    {(coverage?.guidance || []).map((g: string) => (
                      <li key={g}>{g}</li>
                    ))}
                  </ul>
                  <p className="muted">Informational guidance — not a technical failure. You may proceed after acknowledging identity drift risk.</p>
                </div>
              )}
            </section>
          )}

          {(tab === "sheet" || tab === "closeups" || tab === "visual") && (
            <section className="panel" data-testid="character-visual">
              <ReferenceRoleGallery
                title={
                  tab === "closeups"
                    ? "Close-Ups"
                    : tab === "sheet"
                      ? "Character Sheet"
                      : "Visual Identity Pack"
                }
                roles={TAB_ROLES[tab === "visual" ? "sheet" : tab] || TAB_ROLES.sheet || []}
                refs={refs}
                requiredRoles={
                  tab === "closeups"
                    ? ["closeup_front", "closeup_side_left", "closeup_back"]
                    : ["full_body_front", "full_body_side_left", "full_body_back"]
                }
              />
              <h4>Coverage checklist</h4>
              <ul>
                {REQUIRED_ROLES.map((role) => (
                  <li key={role} data-testid={`ref-role-${role}`}>
                    <strong>{role}</strong> — {present.has(role) ? "present" : "missing"}
                  </li>
                ))}
              </ul>
              <div className="row-actions" style={{ gap: "0.5rem", flexWrap: "wrap" }}>
                <select value={attachRole} onChange={(e) => setAttachRole(e.target.value)} data-testid="character-attach-role">
                  {REQUIRED_ROLES.map((r) => (
                    <option key={r} value={r}>
                      {r}
                    </option>
                  ))}
                </select>
                <input
                  value={attachAssetId}
                  onChange={(e) => setAttachAssetId(e.target.value)}
                  placeholder="asset id"
                  data-testid="character-attach-asset"
                />
                <Button disabled={busy} onClick={() => void attach()} data-testid="character-attach-ref">
                  Attach reference
                </Button>
              </div>

              <h4 style={{ marginTop: "1rem" }}>Generate via Image Product</h4>
              <p className="muted" style={{ fontSize: "0.85rem" }}>
                Prefer Visual Gates → Generate Visual Sheet for the full Korri pack. Qwen-Image-2512 is the recommended
                default here; FLUX stays available elsewhere when you want an alternate look.
              </p>
              <textarea
                rows={2}
                value={genPrompt}
                onChange={(e) => setGenPrompt(e.target.value)}
                placeholder="Optional style / wardrobe notes for generation"
                data-testid="character-gen-prompt"
                style={{ width: "100%", marginBottom: "0.5rem" }}
              />
              <label className="muted" style={{ fontSize: "0.85rem", display: "block", marginBottom: "0.5rem" }}>
                <input
                  type="checkbox"
                  checked={bridgeRefs}
                  onChange={(e) => setBridgeRefs(e.target.checked)}
                  data-testid="character-bridge-refs"
                />{" "}
                Bridge attached references into ReferenceAsset store
              </label>
              <div className="row-actions" style={{ gap: "0.4rem", flexWrap: "wrap" }} data-testid="character-generate-actions">
                {CHARACTER_GENERATE_VARIANTS.map((v) => (
                  <Button
                    key={v.id}
                    disabled={busy}
                    onClick={() => void generateVariant(v)}
                    data-testid={`character-generate-${v.id}`}
                  >
                    Generate {v.label}
                  </Button>
                ))}
              </div>
            </section>
          )}

          {(tab === "skin" ||
            tab === "hair" ||
            tab === "personality" ||
            tab === "performance" ||
            tab === "emotion" ||
            tab === "motion") &&
            profile && (
            <section className="panel" data-testid={`character-${tab}`}>
              {(tab === "skin" || tab === "hair") && (
                <ReferenceRoleGallery
                  title={tab === "skin" ? "Skin references" : "Hair references"}
                  roles={TAB_ROLES[tab] || []}
                  refs={refs}
                />
              )}
              <h3>{tab[0].toUpperCase() + tab.slice(1)} domain</h3>
              {tab === "motion" && (
                <p className="muted">
                  Motion Profile describes how the body moves — not actor delivery. Complements Performance Bible.
                </p>
              )}
              {tab === "performance" && (
                <p className="muted">
                  Performance Bible describes how the actor performs (cadence, humor, silence, mannerisms). Feeds
                  Prompt Package and Voice Performance (4.4). Distinct from Motion Profile.
                </p>
              )}
              <textarea
                rows={10}
                value={JSON.stringify(profile[tab] || {}, null, 2)}
                onChange={(e) => {
                  try {
                    const parsed = JSON.parse(e.target.value);
                    setProfile({ ...profile, [tab]: parsed });
                  } catch {
                    /* keep typing */
                  }
                }}
                data-testid={`character-${tab}-json`}
              />
              <Button disabled={busy} onClick={() => void saveSkinHair()} data-testid="character-save-domains">
                Save domains
              </Button>
            </section>
          )}

          {tab === "relationships" && profile && (
            <section className="panel" data-testid="character-relationships">
              <h3>Relationship Graph</h3>
              <p className="muted">
                Originates here; synced to Production Bible on promote. Include Relationship Dynamics
                (communication, humor, conflict resolution, openness, protectiveness, authority).
              </p>
              <textarea
                rows={12}
                value={JSON.stringify(profile.relationships || [], null, 2)}
                onChange={(e) => {
                  try {
                    setProfile({ ...profile, relationships: JSON.parse(e.target.value) });
                  } catch {
                    /* keep typing */
                  }
                }}
                data-testid="character-relationships-json"
              />
              <Button disabled={busy} onClick={() => void saveSkinHair()} data-testid="character-save-relationships">
                Save relationships
              </Button>
            </section>
          )}

          {tab === "prompts" && selectedId && (
            <section className="panel" data-testid="character-prompt-package">
              <h3>Character Prompt Package</h3>
              <p className="muted">Generated products from the approved profile — not separate identities.</p>
              <pre style={{ whiteSpace: "pre-wrap", fontSize: "0.85rem" }} data-testid="character-prompt-package-body">
                {JSON.stringify(profile?.prompt_package || {}, null, 2)}
              </pre>
              <Button
                disabled={busy}
                onClick={() =>
                  void api.getCharacterPromptPackage(project.id, selectedId).then((r) => {
                    setProfile({ ...profile, prompt_package: r.promptPackage });
                    setMsg("Loaded Prompt Package");
                  })
                }
              >
                Refresh Prompt Package
              </Button>
            </section>
          )}

          {tab === "gates" && selectedId && (
            <VisualGatesPanel
              projectId={project.id}
              characterId={selectedId}
              onMsg={setMsg}
              busy={busy}
              setBusy={setBusy}
              onPackChanged={() => void refreshSelected(selectedId)}
            />
          )}

          {tab === "wardrobe" && selectedId && (
            <section className="panel">
              <ReferenceRoleGallery title="Wardrobe references" roles={TAB_ROLES.wardrobe || []} refs={refs} />
              <WardrobePanel projectId={project.id} characterId={selectedId} onMsg={setMsg} />
            </section>
          )}
          {tab === "props" && selectedId && (
            <section className="panel">
              <ReferenceRoleGallery title="Props / Accessories" roles={TAB_ROLES.props || []} refs={refs} />
              <PropsPanel projectId={project.id} characterId={selectedId} onMsg={setMsg} />
            </section>
          )}

          {(tab === "voiceStudio" || tab === "voice" || tab === "voicePerformance") && selectedId && (
            <VoiceStudioWorkspace
              projectId={project.id}
              characterId={selectedId}
              onRefresh={() => void refreshSelected(selectedId)}
              onMsg={setMsg}
              initialPhase={tab === "voicePerformance" ? "performance" : "create"}
            />
          )}

          {tab === "identityRegistry" && (
            <section className="panel" data-testid="character-approved-look">
              {!selectedId ? (
                <div className="empty-state" data-testid="approved-look-choose-character">
                  <h3>Choose a character</h3>
                  <p className="muted">
                    Select a Character Profile to manage approved looks, visual identity versions, and
                    continuity references.
                  </p>
                  {returnWorkspace ? (
                    <p className="muted" style={{ fontSize: "0.85rem" }}>
                      Return destination saved for this session.
                    </p>
                  ) : null}
                </div>
              ) : (
                <IdentityRegistryWorkspace
                  project={project}
                  onChange={onChange}
                  embedded
                  preferredIdentityId={initialIdentityId}
                />
              )}
            </section>
          )}

          {tab === "versions" && selectedId && <VersionsPanel projectId={project.id} characterId={selectedId} onMsg={setMsg} />}
          {(tab === "poses" || tab === "expressions") && profile && (
            <section className="panel" data-testid={`character-${tab}`}>
              <ReferenceRoleGallery
                title={tab === "poses" ? "Poses" : "Expressions"}
                roles={TAB_ROLES[tab] || []}
                refs={refs}
              />
              <div className="row-actions" style={{ gap: "0.5rem", flexWrap: "wrap" }}>
                <input
                  value={attachAssetId}
                  onChange={(e) => setAttachAssetId(e.target.value)}
                  placeholder="asset id"
                />
                <Button
                  disabled={busy}
                  onClick={() => {
                    setAttachRole(tab === "poses" ? "pose_sheet" : "expression_sheet");
                    void attach();
                  }}
                >
                  Attach {tab === "poses" ? "pose_sheet" : "expression_sheet"}
                </Button>
              </div>
            </section>
          )}
          {tab === "assets" && (
            <section className="panel" data-testid="character-generated-assets">
              <ReferenceRoleGallery
                title="Generated Assets"
                roles={Array.from(
                  new Set([
                    ...(TAB_ROLES.sheet || []),
                    ...(TAB_ROLES.closeups || []),
                    ...(TAB_ROLES.poses || []),
                    ...(TAB_ROLES.expressions || []),
                    ...(TAB_ROLES.skin || []),
                    ...(TAB_ROLES.hair || []),
                    ...(TAB_ROLES.wardrobe || []),
                    ...(TAB_ROLES.props || []),
                    ...refs.map((r) => String(r.reference_role || "")).filter(Boolean),
                  ]),
                )}
                refs={refs}
                emptyHint="Run Visual Gates → Generate Visual Sheet"
              />
              <p className="muted">
                {refs.length} role-tagged reference{refs.length === 1 ? "" : "s"} linked to this Character Profile.
              </p>
            </section>
          )}
          {tab === "continuity" && (
            <section className="panel">
              <h3>Continuity</h3>
              <p className="muted">
                Manage locked features via domain fields and Visual Identity references. Character Sheet panels promote
                into the canonical pack when approved.
              </p>
              <pre style={{ whiteSpace: "pre-wrap", fontSize: "0.85rem" }}>
                {JSON.stringify(profile?.continuity || {}, null, 2)}
              </pre>
            </section>
          )}
        </>
      )}
    </div>
  );
}

function VisualGatesPanel({
  projectId,
  characterId,
  onMsg,
  busy,
  setBusy,
  onPackChanged,
}: {
  projectId: string;
  characterId: string;
  onMsg: (m: string) => void;
  busy: boolean;
  setBusy: (b: boolean) => void;
  onPackChanged?: () => void;
}) {
  const [gates, setGates] = useState<any>(null);
  const [pack, setPack] = useState<any>(null);
  const reload = () =>
    Promise.all([
      api.listVisualGates(projectId, characterId),
      api.getCharacterVisualSheet(projectId, characterId).catch(() => null),
    ])
      .then(([g, p]) => {
        setGates(g);
        setPack(p);
      })
      .catch((e) => onMsg(e.message));

  useEffect(() => {
    void reload();
  }, [projectId, characterId]);

  return (
    <section className="panel" data-testid="character-visual-gates">
      <h3>Owner Visual Gates + Generated Image Profile</h3>
      <p className="muted">
        Character Creator never self-approves. Generate a real visual sheet via Qwen-Image-2512 as the recommended
        default, then owner-approve gates with attached assets. No mock sheets.
      </p>
      <div className="row-actions" style={{ gap: "0.5rem", flexWrap: "wrap" }}>
        <Button
          disabled={busy}
          onClick={() => {
            setBusy(true);
            void api
              .proposeVisualDirections(projectId, characterId)
              .then(() => reload())
              .then(() => onMsg("Proposed ≥3 visual directions (korri.v1 locked)"))
              .catch((e) => onMsg(e.message))
              .finally(() => setBusy(false));
          }}
          data-testid="gates-propose"
        >
          Propose directions
        </Button>
        <Button
          disabled={busy}
          onClick={() => {
            setBusy(true);
            void api
              .selectVisualConcept(projectId, characterId, "wild_sun_sprite", "owner")
              .then(() => reload())
              .then(() => onMsg("Owner selected wild_sun_sprite"))
              .catch((e) => onMsg(e.message))
              .finally(() => setBusy(false));
          }}
          data-testid="gates-select-concept"
        >
          Select Wild Sun Sprite
        </Button>
        <Button
          variant="primary"
          disabled={busy}
          onClick={() => {
            setBusy(true);
            void api
              .startCharacterVisualSheet(projectId, characterId, {
                includeDetails: true,
                includePerformance: true,
              })
              .then((r) => {
                setPack(r.pack);
                onMsg(`Visual sheet generating · status ${r.pack?.status || "?"}`);
                onPackChanged?.();
              })
              .catch((e) => onMsg(e.message))
              .finally(() => setBusy(false));
          }}
          data-testid="gates-generate-visual-sheet"
        >
          Generate Visual Sheet (Qwen-Image-2512 Recommended)
        </Button>
        <Button
          disabled={busy}
          onClick={() => {
            setBusy(true);
            void api
              .advanceCharacterVisualSheet(projectId, characterId)
              .then((r) => {
                setPack(r.pack);
                onMsg(`Advanced · ${r.pack?.status || "?"} · roles ${Object.keys(r.pack?.roleAssets || {}).length}`);
                return reload();
              })
              .then(() => onPackChanged?.())
              .catch((e) => onMsg(e.message))
              .finally(() => setBusy(false));
          }}
          data-testid="gates-advance-visual-sheet"
        >
          Advance / Attach Jobs
        </Button>
        <Button
          disabled={busy}
          onClick={() => {
            setBusy(true);
            void api
              .ownerApproveCharacterVisualSheet(projectId, characterId, "owner")
              .then(() => reload())
              .then(() => {
                onPackChanged?.();
                onMsg("Owner approved visual sheet gates with real assetIds");
              })
              .catch((e) => onMsg(e.message))
              .finally(() => setBusy(false));
          }}
          data-testid="gates-owner-approve-visual-sheet"
        >
          Owner Approve Visual Pack
        </Button>
      </div>
      <p className="scene-meta" data-testid="visual-sheet-status">
        Pack: {pack?.status || "NOT_STARTED"}
        {pack?.phase ? ` · ${pack.phase}` : ""}
        {pack?.roleAssets ? ` · ${Object.keys(pack.roleAssets).length} roles` : ""}
        {pack?.engine ? ` · ${pack.engine}` : ""}
      </p>
      <pre style={{ whiteSpace: "pre-wrap", fontSize: "0.8rem" }} data-testid="gates-json">
        {JSON.stringify({ gates: gates?.gates || gates || {}, visualSheet: pack || {} }, null, 2)}
      </pre>
    </section>
  );
}

function WardrobePanel({
  projectId,
  characterId,
  onMsg,
}: {
  projectId: string;
  characterId: string;
  onMsg: (m: string) => void;
}) {
  const [items, setItems] = useState<any[]>([]);
  const [name, setName] = useState("Default");
  useEffect(() => {
    api.listCharacterWardrobes(projectId, characterId).then((r) => setItems(r.items || [])).catch(console.error);
  }, [projectId, characterId]);
  return (
    <section className="panel" data-testid="character-wardrobe">
      <h3>Wardrobe Profiles</h3>
      <ul>
        {items.map((w) => (
          <li key={w.id}>
            {w.name} ({w.approval_status})
          </li>
        ))}
      </ul>
      <input value={name} onChange={(e) => setName(e.target.value)} />
      <Button
        onClick={() =>
          void api
            .createCharacterWardrobe(projectId, characterId, { name })
            .then(() => api.listCharacterWardrobes(projectId, characterId))
            .then((r) => setItems(r.items || []))
            .then(() => onMsg("Wardrobe created"))
            .catch((e) => onMsg(e.message))
        }
        data-testid="character-wardrobe-create"
      >
        Add wardrobe
      </Button>
    </section>
  );
}

function PropsPanel({
  projectId,
  characterId,
  onMsg,
}: {
  projectId: string;
  characterId: string;
  onMsg: (m: string) => void;
}) {
  const [items, setItems] = useState<any[]>([]);
  const [name, setName] = useState("Signature prop");
  useEffect(() => {
    api.listCharacterProps(projectId, characterId).then((r) => setItems(r.items || [])).catch(console.error);
  }, [projectId, characterId]);
  return (
    <section className="panel" data-testid="character-props">
      <h3>Props & accessories</h3>
      <ul>
        {items.map((p) => (
          <li key={p.id}>
            {p.name} ({p.prop_type || "prop"})
          </li>
        ))}
      </ul>
      <input value={name} onChange={(e) => setName(e.target.value)} />
      <Button
        onClick={() =>
          void api
            .createCharacterProp(projectId, characterId, { name })
            .then(() => api.listCharacterProps(projectId, characterId))
            .then((r) => setItems(r.items || []))
            .then(() => onMsg("Prop linked"))
            .catch((e) => onMsg(e.message))
        }
        data-testid="character-prop-create"
      >
        Add prop
      </Button>
    </section>
  );
}

function VersionsPanel({
  projectId,
  characterId,
  onMsg,
}: {
  projectId: string;
  characterId: string;
  onMsg: (m: string) => void;
}) {
  const [items, setItems] = useState<any[]>([]);
  useEffect(() => {
    api.listCharacterVersions(projectId, characterId).then((r) => setItems(r.items || [])).catch(console.error);
  }, [projectId, characterId]);
  return (
    <section className="panel" data-testid="character-versions">
      <h3>Versions</h3>
      <ul>
        {items.map((v) => (
          <li key={v.id}>
            {v.version_label} · {v.status}
            {v.status !== "LOCKED" && (
              <>
                {" "}
                <button
                  type="button"
                  className="ghost"
                  onClick={() =>
                    void api
                      .approveCharacterVersion(projectId, characterId, v.id)
                      .then(() => api.listCharacterVersions(projectId, characterId))
                      .then((r) => setItems(r.items || []))
                      .then(() => onMsg("Version approved"))
                  }
                >
                  Approve
                </button>
                <button
                  type="button"
                  className="ghost"
                  onClick={() =>
                    void api
                      .lockCharacterVersion(projectId, characterId, v.id)
                      .then(() => api.listCharacterVersions(projectId, characterId))
                      .then((r) => setItems(r.items || []))
                      .then(() => onMsg("Version locked"))
                  }
                >
                  Lock
                </button>
              </>
            )}
          </li>
        ))}
      </ul>
    </section>
  );
}
