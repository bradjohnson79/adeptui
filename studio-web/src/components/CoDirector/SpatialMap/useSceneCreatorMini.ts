import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { ersGeneratorOptionDisabled } from "./ersGenerator";
import {
  activeMiniCameras,
  miniOutputCount,
  miniResultSelectable,
  resolveReadyMiniGenerator,
  sceneCreatorMiniApi,
  type MiniAspect,
  type MiniGeneratorId,
  type MiniResult,
  type MiniTake,
} from "./sceneCreatorMiniApi";
import type { SpatialMapDocument } from "./types";

const POLL_MS = 2500;

function asTake(raw: Record<string, unknown> | MiniTake | null | undefined): MiniTake | null {
  if (!raw) return null;
  return raw as MiniTake;
}

export function useSceneCreatorMini(params: {
  projectId: string;
  document: SpatialMapDocument | null;
  isDirty: boolean;
  qwenI2IReady?: boolean | null;
  gptI2IReady?: boolean | null;
}) {
  const { projectId, document, isDirty, qwenI2IReady, gptI2IReady } = params;
  const mapId = document?.id || "";
  const [enabled, setEnabled] = useState(false);
  const [open, setOpen] = useState(false);
  const [generator, setGenerator] = useState<MiniGeneratorId>("qwen2512");
  const [aspect, setAspect] = useState<MiniAspect>("16:9");
  const [take, setTake] = useState<MiniTake | null>(null);
  const [selected, setSelected] = useState<Record<string, boolean>>({});
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const pollRef = useRef<number | null>(null);

  const cameras = useMemo(() => activeMiniCameras(document), [document]);
  const outputCount = miniOutputCount(cameras.length);
  const generatorBlocked = ersGeneratorOptionDisabled(generator, qwenI2IReady, gptI2IReady);
  const canGenerate = enabled && !isDirty && !!mapId && cameras.length > 0 && !busy && !generatorBlocked;

  useEffect(() => {
    const next = resolveReadyMiniGenerator(generator, qwenI2IReady, gptI2IReady);
    if (next !== generator) setGenerator(next);
  }, [generator, gptI2IReady, qwenI2IReady]);

  const gateMessage = !enabled
    ? ""
    : isDirty
      ? "Save Spatial Map to generate a Mini Take."
      : cameras.length === 0
        ? "Add and save at least one camera to generate a Mini Take."
        : generatorBlocked
          ? "Choose a generator that is ready, or repair the local installation."
          : "";

  const stopPoll = useCallback(() => {
    if (pollRef.current) {
      window.clearInterval(pollRef.current);
      pollRef.current = null;
    }
  }, []);

  const refreshTake = useCallback(
    async (takeId: string) => {
      if (!projectId || !mapId) return;
      const res = await sceneCreatorMiniApi.get(projectId, mapId, takeId);
      const next = asTake(res.take);
      setTake(next);
      const live = (next?.results || []).some((r) => r.status === "queued" || r.status === "generating");
      if (!live) stopPoll();
    },
    [projectId, mapId, stopPoll],
  );

  const startPoll = useCallback(
    (takeId: string) => {
      stopPoll();
      void refreshTake(takeId);
      pollRef.current = window.setInterval(() => void refreshTake(takeId), POLL_MS);
    },
    [refreshTake, stopPoll],
  );

  useEffect(() => () => stopPoll(), [stopPoll]);

  const generate = useCallback(async () => {
    if (!canGenerate || !mapId) return;
    setBusy(true);
    setError(null);
    try {
      const res = await sceneCreatorMiniApi.create(projectId, mapId, { generator, aspectRatio: aspect });
      const next = asTake(res.take);
      setTake(next);
      setSelected({});
      if (next?.id) startPoll(next.id);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not generate Mini Take.");
    } finally {
      setBusy(false);
    }
  }, [aspect, canGenerate, generator, mapId, projectId, startPoll]);

  const regenerate = useCallback(
    async (cameraId?: string | null) => {
      if (!take?.id || !mapId || isDirty) return;
      setBusy(true);
      setError(null);
      try {
        const res = await sceneCreatorMiniApi.regenerate(projectId, mapId, take.id, cameraId);
        const next = asTake(res.take);
        setTake(next);
        if (next?.id) startPoll(next.id);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Could not regenerate.");
      } finally {
        setBusy(false);
      }
    },
    [isDirty, mapId, projectId, startPoll, take?.id],
  );

  const toggleSelected = useCallback(
    (resultId: string) => {
      const result = (take?.results || []).find((r) => r.id === resultId);
      if (result && !miniResultSelectable(result)) return;
      setSelected((prev) => ({ ...prev, [resultId]: !prev[resultId] }));
    },
    [take?.results],
  );

  const selectAll = useCallback(() => {
    const complete = (take?.results || []).filter(
      (r) => r.status === "complete" && r.assetId && !r.inLibrary && miniResultSelectable(r),
    );
    const allOn = complete.length > 0 && complete.every((r) => selected[r.id]);
    const next: Record<string, boolean> = {};
    if (!allOn) {
      for (const r of complete) next[r.id] = true;
    }
    setSelected(next);
  }, [selected, take?.results]);

  const selectedIds = useMemo(
    () => Object.entries(selected).filter(([, v]) => v).map(([id]) => id),
    [selected],
  );

  const sendSelected = useCallback(async () => {
    if (!take?.id || !mapId || selectedIds.length === 0) return;
    setBusy(true);
    setError(null);
    try {
      const res = await sceneCreatorMiniApi.sendToLibrary(projectId, mapId, take.id, selectedIds);
      const next = asTake(res.take);
      setTake(next);
      setSelected({});
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not send to Library.");
    } finally {
      setBusy(false);
    }
  }, [mapId, projectId, selectedIds, take?.id]);

  const resultsByCamera = useMemo(() => {
    const groups: { cameraId: string; label: string; results: MiniResult[] }[] = [];
    for (const camera of take?.cameras || cameras) {
      const rows = (take?.results || []).filter((r) => r.cameraId === camera.id);
      groups.push({ cameraId: camera.id, label: camera.label, results: rows });
    }
    return groups;
  }, [cameras, take]);

  return {
    enabled,
    setEnabled,
    open,
    setOpen,
    generator,
    setGenerator,
    aspect,
    setAspect,
    cameras,
    outputCount,
    canGenerate,
    gateMessage,
    take,
    busy,
    error,
    selected,
    selectedIds,
    resultsByCamera,
    generate,
    regenerate,
    toggleSelected,
    selectAll,
    sendSelected,
  };
}
