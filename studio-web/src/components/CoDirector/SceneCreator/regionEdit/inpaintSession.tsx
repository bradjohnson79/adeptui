/**
 * UI session for Inpaint accordion + center-canvas painting.
 * Not a product store — Region Edit / Candidate State remains authoritative.
 */
import { createContext, useContext, useMemo, useRef, useState, type ReactNode, type RefObject } from "react";
import type { ImageMaskEditorHandle } from "../../../imageEdit/ImageMaskEditor";
import {
  defaultExpandFor,
  defaultFeatherFor,
  type ExpandPreset,
  type FeatherPreset,
  type RegionEditOperation,
} from "./regionEdit";

export type InpaintTool = "brush" | "erase";

type InpaintSessionValue = {
  accordionOpen: boolean;
  setAccordionOpen: (open: boolean) => void;
  tool: InpaintTool;
  setTool: (tool: InpaintTool) => void;
  brushSize: number;
  setBrushSize: (size: number) => void;
  prompt: string;
  setPrompt: (prompt: string) => void;
  operation: RegionEditOperation;
  setOperation: (operation: RegionEditOperation) => void;
  expand: ExpandPreset;
  setExpand: (expand: ExpandPreset) => void;
  feather: FeatherPreset;
  setFeather: (feather: FeatherPreset) => void;
  coverage: number;
  setCoverage: (coverage: number) => void;
  sourceId: string;
  setSourceId: (id: string) => void;
  hasMask: boolean;
  setHasMask: (has: boolean) => void;
  maskSourceAssetId: string;
  setMaskSourceAssetId: (id: string) => void;
  maskCameraVersion: number | null;
  setMaskCameraVersion: (version: number | null) => void;
  maskRef: RefObject<ImageMaskEditorHandle | null>;
  maskInteractive: boolean;
};

const InpaintSessionContext = createContext<InpaintSessionValue | null>(null);

export function InpaintSessionProvider({ children }: { children: ReactNode }) {
  const [accordionOpen, setAccordionOpen] = useState(false);
  const [tool, setTool] = useState<InpaintTool>("brush");
  const [brushSize, setBrushSize] = useState(24);
  const [prompt, setPrompt] = useState("");
  const [operation, setOperation] = useState<RegionEditOperation>("remove");
  const [expand, setExpand] = useState<ExpandPreset>("normal");
  const [feather, setFeather] = useState<FeatherPreset>("hard");
  const [coverage, setCoverage] = useState(0);
  const [sourceId, setSourceId] = useState("");
  const [hasMask, setHasMask] = useState(false);
  const [maskSourceAssetId, setMaskSourceAssetId] = useState("");
  const [maskCameraVersion, setMaskCameraVersion] = useState<number | null>(null);
  const maskRef = useRef<ImageMaskEditorHandle | null>(null);

  const value = useMemo<InpaintSessionValue>(
    () => ({
      accordionOpen,
      setAccordionOpen,
      tool,
      setTool,
      brushSize,
      setBrushSize,
      prompt,
      setPrompt,
      operation,
      setOperation: (next: RegionEditOperation) => {
        setOperation(next);
        setExpand(defaultExpandFor(next));
        setFeather(defaultFeatherFor(next));
      },
      expand,
      setExpand,
      feather,
      setFeather,
      coverage,
      setCoverage,
      sourceId,
      setSourceId,
      hasMask,
      setHasMask,
      maskSourceAssetId,
      setMaskSourceAssetId,
      maskCameraVersion,
      setMaskCameraVersion,
      maskRef,
      maskInteractive: accordionOpen && (tool === "brush" || tool === "erase"),
    }),
    [
      accordionOpen,
      tool,
      brushSize,
      prompt,
      operation,
      expand,
      feather,
      coverage,
      sourceId,
      hasMask,
      maskSourceAssetId,
      maskCameraVersion,
    ],
  );

  return <InpaintSessionContext.Provider value={value}>{children}</InpaintSessionContext.Provider>;
}

export function useInpaintSession(): InpaintSessionValue {
  const ctx = useContext(InpaintSessionContext);
  if (!ctx) throw new Error("useInpaintSession must be used inside InpaintSessionProvider");
  return ctx;
}
