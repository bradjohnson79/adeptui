import { useEffect, useMemo, useState } from "react";
import { api } from "../../api";
import type { Project } from "../../types";
import type { EditorTab } from "../../workspacePrefs";
import { PanelHeading } from "../HelpTip";
import { Button } from "../ui";
import { StatusBadge } from "../ui";
import { mapGenerationToolStatus } from "../../status";

type Tool = {
  id: string;
  label: string;
  category: string;
  description?: string;
  providerHint?: string;
  blocked?: boolean;
  blockedReason?: string;
  navTab?: EditorTab;
  inputs?: string[];
};

type Category = { id: string; label: string; tools: Tool[] };

/**
 * M3.2a Tools hub — filmmaking task categories (not model names).
 */
export function GenerationToolsHub({
  project,
  onChange,
  onGo,
}: {
  project: Project;
  onChange?: () => Promise<void>;
  onGo: (tab: EditorTab) => void;
}) {
  const [categories, setCategories] = useState<Category[]>([]);
  const [statusMap, setStatusMap] = useState<Record<string, any>>({});
  const [selected, setSelected] = useState<Tool | null>(null);
  const [sourceAssetId, setSourceAssetId] = useState("");
  const [prompt, setPrompt] = useState("");
  const [documentType, setDocumentType] = useState("treatment");
  const [keyColor, setKeyColor] = useState("green");
  const [msg, setMsg] = useState("");
  const [busy, setBusy] = useState(false);
  const assets = useMemo(
    () => (project.assets || []).filter((a) => a.kind === "image" || a.kind === "video" || a.kind === "audio"),
    [project.assets],
  );

  useEffect(() => {
    api.generationToolsCatalog().then((c) => setCategories(c.categories || [])).catch(console.error);
    api
      .projectGenerationToolsStatus(project.id)
      .then((s) => {
        const map: Record<string, any> = {};
        for (const t of s.tools || []) map[t.id] = t;
        setStatusMap(map);
      })
      .catch(console.error);
  }, [project.id]);

  const run = async () => {
    if (!selected?.id || selected.navTab) return;
    setBusy(true);
    setMsg("");
    try {
      const res = await api.runGenerationTool(project.id, {
        toolId: selected.id,
        sourceAssetId: sourceAssetId || undefined,
        prompt,
        documentType,
        keyColor,
        confirmPaidCloud: false,
      });
      setMsg(
        res.disclosure
          ? `${res.ok === false ? "Blocked" : "OK"} — ${res.disclosure}${res.assetId ? ` · asset ${res.assetId}` : ""}${res.jobId ? ` · job ${res.jobId}` : ""}`
          : JSON.stringify(res),
      );
      await onChange?.();
    } catch (e) {
      setMsg(e instanceof Error ? e.message : "Tool failed");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="page ds-surface" data-testid="generation-tools-hub">
      <PanelHeading
        title="Generation Tools"
        tip="Task-first tools: Create, Enhance, Remove and Replace, Extend and Reframe, Finish. Model names stay in Advanced details. All tools are non-destructive and local by default."
      />
      <p className="muted" data-testid="generation-tools-disclosure">
        Local providers by default. Paid cloud is never submitted silently. Originals are preserved; outputs are new
        project assets with lineage.
      </p>

      <div className="generation-tools-grid" style={{ display: "grid", gridTemplateColumns: "240px 1fr", gap: "1rem" }}>
        <div>
          {categories.map((cat) => (
            <div key={cat.id} style={{ marginBottom: "1rem" }}>
              <h3 style={{ fontSize: "0.85rem", margin: "0 0 0.4rem" }}>{cat.label}</h3>
              <ul style={{ listStyle: "none", padding: 0, margin: 0, display: "grid", gap: "0.35rem" }}>
                {cat.tools.map((t) => {
                  const st = statusMap[t.id];
                  return (
                    <li key={t.id}>
                      <button
                        type="button"
                        className={selected?.id === t.id ? "primary" : "ghost"}
                        data-testid={`gen-tool-${t.id.replace(/\./g, "-")}`}
                        style={{ width: "100%", textAlign: "left" }}
                        onClick={() => {
                          if (t.navTab) {
                            onGo(t.navTab);
                            return;
                          }
                          setSelected(t);
                        }}
                      >
                        {t.label}
                        {st?.status ? (
                          <StatusBadge
                            kind={mapGenerationToolStatus(st.status)}
                            label={st.status}
                            compact
                            style={{ display: "inline-flex", marginTop: "0.35rem", fontSize: "0.72rem" }}
                          />
                        ) : null}
                      </button>
                    </li>
                  );
                })}
              </ul>
            </div>
          ))}
        </div>

        <div className="panel" data-testid="generation-tool-detail">
          {!selected ? (
            <p className="muted">Select a tool. Labels describe the filmmaking task — open Advanced for model names.</p>
          ) : (
            <>
              <h2 style={{ marginTop: 0 }}>{selected.label}</h2>
              <p>{selected.description}</p>
              <details>
                <summary>Advanced · providers & models</summary>
                <p className="muted">{selected.providerHint || statusMap[selected.id]?.provider || "—"}</p>
                {selected.blocked || statusMap[selected.id]?.status === "BLOCKED" ? (
                  <p role="alert">{selected.blockedReason || statusMap[selected.id]?.remediation}</p>
                ) : null}
                {statusMap[selected.id]?.honesty ? <p>{statusMap[selected.id].honesty}</p> : null}
              </details>

              {(selected.inputs || []).includes("sourceAssetId") && (
                <label style={{ display: "block", marginTop: "0.75rem" }}>
                  Source asset (preserved)
                  <select
                    value={sourceAssetId}
                    onChange={(e) => setSourceAssetId(e.target.value)}
                    data-testid="gen-tool-source-asset"
                  >
                    <option value="">Select…</option>
                    {assets.map((a) => (
                      <option key={a.id} value={a.id}>
                        {a.tag || a.filename} ({a.kind})
                      </option>
                    ))}
                  </select>
                </label>
              )}

              {selected.id === "image.chroma_key" && (
                <label style={{ display: "block", marginTop: "0.5rem" }}>
                  Key color
                  <select value={keyColor} onChange={(e) => setKeyColor(e.target.value)}>
                    <option value="green">Green</option>
                    <option value="blue">Blue</option>
                  </select>
                </label>
              )}

              {selected.id === "scriptwriter" && (
                <label style={{ display: "block", marginTop: "0.5rem" }}>
                  Document type
                  <select value={documentType} onChange={(e) => setDocumentType(e.target.value)} data-testid="scriptwriter-doc-type">
                    {[
                      "treatment",
                      "outline",
                      "beat_sheet",
                      "scene",
                      "screenplay",
                      "dialogue_revision",
                      "storyboard_brief",
                      "shot_breakdown",
                      "commercial",
                      "trailer",
                      "social_video",
                    ].map((d) => (
                      <option key={d} value={d}>
                        {d}
                      </option>
                    ))}
                  </select>
                </label>
              )}

              <label style={{ display: "block", marginTop: "0.5rem" }}>
                Brief / prompt
                <textarea
                  rows={3}
                  value={prompt}
                  onChange={(e) => setPrompt(e.target.value)}
                  placeholder="Describe the outcome…"
                  data-testid="gen-tool-prompt"
                />
              </label>

              <div className="row-actions" style={{ marginTop: "0.75rem" }}>
                <Button
                  variant="primary"
                  disabled={busy || selected.blocked || statusMap[selected.id]?.status === "BLOCKED"}
                  onClick={() => void run()}
                  data-testid="gen-tool-run"
                >
                  {busy ? "Working…" : "Run (local)"}
                </Button>
                {selected.id === "scriptwriter" && (
                  <Button variant="ghost" onClick={() => onGo("scriptwriter")}>
                    Open Scriptwriter workspace
                  </Button>
                )}
                {selected.id === "brand.studio" && (
                  <Button variant="ghost" onClick={() => onGo("brandstudio")}>
                    Open Brand Studio
                  </Button>
                )}
                {(selected.id.startsWith("audio.") || selected.id.includes("music") || selected.id.includes("sfx")) && (
                  <Button variant="ghost" onClick={() => onGo("audiostudio")}>
                    Open Audio Studio
                  </Button>
                )}
              </div>
              {msg && (
                <p className="pill" data-testid="gen-tool-result">
                  {msg}
                </p>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  );
}
