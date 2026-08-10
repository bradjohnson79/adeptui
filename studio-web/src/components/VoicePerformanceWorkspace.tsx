/**
 * Voice Performance helpers + legacy entry into unified Voice Studio (M43).
 */
import { VoiceStudioWorkspace } from "./VoiceStudioWorkspace";
export { buildPerformanceMarkup, extractPlainDialogue } from "./voiceStudio/performanceMarkup";

export function VoicePerformanceWorkspace({
  projectId,
  characterId,
  onMsg,
}: {
  projectId: string;
  characterId: string;
  onMsg?: (m: string) => void;
}) {
  return (
    <VoiceStudioWorkspace
      projectId={projectId}
      characterId={characterId}
      onMsg={onMsg || (() => undefined)}
      initialPhase="performance"
    />
  );
}
