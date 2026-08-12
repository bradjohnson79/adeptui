import { api } from "../api";
import { buildHomeCreateProjectPath } from "../projectEntry";
import {
  appendAudit,
  getAction,
  markAskedOnce,
  needsConfirmation,
  type ActionDef,
  type PlannedStep,
} from "./types";

export type ExecuteContext = {
  projectId?: string;
  sceneId?: string;
  navigate?: (path: string) => void;
  goTab?: (tab: string) => void;
  confirm?: (message: string) => boolean;
  onRefresh?: () => Promise<void>;
};

async function assetFirst(projectId: string | undefined, q: string) {
  if (!projectId) return [];
  try {
    const entityMatch = /(?:find|search|locate|get)\s+(?:(character|prop|scene)\s+)?(.+)/i.exec(q);
    const searchQuery = entityMatch?.[2]?.trim() || q;
    const res = await api.library(projectId, { q: searchQuery });
    return (res.items || []).slice(0, 6).map((a: any) => ({
      id: a.id,
      tag: a.tag || a.filename || "asset",
      kind: a.kind || "file",
      libraryPath: a.libraryPath,
    }));
  } catch {
    return [];
  }
}

function looksLikeLibraryPath(q: string): boolean {
  return q.includes("/") || /^put (?:this|it) in /i.test(q) || /^store (?:this|it) in /i.test(q);
}

export async function executeAction(
  actionId: string,
  inputs: Record<string, unknown>,
  ctx: ExecuteContext
): Promise<{ ok: boolean; result?: unknown; error?: string; reuseAssets?: PlannedStep["reuseAssets"] }> {
  const def = getAction(actionId);
  if (!def) return { ok: false, error: `Unknown action: ${actionId}` };

  if (def.category === "destructive" || needsConfirmation(def)) {
    const ok = ctx.confirm?.(
      def.category === "destructive"
        ? `Confirm destructive action: ${def.label}?`
        : `Allow Co-Director to ${def.label}?`
    );
    if (ok === false) {
      appendAudit({ actionId, label: def.label, ok: false, detail: "User declined" });
      return { ok: false, error: "Declined by permission policy" };
    }
    if (ok) markAskedOnce(def.category);
  }

  try {
    const result = await run(def, inputs, ctx);
    appendAudit({ actionId, label: def.label, ok: true, detail: typeof result === "string" ? result : undefined });
    return result && typeof result === "object" && "reuseAssets" in (result as any)
      ? { ok: true, ...(result as any) }
      : { ok: true, result };
  } catch (e) {
    const msg = e instanceof Error ? e.message : String(e);
    appendAudit({ actionId, label: def.label, ok: false, detail: msg });
    return { ok: false, error: msg };
  }
}

async function run(def: ActionDef, inputs: Record<string, unknown>, ctx: ExecuteContext): Promise<unknown> {
  const projectId = String(inputs.projectId || ctx.projectId || "");
  const sceneId = String(inputs.sceneId || ctx.sceneId || "");

  switch (def.id) {
    case "createProject": {
      const suggestedName = String(inputs.name || "").trim() || undefined;
      const returnTo =
        typeof window !== "undefined"
          ? `${window.location.pathname}${window.location.search}${window.location.hash}`
          : undefined;
      ctx.navigate?.(
        buildHomeCreateProjectPath({
          suggestedName,
          pendingEntry: {
            kind: "co-director",
            returnTo,
          },
        }),
      );
      return {
        redirected: true,
        suggestedName: suggestedName || null,
      };
    }
    case "openProject": {
      ctx.navigate?.(`/project/${inputs.projectId}`);
      return { opened: inputs.projectId };
    }
    case "updateProjectSettings": {
      return api.updateProject(projectId, (inputs.patch || {}) as any);
    }
    case "duplicateProject":
      return api.duplicateProject(projectId);
    case "archiveProject":
      return api.archiveProject(projectId, true);
    case "createScene": {
      const body = { name: String(inputs.name || "Scene"), prompt: "", duration_sec: 5 };
      return api.addScene(projectId, body as any);
    }
    case "updateScene":
      return api.updateScene(projectId, sceneId, inputs.patch as any);
    case "goToWorkspace":
      ctx.goTab?.(String(inputs.tab || "home"));
      return { tab: inputs.tab };
    case "searchLibrary": {
      const q = String(inputs.q || "");
      if (looksLikeLibraryPath(q)) {
        const resolved = await api.libraryResolve(projectId, { query: q, path: q.includes("/") ? q : undefined });
        if (resolved?.ambiguous) {
          return { reuseAssets: [], count: 0, ambiguous: true, choices: resolved.candidates || [] };
        }
        if (resolved?.match?.libraryPath) {
          const scoped = await api.library(projectId, { q: "" });
          const folderId = resolved.match.folderId;
          const items = (scoped.items || []).filter((a: any) => a.canonicalFolderId === folderId).slice(0, 6);
          return { reuseAssets: items, count: items.length, resolvedFolder: resolved.match };
        }
      }
      const reuseAssets = await assetFirst(projectId, q);
      return { reuseAssets, count: reuseAssets.length };
    }
    case "resolveLibraryLocation": {
      const q = String(inputs.query || inputs.path || inputs.q || "");
      return api.libraryResolve(projectId, {
        query: q,
        path: inputs.path ? String(inputs.path) : undefined,
        systemKey: inputs.systemKey ? String(inputs.systemKey) : undefined,
      });
    }
    case "planLibraryStorage":
      return api.libraryPreflight(projectId, {
        task: String(inputs.task || "store_asset"),
        path: inputs.path,
        systemKey: inputs.systemKey,
        entityType: inputs.entityType,
        entityName: inputs.entityName,
        entityId: inputs.entityId,
        filenameHint: inputs.filenameHint || inputs.expectedName,
      });
    case "queueImageGeneration": {
      const reuseAssets = await assetFirst(projectId, String(inputs.prompt || "").slice(0, 24));
      const result = await api.imageProduct.generate(projectId, {
        prompt: String(inputs.prompt || ""),
        operation: "image.generate",
        purpose: String(inputs.purpose || ""),
      });
      const job = result.jobId ? await api.getJob(result.jobId) : result;
      return { job, reuseAssets };
    }
    case "queueVideoGeneration": {
      const reuseAssets = await assetFirst(projectId, "video");
      const job = await api.txt2vid(projectId, { prompt: String(inputs.prompt || "") });
      return { job, reuseAssets };
    }
    case "createMasterSheetFromScene":
    case "setSceneAuthority":
    case "validateMasterSheet":
    case "updateIngredient":
    case "renderIngredientsSheet":
    case "createSpatialFromMasterSheet":
    case "translateToSpatial":
    case "syncSpatialToMasterSheet": {
      if (def.id === "createMasterSheetFromScene") {
        const sheet = await api.getMasterSheet(projectId, sceneId).catch(() => null);
        if (sheet?.id) return sheet;
        return api.putMasterSheet(projectId, sceneId, { bootstrap: true });
      }
      if (def.id === "setSceneAuthority") {
        return api.setMasterSheetAuthority(projectId, sceneId, Boolean(inputs.approved ?? true));
      }
      if (def.id === "validateMasterSheet") {
        return api.validateMasterSheet(projectId, sceneId);
      }
      if (def.id === "updateIngredient") {
        const cur = await api.getMasterSheet(projectId, sceneId);
        return api.putMasterSheet(projectId, sceneId, {
          ...cur,
          patch_ingredient: { id: inputs.ingredientId, ...(inputs.patch as object) },
        });
      }
      if (def.id === "renderIngredientsSheet") {
        ctx.goTab?.("mastersheet");
        return { preview: true, note: "Ingredients board opened — export image stubbed" };
      }
      if (def.id === "createSpatialFromMasterSheet" || def.id === "translateToSpatial") {
        // Stub: open spatial; full translation lands with master-sheet API helper
        try {
          await api.putMasterSheet(projectId, sceneId, { translate_to_spatial: true });
        } catch {
          /* optional */
        }
        ctx.goTab?.("spatial");
        return { note: "Spatial translation stub — uncertain positions flagged for review" };
      }
      if (def.id === "syncSpatialToMasterSheet") {
        await api.putMasterSheet(projectId, sceneId, { sync_from_spatial: true });
        return { note: "Sync Spatial → Master Sheet queued for review" };
      }
      return {};
    }
    case "compilePrompt":
      return api.compilePrompt({
        intention: inputs.intention,
        model_id: inputs.modelId || "ltx_2_5_distilled",
        mode: inputs.mode || "creative",
        project_id: projectId || undefined,
        scene_id: sceneId || undefined,
      });
    case "createAvatarSession": {
      const session = await api.createAvatarSession(projectId, {
        name: String(inputs.name || "Avatar Session"),
        character_profile_id: inputs.character_profile_id ? String(inputs.character_profile_id) : undefined,
        character_name: inputs.character_name ? String(inputs.character_name) : undefined,
        mode: String(inputs.mode || "talking_portrait"),
      });
      ctx.goTab?.("avatar");
      return session;
    }
    case "setAvatarLook": {
      const sid = String(inputs.sessionId || "");
      const cur = await api.getAvatarSession(projectId, sid);
      return api.patchAvatarSession(projectId, sid, { look: { ...cur.look, ...(inputs.look as object) } });
    }
    case "attachAvatarAudio": {
      const sid = String(inputs.sessionId || "");
      const cur = await api.getAvatarSession(projectId, sid);
      return api.patchAvatarSession(projectId, sid, {
        voice: { ...cur.voice, audio_asset_id: inputs.audio_asset_id },
      });
    }
    case "prepareAvatarLipSync": {
      ctx.goTab?.("timeline");
      return {
        checkpoint: true,
        message: "Place the black rectangle over the character’s mouth, then select Continue.",
      };
    }
    case "queueAvatarGeneration": {
      const reuseAssets = await assetFirst(projectId, "character");
      const result = await api.imageProduct.generate(projectId, {
        prompt: String(inputs.prompt || "cinematic talking portrait, stable identity"),
        operation: "image.generate",
        purpose: "avatar",
      });
      const job = result.jobId ? await api.getJob(result.jobId) : result;
      return { job, reuseAssets };
    }
    case "approveAvatarTake": {
      const sid = String(inputs.sessionId || "");
      return api.addAvatarTake(projectId, sid, {
        label: String(inputs.label || "Approved take"),
        status: "final",
        approved: true,
        asset_id: inputs.asset_id ? String(inputs.asset_id) : undefined,
      });
    }
    case "sendAvatarToDirector": {
      const assetId = String(inputs.asset_id || "");
      if (!assetId) throw new Error("asset_id required");
      return api.promote(projectId, {
        asset_id: assetId,
        target: "scene_new",
        name: String(inputs.name || "Avatar clip"),
      });
    }
    case "createDirectorSequence": {
      if (!sceneId) throw new Error("sceneId required");
      return api.directorSequenceFromScene(projectId, {
        scene_id: sceneId,
        name: String(inputs.name || "Timeline Sequence"),
        status: "draft",
      });
    }
    case "sendDirectorToEditor": {
      let seqId = String(inputs.sequenceId || "");
      if (!seqId && sceneId) {
        const seq = await api.directorSequenceFromScene(projectId, {
          scene_id: sceneId,
          status: "approved",
        });
        await api.patchDirectorSequence(projectId, seq.id, { approve: true });
        seqId = seq.id;
      }
      if (!seqId) throw new Error("sequenceId required");
      const res = await api.sendDirectorToEditor(projectId, seqId, {
        include_audio: inputs.include_audio !== false,
      });
      ctx.goTab?.("magi");
      return res;
    }
    case "compileDirectorPrompt": {
      return api.compilePrompt({
        intention: String(inputs.intention || "Director shot"),
        model_id: String(inputs.modelId || "ltx_2_5_distilled"),
        mode: String(inputs.mode || "structured"),
        project_id: projectId || undefined,
        scene_id: sceneId || undefined,
        task: "director",
        shot_overrides: (inputs.shot_overrides as Record<string, string>) || {},
      });
    }
    case "importDirectorSequence": {
      const seqId = String(inputs.sequenceId || "");
      if (!seqId) throw new Error("sequenceId required");
      const res = await api.sendDirectorToEditor(projectId, seqId, { track: "video" });
      ctx.goTab?.("magi");
      return res;
    }
    case "assembleSceneFromApproved": {
      ctx.goTab?.("magi");
      const seqs = await api.listDirectorSequences(projectId, "approved").catch(() => []);
      const used = await api.listDirectorSequences(projectId, "used_in_editor").catch(() => []);
      const all = [...(seqs || []), ...(used || [])].filter(
        (s: any) => !sceneId || s.scene_id === sceneId
      );
      return {
        plan: true,
        count: all.length,
        message: `Assemble ${all.length} approved Director sequence(s) in Editor.`,
      };
    }
    case "openSourceInDirector": {
      if (inputs.sceneId) {
        try {
          sessionStorage.setItem("adept_focus_scene", String(inputs.sceneId));
        } catch {
          /* ignore */
        }
      }
      if (inputs.sequenceId) {
        try {
          sessionStorage.setItem("adept_director_sequence_id", String(inputs.sequenceId));
        } catch {
          /* ignore */
        }
      }
      ctx.goTab?.("timeline");
      return { tab: "timeline", sceneId: inputs.sceneId };
    }
    case "applyEditorialContextToDirector": {
      const ctxPayload = {
        needed_duration_sec: inputs.needed_duration_sec,
        prev_clip_label: inputs.prev_clip_label,
        next_clip_label: inputs.next_clip_label,
        required_ending: inputs.required_ending,
        screen_direction: inputs.screen_direction,
        audio_overlap_sec: inputs.audio_overlap_sec,
        source_scene_id: inputs.sceneId || sceneId,
      };
      try {
        sessionStorage.setItem("adept_editorial_context", JSON.stringify(ctxPayload));
      } catch {
        /* ignore */
      }
      ctx.goTab?.("timeline");
      return ctxPayload;
    }
    case "saveMemorySuggestion":
      // TODO: wire when learning promotion API is ready
      return { stub: true, text: inputs.text, todo: "Promote via learning API when available" };
    case "manualCheckpoint":
      return { checkpoint: true, message: inputs.message };
    default:
      throw new Error(`Unhandled action ${def.id}`);
  }
}

export async function executeStep(step: PlannedStep, ctx: ExecuteContext): Promise<PlannedStep> {
  if (step.actionId === "manualCheckpoint" || step.status === "checkpoint") {
    return {
      ...step,
      status: "checkpoint",
      checkpointMessage: step.checkpointMessage || String(step.inputs.message || "Continue when ready"),
    };
  }
  const res = await executeAction(step.actionId, step.inputs, ctx);
  return {
    ...step,
    status: res.ok ? "done" : "failed",
    error: res.error,
    result: res.result,
    reuseAssets: res.reuseAssets,
  };
}
