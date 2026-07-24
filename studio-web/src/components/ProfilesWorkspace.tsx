import { useEffect, useState } from "react";
import { api } from "../api";
import { PanelHeading } from "./HelpTip";

type Profile = {
  id: string;
  kind: string;
  name: string;
  tag: string;
  category: string;
  description: string;
  data: Record<string, unknown>;
  media_path: string;
};

const KINDS = [
  ["character", "Characters"],
  ["voice", "Voice Profiles"],
  ["prop", "Props"],
  ["scene", "Scenes"],
  ["motion", "Motion Library"],
  ["camera_preset", "Camera Presets"],
  ["motion_preset", "Motion Presets"],
] as const;

export function ProfilesWorkspace({ onOpenAvatar }: { onOpenAvatar?: (profileId: string) => void }) {
  const [kind, setKind] = useState<(typeof KINDS)[number][0]>("character");
  const [items, setItems] = useState<Profile[]>([]);
  const [name, setName] = useState("");
  const [tag, setTag] = useState("");
  const [category, setCategory] = useState("");
  const [description, setDescription] = useState("");
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);

  const refresh = async () => {
    const list = await api.listProfiles(kind);
    setItems(list);
  };

  useEffect(() => {
    refresh().catch(console.error);
  }, [kind]);

  const create = async () => {
    setBusy(true);
    setMsg(null);
    try {
      await api.createProfile(kind, {
        name: name || kind,
        tag,
        category,
        description,
        data: {},
      });
      setName("");
      setTag("");
      setCategory("");
      setDescription("");
      await refresh();
    } catch (err) {
      setMsg(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  };

  const uploadMotion = async (file: File) => {
    setBusy(true);
    try {
      await api.uploadProfile(kind, file, { name: name || file.name, tag, category, description });
      await refresh();
    } catch (err) {
      setMsg(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="page profiles-page">
      <div className="panel">
        <PanelHeading
          title="Profiles — Production DNA"
          tip="Cross-project reusable library: characters, props, scenes, motions, and presets."
        />
        <div className="workspace-tabs" role="tablist">
          {KINDS.map(([id, label]) => (
            <button
              key={id}
              type="button"
              className={kind === id ? "primary" : ""}
              onClick={() => setKind(id)}
            >
              {label}
            </button>
          ))}
        </div>
      </div>

      <div className="panel" style={{ marginTop: "0.75rem" }}>
        <div className="section-label">New {kind.replace("_", " ")}</div>
        <div className="field">
          <label>Name</label>
          <input value={name} onChange={(e) => setName(e.target.value)} />
        </div>
        <div className="field">
          <label>Tag {kind === "motion" ? "(auto #tag)" : ""}</label>
          <input
            value={tag}
            onChange={(e) => setTag(e.target.value)}
            placeholder={kind === "motion" ? "#walkMilitary" : "optional"}
          />
        </div>
        <div className="field">
          <label>Category</label>
          <input value={category} onChange={(e) => setCategory(e.target.value)} />
        </div>
        <div className="field">
          <label>Description</label>
          <textarea value={description} onChange={(e) => setDescription(e.target.value)} rows={3} />
        </div>
        <div className="row-actions">
          <button type="button" className="primary" disabled={busy} onClick={create}>
            Create
          </button>
          {(kind === "motion" || kind === "character" || kind === "prop" || kind === "scene") && (
            <label className="ghost" style={{ cursor: "pointer" }}>
              Upload media
              <input
                type="file"
                hidden
                accept={kind === "motion" ? "video/*" : "image/*"}
                onChange={(e) => {
                  const f = e.target.files?.[0];
                  if (f) uploadMotion(f);
                }}
              />
            </label>
          )}
        </div>
        {msg && <p className="scene-meta">{msg}</p>}
      </div>

      <div className="grid-cards" style={{ marginTop: "1rem" }}>
        {items.length === 0 && <div className="empty">No profiles yet</div>}
        {items.map((item) => (
          <div
            className="card"
            key={item.id}
            draggable
            onDragStart={(e) => {
              e.dataTransfer.setData("application/x-adept-profile", item.id);
              e.dataTransfer.setData("application/x-adept-profile-kind", item.kind);
              e.dataTransfer.setData("application/x-adept-profile-tag", item.tag || "");
            }}
          >
            <h3>{item.name}</h3>
            {item.tag && <div className="pill">{item.tag}</div>}
            <p className="scene-meta">{item.category}</p>
            <p>{item.description || "—"}</p>
            {kind === "character" && onOpenAvatar && (
              <button type="button" className="primary" style={{ marginTop: "0.5rem" }} onClick={() => onOpenAvatar(item.id)}>
                Open in Avatar Studio
              </button>
            )}
            {item.media_path && <p className="scene-meta">Media linked</p>}
            <button
              type="button"
              className="danger"
              onClick={async () => {
                await api.deleteProfile(item.id);
                refresh();
              }}
            >
              Delete
            </button>
          </div>
        ))}
      </div>
    </div>
  );
}
