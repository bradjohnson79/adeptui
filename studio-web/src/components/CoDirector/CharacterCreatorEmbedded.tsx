import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "../../api";
import { Button } from "../ui";
import "./character-creator-embedded.css";

const VOCABULARY_KEYWORDS = [
  "sarcastic", "warm", "disciplined", "protective", "reserved",
  "reckless", "curious", "idealistic", "intense", "playful",
  "skeptical", "loyal", "ambitious", "compassionate", "stubborn",
  "charismatic", "analytical", "impulsive", "cunning", "gentle",
  "fierce", "mysterious", "elegant", "rough", "patient",
  "volatile", "dignified", "humble", "proud", "witty",
];

function isImageRole(role: string): boolean {
  const imageRoles = [
    "hero_portrait", "full_body_front", "full_body_back", "full_body_side",
    "closeup_face", "closeup_eyes", "closeup_hands",
    "expression_sheet", "pose_sheet", "turnaround_sheet",
    "hair_front", "hair_back", "hair_side",
    "wardrobe_reference",
  ];
  return imageRoles.some((r) => role.startsWith(r) || role === r);
}

function isVideoAsset(ref: any): boolean {
  const kind = String(ref.kind || ref.assetKind || ref.reference_kind || "").toLowerCase();
  return kind === "video" || ref.mediaType === "video";
}

function isAudioAsset(ref: any): boolean {
  const kind = String(ref.kind || ref.assetKind || ref.reference_kind || "").toLowerCase();
  return kind === "audio" || ref.mediaType === "audio" || String(ref.reference_role || "").includes("voice");
}

function isDocumentAsset(ref: any): boolean {
  const kind = String(ref.kind || ref.assetKind || ref.reference_kind || "").toLowerCase();
  return kind === "document" || kind === "text" || kind === "note" || kind === "notes";
}

function getAssetKind(ref: any): string {
  if (isVideoAsset(ref)) return "video";
  if (isAudioAsset(ref)) return "audio";
  if (isDocumentAsset(ref)) return "document";
  const role = String(ref.reference_role || ref.role || "");
  if (isImageRole(role)) return "image";
  if (role) return "image";
  const kind = String(ref.kind || ref.assetKind || ref.reference_kind || "");
  if (kind === "image") return "image";
  return "other";
}

function assetUrl(assetId: string): string {
  return `/api/assets/${encodeURIComponent(assetId)}/file`;
}

export function CharacterCreatorEmbedded({ projectId }: { projectId: string }) {
  const [characters, setCharacters] = useState<any[]>([]);
  const [loadingList, setLoadingList] = useState(true);
  const [selectedId, setSelectedId] = useState<string>("__create__");
  const [profile, setProfile] = useState<any | null>(null);
  const [loadingProfile, setLoadingProfile] = useState(false);

  const [createName, setCreateName] = useState("");
  const [createRole, setCreateRole] = useState("");
  const [creating, setCreating] = useState(false);

  const [saveState, setSaveState] = useState<"" | "saving" | "saved" | "error">("");
  const saveTimerRef = useRef<number | null>(null);
  const loadedRef = useRef(false);

  const [references, setReferences] = useState<any[]>([]);

  const loadCharacters = useCallback(async () => {
    setLoadingList(true);
    try {
      const res = await api.listCharacterProfiles(projectId);
      setCharacters(res.items || []);
    } catch {
      setCharacters([]);
    }
    setLoadingList(false);
  }, [projectId]);

  const loadProfile = useCallback(async (characterId: string) => {
    setLoadingProfile(true);
    try {
      const res = await api.getCharacterProfile(projectId, characterId);
      setProfile(res);
      loadedRef.current = true;
    } catch {
      setProfile(null);
      loadedRef.current = true;
    }
    setLoadingProfile(false);
  }, [projectId]);

  const loadReferences = useCallback(async (characterId: string) => {
    try {
      const res = await api.listCharacterReferences(projectId, characterId);
      setReferences(res.items || []);
    } catch {
      setReferences([]);
    }
  }, [projectId]);

  useEffect(() => {
    void loadCharacters();
  }, [loadCharacters]);

  useEffect(() => {
    if (!selectedId || selectedId === "__create__") {
      setProfile(null);
      setReferences([]);
      loadedRef.current = false;
      setSaveState("");
      return;
    }
    loadedRef.current = false;
    void loadProfile(selectedId);
    void loadReferences(selectedId);
  }, [selectedId, loadProfile, loadReferences]);

  const scheduleSave = useCallback(
    (patch: Record<string, unknown>) => {
      if (!selectedId || selectedId === "__create__" || !loadedRef.current) return;
      if (saveTimerRef.current) clearTimeout(saveTimerRef.current);
      setSaveState("saving");
      saveTimerRef.current = window.setTimeout(async () => {
        try {
          const updated = await api.patchCharacterProfile(projectId, selectedId, patch);
          setProfile(updated);
          setSaveState("saved");
          setTimeout(() => setSaveState(""), 2000);
        } catch {
          setSaveState("error");
        }
      }, 700);
    },
    [projectId, selectedId],
  );

  useEffect(() => {
    return () => {
      if (saveTimerRef.current) clearTimeout(saveTimerRef.current);
    };
  }, []);

  const handleSelectChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    setSelectedId(e.target.value);
  };

  const handleCreate = async () => {
    if (!createName.trim()) return;
    setCreating(true);
    try {
      const created = await api.createCharacterProfile(projectId, {
        name: createName.trim(),
        role: createRole.trim() || undefined,
      });
      setCharacters((prev) => [...prev, created]);
      setSelectedId(created.id || created.characterId || "");
      setCreateName("");
      setCreateRole("");
      await loadCharacters();
    } catch {
      /* noop */
    }
    setCreating(false);
  };

  if (loadingList) {
    return <p className="muted" data-testid="cd-char-loading">Loading characters…</p>;
  }

  return (
    <div className="cd-character-creator" data-testid="codirector-content-characters">
      {/* Section 1: Character Selector */}
      <div className="cd-character-creator__section">
        <div className="cd-character-creator__section-heading">
          Character
          <span className="cd-character-creator__save-state" data-testid="cd-char-save-state">
            {saveState === "saving" ? "Saving..." : saveState === "saved" ? "Saved" : saveState === "error" ? "Save failed" : ""}
          </span>
        </div>
        <div className="cd-character-creator__selector">
          <select value={selectedId} onChange={handleSelectChange} data-testid="cd-char-select">
            <option value="__create__">— Create New Character —</option>
            {characters.map((c) => (
              <option key={c.id || c.characterId} value={c.id || c.characterId}>
                {c.name || "Unnamed"}
              </option>
            ))}
          </select>
        </div>
        {selectedId === "__create__" && (
          <div className="cd-character-creator__create-inline">
            <input
              type="text"
              placeholder="Character name"
              value={createName}
              onChange={(e) => setCreateName(e.target.value)}
              data-testid="cd-char-create-name"
            />
            <input
              type="text"
              placeholder="Role (optional)"
              value={createRole}
              onChange={(e) => setCreateRole(e.target.value)}
              data-testid="cd-char-create-role"
            />
            <Button variant="primary" disabled={creating || !createName.trim()} onClick={handleCreate} data-testid="cd-char-create-btn">
              {creating ? "Creating…" : "Create"}
            </Button>
          </div>
        )}
      </div>

      {selectedId !== "__create__" && profile && (
        <>
          <BioSection profile={profile} scheduleSave={scheduleSave} saveState={saveState} />
          <KeywordsSection projectId={projectId} profile={profile} selectedId={selectedId} />
          <CastingImageSection references={references} />
          <AssetsSection references={references} />
        </>
      )}

      {selectedId !== "__create__" && loadingProfile && (
        <p className="muted" data-testid="cd-char-loading-profile">Loading profile…</p>
      )}

      {selectedId !== "__create__" && !loadingProfile && !profile && (
        <p className="muted" data-testid="cd-char-no-profile">Could not load character profile.</p>
      )}
    </div>
  );
}

/* ── Section 2: Bio ── */

function BioSection({
  profile,
  scheduleSave,
  saveState,
}: {
  profile: any;
  scheduleSave: (patch: Record<string, unknown>) => void;
  saveState: "" | "saving" | "saved" | "error";
}) {
  const personality = profile.personality || {};
  const [name, setName] = useState(profile.name || "");
  const [role, setRole] = useState(profile.role || "");
  const [age, setAge] = useState(profile.apparent_age || "");
  const [species, setSpecies] = useState(profile.species_or_type || "");
  const [gender, setGender] = useState(profile.gender_presentation || "");
  const [description, setDescription] = useState(profile.description || "");
  const [hair, setHair] = useState(personality.cd_hair || "");
  const [eyes, setEyes] = useState(personality.cd_eyes || "");
  const [build, setBuild] = useState(personality.cd_build || "");
  const [wardrobe, setWardrobe] = useState(personality.cd_wardrobe || "");
  const [biography, setBiography] = useState(personality.cd_biography || "");
  const [notes, setNotes] = useState(personality.cd_notes || "");
  const [initialized, setInitialized] = useState(false);

  const nameRef = useRef(name);
  const roleRef = useRef(role);
  const ageRef = useRef(age);
  const speciesRef = useRef(species);
  const genderRef = useRef(gender);
  const descriptionRef = useRef(description);
  const hairRef = useRef(hair);
  const eyesRef = useRef(eyes);
  const buildRef = useRef(build);
  const wardrobeRef = useRef(wardrobe);
  const biographyRef = useRef(biography);
  const notesRef = useRef(notes);

  useEffect(() => {
    nameRef.current = name;
    roleRef.current = role;
    ageRef.current = age;
    speciesRef.current = species;
    genderRef.current = gender;
    descriptionRef.current = description;
    hairRef.current = hair;
    eyesRef.current = eyes;
    buildRef.current = build;
    wardrobeRef.current = wardrobe;
    biographyRef.current = biography;
    notesRef.current = notes;
  }, [name, role, age, species, gender, description, hair, eyes, build, wardrobe, biography, notes]);

  useEffect(() => {
    const p = profile.personality || {};
    setName(profile.name || "");
    setRole(profile.role || "");
    setAge(profile.apparent_age || "");
    setSpecies(profile.species_or_type || "");
    setGender(profile.gender_presentation || "");
    setDescription(profile.description || "");
    setHair(p.cd_hair || "");
    setEyes(p.cd_eyes || "");
    setBuild(p.cd_build || "");
    setWardrobe(p.cd_wardrobe || "");
    setBiography(p.cd_biography || "");
    setNotes(p.cd_notes || "");
    setInitialized(true);
  }, [profile]);

  const buildPatch = useCallback((): Record<string, unknown> => {
    const p = profile.personality || {};
    return {
      name: nameRef.current,
      role: roleRef.current || undefined,
      apparent_age: ageRef.current || undefined,
      species_or_type: speciesRef.current || undefined,
      gender_presentation: genderRef.current || undefined,
      description: descriptionRef.current || undefined,
      body_type: buildRef.current || undefined,
      personality: {
        ...p,
        cd_hair: hairRef.current || "",
        cd_eyes: eyesRef.current || "",
        cd_build: buildRef.current || "",
        cd_wardrobe: wardrobeRef.current || "",
        cd_biography: biographyRef.current || "",
        cd_notes: notesRef.current || "",
      },
    };
  }, [profile]);

  const onChange = useCallback(() => {
    if (!initialized) return;
    scheduleSave(buildPatch());
  }, [initialized, scheduleSave, buildPatch]);

  return (
    <div className="cd-character-creator__section" data-testid="cd-char-bio-section">
      <div className="cd-character-creator__section-heading">
        Biography
        <span className="cd-character-creator__save-state" data-testid="cd-char-save-state">
          {saveState === "saving" ? "Saving..." : saveState === "saved" ? "Saved" : saveState === "error" ? "Save failed" : ""}
        </span>
      </div>
      <div className="cd-character-creator__bio-grid">
        <Field label="Character Name" testid="cd-char-name" value={name} onChange={(v) => { setName(v); onChange(); }} />
        <Field label="Role" testid="cd-char-role" value={role} onChange={(v) => { setRole(v); onChange(); }} />
        <Field label="Age / Apparent Age" testid="cd-char-age" value={age} onChange={(v) => { setAge(v); onChange(); }} />
        <Field label="Species / Heritage" testid="cd-char-species" value={species} onChange={(v) => { setSpecies(v); onChange(); }} />
        <Field label="Gender Presentation" testid="cd-char-gender" value={gender} onChange={(v) => { setGender(v); onChange(); }} />
        <Field label="Hair" testid="cd-char-hair" value={hair} onChange={(v) => { setHair(v); onChange(); }} />
        <Field label="Eyes" testid="cd-char-eyes" value={eyes} onChange={(v) => { setEyes(v); onChange(); }} />
        <Field label="Build" testid="cd-char-build" value={build} onChange={(v) => { setBuild(v); onChange(); }} />
        <TextAreaField label="Physical Description" testid="cd-char-description" value={description} onChange={(v) => { setDescription(v); onChange(); }} />
        <TextAreaField label="Wardrobe Summary" testid="cd-char-wardrobe" value={wardrobe} onChange={(v) => { setWardrobe(v); onChange(); }} />
        <TextAreaField label="Short Biography" testid="cd-char-bio" value={biography} onChange={(v) => { setBiography(v); onChange(); }} />
        <TextAreaField label="Character Notes" testid="cd-char-notes" value={notes} onChange={(v) => { setNotes(v); onChange(); }} />
      </div>
    </div>
  );
}

function Field({
  label,
  testid,
  value,
  onChange,
}: {
  label: string;
  testid: string;
  value: string;
  onChange: (v: string) => void;
}) {
  return (
    <div className="cd-character-creator__bio-field">
      <label htmlFor={testid}>{label}</label>
      <input id={testid} type="text" value={value} onChange={(e) => onChange(e.target.value)} data-testid={testid} />
    </div>
  );
}

function TextAreaField({
  label,
  testid,
  value,
  onChange,
}: {
  label: string;
  testid: string;
  value: string;
  onChange: (v: string) => void;
}) {
  return (
    <div className="cd-character-creator__bio-field cd-character-creator__bio-field--full">
      <label htmlFor={testid}>{label}</label>
      <textarea id={testid} value={value} onChange={(e) => onChange(e.target.value)} data-testid={testid} />
    </div>
  );
}

/* ── Section 3: Keywords ── */

function KeywordsSection({
  projectId,
  profile,
  selectedId,
}: {
  projectId: string;
  profile: any;
  selectedId: string;
}) {
  const personality = profile.personality || {};
  const [keywords, setKeywords] = useState<string[]>(personality.keywords || []);
  const [customWord, setCustomWord] = useState("");
  const saveTimerRef = useRef<number | null>(null);

  useEffect(() => {
    const p = profile.personality || {};
    setKeywords(p.keywords || []);
  }, [profile]);

  useEffect(() => {
    return () => {
      if (saveTimerRef.current) clearTimeout(saveTimerRef.current);
    };
  }, []);

  const persist = useCallback(
    (updated: string[]) => {
      if (saveTimerRef.current) clearTimeout(saveTimerRef.current);
      saveTimerRef.current = window.setTimeout(async () => {
        const p = profile.personality || {};
        try {
          await api.patchCharacterProfile(projectId, selectedId, {
            personality: { ...p, keywords: updated },
          });
        } catch {
          /* noop */
        }
      }, 700);
    },
    [projectId, selectedId, profile],
  );

  const addKeyword = (word: string) => {
    if (!word.trim() || keywords.includes(word.trim())) return;
    const updated = [...keywords, word.trim()];
    setKeywords(updated);
    persist(updated);
  };

  const removeKeyword = (word: string) => {
    const updated = keywords.filter((k) => k !== word);
    setKeywords(updated);
    persist(updated);
  };

  const available = VOCABULARY_KEYWORDS.filter((k) => !keywords.includes(k));

  return (
    <div className="cd-character-creator__section" data-testid="cd-char-keywords-section">
      <div className="cd-character-creator__section-heading">Personality Keywords</div>
      <div className="cd-character-creator__keywords" data-testid="cd-char-keywords">
        {keywords.map((kw) => (
          <span key={kw} className="cd-character-creator__keyword cd-character-creator__keyword--active" data-testid={`cd-char-keyword-active-${kw}`}>
            {kw}
            <button
              type="button"
              className="cd-character-creator__keyword-remove"
              onClick={() => removeKeyword(kw)}
              aria-label={`Remove ${kw}`}
              data-testid={`cd-char-keyword-remove-${kw}`}
            >
              ×
            </button>
          </span>
        ))}
      </div>
      <div className="cd-character-creator__keywords" style={{ marginTop: "0.3rem" }}>
        {available.map((kw) => (
          <span
            key={kw}
            className="cd-character-creator__keyword cd-character-creator__keyword--available"
            onClick={() => addKeyword(kw)}
            data-testid={`cd-char-keyword-avail-${kw}`}
          >
            + {kw}
          </span>
        ))}
      </div>
      <div className="cd-character-creator__keyword-add">
        <input
          type="text"
          placeholder="Add custom keyword…"
          value={customWord}
          onChange={(e) => setCustomWord(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") {
              addKeyword(customWord);
              setCustomWord("");
            }
          }}
          data-testid="cd-char-keyword-custom-input"
        />
        <Button
          variant="compact"
          disabled={!customWord.trim()}
          onClick={() => {
            addKeyword(customWord);
            setCustomWord("");
          }}
          data-testid="cd-char-keyword-custom-add"
        >
          Add
        </Button>
      </div>
    </div>
  );
}

/* ── Section 4: Approved Casting Image ── */

function CastingImageSection({ references }: { references: any[] }) {
  const heroRefs = references.filter((r) => String(r.reference_role || r.role || "") === "hero_portrait");
  const sorted = [...heroRefs].sort((a, b) => {
    const aCanon = a.canonical ? 1 : 0;
    const bCanon = b.canonical ? 1 : 0;
    if (aCanon !== bCanon) return bCanon - aCanon;
    const aApproved = a.approval_status === "approved" ? 1 : 0;
    const bApproved = b.approval_status === "approved" ? 1 : 0;
    return bApproved - aApproved;
  });
  const best = sorted[0] || null;

  const status = best
    ? best.approval_status === "approved"
      ? "approved"
      : best.approval_status === "pending" || best.canonical
        ? "pending"
        : "none"
    : "none";

  const assetId = best?.assetId || best?.asset_id || best?.fileId || best?.file_id || "";

  return (
    <div className="cd-character-creator__section" data-testid="cd-char-casting-section">
      <div className="cd-character-creator__section-heading">Approved Casting Image</div>
      <div className="cd-character-creator__image-display">
        {best && assetId ? (
          <>
            <img
              className="cd-character-creator__image-preview"
              src={assetUrl(assetId)}
              alt="Casting reference"
              data-testid="cd-char-casting-image"
            />
            <div className="cd-character-creator__image-meta">
              <span
                className={`cd-character-creator__image-status cd-character-creator__image-status--${status}`}
                data-testid="cd-char-casting-status"
              >
                {status === "approved" ? "Approved" : status === "pending" ? "Pending" : "None"}
              </span>
            </div>
          </>
        ) : (
          <p className="cd-character-creator__section-empty" data-testid="cd-char-casting-status">
            None — No hero portrait reference found.
          </p>
        )}
        <p className="muted" style={{ fontSize: "0.75rem", margin: "0.25rem 0 0" }}>
          Use Co-Director to generate new casting options.
        </p>
      </div>
    </div>
  );
}

/* ── Section 5: Character Assets ── */

function AssetsSection({ references }: { references: any[] }) {
  const groups: Record<string, any[]> = { images: [], video: [], audio: [], document: [], other: [] };

  for (const ref of references) {
    const kind = getAssetKind(ref);
    if (!groups[kind]) groups[kind] = [];
    groups[kind].push(ref);
  }

  const labels: Record<string, string> = {
    images: "Images",
    video: "Video",
    audio: "Audio",
    document: "Documents",
    other: "Other",
  };

  const categories = Object.entries(groups).filter(
    ([key]) => key !== "other" || groups[key].length > 0,
  );

  return (
    <div className="cd-character-creator__section" data-testid="cd-char-assets-section">
      <div className="cd-character-creator__section-heading">Character Assets</div>
      <div className="cd-character-creator__assets-grid">
        {categories.map(([key, items]) => (
          <div key={key} className="cd-character-creator__asset-card" data-testid={`cd-char-asset-${key}`}>
            <p className="cd-character-creator__asset-card-heading">{labels[key] || key}</p>
            <p className="cd-character-creator__asset-card-count">{items.length} item{items.length !== 1 ? "s" : ""}</p>
            {items.length === 0 ? (
              <p className="cd-character-creator__section-empty">None yet</p>
            ) : (
              <>
                <div className="cd-character-creator__asset-thumbs">
                  {items.slice(0, 3).map((ref, i) => {
                    const aid = ref.assetId || ref.asset_id || ref.fileId || ref.file_id || "";
                    const isImg = getAssetKind(ref) === "image";
                    return isImg && aid ? (
                      <img
                        key={ref.id || ref.referenceId || i}
                        className="cd-character-creator__asset-thumb"
                        src={assetUrl(aid)}
                        alt=""
                      />
                    ) : (
                      <span
                        key={ref.id || ref.referenceId || i}
                        className="cd-character-creator__asset-thumb"
                        style={{
                          display: "inline-flex",
                          alignItems: "center",
                          justifyContent: "center",
                          fontSize: "0.65rem",
                          color: "var(--codirector-text-muted)",
                          background: "rgba(0,0,0,0.2)",
                          borderRadius: "4px",
                          width: "44px",
                          height: "44px",
                        }}
                      >
                        {key === "video" ? "🎬" : key === "audio" ? "🎙" : "📄"}
                      </span>
                    );
                  })}
                </div>
                {items.length > 3 && (
                  <p className="cd-character-creator__asset-more">(+{items.length - 3} more)</p>
                )}
              </>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
