import { useEffect, useState } from "react";
import { api } from "../api";
import {
  joinProductionControlVideoOptions,
  type TimelineGeneratorOption,
} from "./draftCapabilities";

export async function loadTimelineVideoGenerators(): Promise<TimelineGeneratorOption[]> {
  const [pc, timeline] = await Promise.all([
    api.productionControlModels("video"),
    api.directorTimelineGenerators(),
  ]);
  return joinProductionControlVideoOptions(pc, timeline as Record<string, unknown>);
}

/** Footer Dock and Timeline share Production Control inventory; adapters supply capability. */
export function useTimelineVideoGenerators(): TimelineGeneratorOption[] {
  const [options, setOptions] = useState<TimelineGeneratorOption[]>([]);
  useEffect(() => {
    let alive = true;
    void loadTimelineVideoGenerators()
      .then((rows) => {
        if (alive) setOptions(rows);
      })
      .catch(() => {
        if (alive) setOptions([]);
      });
    return () => {
      alive = false;
    };
  }, []);
  return options;
}
