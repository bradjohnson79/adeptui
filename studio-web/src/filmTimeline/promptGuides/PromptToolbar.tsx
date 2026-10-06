import { useEffect, useRef, useState } from "react";
import { api } from "../../api";
import { applyPromptFragment, composeCameraFragment } from "./applyPromptFragment";
import { LIGHTING_PRESETS } from "./lightingPresets";
import { LENS_PRESETS } from "./lensPresets";
import { PromptGuideFigure } from "./PromptGuideFigure";
import { SCENE_CATEGORIES, SCENE_PRESETS } from "./scenePresets";
import { SHOT_PRESETS } from "./shotPresets";
import type { HelperMemory, PromptPreset } from "./types";

type TemplateRow = { id: string; name: string; promptText: string };
type ModalKind = "scene" | "camera" | "lighting" | null;

function IconScene() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" aria-hidden="true">
      <rect x="3" y="5" width="18" height="14" rx="2" fill="none" stroke="currentColor" strokeWidth="1.6" />
      <path d="M8 15l2.5-3 2 2L16 10l3 5" fill="none" stroke="currentColor" strokeWidth="1.6" />
    </svg>
  );
}

function IconCamera() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" aria-hidden="true">
      <circle cx="12" cy="12" r="3.2" fill="none" stroke="currentColor" strokeWidth="1.6" />
      <circle cx="12" cy="12" r="7" fill="none" stroke="currentColor" strokeWidth="1.6" />
    </svg>
  );
}

function IconLight() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" aria-hidden="true">
      <path d="M12 3l1.6 5.2L19 10l-5.4 1.8L12 17l-1.6-5.2L5 10l5.4-1.8L12 3z" fill="none" stroke="currentColor" strokeWidth="1.6" />
    </svg>
  );
}

function GuideModal({
  title,
  wide,
  summary,
  onClose,
  onSelect,
  canSelect,
  children,
}: {
  title: string;
  wide?: boolean;
  summary: string;
  onClose: () => void;
  onSelect: () => void;
  canSelect: boolean;
  children: React.ReactNode;
}) {
  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);
  return (
    <div className="prompt-guide" role="presentation">
      <button type="button" className="prompt-guide__backdrop" aria-label="Close" onClick={onClose} />
      <div className={`prompt-guide__panel${wide ? " is-wide" : ""}`} role="dialog" aria-modal="true" aria-label={title}>
        <header>
          <h2>{title}</h2>
          <button type="button" aria-label="Close" onClick={onClose}>
            X
          </button>
        </header>
        <div className="prompt-guide__body">{children}</div>
        <footer>
          <span>{summary}</span>
          <button type="button" disabled={!canSelect} onClick={onSelect}>
            Select
          </button>
        </footer>
      </div>
    </div>
  );
}

function PresetList({
  items,
  selectedId,
  onSelect,
}: {
  items: PromptPreset[];
  selectedId: string;
  onSelect: (id: string) => void;
}) {
  const categories = [...new Set(items.map((item) => item.category))];
  return (
    <div className="prompt-guide__lists">
      {categories.map((category) => (
        <section key={category}>
          <h3>{category}</h3>
          {items
            .filter((item) => item.category === category)
            .map((item) => (
              <button key={item.id} type="button" className={item.id === selectedId ? "is-selected" : ""} onClick={() => onSelect(item.id)}>
                {item.label}
              </button>
            ))}
        </section>
      ))}
    </div>
  );
}

export function PromptToolbar({
  projectId,
  sceneId,
  shotId,
  prompt,
  onPrompt,
  onReferences,
  showReferences = true,
}: {
  projectId: string;
  sceneId: string;
  shotId: string;
  prompt: string;
  onPrompt: (value: string) => void;
  onReferences?: () => void;
  showReferences?: boolean;
}) {
  const [modal, setModal] = useState<ModalKind>(null);
  const [memory, setMemory] = useState<HelperMemory>({});
  const [sceneIdPick, setSceneIdPick] = useState(SCENE_PRESETS[0].id);
  const [sceneCategory, setSceneCategory] = useState(SCENE_CATEGORIES[0]);
  const [lensId, setLensId] = useState("");
  const [shotIdPick, setShotIdPick] = useState("");
  const [lightId, setLightId] = useState(LIGHTING_PRESETS[0].id);
  const [templates, setTemplates] = useState<TemplateRow[]>([]);
  const [templateId, setTemplateId] = useState("");
  const [menuOpen, setMenuOpen] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    setMemory({});
  }, [shotId]);

  useEffect(() => {
    if (!menuOpen) return;
    const onDoc = (event: MouseEvent) => {
      if (!menuRef.current?.contains(event.target as Node)) setMenuOpen(false);
    };
    document.addEventListener("mousedown", onDoc);
    return () => document.removeEventListener("mousedown", onDoc);
  }, [menuOpen]);

  const refreshTemplates = () => {
    void api.scenePromptTemplatesList(projectId).then((rows) => {
      setTemplates(Array.isArray(rows) ? rows : []);
    });
  };

  useEffect(() => {
    refreshTemplates();
  }, [projectId]);

  function commit(kind: "scene" | "camera" | "lighting", fragment: string) {
    const next = applyPromptFragment(prompt, kind, fragment, memory);
    setMemory(next.memory);
    onPrompt(next.prompt);
    setModal(null);
  }

  const sceneChoices = SCENE_PRESETS.filter((item) => item.category === sceneCategory);
  const scenePick = SCENE_PRESETS.find((item) => item.id === sceneIdPick) || null;
  const lens = LENS_PRESETS.find((item) => item.id === lensId) || null;
  const shot = SHOT_PRESETS.find((item) => item.id === shotIdPick) || null;
  const light = LIGHTING_PRESETS.find((item) => item.id === lightId) || null;
  const cameraText = composeCameraFragment(lens, shot);
  const selectedTemplate = templates.find((item) => item.id === templateId) || null;

  function loadTemplate() {
    if (!selectedTemplate) return;
    const text = selectedTemplate.promptText || "";
    if (prompt !== text) {
      const ok = window.confirm("Timed Prompt differs from the selected template.\n\nReplace working copy with template text?\n\nOK = Replace\nCancel = keep current text");
      if (!ok) return;
    }
    onPrompt(text);
    setMemory({});
    setMenuOpen(false);
  }

  function saveTemplate() {
    const name = window.prompt("Template name", "Timed Prompt template");
    if (!name?.trim()) return;
    void api
      .scenePromptTemplatesCreate(projectId, { name: name.trim(), promptText: prompt, sourceSceneId: sceneId })
      .then((created) => {
        setTemplateId(String(created?.id || ""));
        refreshTemplates();
      });
  }

  function updateTemplate() {
    if (!selectedTemplate) return;
    const ok = window.confirm(`Overwrite template "${selectedTemplate.name}" with current Timed Prompt text?`);
    if (!ok) return;
    void api.scenePromptTemplatesUpdate(projectId, selectedTemplate.id, { promptText: prompt }).then(() => refreshTemplates());
  }

  function renameTemplate() {
    if (!selectedTemplate) return;
    const name = window.prompt("Rename template", selectedTemplate.name);
    if (!name?.trim()) return;
    void api.scenePromptTemplatesRename(projectId, selectedTemplate.id, name.trim()).then(() => refreshTemplates());
  }

  function deleteTemplate() {
    if (!selectedTemplate) return;
    const ok = window.confirm(`Delete template "${selectedTemplate.name}"? This cannot be undone.`);
    if (!ok) return;
    void api.scenePromptTemplatesDelete(projectId, selectedTemplate.id).then(() => {
      setTemplateId("");
      refreshTemplates();
    });
  }

  return (
    <div className="film-timeline__toolbar" data-testid="film-timeline-prompt-toolbar">
      <button type="button" onClick={() => setModal("scene")}>
        <IconScene /> Scene
      </button>
      <button type="button" onClick={() => setModal("camera")}>
        <IconCamera /> Camera
      </button>
      <button type="button" onClick={() => setModal("lighting")}>
        <IconLight /> Color / Lighting
      </button>
      <div className="film-timeline__template" ref={menuRef}>
        <button type="button" aria-expanded={menuOpen} data-testid="film-timeline-template" onClick={() => setMenuOpen((open) => !open)}>
          Template
        </button>
        {menuOpen ? (
          <div className="film-timeline__template-menu" role="menu" data-testid="film-timeline-template-menu">
            <select value={templateId} data-testid="film-timeline-template-select" onChange={(event) => setTemplateId(event.target.value)}>
              <option value="">Saved templates</option>
              {templates.map((item) => (
                <option key={item.id} value={item.id}>
                  {item.name}
                </option>
              ))}
            </select>
            <button type="button" disabled={!selectedTemplate} onClick={loadTemplate}>
              Replace prompt
            </button>
            <button type="button" onClick={saveTemplate}>
              Save current
            </button>
            <button type="button" disabled={!selectedTemplate} onClick={updateTemplate}>
              Update
            </button>
            <button type="button" disabled={!selectedTemplate} onClick={renameTemplate}>
              Rename
            </button>
            <button type="button" disabled={!selectedTemplate} onClick={deleteTemplate}>
              Delete
            </button>
          </div>
        ) : null}
      </div>
      {showReferences ? (
        <button type="button" data-testid="film-timeline-references" onClick={() => onReferences?.()}>
          References
        </button>
      ) : null}
      {modal === "scene" ? (
        <GuideModal
          title="Scene"
          summary={scenePick?.label || ""}
          canSelect={Boolean(scenePick)}
          onClose={() => setModal(null)}
          onSelect={() => scenePick && commit("scene", scenePick.promptFragment)}
        >
          <div className="prompt-guide__lists">
            <section>
              <h3>Category</h3>
              {SCENE_CATEGORIES.map((category) => (
                <button
                  key={category}
                  type="button"
                  className={category === sceneCategory ? "is-selected" : ""}
                  onClick={() => {
                    setSceneCategory(category);
                    const first = SCENE_PRESETS.find((item) => item.category === category);
                    if (first) setSceneIdPick(first.id);
                  }}
                >
                  {category}
                </button>
              ))}
            </section>
            <PresetList items={sceneChoices} selectedId={sceneIdPick} onSelect={setSceneIdPick} />
          </div>
          <p className="prompt-guide__copy">{scenePick?.promptFragment}</p>
        </GuideModal>
      ) : null}
      {modal === "camera" ? (
        <GuideModal
          title="Camera"
          wide
          summary={[lens?.label, shot?.label].filter(Boolean).join(" · ")}
          canSelect={Boolean(cameraText)}
          onClose={() => setModal(null)}
          onSelect={() => cameraText && commit("camera", cameraText)}
        >
          <div className="prompt-guide__split">
            <div className="prompt-guide__lists">
              <PresetList items={LENS_PRESETS} selectedId={lensId} onSelect={(id) => setLensId((current) => (current === id ? "" : id))} />
              <PresetList items={SHOT_PRESETS} selectedId={shotIdPick} onSelect={(id) => setShotIdPick((current) => (current === id ? "" : id))} />
            </div>
            <aside>
              <PromptGuideFigure lens={lens} shot={shot} />
              <p>{lens?.description}</p>
              <p>{shot?.description}</p>
              <p className="prompt-guide__copy">{cameraText}</p>
            </aside>
          </div>
        </GuideModal>
      ) : null}
      {modal === "lighting" ? (
        <GuideModal
          title="Color / Lighting"
          wide
          summary={light?.label || ""}
          canSelect={Boolean(light)}
          onClose={() => setModal(null)}
          onSelect={() => light && commit("lighting", light.promptFragment)}
        >
          <div className="prompt-guide__split">
            <PresetList items={LIGHTING_PRESETS} selectedId={lightId} onSelect={setLightId} />
            <aside>
              <PromptGuideFigure light={light} />
              <p>{light?.description}</p>
              <p className="prompt-guide__copy">{light?.promptFragment}</p>
            </aside>
          </div>
        </GuideModal>
      ) : null}
    </div>
  );
}
