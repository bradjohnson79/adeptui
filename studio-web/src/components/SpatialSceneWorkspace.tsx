import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { api } from "../api";
import type { Project, Scene } from "../types";
import { PanelHeading } from "./HelpTip";

type EntityType =
  | "character"
  | "prop"
  | "architecture"
  | "vehicle"
  | "camera"
  | "light"
  | "audio"
  | "zone"
  | "marker";

type Avatar = {
  id: string;
  label: string;
  initials: string;
  color: string;
  shape: string;
  entity_type: EntityType;
  x: number;
  y: number;
  rotation: number;
  scale: number;
  height: number;
  profile_id?: string | null;
  spatial_prompt?: string;
  continuity?: string;
  visible?: boolean;
  locked?: boolean;
  facing?: { mode: string; target_avatar_id?: string | null; compass?: string };
  relationships?: { type: string; to_id: string }[];
  camera?: {
    lens_mm: number;
    height_m: number;
    shot_size: string;
    focus_targets: string[];
    fov_deg: number;
    aspect: string;
    rig: string;
    movement: string;
  } | null;
  expression?: string;
  pose?: string;
  wardrobe?: string;
  door_state?: string;
  prop_state?: string;
};

type SpatialDoc = {
  version: number;
  width: number;
  height: number;
  background_asset_id?: string | null;
  notes: string;
  guidance: "loose" | "balanced" | "strict";
  avatars: Avatar[];
  states: { id: string; name: string; camera_id?: string | null; lighting?: string; avatar_overrides?: Record<string, any> }[];
  active_state_id?: string | null;
  prompt_layers: Record<string, string>;
};

const ENTITY_TOOLS: { type: EntityType; label: string }[] = [
  { type: "character", label: "Character" },
  { type: "prop", label: "Prop" },
  { type: "architecture", label: "Architecture" },
  { type: "vehicle", label: "Vehicle" },
  { type: "camera", label: "Camera" },
  { type: "light", label: "Light" },
  { type: "zone", label: "Zone" },
];

const REL_TYPES = [
  "faces",
  "looks_at",
  "speaks_to",
  "holds",
  "approaches",
  "stands_beside",
  "walks_toward",
];

function initialsOf(label: string) {
  const parts = label.trim().split(/\s+/).filter(Boolean);
  if (!parts.length) return "??";
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase();
  return (parts[0][0] + parts[1][0]).toUpperCase();
}

function shapeClass(shape: string) {
  return `avatar-shape avatar-${shape || "circle"}`;
}

export function SpatialSceneWorkspace({
  project,
  scene,
  onChange,
  onGoDirector,
}: {
  project: Project;
  scene?: Scene;
  onChange: () => Promise<void> | void;
  onGoDirector?: () => void;
}) {
  const sceneId = scene?.id || project.scenes[0]?.id;
  const [doc, setDoc] = useState<SpatialDoc | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [tool, setTool] = useState<EntityType>("character");
  const [bottomTab, setBottomTab] = useState<"legend" | "cameras" | "states" | "preview" | "generate" | "director">(
    "legend"
  );
  const [profiles, setProfiles] = useState<any[]>([]);
  const [layers, setLayers] = useState<Record<string, string>>({});
  const [promptPreview, setPromptPreview] = useState("");
  const [msg, setMsg] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [jobId, setJobId] = useState<string | null>(null);
  const [outputAssetId, setOutputAssetId] = useState<string | null>(null);
  const [command, setCommand] = useState("");
  const [proposed, setProposed] = useState<any[] | null>(null);
  const dragRef = useRef<{ id: string; ox: number; oy: number } | null>(null);

  const selected = useMemo(
    () => doc?.avatars.find((a) => a.id === selectedId) || null,
    [doc, selectedId]
  );

  const load = useCallback(async () => {
    if (!sceneId) return;
    const r = await api.getSceneSpatial(project.id, sceneId);
    setDoc(r.doc);
    setLayers(r.doc.prompt_layers || {});
  }, [project.id, sceneId]);

  useEffect(() => {
    load().catch(console.error);
    api.listProfiles().then(setProfiles).catch(() => setProfiles([]));
  }, [load]);

  const persist = async (next: SpatialDoc) => {
    if (!sceneId) return;
    setDoc(next);
    await api.putSceneSpatial(project.id, sceneId, { doc: next, guidance: next.guidance });
  };

  const addAvatarAt = async (x: number, y: number) => {
    if (!doc) return;
    const n = doc.avatars.filter((a) => a.entity_type === tool).length + 1;
    const label =
      tool === "camera" ? `C${n}` : tool === "character" ? `Character ${n}` : `${tool} ${n}`;
    const avatar: Avatar = {
      id: crypto.randomUUID(),
      label,
      initials: initialsOf(label),
      color: ["#0f766e", "#c45c26", "#1d4ed8", "#7c3aed", "#b91c1c"][doc.avatars.length % 5],
      shape:
        tool === "character"
          ? "circle"
          : tool === "prop"
            ? "square"
            : tool === "architecture"
              ? "diamond"
              : tool === "vehicle"
                ? "hex"
                : tool === "camera"
                  ? "camera"
                  : tool === "light"
                    ? "light"
                    : tool === "zone"
                      ? "zone"
                      : "circle",
      entity_type: tool,
      x,
      y,
      rotation: tool === "camera" ? -45 : 0,
      scale: 1,
      height: tool === "character" ? 1.7 : tool === "camera" ? 1.6 : 1,
      facing: { mode: "compass", compass: "south" },
      relationships: [],
      camera:
        tool === "camera"
          ? {
              lens_mm: 35,
              height_m: 1.6,
              shot_size: "medium",
              focus_targets: [],
              fov_deg: 50,
              aspect: "16:9",
              rig: "tripod",
              movement: "static",
            }
          : null,
      continuity: "unlocked",
      visible: true,
      locked: false,
    };
    await persist({ ...doc, avatars: [...doc.avatars, avatar] });
    setSelectedId(avatar.id);
  };

  const patchSelected = async (patch: Partial<Avatar>) => {
    if (!doc || !selected) return;
    const next = {
      ...doc,
      avatars: doc.avatars.map((a) => (a.id === selected.id ? { ...a, ...patch } : a)),
    };
    await persist(next);
  };

  const refreshPrompt = async () => {
    if (!sceneId || !doc) return;
    const r = await api.spatialPrompt(project.id, sceneId, {
      state_id: doc.active_state_id,
      layers,
    });
    setLayers(r.layers);
    setPromptPreview(r.positive);
  };

  const generate = async () => {
    if (!sceneId || !doc) return;
    setBusy(true);
    setMsg(null);
    try {
      const cam = doc.avatars.find((a) => a.entity_type === "camera");
      const r = await api.spatialGenerate(project.id, sceneId, {
        state_id: doc.active_state_id,
        layers,
        camera_avatar_id: cam?.id,
        style: layers.style || "",
      });
      setJobId(r.id);
      setMsg("Spatial generate queued");
    } catch (e: any) {
      setMsg(e?.message || String(e));
    } finally {
      setBusy(false);
    }
  };

  useEffect(() => {
    if (!jobId) return;
    const t = setInterval(() => {
      api.getJob(jobId).then((j) => {
        if (j.status === "done") {
          try {
            const p = JSON.parse(j.params_json || "{}");
            if (p.output_asset_id) setOutputAssetId(p.output_asset_id);
          } catch {
            /* ignore */
          }
          setMsg("Shot ready");
          void onChange();
        }
        if (j.status === "failed") setMsg(j.message || "Generate failed");
      });
    }, 1500);
    return () => clearInterval(t);
  }, [jobId, onChange]);

  const sendDirector = async (createNew: boolean) => {
    if (!sceneId) return;
    const r = await api.spatialSendDirector(project.id, sceneId, {
      create_new_scene: createNew,
      asset_id: outputAssetId,
      slot: "start",
      state_id: doc?.active_state_id,
    });
    setMsg(`Sent to Director (${r.applied.join(", ")})`);
    await onChange();
    onGoDirector?.();
  };

  const runCommand = async (approve = false) => {
    if (!sceneId || !command.trim()) return;
    const r = await api.spatialCommands(project.id, sceneId, { command, approved: approve });
    setProposed(r.proposed_mutations);
    if (r.applied && r.doc) {
      setDoc(r.doc);
      setMsg("Mutations applied");
    } else {
      setMsg("Review proposed mutations — Approve to apply");
    }
  };

  if (!sceneId) {
    return (
      <div className="page">
        <p className="empty">Create a Director scene first to open Spatial Map.</p>
      </div>
    );
  }

  if (!doc) {
    return (
      <div className="page">
        <p className="empty">Loading spatial scene…</p>
      </div>
    );
  }

  return (
    <div className="spatial-workspace">
      <header className="spatial-workspace-head">
        <PanelHeading
          title="Spatial Map"
          tip="Authoritative staging blueprint. Place avatars, attach Profiles, build spatial prompts, generate shots, send to Director."
        />
        <div className="row" style={{ gap: "0.5rem", flexWrap: "wrap" }}>
          <label className="scene-meta">
            Scene{" "}
            <strong>{scene?.name || "Scene"}</strong>
          </label>
          <select
            value={doc.active_state_id || ""}
            onChange={(e) => persist({ ...doc, active_state_id: e.target.value })}
          >
            {doc.states.map((s) => (
              <option key={s.id} value={s.id}>
                {s.name}
              </option>
            ))}
          </select>
          <select
            value={doc.guidance}
            onChange={(e) =>
              persist({ ...doc, guidance: e.target.value as SpatialDoc["guidance"] })
            }
          >
            <option value="loose">Loose</option>
            <option value="balanced">Balanced</option>
            <option value="strict">Strict</option>
          </select>
          <span className="pill">2D</span>
        </div>
      </header>

      {msg && <p className="pill warn">{msg}</p>}

      <div className="spatial-layout">
        <div className="spatial-main">
          <div className="avatar-toolbar">
            {ENTITY_TOOLS.map((t) => (
              <button
                key={t.type}
                type="button"
                className={tool === t.type ? "primary" : ""}
                onClick={() => setTool(t.type)}
              >
                {t.label}
              </button>
            ))}
          </div>
          <div
            className="spatial-canvas spatial-canvas-v2"
            onClick={(e) => {
              if (dragRef.current) return;
              const rect = (e.currentTarget as HTMLDivElement).getBoundingClientRect();
              const x = ((e.clientX - rect.left) / rect.width) * doc.width;
              const y = ((e.clientY - rect.top) / rect.height) * doc.height;
              void addAvatarAt(x, y);
            }}
          >
            {doc.background_asset_id && (
              <img
                className="spatial-bg"
                src={api.assetUrl(doc.background_asset_id)}
                alt=""
                draggable={false}
              />
            )}
            {doc.avatars
              .filter((a) => a.visible !== false)
              .map((a) => {
                const isCam = a.entity_type === "camera";
                const fov = a.camera?.fov_deg || 50;
                return (
                  <div
                    key={a.id}
                    className={`spatial-avatar ${selectedId === a.id ? "selected" : ""} ${a.locked ? "locked" : ""}`}
                    style={{
                      left: `${(a.x / doc.width) * 100}%`,
                      top: `${(a.y / doc.height) * 100}%`,
                      color: a.color,
                    }}
                    onClick={(e) => {
                      e.stopPropagation();
                      setSelectedId(a.id);
                    }}
                    onMouseDown={(e) => {
                      if (a.locked) return;
                      e.stopPropagation();
                      dragRef.current = { id: a.id, ox: e.clientX, oy: e.clientY };
                      const onMove = (ev: MouseEvent) => {
                        if (!dragRef.current || !doc) return;
                        const canvas = (e.currentTarget as HTMLElement).parentElement;
                        if (!canvas) return;
                        const rect = canvas.getBoundingClientRect();
                        const nx = ((ev.clientX - rect.left) / rect.width) * doc.width;
                        const ny = ((ev.clientY - rect.top) / rect.height) * doc.height;
                        setDoc({
                          ...doc,
                          avatars: doc.avatars.map((x) =>
                            x.id === a.id ? { ...x, x: Math.max(0, Math.min(doc.width, nx)), y: Math.max(0, Math.min(doc.height, ny)) } : x
                          ),
                        });
                      };
                      const onUp = () => {
                        window.removeEventListener("mousemove", onMove);
                        window.removeEventListener("mouseup", onUp);
                        const cur = dragRef.current;
                        dragRef.current = null;
                        if (cur && doc) {
                          const latest = doc.avatars.find((x) => x.id === cur.id);
                          if (latest) {
                            void persist({
                              ...doc,
                              avatars: doc.avatars.map((x) => (x.id === cur.id ? latest : x)),
                            });
                          }
                        }
                      };
                      window.addEventListener("mousemove", onMove);
                      window.addEventListener("mouseup", onUp);
                    }}
                  >
                    {isCam && (
                      <div
                        className="fov-cone"
                        style={{
                          transform: `translate(-50%, -100%) rotate(${a.rotation}deg)`,
                          ["--fov" as any]: `${fov}deg`,
                          borderBottomColor: a.color,
                        }}
                      />
                    )}
                    <div className={shapeClass(a.shape)} style={{ borderColor: a.color, background: a.color }}>
                      {a.initials || "?"}
                    </div>
                    <div
                      className="facing-arrow"
                      style={{ transform: `rotate(${a.rotation}deg)`, borderBottomColor: a.color }}
                    />
                    <span className="avatar-height">{a.height?.toFixed?.(1) || a.height}m</span>
                  </div>
                );
              })}
          </div>
        </div>

        <aside className="spatial-inspector">
          <h3>Scene Inspector</h3>
          {!selected ? (
            <p className="empty">Select an avatar</p>
          ) : (
            <>
              <div className="field">
                <label>Label</label>
                <input
                  value={selected.label}
                  onChange={(e) =>
                    patchSelected({ label: e.target.value, initials: initialsOf(e.target.value) })
                  }
                />
              </div>
              <div className="field">
                <label>Profile</label>
                <select
                  value={selected.profile_id || ""}
                  onChange={(e) => patchSelected({ profile_id: e.target.value || null })}
                >
                  <option value="">—</option>
                  {profiles.map((p) => (
                    <option key={p.id} value={p.id}>
                      {p.kind}: {p.name}
                    </option>
                  ))}
                </select>
              </div>
              <div className="field">
                <label>Facing</label>
                <select
                  value={selected.facing?.mode || "compass"}
                  onChange={(e) =>
                    patchSelected({
                      facing: { ...(selected.facing || { compass: "south" }), mode: e.target.value },
                    })
                  }
                >
                  {[
                    "compass",
                    "face_avatar",
                    "face_camera",
                    "look_left",
                    "look_right",
                    "over_shoulder",
                    "back_to_camera",
                    "three_quarter_camera",
                  ].map((m) => (
                    <option key={m} value={m}>
                      {m}
                    </option>
                  ))}
                </select>
              </div>
              {selected.facing?.mode === "face_avatar" && (
                <div className="field">
                  <label>Face avatar</label>
                  <select
                    value={selected.facing?.target_avatar_id || ""}
                    onChange={(e) =>
                      patchSelected({
                        facing: { ...selected.facing!, target_avatar_id: e.target.value },
                      })
                    }
                  >
                    <option value="">—</option>
                    {doc.avatars
                      .filter((a) => a.id !== selected.id)
                      .map((a) => (
                        <option key={a.id} value={a.id}>
                          {a.label}
                        </option>
                      ))}
                  </select>
                </div>
              )}
              <div className="field">
                <label>Rotation°</label>
                <input
                  type="number"
                  value={selected.rotation}
                  onChange={(e) => patchSelected({ rotation: Number(e.target.value) })}
                />
              </div>
              <div className="field">
                <label>Add relationship</label>
                <div className="row">
                  <select
                    id="rel-type"
                    defaultValue="looks_at"
                    onChange={() => undefined}
                  >
                    {REL_TYPES.map((r) => (
                      <option key={r} value={r}>
                        {r}
                      </option>
                    ))}
                  </select>
                  <select
                    id="rel-to"
                    defaultValue=""
                    onChange={(e) => {
                      const typeEl = document.getElementById("rel-type") as HTMLSelectElement;
                      const to = e.target.value;
                      if (!to) return;
                      const type = typeEl?.value || "looks_at";
                      patchSelected({
                        relationships: [...(selected.relationships || []), { type, to_id: to }],
                      });
                      e.target.value = "";
                    }}
                  >
                    <option value="">to…</option>
                    {doc.avatars
                      .filter((a) => a.id !== selected.id)
                      .map((a) => (
                        <option key={a.id} value={a.id}>
                          {a.label}
                        </option>
                      ))}
                  </select>
                </div>
              </div>
              <div className="field">
                <label>Continuity</label>
                <select
                  value={selected.continuity || "unlocked"}
                  onChange={(e) => patchSelected({ continuity: e.target.value })}
                >
                  <option value="unlocked">Unlocked</option>
                  <option value="locked">Locked</option>
                </select>
              </div>
              <div className="row">
                <button type="button" onClick={() => patchSelected({ locked: !selected.locked })}>
                  {selected.locked ? "Unlock" : "Lock"}
                </button>
                <button
                  type="button"
                  onClick={() =>
                    persist({ ...doc, avatars: doc.avatars.filter((a) => a.id !== selected.id) })
                  }
                >
                  Remove
                </button>
              </div>
              {selected.entity_type === "camera" && selected.camera && (
                <>
                  <h4>Camera</h4>
                  <div className="field">
                    <label>Lens mm</label>
                    <input
                      type="number"
                      value={selected.camera.lens_mm}
                      onChange={(e) =>
                        patchSelected({
                          camera: { ...selected.camera!, lens_mm: Number(e.target.value) },
                        })
                      }
                    />
                  </div>
                  <div className="field">
                    <label>Shot size</label>
                    <input
                      value={selected.camera.shot_size}
                      onChange={(e) =>
                        patchSelected({
                          camera: { ...selected.camera!, shot_size: e.target.value },
                        })
                      }
                    />
                  </div>
                  <div className="field">
                    <label>FOV°</label>
                    <input
                      type="number"
                      value={selected.camera.fov_deg}
                      onChange={(e) =>
                        patchSelected({
                          camera: { ...selected.camera!, fov_deg: Number(e.target.value) },
                        })
                      }
                    />
                  </div>
                </>
              )}
            </>
          )}

          <h3 style={{ marginTop: "1rem" }}>Spatial Prompt</h3>
          <button type="button" onClick={() => void refreshPrompt()}>
            Rebuild from map
          </button>
          {["scene", "identity", "spatial", "camera", "negative_spatial"].map((k) => (
            <div className="field" key={k}>
              <label>{k}</label>
              <textarea
                rows={2}
                value={layers[k] || ""}
                onChange={(e) => setLayers({ ...layers, [k]: e.target.value })}
              />
            </div>
          ))}

          <h3>Co-Director</h3>
          <div className="field">
            <input
              value={command}
              onChange={(e) => setCommand(e.target.value)}
              placeholder="Place Barnes near the elevator…"
            />
          </div>
          <div className="row">
            <button type="button" onClick={() => void runCommand(false)}>
              Propose
            </button>
            <button type="button" className="primary" onClick={() => void runCommand(true)}>
              Approve apply
            </button>
          </div>
          {proposed && (
            <pre className="spatial-propose">{JSON.stringify(proposed, null, 2)}</pre>
          )}
        </aside>
      </div>

      <div className="spatial-bottom">
        <div className="workspace-tabs">
          {(["legend", "cameras", "states", "preview", "generate", "director"] as const).map((t) => (
            <button
              key={t}
              type="button"
              className={bottomTab === t ? "primary" : ""}
              onClick={() => setBottomTab(t)}
            >
              {t}
            </button>
          ))}
        </div>
        {bottomTab === "legend" && (
          <ul className="home-list spatial-legend">
            {doc.avatars.map((a) => (
              <li key={a.id}>
                <button type="button" className="linkish" onClick={() => setSelectedId(a.id)}>
                  <span className="pill" style={{ background: a.color, color: "#fff" }}>
                    {a.initials}
                  </span>{" "}
                  {a.label} — {a.entity_type}
                  {a.profile_id ? " · profile" : ""} · facing {a.facing?.mode}
                </button>
              </li>
            ))}
          </ul>
        )}
        {bottomTab === "cameras" && (
          <ul className="home-list">
            {doc.avatars
              .filter((a) => a.entity_type === "camera")
              .map((a) => (
                <li key={a.id}>
                  {a.label}: {a.camera?.shot_size} · {a.camera?.lens_mm}mm · {a.camera?.rig}
                </li>
              ))}
          </ul>
        )}
        {bottomTab === "states" && (
          <div className="row" style={{ gap: "0.5rem", flexWrap: "wrap" }}>
            {doc.states.map((s) => (
              <button
                key={s.id}
                type="button"
                className={doc.active_state_id === s.id ? "primary" : ""}
                onClick={() => persist({ ...doc, active_state_id: s.id })}
              >
                {s.name}
              </button>
            ))}
            <button
              type="button"
              onClick={() => {
                const st = {
                  id: crypto.randomUUID(),
                  name: `State ${String.fromCharCode(65 + doc.states.length)}`,
                };
                void persist({
                  ...doc,
                  states: [...doc.states, st],
                  active_state_id: st.id,
                });
              }}
            >
              + State
            </button>
          </div>
        )}
        {bottomTab === "preview" && (
          <div>
            {outputAssetId ? (
              <img src={api.assetUrl(outputAssetId)} alt="spatial shot" style={{ maxWidth: 360, borderRadius: 8 }} />
            ) : (
              <p className="empty">Generate a shot to preview.</p>
            )}
            {promptPreview && <pre className="spatial-propose">{promptPreview.slice(0, 1200)}</pre>}
          </div>
        )}
        {bottomTab === "generate" && (
          <div className="row" style={{ gap: "0.5rem" }}>
            <button type="button" className="primary" disabled={busy} onClick={() => void generate()}>
              {busy ? "Queuing…" : "Generate shot"}
            </button>
            <button type="button" onClick={() => void refreshPrompt()}>
              Refresh prompt
            </button>
          </div>
        )}
        {bottomTab === "director" && (
          <div className="row" style={{ gap: "0.5rem", flexWrap: "wrap" }}>
            <button type="button" className="primary" onClick={() => void sendDirector(false)}>
              Update current scene
            </button>
            <button type="button" onClick={() => void sendDirector(true)}>
              Create Director scene
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
