import { useCallback, useEffect, useMemo, useState } from "react";
import { ApiError, api } from "../../api";
import type { Project, Scene } from "../../types";
import { PanelHeading } from "../HelpTip";
import { Button } from "../ui";
import { Collage360Panel } from "./Collage360Panel";
import { CameraInspector } from "./CameraInspector";
import { SpatialCanvas } from "./SpatialCanvas";
import {
  SPATIAL_MAP_LIMITS,
  spatialMapCounts,
  type SpatialBundleTarget,
  type SpatialCameraUpdateBody,
  type SpatialCapturePlan,
  type SpatialCharacterPlacementUpdateBody,
  type SpatialConsistencyCheckResponse,
  type SpatialMapDocument,
  type SpatialPropPlacementUpdateBody,
  type SpatialRequiredDirection,
  type Spatial360ViewUpsertBody,
  type SpatialMapStudioTab,
} from "../../contracts/spatialMapM411";

type PlacementKind = "character" | "prop" | "camera";

const TAB_LABELS: Array<{ id: SpatialMapStudioTab; label: string }> = [
  { id: "map", label: "Spatial Map" },
  { id: "collage360", label: "360° Collage" },
  { id: "cameras", label: "Camera Views" },
  { id: "export", label: "Export" },
];

function firstSelectableId(document: SpatialMapDocument | null) {
  if (!document) return null;
  return document.characters[0]?.id || document.props[0]?.id || document.cameras[0]?.id || null;
}

function upsertDocument(documents: SpatialMapDocument[], next: SpatialMapDocument) {
  const filtered = documents.filter((item) => item.id !== next.id);
  return [next, ...filtered];
}

function patchPlacement(
  document: SpatialMapDocument,
  kind: PlacementKind,
  placementId: string,
  patch: Record<string, unknown>
) {
  if (kind === "character") {
    return {
      ...document,
      characters: document.characters.map((item) =>
        item.id === placementId ? { ...item, ...patch } : item
      ),
    };
  }
  if (kind === "prop") {
    return {
      ...document,
      props: document.props.map((item) => (item.id === placementId ? { ...item, ...patch } : item)),
    };
  }
  return {
    ...document,
    cameras: document.cameras.map((item) => (item.id === placementId ? { ...item, ...patch } : item)),
  };
}

function creatorErrorMessage(error: unknown, fallback: string) {
  if (!(error instanceof ApiError)) return fallback;
  if (error.code === "CHARACTER_LIMIT_REACHED") return "This map already has four characters. Remove one or make a variant.";
  if (error.code === "PROP_LIMIT_REACHED") return "This map already has four props. Remove one or make a variant.";
  if (error.code === "CAMERA_LIMIT_REACHED") return "This map already has eight cameras. Reuse an angle or remove one.";
  return error.message || fallback;
}

export function SpatialMapStudio({
  project,
  scene,
  onChange,
  onGoTimeline,
}: {
  project: Project;
  scene?: Scene;
  onChange: () => Promise<void> | void;
  onGoTimeline?: () => void;
}) {
  const sceneId = scene?.id || project.scenes[0]?.id;
  const [documents, setDocuments] = useState<SpatialMapDocument[]>([]);
  const [document, setDocument] = useState<SpatialMapDocument | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<SpatialMapStudioTab>("map");
  const [placementMode, setPlacementMode] = useState<PlacementKind | null>("character");
  const [message, setMessage] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [collageBusy, setCollageBusy] = useState(false);
  const [capturePlan, setCapturePlan] = useState<SpatialCapturePlan | null>(null);
  const [titleDraft, setTitleDraft] = useState("");
  const [notesDraft, setNotesDraft] = useState("");
  const [environmentDraft, setEnvironmentDraft] = useState("");
  const [tagsDraft, setTagsDraft] = useState("");
  const [bundleTarget, setBundleTarget] = useState<SpatialBundleTarget>("image");
  const [selectedCameraId, setSelectedCameraId] = useState<string>("");
  const [bundleSummary, setBundleSummary] = useState<string>("");
  const [consistencyWarnings, setConsistencyWarnings] = useState<string[]>([]);

  const syncDocument = useCallback((next: SpatialMapDocument) => {
    setDocument(next);
    setDocuments((current) => upsertDocument(current, next));
    setSelectedId((current) => current || firstSelectableId(next));
  }, []);

  const loadMaps = useCallback(
    async (preferredDocumentId?: string) => {
      setLoading(true);
      try {
        const listResponse = await api.spatialMap.listMaps(project.id);
        let nextDocuments = listResponse.documents;
        let nextDocument =
          nextDocuments.find((item) => item.id === preferredDocumentId) ||
          nextDocuments.find((item) => item.sceneId === sceneId || item.assignedSceneIds.includes(sceneId || "")) ||
          null;

        if (!nextDocument) {
          const created = await api.spatialMap.createMap(project.id, {
            title: scene?.name ? `${scene.name} Spatial Map` : "Spatial Map",
            sceneId: sceneId || null,
            notes: scene?.summary || "",
            masterEnvironmentPrompt: scene?.prompt || "",
          });
          nextDocument = created.document;
          nextDocuments = upsertDocument(nextDocuments, created.document);
        }

        setDocuments(nextDocuments);
        setDocument(nextDocument);
        setSelectedId(firstSelectableId(nextDocument));
        setMessage(null);
      } catch (error) {
        console.error(error);
        setMessage("Could not load Spatial Map right now.");
      } finally {
        setLoading(false);
      }
    },
    [project.id, scene?.name, scene?.prompt, scene?.summary, sceneId]
  );

  useEffect(() => {
    if (!sceneId) return;
    void loadMaps();
  }, [loadMaps, sceneId]);

  useEffect(() => {
    if (!document) return;
    setTitleDraft(document.title || "");
    setNotesDraft(document.notes || "");
    setEnvironmentDraft(document.masterEnvironmentPrompt || "");
    setTagsDraft(document.tags.join(", "));
    if (!document.cameras.some((item) => item.id === selectedCameraId)) {
      setSelectedCameraId(document.cameras.find((item) => item.hero)?.id || document.cameras[0]?.id || "");
    }
  }, [document, selectedCameraId]);

  const counts = useMemo(
    () => (document ? spatialMapCounts(document) : { characters: 0, props: 0, cameras: 0 }),
    [document]
  );

  const refreshExportData = useCallback(async () => {
    if (!document) return;
    try {
      const [bundle, consistency] = await Promise.all([
        api.spatialMap.referenceBundle(project.id, document.id, bundleTarget, selectedCameraId || undefined),
        api.spatialMap.consistencyCheck(project.id, document.id),
      ]);
      const summary = [
        `Environment: ${bundle.bundle.environmentPrompt || "Not set yet."}`,
        `Reference assets: ${bundle.bundle.referenceAssetIds.length}`,
        `Characters: ${bundle.bundle.characters.map((item) => item.label).join(", ") || "None placed yet"}`,
        `Props: ${bundle.bundle.props.map((item) => item.label).join(", ") || "None placed yet"}`,
        `Primary camera: ${bundle.bundle.primaryCamera?.label || "No camera selected"}`,
      ].join("\n");
      setBundleSummary(summary);
      setConsistencyWarnings((consistency as SpatialConsistencyCheckResponse).warnings || []);
    } catch (error) {
      console.error(error);
      setMessage("Could not refresh the export bundle.");
    }
  }, [bundleTarget, document, project.id, selectedCameraId]);

  useEffect(() => {
    if (activeTab !== "export" || !document) return;
    void refreshExportData();
  }, [activeTab, document, refreshExportData]);

  const updateDocumentFields = useCallback(
    async (body: { title?: string; notes?: string; tags?: string[]; masterEnvironmentPrompt?: string; backgroundAssetId?: string | null }) => {
      if (!document) return;
      try {
        const response = await api.spatialMap.updateMap(project.id, document.id, body);
        syncDocument(response.document);
        await onChange();
      } catch (error) {
        console.error(error);
        setMessage("We couldn't save that map change.");
      }
    },
    [document, onChange, project.id, syncDocument]
  );

  const previewMove = useCallback(
    (kind: PlacementKind, placementId: string, patch: { x?: number; z?: number }) => {
      if (!document) return;
      setDocument(patchPlacement(document, kind, placementId, patch));
    },
    [document]
  );

  const commitMove = useCallback(
    async (kind: PlacementKind, placementId: string, patch: { x?: number; z?: number; yawDegrees?: number }) => {
      if (!document) return;
      try {
        const response =
          kind === "character"
            ? await api.spatialMap.moveCharacter(project.id, document.id, placementId, patch as SpatialCharacterPlacementUpdateBody)
            : kind === "prop"
              ? await api.spatialMap.moveProp(project.id, document.id, placementId, patch as SpatialPropPlacementUpdateBody)
              : await api.spatialMap.updateCamera(project.id, document.id, placementId, patch as SpatialCameraUpdateBody);
        syncDocument(response.document);
        await onChange();
      } catch (error) {
        console.error(error);
        setMessage("We couldn't save that move.");
        void loadMaps(document.id);
      }
    },
    [document, loadMaps, onChange, project.id, syncDocument]
  );

  const placeItem = useCallback(
    async (kind: PlacementKind, x: number, z: number) => {
      if (!document) return;
      try {
        const response =
          kind === "character"
            ? await api.spatialMap.placeCharacter(project.id, document.id, {
                characterId: `${sceneId || "scene"}-character-${counts.characters + 1}`,
                label: `Character ${counts.characters + 1}`,
                x,
                y: 0,
                z,
              })
            : kind === "prop"
              ? await api.spatialMap.placeProp(project.id, document.id, {
                  label: `Prop ${counts.props + 1}`,
                  x,
                  y: 0,
                  z,
                })
              : await api.spatialMap.createCamera(project.id, document.id, {
                  label: `Camera ${counts.cameras + 1}`,
                  x,
                  y: 1.6,
                  z,
                  heightMeters: 1.6,
                  shotType: "medium",
                  hero: document.cameras.length === 0,
                });
        syncDocument(response.document);
        setSelectedId(
          kind === "character"
            ? response.document.characters.at(-1)?.id || null
            : kind === "prop"
              ? response.document.props.at(-1)?.id || null
              : response.document.cameras.at(-1)?.id || null
        );
        await onChange();
      } catch (error) {
        console.error(error);
        setMessage(creatorErrorMessage(error, "We couldn't place that marker."));
      }
    },
    [counts.cameras, counts.characters, counts.props, document, onChange, project.id, sceneId, syncDocument]
  );

  const updateCharacter = useCallback(
    async (placementId: string, body: SpatialCharacterPlacementUpdateBody) => {
      if (!document) return;
      try {
        const response = await api.spatialMap.moveCharacter(project.id, document.id, placementId, body);
        syncDocument(response.document);
        await onChange();
      } catch (error) {
        console.error(error);
        setMessage("We couldn't save that character change.");
      }
    },
    [document, onChange, project.id, syncDocument]
  );

  const updateProp = useCallback(
    async (placementId: string, body: SpatialPropPlacementUpdateBody) => {
      if (!document) return;
      try {
        const response = await api.spatialMap.moveProp(project.id, document.id, placementId, body);
        syncDocument(response.document);
        await onChange();
      } catch (error) {
        console.error(error);
        setMessage("We couldn't save that prop change.");
      }
    },
    [document, onChange, project.id, syncDocument]
  );

  const updateCamera = useCallback(
    async (cameraId: string, body: SpatialCameraUpdateBody) => {
      if (!document) return;
      try {
        const response = await api.spatialMap.updateCamera(project.id, document.id, cameraId, body);
        syncDocument(response.document);
        await onChange();
      } catch (error) {
        console.error(error);
        setMessage("We couldn't save that camera change.");
      }
    },
    [document, onChange, project.id, syncDocument]
  );

  const removeItem = useCallback(
    async (kind: PlacementKind, placementId: string) => {
      if (!document) return;
      try {
        const response =
          kind === "character"
            ? await api.spatialMap.removeCharacter(project.id, document.id, placementId)
            : kind === "prop"
              ? await api.spatialMap.removeProp(project.id, document.id, placementId)
              : await api.spatialMap.removeCamera(project.id, document.id, placementId);
        syncDocument(response.document);
        setSelectedId(firstSelectableId(response.document));
        await onChange();
      } catch (error) {
        console.error(error);
        setMessage("We couldn't remove that placement.");
      }
    },
    [document, onChange, project.id, syncDocument]
  );

  const generate360 = useCallback(async () => {
    if (!document) return;
    setCollageBusy(true);
    try {
      const planResponse = await api.spatialMap.capturePlan(project.id, document.id, {
        includeCharacters: document.characters.length > 0,
        masterEnvironmentPrompt: document.masterEnvironmentPrompt,
        cameraHeightMeters: document.cameras.find((item) => item.hero)?.heightMeters || 1.6,
        lensMm: document.cameras.find((item) => item.hero)?.lensMm || 24,
      });
      setCapturePlan(planResponse.plan);
      const createResponse = await api.spatialMap.createCollage(project.id, document.id, {
        masterEnvironmentPrompt: planResponse.plan.masterEnvironmentPrompt,
        captureMode: planResponse.plan.captureMode,
        cameraHeightMeters: planResponse.plan.cameraHeightMeters,
        lensMm: planResponse.plan.lensMm,
      });
      let nextDocument = createResponse.document;
      for (const shot of planResponse.plan.shots) {
        const viewResponse = await api.spatialMap.upsertCollageView(
          project.id,
          document.id,
          shot.direction,
          { prompt: shot.prompt, status: "planned" }
        );
        nextDocument = viewResponse.document;
      }
      syncDocument(nextDocument);
      setMessage("360 collage laid out from the real capture planner.");
      await onChange();
    } catch (error) {
      console.error(error);
      setMessage("We couldn't build the 360 collage.");
    } finally {
      setCollageBusy(false);
    }
  }, [document, onChange, project.id, syncDocument]);

  const updateCollageView = useCallback(
    async (direction: SpatialRequiredDirection, body: Spatial360ViewUpsertBody) => {
      if (!document) return;
      try {
        const response = await api.spatialMap.upsertCollageView(project.id, document.id, direction, body);
        syncDocument(response.document);
        await onChange();
      } catch (error) {
        console.error(error);
        setMessage("We couldn't save that collage view.");
      }
    },
    [document, onChange, project.id, syncDocument]
  );

  const assignScene = useCallback(async () => {
    if (!document || !sceneId) return;
    try {
      const response = await api.spatialMap.assignScene(project.id, document.id, {
        sceneId,
        locationId: document.locationId || null,
      });
      syncDocument(response.document);
      setMessage("Spatial Map assigned back to the scene.");
      await onChange();
      onGoTimeline?.();
    } catch (error) {
      console.error(error);
      setMessage("We couldn't assign this map back to the scene.");
    }
  }, [document, onChange, onGoTimeline, project.id, sceneId, syncDocument]);

  if (!sceneId) {
    return (
      <div className="page">
        <p className="empty">Create a scene first to open Spatial Map.</p>
      </div>
    );
  }

  if (loading || !document) {
    return (
      <div className="page">
        <p className="empty">Loading Spatial Map…</p>
      </div>
    );
  }

  return (
    <div className="spatial-workspace spatial-map-studio" data-testid="spatial-map-studio">
      <header className="spatial-workspace-head spatial-map-studio__head">
        <div>
          <PanelHeading
            title="Spatial Map"
            tip="Block your scene with filmmaker language: place performers, place props, move cameras, and keep the canvas as your main staging surface."
          />
          <p className="scene-meta">
            {scene?.name || "Scene"} · version {document.version} · {documents.length} saved map
            {documents.length === 1 ? "" : "s"} in this project.
          </p>
        </div>
        <div className="spatial-map-hero-actions">
          <div className="row" style={{ gap: "0.5rem", flexWrap: "wrap" }}>
            <label className="scene-meta">
              Open Map
              <select
                value={document.id}
                onChange={(event) => {
                  const next = documents.find((item) => item.id === event.target.value) || null;
                  setDocument(next);
                  setSelectedId(firstSelectableId(next));
                }}
              >
                {documents.map((item) => (
                  <option key={item.id} value={item.id}>
                    {item.title}
                  </option>
                ))}
              </select>
            </label>
          </div>
          <div className="spatial-map-limit-strip">
            <span className="pill" data-testid="spatial-character-limit">
              {counts.characters} / {SPATIAL_MAP_LIMITS.characters} characters
              {counts.characters >= SPATIAL_MAP_LIMITS.characters ? " · limit reached" : ""}
            </span>
            <span className="pill" data-testid="spatial-prop-limit">
              {counts.props} / {SPATIAL_MAP_LIMITS.props} props
              {counts.props >= SPATIAL_MAP_LIMITS.props ? " · limit reached" : ""}
            </span>
            <span className="pill">
              {counts.cameras} / {SPATIAL_MAP_LIMITS.cameras} cameras
              {counts.cameras >= SPATIAL_MAP_LIMITS.cameras ? " · limit reached" : ""}
            </span>
          </div>
          <div className="spatial-map-placement-actions">
            <Button
              variant={placementMode === "character" ? "primary" : "secondary"}
              data-testid="spatial-add-character"
              disabled={counts.characters >= SPATIAL_MAP_LIMITS.characters}
              onClick={() => setPlacementMode("character")}
            >
              Place Character
            </Button>
            <Button
              variant={placementMode === "prop" ? "primary" : "secondary"}
              data-testid="spatial-add-prop"
              disabled={counts.props >= SPATIAL_MAP_LIMITS.props}
              onClick={() => setPlacementMode("prop")}
            >
              Place Prop
            </Button>
            <Button
              variant={placementMode === "camera" ? "primary" : "secondary"}
              data-testid="spatial-add-camera"
              disabled={counts.cameras >= SPATIAL_MAP_LIMITS.cameras}
              onClick={() => setPlacementMode("camera")}
            >
              Move Camera
            </Button>
            <Button variant="ghost" onClick={() => setPlacementMode(null)}>
              Stop Placing
            </Button>
          </div>
        </div>
      </header>

      {message ? <p className="pill warn">{message}</p> : null}

      <div className="workspace-tabs spatial-map-tabs" role="tablist">
        {TAB_LABELS.map((tab) => (
          <button
            key={tab.id}
            type="button"
            className={activeTab === tab.id ? "primary" : ""}
            aria-selected={activeTab === tab.id}
            data-testid={tab.id === "collage360" ? "spatial-360-tab" : undefined}
            onClick={() => setActiveTab(tab.id)}
          >
            {tab.label}
          </button>
        ))}
      </div>

      <div className="spatial-layout spatial-map-layout">
        <main className="spatial-main spatial-map-main">
          {activeTab === "map" ? (
            <>
              <section className="spatial-map-panel">
                <PanelHeading
                  title="Blocking Canvas"
                  tip="This top-down view maps left-to-right across X and foreground-to-background across Z."
                >
                  <label className="scene-meta">
                    Background Plate
                    <select
                      value={document.backgroundAssetId || ""}
                      onChange={(event) =>
                        void updateDocumentFields({ backgroundAssetId: event.target.value || null })
                      }
                    >
                      <option value="">None yet</option>
                      {project.assets
                        .filter((asset) => asset.kind === "image" || asset.kind === "environment")
                        .map((asset) => (
                          <option key={asset.id} value={asset.id}>
                            {asset.tag || asset.filename}
                          </option>
                        ))}
                    </select>
                  </label>
                </PanelHeading>
                <SpatialCanvas
                  document={document}
                  backgroundUrl={document.backgroundAssetId ? api.assetUrl(document.backgroundAssetId) : null}
                  selectedId={selectedId}
                  placementMode={placementMode}
                  onSelect={setSelectedId}
                  onPlace={placeItem}
                  onPreviewMove={previewMove}
                  onCommitMove={commitMove}
                />
              </section>

              <section className="spatial-map-panel">
                <PanelHeading
                  title="Scene Feel"
                  tip="Write the plain-language staging note and environment direction your crew should share."
                />
                <div className="field">
                  <label>Map Name</label>
                  <input
                    value={titleDraft}
                    onChange={(event) => setTitleDraft(event.target.value)}
                    onBlur={() => void updateDocumentFields({ title: titleDraft })}
                  />
                </div>
                <div className="field">
                  <label>Staging Note</label>
                  <textarea
                    rows={4}
                    value={notesDraft}
                    placeholder="Warm apartment interior, breakfast table in the center, performers keeping the window side open."
                    onChange={(event) => setNotesDraft(event.target.value)}
                    onBlur={() => void updateDocumentFields({ notes: notesDraft })}
                  />
                </div>
                <div className="field">
                  <label>Master Environment Prompt</label>
                  <textarea
                    rows={4}
                    value={environmentDraft}
                    placeholder="Lantern-lit courtyard with a cool moon wash and clear stone paths."
                    onChange={(event) => setEnvironmentDraft(event.target.value)}
                    onBlur={() => void updateDocumentFields({ masterEnvironmentPrompt: environmentDraft })}
                  />
                </div>
                <div className="field">
                  <label>Tags</label>
                  <input
                    value={tagsDraft}
                    placeholder="hero, courtyard, night"
                    onChange={(event) => setTagsDraft(event.target.value)}
                    onBlur={() =>
                      void updateDocumentFields({
                        tags: tagsDraft
                          .split(",")
                          .map((item) => item.trim())
                          .filter(Boolean),
                      })
                    }
                  />
                </div>
              </section>
            </>
          ) : null}

          {activeTab === "collage360" ? (
            <Collage360Panel
              document={document}
              assets={project.assets}
              capturePlan={capturePlan}
              busy={collageBusy}
              onGenerate={() => void generate360()}
              onUpdateView={(direction, body) => void updateCollageView(direction, body)}
            />
          ) : null}

          {activeTab === "cameras" ? (
            <section className="spatial-map-panel">
              <PanelHeading
                title="Camera Views"
                tip="Keep coverage readable: lens choice, hero angle, and which performer each camera is carrying."
              />
              {document.cameras.length ? (
                <div className="spatial-map-camera-list">
                  {document.cameras.map((camera) => (
                    <button
                      key={camera.id}
                      type="button"
                      className={`spatial-map-camera-card${selectedId === camera.id ? " spatial-map-camera-card--selected" : ""}`}
                      onClick={() => setSelectedId(camera.id)}
                    >
                      <strong>{camera.label}</strong>
                      <span>{camera.shotType || "Medium"} · {camera.lensMm}mm</span>
                      <span>{camera.hero ? "Hero angle" : "Support angle"} · facing {Math.round(camera.yawDegrees)}°</span>
                    </button>
                  ))}
                </div>
              ) : (
                <p className="empty">Add a camera on the map to shape camera coverage.</p>
              )}
            </section>
          ) : null}

          {activeTab === "export" ? (
            <section className="spatial-map-panel">
              <PanelHeading
                title="Export"
                tip="Pull the live reference bundle, check consistency warnings, and assign the map back to the scene."
              />
              <div className="spatial-map-export-actions">
                <label className="scene-meta">
                  Bundle Target
                  <select value={bundleTarget} onChange={(event) => setBundleTarget(event.target.value as SpatialBundleTarget)}>
                    <option value="image">Image</option>
                    <option value="video">Video</option>
                  </select>
                </label>
                <label className="scene-meta">
                  Camera View
                  <select value={selectedCameraId} onChange={(event) => setSelectedCameraId(event.target.value)}>
                    <option value="">Hero or first camera</option>
                    {document.cameras.map((camera) => (
                      <option key={camera.id} value={camera.id}>
                        {camera.label}
                      </option>
                    ))}
                  </select>
                </label>
                <Button variant="secondary" onClick={() => void refreshExportData()}>
                  Refresh Bundle
                </Button>
                <Button variant="secondary" data-testid="spatial-assign-scene" onClick={() => void assignScene()}>
                  Assign to Scene
                </Button>
              </div>

              {bundleSummary ? <pre className="spatial-propose">{bundleSummary}</pre> : null}
              {consistencyWarnings.length ? (
                <div className="pill warn">{consistencyWarnings.join(" ")}</div>
              ) : (
                <p className="scene-meta">No consistency warnings right now.</p>
              )}
            </section>
          ) : null}
        </main>

        <CameraInspector
          project={project}
          document={document}
          selectedId={selectedId}
          onSelect={setSelectedId}
          onUpdateCharacter={(placementId, body) => void updateCharacter(placementId, body)}
          onUpdateProp={(placementId, body) => void updateProp(placementId, body)}
          onUpdateCamera={(cameraId, body) => void updateCamera(cameraId, body)}
          onRemove={(kind, placementId) => void removeItem(kind, placementId)}
        />
      </div>
    </div>
  );
}
