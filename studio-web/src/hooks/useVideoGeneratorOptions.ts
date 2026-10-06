import { useCallback, useEffect, useState } from "react";
import type { TimelineGeneratorOption } from "../timelineMaster/draftCapabilities";
import { loadTimelineVideoGenerators } from "../timelineMaster/useTimelineVideoGenerators";

export interface VideoGeneratorOption {
  id: string;
  label: string;
  locality: "local" | "hosted";
  executable: boolean;
  capabilityLabel: string;
  disabledReason?: string;
}

interface UseVideoGeneratorOptionsReturn {
  localOptions: VideoGeneratorOption[];
  apiOptions: VideoGeneratorOption[];
  isLoading: boolean;
  error: string | null;
  reload: () => void;
}

function toOption(row: TimelineGeneratorOption): VideoGeneratorOption {
  const hosted = row.id.includes("-api") || row.id.includes("-kie") || row.id.includes("-fal");
  return {
    id: row.id,
    label: row.label,
    locality: hosted ? "hosted" : "local",
    executable: row.executable,
    capabilityLabel: row.readiness || row.capabilityLabel || "",
    disabledReason: row.disabledReason || row.notes,
  };
}

/** Thin presenter over the backend-joined Timeline / Production Control list. */
export function useVideoGeneratorOptions(): UseVideoGeneratorOptionsReturn {
  const [localOptions, setLocalOptions] = useState<VideoGeneratorOption[]>([]);
  const [apiOptions, setApiOptions] = useState<VideoGeneratorOption[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchRows = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const rows = await loadTimelineVideoGenerators();
      const local: VideoGeneratorOption[] = [];
      const api: VideoGeneratorOption[] = [];
      for (const row of rows) {
        const opt = toOption(row);
        if (opt.locality === "local") local.push(opt);
        else api.push(opt);
      }
      setLocalOptions(local);
      setApiOptions(api);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    void fetchRows();
  }, [fetchRows]);

  return { localOptions, apiOptions, isLoading, error, reload: fetchRows };
}
