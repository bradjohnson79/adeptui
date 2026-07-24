import { useEffect, useState } from "react";
import { api } from "../api";

export function LoRAManager({
  scope,
  baseModel,
  stack,
  onStackChange,
}: {
  scope: string;
  baseModel: string;
  stack: any[];
  onStackChange: (stack: any[]) => void;
}) {
  const [catalog, setCatalog] = useState<any[]>([]);
  const [path, setPath] = useState("");
  const [msg, setMsg] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const refresh = () =>
    api.marketplace({ category: "loras", base_model: baseModel }).then(setCatalog).catch(console.error);

  useEffect(() => {
    refresh();
  }, [baseModel]);

  const approveInstall = async (itemId: string) => {
    if (!confirm("Approve install of this LoRA/pack? Nothing is downloaded silently.")) return;
    setBusy(true);
    setMsg(null);
    try {
      const r = await api.marketplaceInstall(itemId, path, true);
      setMsg(`${r.status}: ${r.message}`);
      await refresh();
    } catch (e: any) {
      setMsg(e?.message || String(e));
    } finally {
      setBusy(false);
    }
  };

  const addToStack = (item: any) => {
    if (stack.some((s) => s.id === item.id)) return;
    const next = [...stack, { id: item.id, name: item.name, strength: item.recommended_weight || 0.8 }];
    onStackChange(next);
    api.putLoraStack(scope, next).catch(console.error);
  };

  const setStrength = (id: string, strength: number) => {
    const next = stack.map((s) => (s.id === id ? { ...s, strength } : s));
    onStackChange(next);
    api.putLoraStack(scope, next).catch(console.error);
  };

  const remove = (id: string) => {
    const next = stack.filter((s) => s.id !== id);
    onStackChange(next);
    api.putLoraStack(scope, next).catch(console.error);
  };

  return (
    <div className="lora-manager card" style={{ marginTop: "0.75rem" }}>
      <h3>LoRA Manager</h3>
      <p className="muted">Ordered layers with strengths. Installs always require explicit approval.</p>
      {msg && <p className="pill warn">{msg}</p>}

      <div className="field">
        <label>Optional local .safetensors path (for approve-install)</label>
        <input value={path} onChange={(e) => setPath(e.target.value)} placeholder="C:\\…\\lora.safetensors" />
      </div>

      <h4>Active stack</h4>
      {!stack.length ? (
        <p className="empty">No LoRAs in stack.</p>
      ) : (
        <ul className="home-list">
          {stack.map((s, i) => (
            <li key={s.id}>
              {i + 1}. {s.name}{" "}
              <input
                type="range"
                min={0}
                max={1.5}
                step={0.05}
                value={s.strength}
                onChange={(e) => setStrength(s.id, Number(e.target.value))}
              />{" "}
              {Number(s.strength).toFixed(2)}
              <button type="button" onClick={() => remove(s.id)} style={{ marginLeft: 8 }}>
                Remove
              </button>
            </li>
          ))}
        </ul>
      )}

      <h4>Catalog (compatible with {baseModel})</h4>
      <div className="grid-cards">
        {catalog.map((item) => (
          <div className="card" key={item.id}>
            <h3>{item.name}</h3>
            <p>{item.description}</p>
            <p className="muted">
              {item.compatible ? "Compatible" : "May be incompatible"} · w={item.recommended_weight} ·{" "}
              {item.file_size_mb} MB
            </p>
            <div className="row">
              <button type="button" disabled={busy} onClick={() => approveInstall(item.id)}>
                Approve install
              </button>
              <button type="button" onClick={() => addToStack(item)}>
                Add to stack
              </button>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
