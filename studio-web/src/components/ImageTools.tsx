import { useMemo, useState } from "react";
import type { Asset, Project } from "../types";
import { api } from "../api";
import { PanelHeading } from "./HelpTip";

export function ImageToolsPanel({ project, onChange }: { project: Project; onChange: () => void }) {
  const images = useMemo(() => project.assets.filter((a) => a.kind === "image"), [project.assets]);
  const [sheetSource, setSheetSource] = useState(images[0]?.id || "");
  const [angleSource, setAngleSource] = useState(images[0]?.id || "");
  const [charName, setCharName] = useState("hero");
  const [extraSheet, setExtraSheet] = useState("");
  const [extraAngle, setExtraAngle] = useState("");
  const [busy, setBusy] = useState<string | null>(null)

  const sourcePreview = (id: string) => images.find((a) => a.id === id);

  const runSheet = async () => {
    if (!sheetSource) return;
    setBusy("sheet");
    try {
      await api.characterSheet(project.id, {
        source_asset_id: sheetSource,
        character_name: charName,
        extra_prompt: extraSheet,
      });
      onChange();
    } finally {
      setBusy(null);
    }
  };

  const runAngles = async () => {
    if (!angleSource) return;
    setBusy("angles");
    try {
      await api.multiAngle(project.id, {
        source_asset_id: angleSource,
        character_name: charName || "shot",
        extra_prompt: extraAngle,
      });
      onChange();
    } finally {
      setBusy(null);
    }
  };

  const sheetResults = images.filter((a) => a.tag.startsWith(`${charName}_`) && /front|side|back|closeup/.test(a.tag));
  const angleResults = images.filter((a) => a.tag.includes("_angle_"));

  return (
    <div className="page" style={{ width: "min(1100px, calc(100% - 2rem))" }}>
      <section className="hero" style={{ paddingTop: "1rem" }}>
        <h1 style={{ fontSize: "2rem" }}>Consistency tools</h1>
        <p>Build a character turnaround sheet, or generate matched camera angles from one still — powered by Z-Image Turbo with reference conditioning.</p>
      </section>

      <div className="grid-cards" style={{ gridTemplateColumns: "repeat(auto-fit, minmax(320px, 1fr))" }}>
        <div className="card">
          <PanelHeading
            title="Character sheet"
            tip="From one reference, generate front, side, back, and close-ups. Results become tagged Assets for @mentions."
            as="h3"
          />
          <p>Front, side, back, plus front & side close-ups. Results land in Assets as @{charName}_*</p>
          <div className="field" style={{ marginTop: "0.85rem" }}>
            <label>Character name (used for @tags)</label>
            <input value={charName} onChange={(e) => setCharName(e.target.value)} placeholder="hero" />
          </div>
          <div className="field">
            <label>Reference image</label>
            <select value={sheetSource} onChange={(e) => setSheetSource(e.target.value)}>
              <option value="">Select asset…</option>
              {images.map((a: Asset) => (
                <option key={a.id} value={a.id}>
                  @{a.tag || a.filename}
                </option>
              ))}
            </select>
          </div>
          {sourcePreview(sheetSource) && (
            <img
              src={api.assetUrl(sheetSource)}
              alt="ref"
              style={{ width: "100%", maxHeight: 180, objectFit: "cover", borderRadius: 12, marginBottom: 8 }}
            />
          )}
          <div className="field">
            <label>Extra style notes (optional)</label>
            <textarea value={extraSheet} onChange={(e) => setExtraSheet(e.target.value)} placeholder="cinematic costume, soft key light" />
          </div>
          <button className="primary" disabled={!sheetSource || busy !== null} onClick={runSheet}>
            {busy === "sheet" ? "Queuing…" : "Generate character sheet (5 views)"}
          </button>
          {sheetResults.length > 0 && (
            <div className="kf-row" style={{ marginTop: 12 }}>
              {sheetResults.slice(0, 5).map((a) => (
                <div className="kf" key={a.id}>
                  <span className="badge">@{a.tag}</span>
                  <img src={api.assetUrl(a.id)} alt={a.tag} />
                </div>
              ))}
            </div>
          )}
        </div>

        <div className="card">
          <PanelHeading
            title="Multi-angle camera"
            tip="From one still, create three matching camera angles with character and background continuity."
            as="h3"
          />
          <p>From one shot, generate 3 new angles with matching character + background continuity.</p>
          <div className="field" style={{ marginTop: "0.85rem" }}>
            <label>Source camera shot</label>
            <select value={angleSource} onChange={(e) => setAngleSource(e.target.value)}>
              <option value="">Select asset…</option>
              {images.map((a: Asset) => (
                <option key={a.id} value={a.id}>
                  @{a.tag || a.filename}
                </option>
              ))}
            </select>
          </div>
          {sourcePreview(angleSource) && (
            <img
              src={api.assetUrl(angleSource)}
              alt="shot"
              style={{ width: "100%", maxHeight: 180, objectFit: "cover", borderRadius: 12, marginBottom: 8 }}
            />
          )}
          <div className="field">
            <label>Extra continuity notes (optional)</label>
            <textarea value={extraAngle} onChange={(e) => setExtraAngle(e.target.value)} placeholder="keep window on left, same wardrobe" />
          </div>
          <button className="primary" disabled={!angleSource || busy !== null} onClick={runAngles}>
            {busy === "angles" ? "Queuing…" : "Generate 3 camera angles"}
          </button>
          {angleResults.length > 0 && (
            <div className="kf-row" style={{ marginTop: 12 }}>
              {angleResults.slice(0, 3).map((a) => (
                <div className="kf" key={a.id}>
                  <span className="badge">@{a.tag}</span>
                  <img src={api.assetUrl(a.id)} alt={a.tag} />
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      <p className="scene-meta" style={{ marginTop: "1rem" }}>
        Tip: watch the Render queue while jobs run. New images appear in Assets automatically — use them as Start/Middle/End frames or @tags in prompts.
      </p>
    </div>
  );
}
