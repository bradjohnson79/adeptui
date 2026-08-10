import {
  createLowerThirdGroup,
  createTextElement,
  createVectorElement,
  type MagiOverlayElement,
} from "./types";

export type MagiOverlayPreset = {
  id: string;
  category: "Basic" | "Modern" | "Broadcast" | "Cinematic";
  name: string;
  build: () => MagiOverlayElement[];
};

export const OVERLAY_PRESETS: MagiOverlayPreset[] = [
  {
    id: "simple-name",
    category: "Basic",
    name: "Simple Name",
    build: () => [createTextElement({ text: "NAME", name: "Simple Name", y: 0.82, x: 0.08 })],
  },
  {
    id: "name-role",
    category: "Basic",
    name: "Name and Role",
    build: () => [createLowerThirdGroup("NAME", "Role")],
  },
  {
    id: "location",
    category: "Basic",
    name: "Location",
    build: () => [
      createTextElement({
        text: "LOCATION",
        name: "Location",
        y: 0.86,
        x: 0.08,
        textStyle: {
          ...createTextElement().textStyle,
          fontSize: 28,
          uppercase: true,
        },
      }),
    ],
  },
  {
    id: "quote",
    category: "Basic",
    name: "Quote",
    build: () => [
      createTextElement({
        text: "“A line worth keeping.”",
        name: "Quote",
        x: 0.15,
        y: 0.4,
        width: 0.7,
        height: 0.16,
        textStyle: { ...createTextElement().textStyle, fontSize: 36, fontWeight: 400, alignment: "center" },
        backgroundStyle: {
          ...createTextElement().backgroundStyle!,
          enabled: true,
          fill: "#000000",
          opacity: 0.45,
          cornerRadius: 8,
        },
      }),
    ],
  },
  {
    id: "minimal-caption",
    category: "Basic",
    name: "Minimal Caption",
    build: () => [
      createTextElement({
        text: "Caption",
        name: "Caption",
        x: 0.2,
        y: 0.88,
        width: 0.6,
        height: 0.06,
        textStyle: { ...createTextElement().textStyle, fontSize: 24, alignment: "center", fontWeight: 400 },
      }),
    ],
  },
  {
    id: "accent-bar",
    category: "Modern",
    name: "Accent Bar",
    build: () => {
      const g = createLowerThirdGroup("TITLE", "Subtitle");
      return [g];
    },
  },
  {
    id: "framed",
    category: "Modern",
    name: "Framed",
    build: () => {
      const frame = createVectorElement("rounded_rectangle");
      frame.x = 0.08;
      frame.y = 0.76;
      frame.width = 0.4;
      frame.height = 0.14;
      frame.fill = null;
      frame.stroke = "#a78bfa";
      frame.strokeWidth = 3;
      const t = createTextElement({ text: "FRAMED", x: 0.11, y: 0.8, width: 0.34, height: 0.06 });
      return [frame, t];
    },
  },
  {
    id: "news-lt",
    category: "Broadcast",
    name: "News Lower Third",
    build: () => [createLowerThirdGroup("ANCHOR NAME", "Breaking · Desk")],
  },
  {
    id: "interview",
    category: "Broadcast",
    name: "Interview Identifier",
    build: () => [createLowerThirdGroup("GUEST", "Title · Organization")],
  },
  {
    id: "film-title",
    category: "Cinematic",
    name: "Minimal Film Title",
    build: () => [
      createTextElement({
        text: "THE VENTURE",
        name: "Film Title",
        x: 0.2,
        y: 0.42,
        width: 0.6,
        height: 0.12,
        textStyle: {
          ...createTextElement().textStyle,
          fontFamily: "dejavu-serif",
          fontSize: 64,
          alignment: "center",
          uppercase: true,
          letterSpacing: 4,
        },
      }),
    ],
  },
  {
    id: "chapter",
    category: "Cinematic",
    name: "Chapter Card",
    build: () => [
      createTextElement({
        text: "CHAPTER I",
        x: 0.25,
        y: 0.45,
        width: 0.5,
        height: 0.08,
        textStyle: { ...createTextElement().textStyle, alignment: "center", fontSize: 40 },
      }),
    ],
  },
];
