import { useEffect, useState } from "react";
import {
  ensureLocalGenerationMonitor,
  getLocalGenerationAttention,
  LOCAL_GENERATION_ATTENTION,
  subscribeLocalGenerationAttention,
  type LocalGenerationSnapshot,
} from "../runtime/localGenerationAttention";

export function useLocalGenerationAttention(): LocalGenerationSnapshot & {
  message: string;
} {
  const [snap, setSnap] = useState(getLocalGenerationAttention);
  useEffect(() => {
    ensureLocalGenerationMonitor();
    return subscribeLocalGenerationAttention(setSnap);
  }, []);
  return {
    ...snap,
    message: snap.active ? LOCAL_GENERATION_ATTENTION : "",
  };
}
