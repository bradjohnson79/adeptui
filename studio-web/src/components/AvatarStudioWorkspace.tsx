import { useEffect, useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { api } from "../api";
import type { Project } from "../types";
import type { EditorTab } from "../workspacePrefs";
import {
  AVATAR_MODES,
  AVATAR_PRESETS,
  buildAvatarPrompt,
  emptyAvatarSession,
  emptyLook,
  emptyPerformance,
  estimateDialogueSeconds,
  validateAvatarSession,
  type AvatarMode,
  type AvatarSession,
  type PerformanceTone,
} from "../avatar/types";

type ProfileItem = { id: string; name: string; kind: string; media_path?: string; tag?: string };

/**
 * Avatar Studio — talking characters as film performances.
 * Profile → Look → Voice/audio → Performance → Lip Sync → Clip → Director
 */
export function AvatarStudioWorkspace({
  project,
  onChange,
  onGo,
}: {
  project: Project;
  onChange?: () => Promise<void>;
  onGo: (tab: EditorTab) => void;
}) {
  const [params] = useSearchParams();
  const [sessions, setSessions] = useState<AvatarSession[]>([]);
  const [session, setSession] = useState<AvatarSession | null>(null);
  const [characters, setCharacters] = useState<ProfileItem[]>([]);
  const [voices, setVoices] = useState<ProfileItem[]>([]);
  const [audioAssets, setAudioAssets] = useState<any[]>([]);
  const [videoAssets, setVideoAssets] = useState<any[]>([]);
  const [imageAssets, setImageAssets] = useState<any[]>([]);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState("");
  const [issues, setIssues] = useState<{ level: string; text: string }[]>([]);
  const [tab, setTab] = useState<"script" | "voice" | "motion" | "lipsync" | "preview" | "generate">("script");
  const [jobId, setJobId] = useState<string | null>(null);

  const loadLists = async () => {
    const [chars, vox, lib, list] = await Promise.all([
      api.listProfiles("character").catch(() => []),
      api.listProfiles("voice").catch(() => []),
      api.library(project.id).catch(() => []),
      api.listAvatarSessions(project.id).catch(() => []),
    ]);
    setCharacters(chars || []);
    setVoices(vox || []);
    const assets = lib || [];
    setAudioAssets(assets.filter((a: any) => a.kind === "audio"));
    setVideoAssets(assets.filter((a: any) => a.kind === "video"));
    setImageAssets(assets.filter((a: any) => a.kind === "image"));
    setSessions(list || []);
    return list as AvatarSession[];
  };

  useEffect(() => {
    (async () => {
      const list = await loadLists();
      let profileQ = params.get("profile");
      if (!profileQ) {
        try {
          profileQ = sessionStorage.getItem("adept_avatar_profile");
          if (profileQ) sessionStorage.removeItem("adept_avatar_profile");
        } catch {
          /* ignore */
        }
      }
      if (list?.length) {
        let pick = list[0];
        if (profileQ) {
          const hit = list.find((s) => s.character_profile_id === profileQ);
          if (hit) pick = hit;
        }
        setSession(pick);
      } else {
        const boot = emptyAvatarSession(project.id, "New Avatar Session");
        if (profileQ) {
          boot.character_profile_id = profileQ;
          const chars = await api.listProfiles("character").catch(() => []);
          const c = (chars || []).find((x: any) => x.id === profileQ);
          if (c) boot.character_name = c.name;
        }
        const created = await api.createAvatarSession(project.id, {
          name: boot.name,
          character_profile_id: boot.character_profile_id || undefined,
          character_name: boot.character_name,
          mode: boot.mode,
          bootstrap: boot,
        });
        setSession(created);
        setSessions([created]);
      }
    })().catch(console.error);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [project.id]);

  const dur = useMemo(
    () => estimateDialogueSeconds(session?.dialogue_spoken || session?.dialogue_original || ""),
    [session?.dialogue_spoken, session?.dialogue_original]
  );

  const save = async (next: AvatarSession) => {
    setBusy(true);
    try {
      const prompts = buildAvatarPrompt(next);
      const payload = {
        ...next,
        prompt: next.prompt || prompts.prompt,
        negative_prompt: next.negative_prompt || prompts.negative_prompt,
      };
      const saved = await api.patchAvatarSession(project.id, next.id, payload);
      setSession(saved);
      setSessions((prev) => prev.map((s) => (s.id === saved.id ? saved : s)));
      await onChange?.();
    } finally {
      setBusy(false);
    }
  };

  const patch = (p: Partial<AvatarSession>) => {
    if (!session) return;
    const next = { ...session, ...p, updated_at: new Date().toISOString() };
    setSession(next);
  };

  const createNew = async () => {
    setBusy(true);
    try {
      const created = await api.createAvatarSession(project.id, { name: `Avatar ${sessions.length + 1}` });
      setSession(created);
      setSessions((prev) => [created, ...prev]);
    } finally {
      setBusy(false);
    }
  };

  const runValidate = async () => {
    if (!session) return;
    await save(session);
    const res = await api.validateAvatarSession(project.id, session.id);
    setIssues(res.issues || validateAvatarSession(session));
    setMsg(res.ok ? "Validation passed (warnings may remain)." : "Validation found blocking issues.");
  };

  const uploadAudio = async (file: File | null) => {
    if (!file || !session) return;
    setBusy(true);
    try {
      const asset = (await api.uploadAsset(project.id, file, `avatar-voice-${session.character_name || "line"}`, "audio")) as {
        id: string;
      };
      const next = {
        ...session,
        voice: { ...session.voice, audio_asset_id: asset.id, provider: "upload" },
      };
      await save(next);
      await loadLists();
      setMsg("Audio attached.");
    } catch (e) {
      setMsg(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  };

  const createVoiceProfile = async () => {
    if (!session) return;
    const name = window.prompt("Voice profile name", `${session.character_name || "Character"} Voice`);
    if (!name) return;
    await api.createProfile("voice", {
      name,
      description: session.voice.pronunciation_notes || "",
      data: session.voice,
    } as any);
    await loadLists();
    setMsg("Voice Profile saved.");
  };

  const generateStill = async () => {
    if (!session) return;
    setBusy(true);
    setMsg("Queuing ImageGen…");
    try {
      const { prompt, negative_prompt } = buildAvatarPrompt(session);
      const job = await api.imagegen(project.id, {
        prompt,
        negative_prompt,
        aspect: session.camera.aspect || session.look.aspect || "16:9",
      });
      setJobId(job.id);
      setMsg(`ImageGen queued (${job.id.slice(0, 8)}…).`);
      await pollJob(job.id, async (done) => {
        if (done.output_path || (done as any).asset_id) {
          const assetId = (done as any).asset_id;
          if (assetId) {
            await save({ ...session, source_still_asset_id: assetId, prompt, negative_prompt });
            setMsg("Still ready — continue to video or lip sync.");
          }
        }
      });
    } catch (e) {
      setMsg(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  };

  const generateVideo = async () => {
    if (!session) return;
    if (session.mode === "existing_video_lipsync") {
      setTab("lipsync");
      setMsg("Source video mode — prepare mouth mask, then apply lip sync in Director.");
      return;
    }
    setBusy(true);
    setMsg("Queuing Txt2Vid…");
    try {
      const { prompt, negative_prompt } = buildAvatarPrompt(session);
      const job = await api.txt2vid(project.id, {
        prompt,
        negative_prompt,
        aspect: session.camera.aspect || "16:9",
        duration_sec: Math.min(8, Math.max(3, dur || 4)),
        start_asset_id: session.source_still_asset_id || undefined,
      });
      setJobId(job.id);
      setMsg(`Video job queued (${job.id.slice(0, 8)}…).`);
      await pollJob(job.id, async (done) => {
        const assetId = (done as any).asset_id;
        if (assetId || done.output_path) {
          const take = await api.addAvatarTake(project.id, session.id, {
            asset_id: assetId,
            label: `Take ${(session.takes?.length || 0) + 1}`,
            status: "preview",
            performance_note: session.performance.tone,
          });
          const refreshed = await api.getAvatarSession(project.id, session.id);
          setSession(refreshed);
          setMsg(`Take registered: ${take.label}. Prepare mouth mask next.`);
          setTab("lipsync");
        }
      });
    } catch (e) {
      setMsg(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  };

  const pollJob = async (id: string, onDone: (j: any) => Promise<void>) => {
    for (let i = 0; i < 90; i++) {
      await new Promise((r) => setTimeout(r, 2000));
      try {
        const j = await api.getJob(id);
        if (j.status === "done") {
          await onDone(j);
          return;
        }
        if (j.status === "failed") {
          setMsg(j.message || "Job failed");
          return;
        }
      } catch {
        /* keep polling */
      }
    }
    setMsg("Job still running — check Jobs panel.");
  };

  const markMouthMask = async () => {
    if (!session) return;
    await save({ ...session, mouth_mask: { ...session.mouth_mask, placed: true } });
    setMsg("Mouth mask marked confirmed. Apply lip sync from Director when ready.");
  };

  const sendTakeToDirector = async (takeId: string) => {
    if (!session) return;
    const take = session.takes.find((t) => t.id === takeId);
    if (!take?.asset_id) {
      setMsg("Take has no asset yet.");
      return;
    }
    setBusy(true);
    try {
      await api.promote(project.id, { asset_id: take.asset_id, target: "scene_new", name: `${session.character_name || "Avatar"} — ${take.label}` });
      await api.addAvatarTake(project.id, session.id, {
        asset_id: take.asset_id ?? undefined,
        scene_id: take.scene_id ?? undefined,
        approved: true,
        status: "final",
        label: take.label,
        performance_note: take.performance_note,
        favorite: take.favorite,
      });
      setMsg("Sent to Director as new scene.");
      onGo("director");
    } catch (e) {
      setMsg(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  };

  const applyPreset = (presetId: string) => {
    if (!session) return;
    const preset = AVATAR_PRESETS.find((p) => p.id === presetId);
    if (!preset) return;
    const next: AvatarSession = {
      ...session,
      preset_id: presetId,
      background_mode: preset.background_mode || session.background_mode,
      camera: preset.camera || session.camera,
      look: {
        ...session.look,
        framing: preset.camera?.shot_size || session.look.framing,
        lens: preset.camera?.lens || session.look.lens,
        camera_angle: preset.camera?.angle || session.look.camera_angle,
      },
    };
    setSession(next);
  };

  if (!session) {
    return (
      <div className="page">
        <p className="empty">Loading Avatar Studio…</p>
      </div>
    );
  }

  const previewSrc =
    (session.source_still_asset_id && api.assetUrl(session.source_still_asset_id)) ||
    (session.takes.find((t) => t.asset_id)?.asset_id && api.assetUrl(session.takes.find((t) => t.asset_id)!.asset_id!)) ||
    null;

  return (
    <div className="page avatar-studio">
      <header className="avatar-studio-head">
        <div>
          <p className="eyebrow">Avatar Studio</p>
          <h1>
            {session.character_name || "Character"}{" "}
            <span className="muted" style={{ fontSize: "0.85rem", fontWeight: 400 }}>
              · {session.name}
            </span>
          </h1>
          <p className="muted">Character → Appearance → Voice → Performance → Lip Sync → Director</p>
        </div>
        <div className="row" style={{ flexWrap: "wrap", gap: "0.4rem" }}>
          <select
            aria-label="Avatar session"
            value={session.id}
            onChange={async (e) => {
              const s = await api.getAvatarSession(project.id, e.target.value);
              setSession(s);
            }}
          >
            {sessions.map((s) => (
              <option key={s.id} value={s.id}>
                {s.name}
              </option>
            ))}
          </select>
          <button type="button" onClick={createNew} disabled={busy}>
            New Session
          </button>
          <button type="button" className="primary" onClick={() => save(session)} disabled={busy}>
            Save
          </button>
        </div>
      </header>

      <div className="type-chips" role="listbox" aria-label="Avatar mode">
        {AVATAR_MODES.map((m) => (
          <button
            key={m.id}
            type="button"
            role="option"
            aria-selected={session.mode === m.id}
            className={session.mode === m.id ? "primary" : ""}
            title={m.blurb}
            onClick={() => patch({ mode: m.id as AvatarMode })}
          >
            {m.label}
          </button>
        ))}
      </div>

      <div className="avatar-layout">
        <section className="dash-card avatar-preview-pane">
          <p className="eyebrow">Avatar Preview</p>
          <div className={`cinematic-media motif-imagegen avatar-preview-media`}>
            <div className="cinematic-media-fallback" aria-hidden="true" />
            {previewSrc && (
              <img
                src={previewSrc}
                alt={`${session.character_name || "Avatar"} preview`}
                onError={(e) => {
                  (e.currentTarget as HTMLImageElement).style.display = "none";
                }}
              />
            )}
            <div className="cinematic-media-overlay" />
            <span className="hero-media-caption">
              {session.camera.shot_size} · {session.performance.tone}
            </span>
          </div>
          {msg && <p className="pill" style={{ marginTop: "0.75rem" }}>{msg}</p>}
          {jobId && <p className="scene-meta">Last job: {jobId}</p>}
        </section>

        <aside className="dash-card avatar-inspector">
          <p className="eyebrow">Avatar Inspector</p>

          <div className="field">
            <label>Character Profile</label>
            <select
              value={session.character_profile_id || ""}
              onChange={(e) => {
                const id = e.target.value || null;
                const c = characters.find((x) => x.id === id);
                patch({ character_profile_id: id, character_name: c?.name || session.character_name });
              }}
            >
              <option value="">— Select —</option>
              {characters.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.name}
                </option>
              ))}
            </select>
          </div>
          <div className="field">
            <label>Display name</label>
            <input value={session.character_name} onChange={(e) => patch({ character_name: e.target.value })} />
          </div>
          <label className="row" style={{ gap: "0.5rem", alignItems: "center" }}>
            <input
              type="checkbox"
              checked={session.continuity_lock}
              onChange={(e) => patch({ continuity_lock: e.target.checked })}
            />
            Continuity lock
          </label>

          <div className="field">
            <label>Look name</label>
            <input
              value={session.look.name}
              onChange={(e) => patch({ look: { ...session.look, name: e.target.value } })}
            />
          </div>
          <div className="gen-grid">
            <div className="field">
              <label>Wardrobe</label>
              <input
                value={session.look.wardrobe}
                onChange={(e) => patch({ look: { ...session.look, wardrobe: e.target.value } })}
              />
            </div>
            <div className="field">
              <label>Expression</label>
              <input
                value={session.look.expression}
                onChange={(e) => patch({ look: { ...session.look, expression: e.target.value } })}
              />
            </div>
          </div>

          <div className="field">
            <label>Voice Profile</label>
            <select
              value={session.voice.profile_id || ""}
              onChange={(e) => patch({ voice: { ...session.voice, profile_id: e.target.value || null } })}
            >
              <option value="">— Optional —</option>
              {voices.map((v) => (
                <option key={v.id} value={v.id}>
                  {v.name}
                </option>
              ))}
            </select>
          </div>
          <div className="field">
            <label>Dialogue audio (required for lip sync)</label>
            <select
              value={session.voice.audio_asset_id || ""}
              onChange={(e) => patch({ voice: { ...session.voice, audio_asset_id: e.target.value || null } })}
            >
              <option value="">— Select audio —</option>
              {audioAssets.map((a) => (
                <option key={a.id} value={a.id}>
                  {a.tag || a.filename}
                </option>
              ))}
            </select>
            <input
              type="file"
              accept="audio/*"
              style={{ marginTop: "0.35rem" }}
              onChange={(e) => uploadAudio(e.target.files?.[0] || null)}
            />
            <button type="button" className="ghost" style={{ marginTop: "0.35rem" }} onClick={createVoiceProfile}>
              Save as Voice Profile
            </button>
          </div>

          <div className="field">
            <label>Dialogue (original script — never silently changed)</label>
            <textarea
              rows={2}
              value={session.dialogue_original}
              onChange={(e) => patch({ dialogue_original: e.target.value })}
              placeholder="BARNES&#10;Now you have me curious, Doctor."
            />
          </div>
          <div className="field">
            <label>Spoken adaptation</label>
            <textarea
              rows={2}
              value={session.dialogue_spoken}
              onChange={(e) => patch({ dialogue_spoken: e.target.value })}
              placeholder="Optional performance rewrite"
            />
            <div className="row" style={{ marginTop: "0.35rem", gap: "0.35rem" }}>
              <button
                type="button"
                onClick={() =>
                  patch({
                    dialogue_spoken: session.dialogue_spoken || session.dialogue_original,
                    dialogue_adaptation_accepted: true,
                  })
                }
              >
                Accept
              </button>
              <button type="button" onClick={() => patch({ dialogue_spoken: "", dialogue_adaptation_accepted: false })}>
                Reject
              </button>
              <span className="scene-meta">~{dur}s</span>
            </div>
          </div>

          <div className="field">
            <label>Performance tone</label>
            <select
              value={session.performance.tone}
              onChange={(e) =>
                patch({ performance: { ...session.performance, tone: e.target.value as PerformanceTone } })
              }
            >
              {(
                [
                  "calm",
                  "friendly",
                  "serious",
                  "excited",
                  "suspicious",
                  "angry",
                  "sad",
                  "confident",
                  "nervous",
                  "restrained",
                  "custom",
                ] as PerformanceTone[]
              ).map((t) => (
                <option key={t} value={t}>
                  {t}
                </option>
              ))}
            </select>
          </div>
          <div className="gen-grid">
            <div className="field">
              <label>Eye line</label>
              <input
                value={session.performance.eye_contact}
                onChange={(e) => patch({ performance: { ...session.performance, eye_contact: e.target.value } })}
              />
            </div>
            <div className="field">
              <label>Gesture intensity</label>
              <input
                value={session.performance.gesture_intensity}
                onChange={(e) =>
                  patch({ performance: { ...session.performance, gesture_intensity: e.target.value } })
                }
              />
            </div>
          </div>

          <div className="field">
            <label>Background mode</label>
            <select value={session.background_mode} onChange={(e) => patch({ background_mode: e.target.value })}>
              {["solid", "transparent", "uploaded", "environment", "generated", "master_sheet", "spatial", "video"].map(
                (b) => (
                  <option key={b} value={b}>
                    {b}
                  </option>
                )
              )}
            </select>
          </div>
          <div className="field">
            <label>Background notes</label>
            <input value={session.background_notes} onChange={(e) => patch({ background_notes: e.target.value })} />
          </div>

          {session.mode === "existing_video_lipsync" && (
            <div className="field">
              <label>Source video</label>
              <select
                value={session.source_video_asset_id || ""}
                onChange={(e) => patch({ source_video_asset_id: e.target.value || null })}
              >
                <option value="">— Select —</option>
                {videoAssets.map((a) => (
                  <option key={a.id} value={a.id}>
                    {a.tag || a.filename}
                  </option>
                ))}
              </select>
            </div>
          )}

          <div className="field">
            <label>Source still (optional)</label>
            <select
              value={session.source_still_asset_id || ""}
              onChange={(e) => patch({ source_still_asset_id: e.target.value || null })}
            >
              <option value="">— Select —</option>
              {imageAssets.map((a) => (
                <option key={a.id} value={a.id}>
                  {a.tag || a.filename}
                </option>
              ))}
            </select>
          </div>

          <div className="field">
            <label>Preset</label>
            <select value={session.preset_id || ""} onChange={(e) => applyPreset(e.target.value)}>
              <option value="">— Apply preset —</option>
              {AVATAR_PRESETS.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.label}
                </option>
              ))}
            </select>
          </div>

          <p className="eyebrow" style={{ marginTop: "1rem" }}>
            Lip Sync
          </p>
          <p className="scene-meta">
            Method: {session.lip_sync_method} · Mask: {session.mouth_mask.placed ? "confirmed" : "needs user"}
          </p>
          <div className="row" style={{ gap: "0.35rem", flexWrap: "wrap" }}>
            <button
              type="button"
              onClick={() => {
                onGo("director");
                setMsg("Place the black rectangle over the mouth in Director Lip Sync, then return and confirm.");
              }}
            >
              Open Lip Sync (Director)
            </button>
            <button type="button" onClick={markMouthMask}>
              Confirm mouth mask
            </button>
          </div>
        </aside>
      </div>

      <nav className="avatar-tool-tabs" role="tablist" aria-label="Avatar tools">
        {(["script", "voice", "motion", "lipsync", "preview", "generate"] as const).map((t) => (
          <button key={t} type="button" role="tab" aria-selected={tab === t} className={tab === t ? "primary" : ""} onClick={() => setTab(t)}>
            {t === "lipsync" ? "Lip Sync" : t[0].toUpperCase() + t.slice(1)}
          </button>
        ))}
      </nav>

      <section className="dash-card avatar-tool-panel">
        {tab === "script" && (
          <>
            <h2>Script</h2>
            <p className="muted">Original dialogue is preserved. Spoken adaptation is optional performance rewrite.</p>
            <button type="button" onClick={() => onGo("script")}>
              Open Script / Storyboard
            </button>
          </>
        )}
        {tab === "voice" && (
          <>
            <h2>Voice</h2>
            <p className="muted">TTS providers are stored as metadata; execute path is uploaded audio this pass.</p>
            <div className="gen-grid">
              <div className="field">
                <label>Provider</label>
                <input
                  value={session.voice.provider}
                  onChange={(e) => patch({ voice: { ...session.voice, provider: e.target.value } })}
                />
              </div>
              <div className="field">
                <label>Language</label>
                <input
                  value={session.voice.language}
                  onChange={(e) => patch({ voice: { ...session.voice, language: e.target.value } })}
                />
              </div>
            </div>
          </>
        )}
        {tab === "motion" && (
          <>
            <h2>Motion & Camera</h2>
            <div className="gen-grid">
              {(["shot_size", "lens", "height", "angle", "movement", "aspect"] as const).map((k) => (
                <div className="field" key={k}>
                  <label>{k.replace("_", " ")}</label>
                  <input
                    value={session.camera[k]}
                    onChange={(e) => patch({ camera: { ...session.camera, [k]: e.target.value } })}
                  />
                </div>
              ))}
            </div>
          </>
        )}
        {tab === "lipsync" && (
          <>
            <h2>Lip Sync checkpoint</h2>
            <p className="muted">
              Place the black rectangle over the character’s mouth in Director, then select Continue / Confirm here.
            </p>
            <div className="row" style={{ gap: "0.5rem", flexWrap: "wrap" }}>
              <button type="button" className="primary" onClick={() => onGo("director")}>
                Prepare mouth mask
              </button>
              <button type="button" onClick={markMouthMask}>
                Continue — mask confirmed
              </button>
            </div>
          </>
        )}
        {tab === "preview" && (
          <>
            <h2>Takes</h2>
            {!session.takes.length ? (
              <p className="empty">No takes yet — Generate a clip first.</p>
            ) : (
              <ul className="home-list">
                {session.takes.map((t) => (
                  <li key={t.id}>
                    {t.label} · {t.status}
                    {t.performance_note ? ` · ${t.performance_note}` : ""}
                    <button type="button" style={{ marginLeft: 8 }} onClick={() => sendTakeToDirector(t.id)}>
                      Send to Director
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </>
        )}
        {tab === "generate" && (
          <>
            <h2>Generate</h2>
            <div className="row" style={{ gap: "0.5rem", flexWrap: "wrap", marginBottom: "0.75rem" }}>
              <button type="button" onClick={runValidate} disabled={busy}>
                Validate
              </button>
              <button type="button" onClick={generateStill} disabled={busy}>
                Generate still
              </button>
              <button type="button" className="primary" onClick={generateVideo} disabled={busy}>
                {session.mode === "existing_video_lipsync" ? "Skip to lip sync prep" : "Generate video"}
              </button>
              <button type="button" onClick={() => save({ ...session, look: emptyLook(session.look.name) })}>
                Reset look
              </button>
              <button
                type="button"
                onClick={() => save({ ...session, performance: emptyPerformance() })}
              >
                Reset performance
              </button>
            </div>
            {!!issues.length && (
              <ul className="health-list">
                {issues.map((i, idx) => (
                  <li key={idx}>
                    <span className={`status-badge ${i.level === "bad" ? "bad" : i.level === "warn" ? "warn" : "ok"}`}>
                      {i.level}
                    </span>{" "}
                    {i.text}
                  </li>
                ))}
              </ul>
            )}
            <div className="field">
              <label>Prompt</label>
              <textarea rows={3} value={session.prompt || buildAvatarPrompt(session).prompt} onChange={(e) => patch({ prompt: e.target.value })} />
            </div>
            <div className="field">
              <label>Negative</label>
              <textarea rows={2} value={session.negative_prompt} onChange={(e) => patch({ negative_prompt: e.target.value })} />
            </div>
          </>
        )}
      </section>
    </div>
  );
}
