import type { PromptPreset } from "./types";

const row = (
  id: string,
  category: string,
  label: string,
  description: string,
  promptFragment: string,
  palette: [string, string, string],
): PromptPreset => ({ id, category, label, description, promptFragment, palette });

export const LIGHTING_PRESETS: PromptPreset[] = [
  row("daylight", "Natural", "Neutral Daylight", "Even sun with honest color.", "Neutral daylight with even sunlight, honest color, and soft natural shadows.", ["#d7e4ef", "#f4f7fb", "#8aa0b4"]),
  row("golden", "Natural", "Golden Hour", "Warm low sun and long shadows.", "Warm golden-hour illumination with soft directional sunlight, long gentle shadows, subtle atmospheric glow, and naturally warm cinematic color separation.", ["#f0b429", "#f6d7a8", "#6b3f2a"]),
  row("blue-hour", "Natural", "Blue Hour", "The cool pause after sunset.", "Blue-hour light with cool ambient sky, lingering warmth in practicals, and a quiet cinematic dusk.", ["#1d3d66", "#7ea0c4", "#e7c9a9"]),
  row("overcast", "Natural", "Soft Overcast", "Shadowless, even, and kind.", "Soft overcast light with gentle wrap, low contrast, and even illumination across the subject.", ["#c5ced6", "#eef2f5", "#8d99a6"]),
  row("moonlight", "Natural", "Moonlight", "Cool night and silver edges.", "Moonlight with cool silver edges, deep blue shadows, and a quiet nocturnal atmosphere.", ["#0e1a2b", "#9bb7d4", "#d5e4f2"]),
  row("window", "Natural", "Window Light", "One soft source from the side.", "Window light from one side, with soft falloff, a gentle fill, and a lived-in interior.", ["#f3efe6", "#d9cbb8", "#6e6258"]),
  row("teal-orange", "Cinematic", "Teal / Orange", "Complementary skin and shadow.", "Teal and orange cinematic grade, with warm skin tones against cooler shadows and a controlled complementary palette.", ["#0e7490", "#f4a261", "#12324a"]),
  row("warm-cine", "Cinematic", "Warm Cinematic", "Amber midtones and gentle contrast.", "Warm cinematic color with amber midtones, gentle contrast, and a cohesive golden cast.", ["#c47b3a", "#f3d2a4", "#3d2a22"]),
  row("cool-cine", "Cinematic", "Cool Cinematic", "Steel highlights and reserved warmth.", "Cool cinematic color with steel highlights, reserved warmth in skin, and a measured blue cast.", ["#31556e", "#d5e2ea", "#1b2832"]),
  row("desat", "Cinematic", "Desaturated Drama", "Color pulled back so performance leads.", "Desaturated dramatic grade with restrained color, soft contrast, and emphasis on performance rather than palette.", ["#8d8680", "#d9d3cc", "#3f3a36"]),
  row("high-contrast", "Cinematic", "High Contrast", "Bright highlights and firm blacks.", "High-contrast cinematic light with bright highlights, firm blacks, and clear separation of planes.", ["#f8fafc", "#94a3b8", "#0f172a"]),
  row("low-contrast", "Cinematic", "Low Contrast", "A gentler, milky tonal range.", "Low-contrast cinematic light with a milky tonal range, soft blacks, and gentle highlights.", ["#e7e5e4", "#a8a29e", "#57534e"]),
  row("bleach", "Cinematic", "Bleach Bypass", "Silvered highlights and muted color.", "Bleach-bypass-inspired treatment with silvered highlights, muted color, and a stark metallic contrast.", ["#d6d3d1", "#78716c", "#1c1917"]),
  row("pastel", "Cinematic", "Filmic Pastel", "Soft candy color with film texture.", "Filmic pastel color with soft candy hues, gentle contrast, and a delicate cinematic texture.", ["#f3c6d3", "#c7d7f0", "#f6edd8"]),
  row("noir-light", "Dramatic", "Film Noir", "Hard light and deep shadow.", "High-contrast low-key lighting with deep sculpted shadows, hard directional highlights, dramatic negative space, and restrained noir tonality.", ["#f5f5f4", "#737373", "#0a0a0a"]),
  row("chiaroscuro", "Dramatic", "Chiaroscuro", "Painted pools of light.", "Chiaroscuro lighting with painted pools of brightness against large areas of darkness.", ["#fde68a", "#44403c", "#0c0a09"]),
  row("low-key", "Dramatic", "Low-Key", "Most of the frame stays dark.", "Low-key lighting with most of the frame in darkness and a few deliberate highlights.", ["#1c1917", "#a8a29e", "#0c0a09"]),
  row("high-key", "Dramatic", "High-Key", "Bright, open, and nearly shadowless.", "High-key lighting with a bright open field, soft shadows, and an airy tonal range.", ["#f8fafc", "#e2e8f0", "#cbd5e1"]),
  row("silhouette", "Dramatic", "Silhouette", "The subject is a shape against the light.", "Silhouette lighting with the subject held as a shape against a brighter background.", ["#f59e0b", "#1f2937", "#0f172a"]),
  row("rim", "Dramatic", "Rim Light", "An edge of light separates the subject.", "Rim light tracing the edge of the subject and separating them from the background.", ["#e2e8f0", "#334155", "#0f172a"]),
  row("volume", "Dramatic", "Volumetric Backlight", "Beams made visible in the air.", "Volumetric backlight with visible beams in the air and a glowing separation behind the subject.", ["#fde68a", "#78716c", "#292524"]),
  row("cyan", "Sci-Fi / Fantasy", "Cyan / Blue Futuristic", "Clean future light.", "Futuristic cyan and blue illumination with clean highlights and a designed, technological atmosphere.", ["#22d3ee", "#0e7490", "#082f49"]),
  row("neon", "Sci-Fi / Fantasy", "Neon Cyberpunk", "Magenta and cyan practicals.", "Neon cyberpunk lighting with magenta and cyan practicals, wet reflections, and dense urban color.", ["#e879f9", "#22d3ee", "#111827"]),
  row("aurora", "Sci-Fi / Fantasy", "Ethereal Aurora", "Celestial cyan, blue, and violet.", "Ethereal cyan, blue, and violet illumination with soft luminous gradients, atmospheric glow, gentle volumetric light, and celestial color separation.", ["#67e8f9", "#818cf8", "#1e1b4b"]),
  row("mystic-gold", "Sci-Fi / Fantasy", "Mystical Gold", "Warm magic in a darker room.", "Mystical gold light with warm luminous accents, deep surrounding shadow, and a sense of ritual.", ["#fbbf24", "#78350f", "#1c1917"]),
  row("bio", "Sci-Fi / Fantasy", "Alien Bioluminescence", "Living light from within the world.", "Alien bioluminescent light with living color glowing from within the environment.", ["#4ade80", "#2dd4bf", "#052e16"]),
  row("sick-green", "Horror", "Sickly Green", "Unhealthy color and uneasy fill.", "Sickly green illumination with an unhealthy cast, thin fill, and an uneasy atmosphere.", ["#84cc16", "#365314", "#14532d"]),
  row("cold-horror", "Horror", "Cold Moonlit Horror", "Blue night with nowhere to hide.", "Cold moonlit horror light with blue darkness, hard edges, and little warmth.", ["#93c5fd", "#1e3a8a", "#020617"]),
  row("deep-red", "Horror", "Deep Red Horror", "A restricted red that feels dangerous.", "Deep red horror lighting with a restricted crimson cast and heavy surrounding darkness.", ["#b91c1c", "#450a0a", "#0a0a0a"]),
  row("shadow-dom", "Horror", "Shadow-Dominant", "The dark is the subject.", "Shadow-dominant lighting in which darkness occupies most of the frame and light is scarce.", ["#292524", "#0c0a09", "#44403c"]),
  row("product", "Commercial", "Bright Product Lighting", "Clear, even, and appetizing.", "Bright product lighting with clear even illumination, crisp edges, and an appetizing finish.", ["#ffffff", "#e2e8f0", "#94a3b8"]),
  row("luxury", "Commercial", "Luxury Commercial", "Controlled highlights and rich shadow.", "Luxury commercial lighting with controlled highlights, rich shadow, and a polished material sheen.", ["#d6d3d1", "#a16207", "#1c1917"]),
  row("white-studio", "Commercial", "Clean White Studio", "A seamless bright field.", "Clean white studio light with a seamless bright field and soft, nearly invisible shadows.", ["#ffffff", "#f8fafc", "#e2e8f0"]),
  row("beauty", "Commercial", "High-End Beauty", "Flattering wrap and glowing skin.", "High-end beauty lighting with flattering wrap, glowing skin, and a soft catchlight.", ["#fce7f3", "#fff7ed", "#e7e5e4"]),
];

export const LIGHTING_CATEGORIES = [...new Set(LIGHTING_PRESETS.map((item) => item.category))];
