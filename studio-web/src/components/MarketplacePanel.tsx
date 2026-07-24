import { useEffect, useState } from "react";
import { api } from "../api";
import type { Project } from "../types";
import { LoRAManager } from "./LoRAManager";

const CATS = [
  ["loras", "Creative Assets / LoRAs"],
  ["packs", "Essential Packs"],
  ["models", "Models"],
  ["workflows", "Workflows"],
  ["nodes", "Nodes"],
  ["embeddings", "Embeddings"],
  ["styles", "Styles"],
] as const;

export function MarketplacePanel({ project }: { project: Project }) {
  const [cat, setCat] = useState<(typeof CATS)[number][0]>("loras");
  const [q, setQ] = useState("");
  const [items, setItems] = useState<any[]>([]);
  const [path, setPath] = useState("");
  const [msg, setMsg] = useState<string | null>(null);
  const [stack, setStack] = useState<any[]>([]);

  const refresh = () =>
    api.marketplace({ category: cat, q }).then(setItems).catch(console.error);

  useEffect(() => {
    refresh();
  }, [cat, q]);

  useEffect(() => {
    api.loraStack(`project:${project.id}`).then((r) => setStack(r.stack || [])).catch(() => undefined);
  }, [project.id]);

  const install = async (id: string) => {
    if (!confirm("Approve marketplace install? Explicit approval required.")) return;
    try {
      const r = await api.marketplaceInstall(id, path, true);
      setMsg(`${r.status}: ${r.message}`);
      refresh();
    } catch (e: any) {
      setMsg(e?.message || String(e));
    }
  };

  return (
    <div className="page marketplace-page">
      <h1>Adept Marketplace</h1>
      <p className="muted">Curated shell — LoRAs and Essential Packs ship first. No silent downloads.</p>
      {msg && <p className="pill warn">{msg}</p>}

      <div className="workspace-tabs" role="tablist">
        {CATS.map(([id, label]) => (
          <button
            key={id}
            type="button"
            role="tab"
            className={cat === id ? "primary" : ""}
            aria-selected={cat === id}
            onClick={() => setCat(id)}
          >
            {label}
          </button>
        ))}
      </div>

      <div className="field">
        <label>Search</label>
        <input value={q} onChange={(e) => setQ(e.target.value)} />
      </div>
      <div className="field">
        <label>Optional local file path for install</label>
        <input value={path} onChange={(e) => setPath(e.target.value)} />
      </div>

      {!items.length ? (
        <p className="empty">No curated items in this category yet — slots reserved.</p>
      ) : (
        <div className="grid-cards">
          {items.map((item) => (
            <div className="card" key={item.id}>
              <h3>
                {item.name} {item.verified ? <span className="pill">Verified</span> : null}
              </h3>
              <p>{item.description}</p>
              <p className="muted">
                {item.creator} · {item.license} · ★ {item.rating}
              </p>
              <p className="muted">{(item.tags || []).join(", ")}</p>
              <button type="button" className="primary" onClick={() => install(item.id)} disabled={item.installed}>
                {item.installed ? "Installed / registered" : "Approve install"}
              </button>
            </div>
          ))}
        </div>
      )}

      <LoRAManager
        scope={`project:${project.id}`}
        baseModel="flux"
        stack={stack}
        onStackChange={setStack}
      />
    </div>
  );
}
