/**
 * Character Creator embedded view — Co-Director Project Building pane.
 *
 * Complete beginner-friendly create/cast flow:
 *   name → bio/personality → visual description → style → optional ref image
 *   → generate 4 candidates → review → approve → save.
 *
 * Shares the same authoritative CharacterProfile + CharacterReference data as
 * the standalone CharacterProfileWorkspace and the Co-Director tools. No
 * duplicate store. "Open Full Character Creator" preserves projectId +
 * characterId (flushed pending save first).
 */
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { api } from "../../../api";
import {
  getCardPreviewUrl,
  getDisplayDate,
  getDocumentKind,
  isAudioAsset,
  isImageAsset,
  isVideoAsset,
  matchesFilter,
  type LibraryAsset,
} from "../library/assetModel";
import "./characterCompact.css";

type CharacterProfile = {
  id: string;
  name: string;
  role?: string;
  description?: string;
  visual_description?: string;
  visual_style?: string;
  gender_presentation?: string;
  apparent_age?: string;
  species_or_type?: string;
  body_type?: string;
  height_description?: string;
  active_voice_profile_id?: string | null;
  hair?: {
    primary_color?: string;
    canonical_style?: string;
    length?: string;
  };
  personality?: {
    core_personality?: string;
    temperament?: string;
    humor?: string;
    strengths?: string | string[];
    flaws?: string | string[];
  };
  continuity?: {
    notes?: string;
  };
  approval_status?: string;
  updated_at?: string;
};

type CharacterReference = {
  id: string;
  asset_id?: string | null;
  reference_role?: string;
  approval_status?: string;
  canonical?: boolean;
  source_type?: string;
};

type VoiceProfile = {
  id: string;
  name?: string;
  status?: string;
  approval_status?: string;
  approved_preview_asset_id?: string | null;
  reference_asset_id?: string | null;
  tone_description?: string;
  provider?: string;
};

type Candidate = {
  assetId?: string | null;
  jobId?: string;
  label?: string;
  status?: string;
  candidateIndex?: number;
};

type Props = {
  projectId: string;
  onOpenFull?: (characterId?: string) => void;
};

const PREDEFINED_TAGS = [
  "Brave",
  "Sarcastic",
  "Kind",
  "Cunning",
  "Stoic",
  "Cheerful",
  "Mysterious",
  "Loyal",
  "Ambitious",
  "Anxious",
  "Confident",
  "Gentle",
];

const STYLE_OPTIONS = [
  { value: "", label: "Select a style…" },
  { value: "live_action", label: "Live Action" },
  { value: "anime", label: "Anime" },
  { value: "realistic_anime", label: "Realistic Anime" },
  { value: "stylized_3d_animation", label: "Stylized 3D" },
  { value: "stop_motion", label: "Stop Motion" },
  { value: "claymation", label: "Claymation" },
  { value: "graphic_novel", label: "Comic / Graphic Novel" },
  { value: "watercolor", label: "Watercolor" },
  { value: "oil_painting", label: "Oil Painting" },
  { value: "documentary_realism", label: "Photorealistic" },
];

const ASSET_FILTERS = [
  { id: "images" as const, label: "Images" },
  { id: "video" as const, label: "Video" },
  { id: "audio" as const, label: "Audio" },
  { id: "documents" as const, label: "Documents" },
];

function toArray(value: string | string[] | undefined): string[] {
  if (!value) return [];
  if (Array.isArray(value)) return value.filter(Boolean);
  return String(value)
    .split(/[,;]|\band\b/i)
    .map((s) => s.trim())
    .filter(Boolean);
}

function getApprovedImage(refs: CharacterReference[]): CharacterReference | undefined {
  return (
    refs.find((r) => (r.reference_role === "hero_identity" || r.reference_role === "hero_portrait") && r.canonical && r.approval_status === "approved") ||
    refs.find((r) => (r.reference_role === "hero_identity" || r.reference_role === "hero_portrait") && r.canonical) ||
    refs.find((r) => (r.reference_role === "hero_identity" || r.reference_role === "hero_portrait") && r.approval_status === "approved") ||
    refs.find((r) => r.reference_role === "hero_identity" || r.reference_role === "hero_portrait")
  );
}

function getReferenceImage(refs: CharacterReference[]): CharacterReference | undefined {
  return refs.find((r) => r.reference_role === "reference_image" && r.asset_id);
}

function getVoiceName(voice: VoiceProfile): string {
  return voice.name || "Approved voice";
}

function useDebouncedPatch() {
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const pendingRef = useRef<{ projectId: string; characterId: string; body: Record<string, unknown> } | null>(null);

  const schedule = useCallback(
    (
      projectId: string,
      characterId: string,
      body: Record<string, unknown>,
      onSaved?: () => void,
    ) => {
      pendingRef.current = { projectId, characterId, body: { ...pendingRef.current?.body, ...body } };
      if (timerRef.current) clearTimeout(timerRef.current);
      timerRef.current = setTimeout(async () => {
        const pending = pendingRef.current;
        pendingRef.current = null;
        if (!pending) return;
        try {
          await api.patchCharacterProfile(pending.projectId, pending.characterId, pending.body);
          onSaved?.();
        } catch {
          // swallow; UI state remains author-driven
        }
      }, 700);
    },
    [],
  );

  const flush = useCallback(async () => {
    if (timerRef.current) clearTimeout(timerRef.current);
    const pending = pendingRef.current;
    pendingRef.current = null;
    if (pending) {
      try {
        await api.patchCharacterProfile(pending.projectId, pending.characterId, pending.body);
      } catch {
        // best-effort flush
      }
    }
  }, []);

  useEffect(() => () => {
    if (timerRef.current) clearTimeout(timerRef.current);
  }, []);

  return { schedule, flush };
}

type AssetCardProps = {
  asset: LibraryAsset;
  onOpen?: () => void;
};

function AssetCard({ asset, onOpen }: AssetCardProps) {
  const name = asset.tag || asset.filename || "Untitled";
  return (
    <button type="button" className="character-compact__asset is-media" onClick={onOpen} aria-label={`Open ${name}`}>
      {isVideoAsset(asset) ? (
        <video src={api.assetUrl(asset.id)} preload="metadata" muted />
      ) : isImageAsset(asset) ? (
        <img src={getCardPreviewUrl(asset) || api.assetUrl(asset.id)} alt={name} loading="lazy" />
      ) : isAudioAsset(asset) ? (
        <div className="character-compact__asset-icon">Aud</div>
      ) : (
        <div className="character-compact__asset-icon">{getDocumentKind(asset.filename)}</div>
      )}
      <strong>{name}</strong>
      <span>{getDisplayDate(asset)}</span>
    </button>
  );
}

type CharacterDetailProps = {
  projectId: string;
  characterId: string;
  onOpenFull?: (id?: string) => void;
};

function CharacterDetail({ projectId, characterId, onOpenFull }: CharacterDetailProps) {
  const [profile, setProfile] = useState<CharacterProfile | null>(null);
  const [refs, setRefs] = useState<CharacterReference[]>([]);
  const [voices, setVoices] = useState<VoiceProfile[]>([]);
  const [libraryAssets, setLibraryAssets] = useState<LibraryAsset[]>([]);
  const [busy, setBusy] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [tagInput, setTagInput] = useState("");
  const [candidates, setCandidates] = useState<Candidate[]>([]);
  const [generating, setGenerating] = useState(false);
  const [genMsg, setGenMsg] = useState("");
  const [approvingId, setApprovingId] = useState<string | null>(null);
  const [savedMsg, setSavedMsg] = useState("");
  const [assetFilter, setAssetFilter] = useState<(typeof ASSET_FILTERS)[number]["id"]>("images");
  const [previewAsset, setPreviewAsset] = useState<LibraryAsset | null>(null);
  const [refImageBusy, setRefImageBusy] = useState(false);
  const [removingRef, setRemovingRef] = useState(false);
  const [libraryPickerOpen, setLibraryPickerOpen] = useState(false);
  const [selectedPickerAsset, setSelectedPickerAsset] = useState<LibraryAsset | null>(null);
  const [deleteConfirm, setDeleteConfirm] = useState(false);
  const [deleteBusy, setDeleteBusy] = useState(false);
  const [deleteError, setDeleteError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const patcher = useDebouncedPatch();

  // Amendment 3: Voice Studio navigation draft preservation.
  // Before navigating to Voice Studio, serialize the current draft to
  // sessionStorage so creator-authored Profile text is not lost. On return,
  // restore the draft + refresh available voices.
  const draftKey = `adept.character.draft.${projectId}.${characterId}`;
  const saveDraftToSession = useCallback(() => {
    try {
      sessionStorage.setItem(
        draftKey,
        JSON.stringify({
          name: profile?.name || "",
          gender_presentation: (profile as CharacterProfile & { gender_presentation?: string })?.gender_presentation || "",
          visual_description: profile?.visual_description || "",
          description: profile?.description || "",
          visual_style: profile?.visual_style || "",
          active_voice_profile_id: (profile as CharacterProfile & { active_voice_profile_id?: string })?.active_voice_profile_id || "",
          candidates,
          savedAt: new Date().toISOString(),
        }),
      );
    } catch {
      // sessionStorage may be unavailable; best-effort
    }
  }, [draftKey, profile, candidates]);

  const restoreDraftFromSession = useCallback((): {
    visual_description?: string;
    description?: string;
    name?: string;
    visual_style?: string;
    active_voice_profile_id?: string;
    gender_presentation?: string;
    candidates?: Candidate[];
  } | null => {
    try {
      const raw = sessionStorage.getItem(draftKey);
      if (!raw) return null;
      const draft = JSON.parse(raw);
      if (!draft || !draft.visual_description) return null;
      return {
        visual_description: draft.visual_description,
        description: draft.description || draft.visual_description,
        name: draft.name || "",
        visual_style: draft.visual_style || "",
        active_voice_profile_id: draft.active_voice_profile_id || "",
        gender_presentation: draft.gender_presentation || "",
        candidates: Array.isArray(draft.candidates) ? draft.candidates : [],
      };
    } catch {
      return null;
    }
  }, [draftKey]);

  // On mount, refresh voices so a newly-created voice is available for selection
  // after returning from Voice Studio. Draft profile fields are reconciled inside
  // the main refresh() effect below, so they merge onto real server data.
  useEffect(() => {
    void (async () => {
      try {
        const hasDraft = sessionStorage.getItem(draftKey) !== null;
        if (!hasDraft) return;
        const v = await api.listCharacterVoiceProfiles(projectId, characterId).catch(() => ({ items: [] }));
        setVoices(Array.isArray((v as { items?: VoiceProfile[] }).items) ? (v as { items: VoiceProfile[] }).items : []);
      } catch {
        // best-effort
      }
    })();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const handleOpenVoiceStudio = useCallback(async () => {
    // Amendment 3: preserve draft before navigation (do NOT require Save)
    await patcher.flush();
    saveDraftToSession();
    // Deep-link to Voice Studio with return route
    const params = new URLSearchParams({
      workspace: "voicestudio",
      characterId,
      returnWorkspace: "codirector",
    });
    window.location.assign(`/project/${projectId}?${params.toString()}`);
  }, [patcher, saveDraftToSession, projectId, characterId]);

  const refresh = useCallback(async () => {
    setBusy(true);
    setError(null);
    try {
      const [p, r, v, lib] = await Promise.all([
        api.getCharacterProfile(projectId, characterId),
        api.listCharacterReferences(projectId, characterId),
        api.listCharacterVoiceProfiles(projectId, characterId).catch(() => ({ items: [] })),
        api.library(projectId, { q: "" }).catch(() => ({ items: [] as LibraryAsset[] })),
      ]);
      setProfile(p as CharacterProfile);
      setRefs(
        Array.isArray((r as { items?: CharacterReference[] }).items)
          ? (r as { items: CharacterReference[] }).items
          : [],
      );
      setVoices(
        Array.isArray((v as { items?: VoiceProfile[] }).items)
          ? (v as { items: VoiceProfile[] }).items
          : [],
      );
      const libItems = Array.isArray((lib as { items?: LibraryAsset[] }).items)
        ? (lib as { items: LibraryAsset[] }).items
        : [];
      setLibraryAssets(libItems);
      // Load existing candidate pack if present
      let serverCandidates: Candidate[] = [];
      try {
        const pack = await api.getCharacterVisualSheet(projectId, characterId);
        if (pack?.candidates?.length) {
          serverCandidates = pack.candidates as Candidate[];
        }
      } catch {
        // no pack yet
      }
      // Amendment 3: merge any saved draft onto the freshly-loaded server profile
      // so creator-authored text survives a Voice Studio round-trip. The draft is
      // applied AFTER server data is available, then cleared.
      const draft = restoreDraftFromSession();
      if (draft) {
        const merged = {
          ...(p as CharacterProfile),
          visual_description: draft.visual_description,
          description: draft.description,
          name: draft.name || (p as CharacterProfile).name,
          visual_style: draft.visual_style || (p as CharacterProfile).visual_style,
          active_voice_profile_id: draft.active_voice_profile_id || (p as CharacterProfile).active_voice_profile_id,
          gender_presentation: draft.gender_presentation || (p as CharacterProfile & { gender_presentation?: string }).gender_presentation,
        } as CharacterProfile;
        setProfile(merged);
        if (draft.candidates?.length) {
          setCandidates(draft.candidates);
        } else if (serverCandidates.length) {
          setCandidates(serverCandidates);
        }
        try { sessionStorage.removeItem(draftKey); } catch { /* ignore */ }
      } else {
        if (serverCandidates.length) {
          setCandidates(serverCandidates);
        }
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  }, [projectId, characterId, draftKey, restoreDraftFromSession]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const handleAttachLibraryRef = useCallback(
    async (asset: LibraryAsset) => {
      setRefImageBusy(true);
      setGenMsg("");
      try {
        await api.attachCharacterReference(projectId, characterId, {
          asset_id: asset.id,
          reference_role: "reference_image",
          source_type: "upload",
          canonical: false,
        });
        await refresh();
        setLibraryPickerOpen(false);
      } catch (e) {
        setGenMsg(e instanceof Error ? e.message : "Attach failed");
      } finally {
        setRefImageBusy(false);
      }
    },
    [projectId, characterId, refresh],
  );

  const approvedImage = getApprovedImage(refs);
  const referenceImage = getReferenceImage(refs);
  const approvedVoice = voices.find((v) => v.approval_status === "approved" || v.status === "APPROVED");

  const personalityTags = useMemo(() => {
    const p = profile?.personality || {};
    return [
      ...(p.core_personality ? [p.core_personality] : []),
      ...(p.temperament ? [p.temperament] : []),
      ...(p.humor ? [p.humor] : []),
      ...toArray(p.strengths),
      ...toArray(p.flaws),
    ].filter((v, i, arr) => arr.indexOf(v) === i);
  }, [profile?.personality]);

  const canGenerate = useMemo(() => {
    const name = profile?.name?.trim() || "";
    const bio = profile?.description?.trim() || "";
    const visual = profile?.visual_description?.trim() || "";
    const style = profile?.visual_style?.trim() || "";
    const hasDescription = bio.length >= 20 || visual.length >= 20;
    return name.length > 0 && hasDescription && style.length > 0;
  }, [profile]);

  const characterAssets = useMemo(() => {
    const refAssetIds = new Set(refs.map((r) => r.asset_id).filter(Boolean) as string[]);
    return libraryAssets.filter((a) => refAssetIds.has(a.id));
  }, [refs, libraryAssets]);

  const visibleAssets = useMemo(
    () => characterAssets.filter((a) => matchesFilter(a, assetFilter)),
    [characterAssets, assetFilter],
  );

  const imageAssets = useMemo(() => libraryAssets.filter(isImageAsset), [libraryAssets]);

  useEffect(() => {
    if (!libraryPickerOpen) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        setLibraryPickerOpen(false);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [libraryPickerOpen]);

  const handleFieldChange = useCallback(
    (field: keyof CharacterProfile, value: string) => {
      setProfile((prev) => (prev ? { ...prev, [field]: value } : prev));
      patcher.schedule(projectId, characterId, { [field]: value }, () => {
        setSavedMsg("Saved");
        setTimeout(() => setSavedMsg(""), 1500);
      });
    },
    [projectId, characterId, patcher],
  );

  const handleAddTag = useCallback(() => {
    const v = tagInput.trim();
    if (!v || !profile) return;
    setTagInput("");
    const existing = profile.personality?.core_personality || "";
    const updated = existing ? `${existing}, ${v}` : v;
    setProfile((prev) =>
      prev ? { ...prev, personality: { ...(prev.personality || {}), core_personality: updated } } : prev,
    );
    void api
      .patchCharacterProfile(projectId, characterId, {
        personality: { ...(profile.personality || {}), core_personality: updated },
      })
      .then(() => {
        setSavedMsg("Saved");
        setTimeout(() => setSavedMsg(""), 1500);
      });
  }, [tagInput, profile, projectId, characterId]);

  const handleUploadRefImage = useCallback(
    async (file: File) => {
      setRefImageBusy(true);
      setGenMsg("");
      try {
        const asset = await api.uploadAsset(projectId, file, "character_reference", "image");
        await api.attachCharacterReference(projectId, characterId, {
          asset_id: asset.id,
          reference_role: "reference_image",
          source_type: "upload",
          canonical: false,
        });
        await refresh();
      } catch (e) {
        setGenMsg(e instanceof Error ? e.message : "Upload failed");
      } finally {
        setRefImageBusy(false);
      }
    },
    [projectId, characterId, refresh],
  );

  const handleRemoveReference = useCallback(
    async () => {
      if (!referenceImage?.asset_id) return;
      setRemovingRef(true);
      setGenMsg("");
      try {
        await api.detachCharacterReference(projectId, characterId, referenceImage.asset_id);
        await refresh();
      } catch (e) {
        setGenMsg(e instanceof Error ? e.message : "Remove failed");
      } finally {
        setRemovingRef(false);
      }
    },
    [projectId, characterId, referenceImage, refresh],
  );

  const handleGenerate = useCallback(
    async (regenerate: boolean) => {
      if (!profile) return;
      if (!canGenerate) {
        setGenMsg("Add a character name, description, and style before generating casting candidates.");
        return;
      }
      setGenerating(true);
      setGenMsg(regenerate ? "Regenerating 4 candidates…" : "Generating 4 candidates…");
      setCandidates([]);
      try {
        const res = await api.startCharacterVisualSheet(projectId, characterId, {
          candidateCount: 4,
          visualStyle: profile.visual_style || undefined,
          includeDetails: false,
          includePerformance: false,
        });
        const pack = (res as { pack?: { candidates?: Candidate[] } }).pack;
        setCandidates(pack?.candidates || []);
        // Poll for completion
        const poll = async (attemptsLeft: number) => {
          if (attemptsLeft <= 0) {
            setGenMsg("");
            return;
          }
          try {
            const adv = await api.advanceCharacterVisualSheet(projectId, characterId);
            const advPack = (adv as { pack?: { candidates?: Candidate[]; status?: string } }).pack;
            if (advPack?.candidates?.length) {
              setCandidates(advPack.candidates);
            }
            const allDone = (advPack?.candidates || []).every((c) => c.status === "done" || c.assetId);
            if (allDone || advPack?.status === "READY_FOR_OWNER" || advPack?.status === "OWNER_APPROVED") {
              setGenMsg("");
              return;
            }
          } catch {
            // ignore transient poll errors
          }
          setTimeout(() => void poll(attemptsLeft - 1), 3000);
        };
        void poll(40);
      } catch (e) {
        setGenMsg(e instanceof Error ? e.message : "Generation failed");
      } finally {
        setGenerating(false);
      }
    },
    [profile, projectId, characterId, canGenerate],
  );

  const handleApprove = useCallback(
    async (candidate: Candidate) => {
      if (!candidate.assetId) {
        setGenMsg("Candidate is still generating. Wait for the image to finish.");
        return;
      }
      if (!profile) return;
      const hasApproved = !!approvedImage;
      if (hasApproved) {
        const confirmed = window.confirm(`Replace ${profile.name || "this character"}'s approved casting image?`);
        if (!confirmed) return;
      }
      setApprovingId(candidate.assetId);
      setGenMsg("");
      try {
        await api.approveCharacterCandidate(projectId, characterId, {
          assetId: candidate.assetId,
          referenceRole: "hero_identity",
          sourceType: "generation",
          notes: `Approved casting candidate ${candidate.label || ""}`.trim(),
        });
        // Best-effort: flip visual sheet gates to owner-approved
        try {
          await api.ownerApproveCharacterVisualSheet(projectId, characterId);
        } catch {
          // gate approval is optional for the embedded flow
        }
        await refresh();
        setSavedMsg("Character Saved ✓");
        setTimeout(() => setSavedMsg(""), 2500);
      } catch (e) {
        setGenMsg(e instanceof Error ? e.message : "Approve failed");
      } finally {
        setApprovingId(null);
      }
    },
    [projectId, characterId, profile, approvedImage, refresh],
  );

  const handleDelete = useCallback(async () => {
    setDeleteBusy(true);
    setDeleteError(null);
    try {
      await api.deleteCharacterProfile(projectId, characterId);
      setDeleteConfirm(false);
      setDeleteBusy(false);
      try { sessionStorage.removeItem(draftKey); } catch { /* ignore */ }
      onOpenFull?.("__delete__");
    } catch (e) {
      setDeleteError(e instanceof Error ? e.message : String(e));
      setDeleteBusy(false);
    }
  }, [projectId, characterId, draftKey, onOpenFull]);

  const handleOpenFull = useCallback(async () => {
    await patcher.flush();
    onOpenFull?.(characterId);
  }, [patcher, onOpenFull, characterId]);

  if (busy) {
    return (
      <div className="character-compact__state" aria-hidden="true">
        {Array.from({ length: 5 }).map((_, i) => (
          <div key={i} className="character-compact__skeleton-line" />
        ))}
      </div>
    );
  }
  if (error) {
    return (
      <div className="character-compact__state character-compact__state--error">
        <strong>Character could not load</strong>
        <p>{error}</p>
        <button type="button" className="character-compact__actions-button primary" onClick={() => void refresh()}>
          Retry
        </button>
      </div>
    );
  }
  if (!profile) return null;

  return (
    <div className="character-compact__detail">
      <input
        ref={fileInputRef}
        type="file"
        accept="image/*"
        hidden
        onChange={(e) => {
          const f = e.target.files?.[0];
          if (f) void handleUploadRefImage(f);
          e.target.value = "";
        }}
      />

      <div className="character-compact__field">
        <label htmlFor="character-name">Character Name</label>
        <input
          id="character-name"
          type="text"
          data-testid="character-compact-name"
          placeholder="e.g. Mieke"
          value={profile.name || ""}
          onChange={(e) => handleFieldChange("name", e.target.value)}
        />
      </div>

      <div className="character-compact__field">
        <label htmlFor="character-gender">Character Gender</label>
        <select
          id="character-gender"
          data-testid="character-compact-gender"
          className="character-compact__select"
          value={(profile as CharacterProfile & { gender_presentation?: string }).gender_presentation || ""}
          onChange={(e) => handleFieldChange("gender_presentation" as keyof CharacterProfile, e.target.value)}
        >
          <option value="">Select a gender presentation…</option>
          <option value="female">Female</option>
          <option value="male">Male</option>
          <option value="nonbinary">Non-binary</option>
          <option value="androgynous">Androgynous</option>
          <option value="unspecified">Prefer not to specify</option>
        </select>
      </div>

      <div className="character-compact__field">
        <label htmlFor="character-profile">Character Profile</label>
        <textarea
          id="character-profile"
          data-testid="character-compact-profile"
          rows={6}
          placeholder="Who is this character? Appearance, personality, wardrobe, background… This is the primary source for casting image generation."
          value={profile.visual_description || profile.description || ""}
          onChange={(e) => {
            const val = e.target.value;
            setProfile((prev) =>
              prev ? { ...prev, visual_description: val, description: val } : prev,
            );
            patcher.schedule(projectId, characterId, { visual_description: val, description: val }, () => {
              setSavedMsg("Saved");
              setTimeout(() => setSavedMsg(""), 1500);
            });
          }}
        />
      </div>

      <div className="character-compact__field">
        <label htmlFor="character-style">Character Style</label>
        <select
          id="character-style"
          data-testid="character-compact-style"
          className="character-compact__select"
          value={profile.visual_style || ""}
          onChange={(e) => handleFieldChange("visual_style", e.target.value)}
        >
          {STYLE_OPTIONS.map((opt) => (
            <option key={opt.value || "blank"} value={opt.value}>
              {opt.label}
            </option>
          ))}
        </select>
      </div>

      <div className="character-compact__field">
        <label>Character Reference — Optional</label>
        <div className="character-compact__ref-row">
          <button
            type="button"
            className="character-compact__actions-button"
            data-testid="character-compact-add-ref"
            disabled={refImageBusy}
            onClick={() => fileInputRef.current?.click()}
          >
            {refImageBusy ? "Adding…" : "Upload Image"}
          </button>
          <button
            type="button"
            className="character-compact__actions-button"
            data-testid="character-compact-add-ref-library"
            disabled={refImageBusy}
            onClick={() => setLibraryPickerOpen(true)}
          >
            Choose from Library
          </button>
          {referenceImage?.asset_id ? (
            <div className="character-compact__ref-thumb" data-testid="character-compact-ref-thumb">
              <img src={api.assetUrl(referenceImage.asset_id)} alt="Reference" />
            </div>
          ) : null}
          {referenceImage?.asset_id ? (
            <button
              type="button"
              className="character-compact__actions-button character-compact__ref-remove"
              data-testid="character-compact-remove-ref"
              disabled={removingRef || refImageBusy}
              onClick={() => void handleRemoveReference()}
            >
              {removingRef ? "Removing…" : "Remove"}
            </button>
          ) : null}
        </div>
      </div>

      <div className="character-compact__gen-row">
        <button
          type="button"
          className="character-compact__actions-button primary"
          data-testid="character-compact-generate"
          disabled={!canGenerate || generating}
          onClick={() => void handleGenerate(false)}
        >
          {generating ? "Generating…" : candidates.length > 0 ? "Re-generate Images" : "Generate Images"}
        </button>
        {!canGenerate && !generating ? (
          <p className="character-compact__hint">Add a name, profile, and style to enable generation.</p>
        ) : null}
        {genMsg ? (
          <p className="character-compact__hint" data-testid="character-compact-gen-msg">
            {genMsg}
          </p>
        ) : null}
      </div>

      {candidates.length > 0 ? (
        <div className="character-compact__section">
          <h4>CASTING IMAGES</h4>
          <div className="character-compact__candidates" data-testid="character-compact-candidates">
            {candidates.map((c, i) => {
              const isApproved = approvedImage?.asset_id === c.assetId && !!c.assetId;
              return (
                <div
                  key={c.assetId || c.jobId || i}
                  className={`character-compact__candidate${isApproved ? " is-approved" : ""}`}
                  data-testid="character-compact-candidate"
                >
                  {c.assetId ? (
                    <img src={api.assetUrl(c.assetId)} alt={c.label || `Candidate ${i + 1}`} />
                  ) : (
                    <div className="character-compact__candidate-placeholder">
                      {c.status === "failed" ? "Failed" : "Generating…"}
                    </div>
                  )}
                  <span>{c.label || `Candidate ${i + 1}`}</span>
                  <label className="character-compact__radio">
                    <input
                      type="radio"
                      name="character-candidate-approval"
                      data-testid="character-compact-approve-radio"
                      checked={isApproved}
                      disabled={!c.assetId || approvingId === c.assetId}
                      onChange={() => void handleApprove(c)}
                    />
                    {approvingId === c.assetId ? "Approving…" : isApproved ? "Active Identity ✓" : "Approve"}
                  </label>
                </div>
              );
            })}
          </div>
          <p className="character-compact__hint">
            Not satisfied? Adjust the Character Profile, then re-generate for better results. Casting images are full-body by default.
          </p>
        </div>
      ) : null}

      <div className="character-compact__section">
        <h4>Approved Casting Image</h4>
        {approvedImage?.asset_id ? (
          <div className="character-compact__hero">
            <img
              className="character-compact__hero-img"
              src={api.assetUrl(approvedImage.asset_id)}
              alt={`${profile.name} casting`}
            />
            <span className="character-compact__tag">
              {approvedImage.reference_role || "Hero"}
              {approvedImage.approval_status === "approved" ? " · Approved" : ""}
            </span>
            <button
              type="button"
              className="character-compact__actions-button"
              onClick={() => {
                document
                  .querySelector(".character-compact__gen-row")
                  ?.scrollIntoView({ behavior: "smooth", block: "center" });
              }}
            >
              Change / Generate New Candidates
            </button>
          </div>
        ) : (
          <div className="character-compact__hero-placeholder">No approved casting image yet.</div>
        )}
      </div>

      <div className="character-compact__section">
        <h4>Character Voice</h4>
        <select
          className="character-compact__select"
          data-testid="character-compact-voice-select"
          value={(profile as CharacterProfile & { active_voice_profile_id?: string }).active_voice_profile_id || ""}
          onChange={(e) => {
            const voiceId = e.target.value || null;
            setProfile((prev) =>
              prev ? { ...prev, active_voice_profile_id: voiceId } as CharacterProfile : prev,
            );
            patcher.schedule(projectId, characterId, { active_voice_profile_id: voiceId }, () => {
              setSavedMsg("Saved");
              setTimeout(() => setSavedMsg(""), 1500);
            });
          }}
        >
          <option value="">— No voice selected —</option>
          {voices.map((v) => (
            <option key={v.id} value={v.id}>
              {getVoiceName(v)}{v.approval_status === "approved" ? " ✓" : ""}
            </option>
          ))}
        </select>
        {approvedVoice?.approved_preview_asset_id ? (
          <audio controls src={api.assetUrl(approvedVoice.approved_preview_asset_id)} data-testid="character-compact-voice-preview" />
        ) : null}
        <button
          type="button"
          className="character-compact__actions-button"
          data-testid="character-compact-create-voice"
          onClick={() => void handleOpenVoiceStudio()}
        >
          Create Voice in Voice Studio →
        </button>
      </div>

      <div className="character-compact__section">
        <h4>Personality</h4>
        <div className="character-compact__tags">
          {personalityTags.map((tag) => (
            <span key={tag} className="character-compact__tag">
              {tag}
            </span>
          ))}
          {personalityTags.length === 0 ? (
            <span className="character-compact__bio-text">No personality keywords yet.</span>
          ) : null}
        </div>
        <div className="character-compact__tag-add">
          <input
            type="text"
            placeholder="Add a keyword…"
            value={tagInput}
            onChange={(e) => setTagInput(e.target.value)}
            list="character-predefined-tags"
            aria-label="Add personality keyword"
          />
          <datalist id="character-predefined-tags">
            {PREDEFINED_TAGS.map((t) => (
              <option key={t} value={t} />
            ))}
          </datalist>
          <button type="button" data-testid="character-compact-add-tag" onClick={handleAddTag}>
            Add
          </button>
        </div>
      </div>

      <div className="character-compact__section">
        <h4>Character Assets</h4>
        <div className="character-compact__asset-filters">
          {ASSET_FILTERS.map((f) => (
            <button
              key={f.id}
              type="button"
              className={`character-compact__asset-filter${assetFilter === f.id ? " is-selected" : ""}`}
              data-testid={`character-compact-asset-filter-${f.id}`}
              onClick={() => setAssetFilter(f.id)}
            >
              {f.label}
            </button>
          ))}
        </div>
        {visibleAssets.length === 0 ? (
          <p className="character-compact__bio-text">No {assetFilter} assets linked to this character yet.</p>
        ) : (
          <div className="character-compact__assets-grid">
            {visibleAssets.map((a) => (
              <AssetCard key={a.id} asset={a} onOpen={() => setPreviewAsset(a)} />
            ))}
          </div>
        )}
      </div>

      {savedMsg ? (
        <div className="character-compact__saved" data-testid="character-compact-saved">
          {savedMsg}
        </div>
      ) : null}

      <div className="character-compact__actions">
        <div className="character-compact__actions-left">
          <button
            type="button"
            className="character-compact__actions-button primary"
            data-testid="character-compact-save"
            disabled={!profile.name?.trim()}
            onClick={async () => {
              await patcher.flush();
              try { sessionStorage.removeItem(draftKey); } catch { /* ignore */ }
              setSavedMsg("Character Saved ✓");
              setTimeout(() => setSavedMsg(""), 2500);
            }}
          >
            Save Character
          </button>
          <button
            type="button"
            className="character-compact__actions-button"
            data-testid="character-compact-reset"
            onClick={async () => {
              if (window.confirm("Reset? This clears unsaved changes and reverts to the last saved state.")) {
                try { sessionStorage.removeItem(draftKey); } catch { /* ignore */ }
                if (profile?.id) {
                  await refresh();
                } else {
                  setCandidates([]);
                }
              }
            }}
          >
            Reset
          </button>
          <button
            type="button"
            className="character-compact__actions-button"
            data-testid="character-compact-open-full"
            onClick={() => void handleOpenFull()}
          >
            Open Full Character Creator
          </button>
        </div>
        <div className="character-compact__actions-right">
          <button
            type="button"
            className="character-compact__actions-button character-compact__actions-button--danger"
            data-testid="character-compact-delete"
            disabled={deleteBusy}
            onClick={() => setDeleteConfirm(true)}
          >
            {deleteBusy ? "Deleting…" : "Delete Character"}
          </button>
        </div>
      </div>

      {deleteConfirm ? (
        <div className="character-compact__confirm-overlay" onClick={() => !deleteBusy && setDeleteConfirm(false)}>
          <div className="character-compact__confirm-dialog" onClick={(e) => e.stopPropagation()}>
            <strong>Delete Character?</strong>
            <p>Are you sure you want to delete "{profile.name}"?</p>
            <p className="character-compact__confirm-hint">
              This will remove the character from this project.
              This action cannot be undone.
            </p>
            <p className="character-compact__confirm-hint">
              References in Spatial Map, Scene Creator, Timeline, and Wiki may remain and should be reviewed.
            </p>
            {deleteError ? (
              <p className="character-compact__confirm-error" data-testid="character-compact-delete-error">{deleteError}</p>
            ) : null}
            <div className="character-compact__confirm-actions">
              <button
                type="button"
                className="character-compact__actions-button"
                data-testid="character-compact-delete-cancel"
                disabled={deleteBusy}
                onClick={() => setDeleteConfirm(false)}
              >
                Cancel
              </button>
              <button
                type="button"
                className="character-compact__actions-button character-compact__actions-button--danger"
                data-testid="character-compact-delete-confirm"
                disabled={deleteBusy}
                onClick={() => void handleDelete()}
              >
                {deleteBusy ? "Deleting…" : "Delete Character"}
              </button>
            </div>
          </div>
        </div>
      ) : null}

      {previewAsset ? (
        <div
          className="character-compact__preview"
          role="dialog"
          aria-label="Asset preview"
          onClick={() => setPreviewAsset(null)}
        >
          <div className="character-compact__preview-body" onClick={(e) => e.stopPropagation()}>
            {isImageAsset(previewAsset) ? (
              <img src={api.assetUrl(previewAsset.id)} alt={previewAsset.tag || previewAsset.filename} />
            ) : isVideoAsset(previewAsset) ? (
              <video src={api.assetUrl(previewAsset.id)} controls autoPlay />
            ) : isAudioAsset(previewAsset) ? (
              <audio controls src={api.assetUrl(previewAsset.id)} />
            ) : (
              <div className="character-compact__preview-doc">
                <div className="character-compact__asset-icon">{getDocumentKind(previewAsset.filename)}</div>
                <strong>{previewAsset.tag || previewAsset.filename || "Document"}</strong>
                <span>Document preview not available inline.</span>
              </div>
            )}
            <button type="button" className="character-compact__actions-button" onClick={() => setPreviewAsset(null)}>
              Close
            </button>
          </div>
        </div>
      ) : null}

      {libraryPickerOpen
        ? createPortal(
            <div
              className="character-compact__preview"
              role="dialog"
              aria-label="Choose reference from Library"
              aria-modal="true"
              onClick={() => setLibraryPickerOpen(false)}
            >
              <div className="character-compact__picker-body" onClick={(e) => e.stopPropagation()}>
                <div className="character-compact__picker-header">
                  <strong>Choose a Reference Image</strong>
                </div>
                <div className="character-compact__picker-grid">
                  <div className="character-compact__assets-grid" role="listbox" aria-label="Library images">
                    {imageAssets.map((a) => {
                      const isSelected = selectedPickerAsset?.id === a.id;
                      return (
                        <button
                          key={a.id}
                          type="button"
                          className={`character-compact__asset is-media${isSelected ? " is-selected" : ""}`}
                          onClick={() => setSelectedPickerAsset(a)}
                          aria-label={`Select ${a.tag || a.filename}${isSelected ? " (currently selected)" : ""}`}
                          role="option"
                          aria-selected={isSelected}
                        >
                          <img src={getCardPreviewUrl(a) || api.assetUrl(a.id)} alt={a.tag || a.filename} loading="lazy" />
                          <strong>{a.tag || a.filename}</strong>
                          {isSelected ? <span className="character-compact__asset-check">✓</span> : null}
                        </button>
                      );
                    })}
                    {imageAssets.length === 0 ? (
                      <p className="character-compact__bio-text">No images in your Library yet.</p>
                    ) : null}
                  </div>
                </div>
                <div className="character-compact__picker-footer">
                  <div className="character-compact__picker-footer-inner">
                    <button type="button" className="character-compact__actions-button" onClick={() => { setLibraryPickerOpen(false); setSelectedPickerAsset(null); }}>
                      Cancel
                    </button>
                    <button
                      type="button"
                      className="character-compact__actions-button primary"
                      data-testid="character-compact-picker-select"
                      disabled={!selectedPickerAsset}
                      onClick={() => {
                        if (selectedPickerAsset) {
                          void handleAttachLibraryRef(selectedPickerAsset);
                          setSelectedPickerAsset(null);
                        }
                      }}
                    >
                      Select
                    </button>
                  </div>
                </div>
              </div>
            </div>,
            document.body,
          )
        : null}
    </div>
  );
}

export function CharacterCompactView({ projectId, onOpenFull }: Props) {
  const [characters, setCharacters] = useState<CharacterProfile[]>([]);
  const [selectedId, setSelectedId] = useState<string>("");
  const [busy, setBusy] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    setBusy(true);
    setError(null);
    try {
      const result = (await api.listCharacterProfiles(projectId)) as { items?: CharacterProfile[] };
      const list = Array.isArray(result?.items) ? result.items : [];
      setCharacters(list);
      setSelectedId((prev) => prev || list[0]?.id || "");
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  }, [projectId]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const handleCreate = useCallback(async () => {
    try {
      const created = (await api.createCharacterProfile(projectId, { name: "New Character" })) as CharacterProfile;
      await refresh();
      setSelectedId(created.id);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }, [projectId, refresh]);

  return (
    <div className="character-compact" data-testid="character-compact">
      {busy ? (
        <div className="character-compact__state" aria-hidden="true">
          {Array.from({ length: 5 }).map((_, i) => (
            <div key={i} className="character-compact__skeleton-line" />
          ))}
        </div>
      ) : error ? (
        <div className="character-compact__state character-compact__state--error" data-testid="character-compact-error">
          <strong>Characters could not load</strong>
          <p>{error}</p>
          <button type="button" className="character-compact__actions-button primary" onClick={() => void refresh()}>
            Retry
          </button>
        </div>
      ) : (
        <>
          <div className="character-compact__selector">
            <label htmlFor="character-select">Saved Characters</label>
            <select
              id="character-select"
              className="character-compact__select"
              data-testid="character-compact-saved-select"
              value={selectedId}
              onChange={(e) => setSelectedId(e.target.value)}
              aria-label="Select saved character"
            >
              <option value="">— Select a saved character —</option>
              {characters.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.name}
                </option>
              ))}
            </select>
          </div>
          {selectedId ? (
            <CharacterDetail
              projectId={projectId}
              characterId={selectedId}
              onOpenFull={(id) => {
                if (id === "__delete__") {
                  void refresh();
                  setSelectedId("");
                } else {
                  onOpenFull?.(id);
                }
              }}
            />
          ) : (
            <div className="character-compact__state" data-testid="character-compact-empty">
              <strong>No characters have been created yet.</strong>
              <p>Define your cast and assign casting images, voice and references.</p>
              <button
                type="button"
                className="character-compact__actions-button primary"
                data-testid="character-compact-create"
                onClick={() => void handleCreate()}
              >
                Create Character
              </button>
            </div>
          )}
        </>
      )}
    </div>
  );
}
