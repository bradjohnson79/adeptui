/**
 * Legacy entry — Character Voice Creator now routes into unified Voice Studio (M43).
 */
import { VoiceStudioWorkspace } from "./VoiceStudioWorkspace";

export function VoiceCreatorWorkspace({
  projectId,
  characterId,
  onMsg,
  onRefresh,
  onOpenVoicePerformance,
}: {
  projectId: string;
  characterId: string;
  onMsg: (m: string) => void;
  onRefresh: () => void;
  onOpenVoicePerformance?: () => void;
}) {
  return (
    <VoiceStudioWorkspace
      projectId={projectId}
      characterId={characterId}
      onMsg={onMsg}
      onRefresh={onRefresh}
      initialPhase={onOpenVoicePerformance ? "create" : "create"}
    />
  );
}
