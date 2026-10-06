import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { api } from "../../../api";
import { spatialMapApi } from "./spatialMapApi";
import type { SpinProviderOption } from "./spinCameraGating";
import type { SpinCameraPlacement, SpinPackageManifest, SpinViewKey } from "./types";

const POLL_MS = 2500;

export function useSpinCamera(params: {
  projectId: string;
  mapId: string | null;
}) {
  const { projectId, mapId } = params;

  const [spinCamera, setSpinCamera] = useState<SpinCameraPlacement | null>(null);
  const [centerStatus, setCenterStatus] = useState<{ centered: boolean; distanceMeters: number; toleranceMeters: number } | null>(null);
  const [packages, setPackages] = useState<SpinPackageManifest[]>([]);
  const [activePackageId, setActivePackageId] = useState<string | null>(null);
  const [providerOptions, setProviderOptions] = useState<SpinProviderOption[]>([]);
  const [selectedProviderId, setSelectedProviderId] = useState<string>("");
  const [ersAssetId, setErsAssetId] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const pollRef = useRef<number | null>(null);

  const activePackage = useMemo(
    () => packages.find((p) => p.spinPackageId === activePackageId) || packages[0] || null,
    [packages, activePackageId],
  );

  const stopPoll = useCallback(() => {
    if (pollRef.current) {
      window.clearInterval(pollRef.current);
      pollRef.current = null;
    }
  }, []);

  const refreshActivePackage = useCallback(async () => {
    if (!projectId || !mapId || !activePackage) return;
    try {
      const next = await spatialMapApi.getSpinPackage(projectId, mapId, activePackage.spinPackageId);
      setPackages((prev) =>
        prev.map((p) => (p.spinPackageId === next.spinPackageId ? next : p)),
      );
      const pending = Object.values(next.views || {}).some(
        (v) => v.status === "queued" || v.status === "generating",
      );
      if (!pending) stopPoll();
    } catch {
      // keep last-known state; next poll retries
    }
  }, [projectId, mapId, activePackage, stopPoll]);

  const startPoll = useCallback(
    (packageId: string) => {
      stopPoll();
      setActivePackageId(packageId);
      void refreshActivePackage();
      pollRef.current = window.setInterval(() => void refreshActivePackage(), POLL_MS);
    },
    [refreshActivePackage, stopPoll],
  );

  useEffect(() => () => stopPoll(), [stopPoll]);

  // Load provider options from live discovery.
  useEffect(() => {
    let cancelled = false;
    const load = async () => {
      try {
        const discovered = await api.hostedProvidersDiscoveredModels("image").catch(() => null);
        const items =
          ((discovered as { items?: { id?: string; label?: string; executable?: boolean; supportsReferences?: boolean }[] } | null)?.items) ||
          ((discovered as { models?: { id?: string; label?: string; executable?: boolean; supportsReferences?: boolean }[] } | null)?.models) ||
          [];
        if (cancelled) return;
        const opts: SpinProviderOption[] = items.map((m) => ({
          id: String(m.id || ""),
          label: String(m.label || m.id || ""),
          executable: m.executable === true,
          supportsReferences: m.supportsReferences === true,
        }));
        setProviderOptions(opts);
        setSelectedProviderId((prev) => {
          if (prev && opts.some((o) => o.id === prev)) return prev;
          const firstReady = opts.find((o) => o.executable);
          return firstReady?.id || "";
        });
      } catch {
        if (!cancelled) setProviderOptions([]);
      }
    };
    void load();
    return () => {
      cancelled = true;
    };
  }, [projectId]);

  // Load spin camera + packages whenever the map changes.
  useEffect(() => {
    setSpinCamera(null);
    setCenterStatus(null);
    setPackages([]);
    setActivePackageId(null);
    setErsAssetId(null);
    setError(null);
    stopPoll();
    if (!projectId || !mapId) return;
    let cancelled = false;
    const load = async () => {
      try {
        const cam = await spatialMapApi.getSpinCamera(projectId, mapId);
        if (cancelled) return;
        setSpinCamera(cam.placement);
        setCenterStatus(cam.centerStatus);
      } catch (err) {
        if (!cancelled) setError(err instanceof Error ? err.message : "Could not load Spin Camera.");
      }
      try {
        const manifests = await spatialMapApi.listSpinPackages(projectId, mapId);
        if (cancelled) return;
        setPackages(manifests);
        if (manifests[0]) {
          setActivePackageId(manifests[0].spinPackageId);
          const pending = Object.values(manifests[0].views || {}).some(
            (v) => v.status === "queued" || v.status === "generating",
          );
          if (pending) startPoll(manifests[0].spinPackageId);
        }
      } catch {
        // packages are optional until one is created
      }
    };
    void load();
    return () => {
      cancelled = true;
    };
  }, [projectId, mapId, startPoll, stopPoll]);

  const placeSpinCamera = useCallback(
    async (body: { x: number; z: number; sceneId?: string | null }) => {
      if (!projectId || !mapId) return;
      setBusy(true);
      setError(null);
      try {
        const res = await spatialMapApi.placeSpinCamera(projectId, mapId, body);
        setSpinCamera(res.placement);
        setCenterStatus(res.centerStatus);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Could not place Spin Camera.");
      } finally {
        setBusy(false);
      }
    },
    [projectId, mapId],
  );

  const removeSpinCamera = useCallback(async () => {
    if (!projectId || !mapId) return;
    setBusy(true);
    setError(null);
    try {
      await spatialMapApi.removeSpinCamera(projectId, mapId);
      setSpinCamera(null);
      setCenterStatus(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not remove Spin Camera.");
    } finally {
      setBusy(false);
    }
  }, [projectId, mapId]);

  const createPackage = useCallback(
    async (providerId: string, confirmPaidCloud = false) => {
      if (!projectId || !mapId || !providerId) return;
      setBusy(true);
      setError(null);
      try {
        const manifest = await spatialMapApi.createSpinPackage(projectId, mapId, {
          provider: providerId,
          confirmPaidCloud,
        });
        setPackages((prev) => {
          const next = [manifest, ...prev.filter((p) => p.spinPackageId !== manifest.spinPackageId)];
          return next;
        });
        setActivePackageId(manifest.spinPackageId);
        startPoll(manifest.spinPackageId);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Could not create Spin Package.");
      } finally {
        setBusy(false);
      }
    },
    [projectId, mapId, startPoll],
  );

  const regenerateDirection = useCallback(
    async (packageId: string, direction: SpinViewKey, confirmPaidCloud = false) => {
      if (!projectId || !mapId) return;
      setBusy(true);
      setError(null);
      try {
        const manifest = await spatialMapApi.regenerateSpinView(projectId, mapId, packageId, direction, {
          confirmPaidCloud,
        });
        setPackages((prev) =>
          prev.map((p) => (p.spinPackageId === manifest.spinPackageId ? manifest : p)),
        );
        if (activePackageId === manifest.spinPackageId) {
          startPoll(manifest.spinPackageId);
        }
      } catch (err) {
        setError(err instanceof Error ? err.message : "Could not regenerate direction.");
      } finally {
        setBusy(false);
      }
    },
    [projectId, mapId, activePackageId, startPoll],
  );

  const buildErs = useCallback(
    async (packageId: string) => {
      if (!projectId || !mapId) return;
      setBusy(true);
      setError(null);
      try {
        const res = await spatialMapApi.buildErsFromSpinPackage(projectId, mapId, packageId);
        setErsAssetId(res.ersAssetId || null);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Could not build ERS from spin package.");
      } finally {
        setBusy(false);
      }
    },
    [projectId, mapId],
  );

  return {
    spinCamera,
    centerStatus,
    packages,
    activePackage,
    activePackageId,
    setActivePackageId,
    providerOptions,
    selectedProviderId,
    setSelectedProviderId,
    ersAssetId,
    busy,
    error,
    placeSpinCamera,
    removeSpinCamera,
    createPackage,
    regenerateDirection,
    buildErs,
  };
}
