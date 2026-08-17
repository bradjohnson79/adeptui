import { useEffect, useRef } from "react";
import type { Project } from "../types";
import { useLanguagePrefs } from "./LanguageProvider";
import { hasProjectLanguage, parseProjectLanguage } from "./projectLanguage";

/** Hydrate conversation/policy/canonical from the open project without touching interface locale. */
export function ProjectLanguageSync({ project }: { project: Project }) {
  const { setPrefs } = useLanguagePrefs();
  const appliedRef = useRef<string>("");

  useEffect(() => {
    if (!hasProjectLanguage(project.settings_json)) return;
    const token = `${project.id}:${project.settings_json || ""}`;
    if (appliedRef.current === token) return;
    appliedRef.current = token;
    const language = parseProjectLanguage(project.settings_json);
    setPrefs({
      conversationLocale: language.conversationLocale,
      projectPrimaryLocale: language.projectPrimaryLocale,
      promptLanguagePolicy: language.promptLanguagePolicy,
      exportLocale: language.exportLocale,
    });
  }, [project.id, project.settings_json, setPrefs]);

  return null;
}
