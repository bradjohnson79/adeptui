"""Visual style intelligence registry for Qwen-Image-2512."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

REQUIRED_STYLE_KEYS: tuple[str, ...] = (
    "anime",
    "realistic_anime",
    "live_action",
    "stop_motion",
    "claymation",
    "stylized_3d_animation",
    "graphic_novel",
    "watercolor",
    "oil_painting",
    "documentary_realism",
)

_SHARED_IDENTITY_PRESERVATION_RULES: tuple[str, ...] = (
    "Treat style as a rendering layer only; the same character identity must remain intact across every style change.",
    "Do not change eye color, iris pattern, gaze character, or the recognizability of the eyes.",
    "Do not change hair color, haircut, length, silhouette, texture family, or signature hair accessories.",
    "Do not change ears, species markers, body type, body proportions, age read, limb count, or other anatomical identity anchors.",
    "Do not change wardrobe design, garment layering, signature accessories, or the placement and shape of circuitry, markings, or tattoos.",
    "Keep facial structure, expression tendencies, and personality cues recognizable even when the rendering style becomes more stylized.",
    "Never replace the subject with a redesigned variant, alternate costume, alternate ethnicity, or generic style archetype.",
)


@dataclass(frozen=True)
class VisualStyleProfile:
    key: str
    displayName: str
    identityPreservationRules: tuple[str, ...]
    renderingLanguage: str
    anatomyLanguage: str
    faceLanguage: str
    materialLanguage: str
    lightingLanguage: str
    colorLanguage: str
    cameraLanguage: str
    negativeConstraints: tuple[str, ...]
    qwen2512PromptRules: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "displayName": self.displayName,
            "identityPreservationRules": list(self.identityPreservationRules),
            "renderingLanguage": self.renderingLanguage,
            "anatomyLanguage": self.anatomyLanguage,
            "faceLanguage": self.faceLanguage,
            "materialLanguage": self.materialLanguage,
            "lightingLanguage": self.lightingLanguage,
            "colorLanguage": self.colorLanguage,
            "cameraLanguage": self.cameraLanguage,
            "negativeConstraints": list(self.negativeConstraints),
            "qwen2512PromptRules": list(self.qwen2512PromptRules),
        }


def _rules(*style_specific: str) -> tuple[str, ...]:
    return _SHARED_IDENTITY_PRESERVATION_RULES + tuple(style_specific)


def _negatives(*extra: str) -> tuple[str, ...]:
    base = (
        "No identity drift, no eye-color drift, and no hair-color drift.",
        "No ear redesign, body redesign, wardrobe replacement, or circuitry relocation.",
        "No personality rewrite, no emotional tone inversion, and no generic template face.",
        "No extra limbs, duplicate accessories, missing signature features, or age-band mutation.",
    )
    return base + tuple(extra)


def _prompt_rules(*rules: str) -> tuple[str, ...]:
    return (
        "State the identity lock first, then state the style treatment second.",
        "Use concrete visual nouns for the style instead of vague adjectives like prettier, cooler, or more cinematic.",
        "Separate immutable character traits from mutable rendering instructions in distinct clauses.",
    ) + tuple(rules)


STYLE_REGISTRY: dict[str, VisualStyleProfile] = {
    "anime": VisualStyleProfile(
        key="anime",
        displayName="Anime",
        identityPreservationRules=_rules(
            "Anime stylization may simplify surfaces and line economy, but it must preserve exact eye color, hair silhouette, ear shape, body proportions, wardrobe structure, circuitry placement, and personality.",
            "Allow expressive anime appeal only if the face still reads as the same character rather than a generic anime redesign.",
            "Keep signature costume pieces and accessories in the same arrangement even when folds, shaders, and linework become stylized.",
        ),
        renderingLanguage="Clean anime linework, shape-led silhouettes, cel shading, readable forms, and polished 2D illustration craft.",
        anatomyLanguage="Stylized anime anatomy with consistent proportions, clean hands, readable joints, and no proportion drift away from the established character body.",
        faceLanguage="Expressive anime face design with preserved eye color, preserved face shape, preserved nose and mouth placement, and the same recognizable emotional attitude.",
        materialLanguage="Simplified anime material rendering with clear fabric separation, readable hair masses, and precise treatment of accessories and circuitry details.",
        lightingLanguage="Graphic anime lighting with clear key and fill relationships, elegant shadow shapes, and restrained bloom.",
        colorLanguage="Intentional anime color scripting with controlled saturation, preserved canonical palette anchors, and strong shape separation.",
        cameraLanguage="Anime production framing that supports character readability first, with clean lenses, deliberate staging, and no identity-obscuring distortion.",
        negativeConstraints=_negatives(
            "No chibi conversion, no eye-color reinterpretation, no hairstyle redesign, and no fantasy-species embellishment beyond the locked identity.",
            "Do not convert the subject into a different anime archetype, school-uniform swap, idol redesign, or alternate-age portrayal.",
        ),
        qwen2512PromptRules=_prompt_rules(
            "Explicitly say 'same character, anime rendering only' or equivalent to prevent style drift.",
            "Mention preserved silhouette anchors before anime flourishes such as linework, cel shading, or speed-line energy.",
        ),
    ),
    "realistic_anime": VisualStyleProfile(
        key="realistic_anime",
        displayName="Realistic Anime",
        identityPreservationRules=_rules(
            "Blend anime clarity with grounded realism without changing eye color, hair identity, ears, body, wardrobe, circuitry, or personality.",
            "Facial realism may add skin nuance and depth, but the result must still read as the same person instead of a recast live-action performer.",
            "Preserve the exact costume layout and character silhouette while increasing believable textures and light behavior.",
        ),
        renderingLanguage="Hybrid realistic-anime illustration with refined line control, grounded shading, believable depth, and stylized clarity.",
        anatomyLanguage="Near-real anatomy with elegant stylization, disciplined proportions, and faithful preservation of the established body plan.",
        faceLanguage="Refined realistic-anime facial rendering with preserved eye hue, preserved hair framing, controlled skin detail, and familiar expression language.",
        materialLanguage="Believable fabrics, skin, metal, and hair with stylized cleanup and no substitution of key costume or circuitry materials.",
        lightingLanguage="Cinematic hybrid lighting with soft falloff, shape-preserving highlights, and readable contrast.",
        colorLanguage="Controlled realistic palette with anime-inspired separation, preserved identity colors, and tasteful saturation discipline.",
        cameraLanguage="Illustrative cinematic coverage with grounded lenses, flattering perspective, and composition that protects facial recognition.",
        negativeConstraints=_negatives(
            "No full photoreal conversion, no recasting into a different ethnicity or age read, and no beauty-filter face homogenization.",
            "Do not trade the established costume or silhouette for generic fashion-realism styling.",
        ),
        qwen2512PromptRules=_prompt_rules(
            "Describe the prompt as anime-rooted identity with realistic shading, not as a new person photographed in costume.",
            "Call out preserved face geometry and canonical palette locks before adding realistic skin or material detail.",
        ),
    ),
    "live_action": VisualStyleProfile(
        key="live_action",
        displayName="Live Action",
        identityPreservationRules=_rules(
            "Translate the same character into live-action photography without changing eye color, hair silhouette, ears, body, wardrobe, circuitry, or personality.",
            "Live-action treatment must behave like faithful casting and costuming of the same character, never a redesign into a different performer or ethnicity.",
            "Preserve prosthetic or species-defining ear shapes, costume architecture, and circuitry placement as physical production design elements.",
        ),
        renderingLanguage="Photographic live-action realism with production-grade costuming, believable skin response, and grounded on-set detail.",
        anatomyLanguage="Human-real anatomical fidelity that preserves the canonical body build, age band, limb structure, and species markers.",
        faceLanguage="Photographic face rendering with preserved eye color, preserved facial proportions, and authentic personality expression rather than glamour retouching.",
        materialLanguage="Real-world fabrics, leather, wood, metal, skin, and circuitry rendered as practical wardrobe and prop materials.",
        lightingLanguage="Live-action cinematography with physically plausible key light, practical motivation, controlled contrast, and production realism.",
        colorLanguage="Photographic color grading with preserved wardrobe palette anchors and no palette drift that would alter the character read.",
        cameraLanguage="Live-action lens language with grounded focal lengths, physical staging, and no stylization that erases identity cues.",
        negativeConstraints=_negatives(
            "No actor recasting drift, no fashion makeover, no cosmetic surgery drift, and no replacement of prosthetic ears or circuitry with generic realism.",
            "Do not flatten the personality into a neutral mannequin performance just because the style becomes photographic.",
        ),
        qwen2512PromptRules=_prompt_rules(
            "Write the prompt as a faithful live-action adaptation of the same character, explicitly locking cast, costume, and identity features.",
            "Specify practical-production equivalents for nonhuman or stylized features instead of omitting them.",
        ),
    ),
    "stop_motion": VisualStyleProfile(
        key="stop_motion",
        displayName="Stop Motion",
        identityPreservationRules=_rules(
            "Convert the same character into stop-motion fabrication while preserving eye color coding, hair silhouette, ear geometry, body proportions, wardrobe layout, circuitry placement, and personality.",
            "Puppet joints, armature logic, stitched costumes, and miniature sets are allowed, but they must describe the same character design rather than a simplified replacement.",
            "Keep the subject recognizable even with handcrafted fabrication artifacts such as visible seams, sculpted textures, and miniature scale cues.",
        ),
        renderingLanguage="Handcrafted stop-motion aesthetic with miniature sets, tactile fabrication, frame-by-frame charm, and cinematic staging.",
        anatomyLanguage="Puppet anatomy guided by the canonical silhouette, with articulated joints and armature logic that preserve body identity.",
        faceLanguage="Stop-motion facial design with replaceable-expression or sculpted-face logic that keeps the same eye color, face shape, and personality read.",
        materialLanguage="Fabricated materials such as foam, resin, felt, wire, carved wood, cloth, and painted surfaces with tactile craftsmanship.",
        lightingLanguage="Miniature-stage lighting with practical falloff, cinematic motivated sources, and controlled shadows suited to stop-motion photography.",
        colorLanguage="Rich handcrafted color design that preserves canonical palette anchors while embracing miniature-art direction.",
        cameraLanguage="Stop-motion camera grammar with dolly-like moves, macro-friendly framing, and physical miniature depth cues.",
        negativeConstraints=_negatives(
            "No redesign into a generic puppet with missing ears, altered costume patterning, or simplified circuitry marks.",
            "Do not swap hair silhouette for a different sculpt just because the medium is fabricated.",
        ),
        qwen2512PromptRules=_prompt_rules(
            "Name the fabrication approach after the identity lock: same character, stop-motion puppet interpretation only.",
            "Include miniature build details, seams, and handcrafted materials without loosening any identity anchors.",
        ),
    ),
    "claymation": VisualStyleProfile(
        key="claymation",
        displayName="Claymation",
        identityPreservationRules=_rules(
            "Render the same character as sculpted clay without changing eye color, hair massing, ear shape, body build, wardrobe construction, circuitry motifs, or personality.",
            "Clay fingerprints, sculpt marks, and squash-and-stretch are allowed only if the subject remains the same recognizable character.",
            "Preserve costume silhouettes and accessory placement even when fabrics and props are translated into clay forms.",
        ),
        renderingLanguage="Expressive claymation with hand-sculpted forms, tactile fingerprints, charming imperfections, and staged animation appeal.",
        anatomyLanguage="Clay-sculpted anatomy with controlled squash-and-stretch, stable proportions, and clear preservation of the original body identity.",
        faceLanguage="Sculpted clay face with preserved eye hue, preserved feature spacing, and strong personality performance embedded in the pose and expression.",
        materialLanguage="Matte and semi-gloss clay surfaces, sculpted costume forms, stylized prop clay, and handcrafted tactile detail.",
        lightingLanguage="Playful studio lighting for clay sets with readable form shadows, warm specular response, and handcrafted depth.",
        colorLanguage="Bold clay color blocking with preserved identity colors, charming saturation, and no palette-based identity drift.",
        cameraLanguage="Physical set photography and animation framing that embraces clay scale and handmade presence without obscuring core identity.",
        negativeConstraints=_negatives(
            "No gummy facial collapse, no costume substitution, and no exaggerated squash that rewrites body identity.",
            "Do not turn the character into a generic blob-like clay figure with lost ear, hair, or circuitry details.",
        ),
        qwen2512PromptRules=_prompt_rules(
            "State preserved character locks first, then add claymation cues like fingerprints, sculpt seams, and stop-frame charm.",
            "Use sculptural wording for wardrobe and accessories so the medium changes without the design changing.",
        ),
    ),
    "stylized_3d_animation": VisualStyleProfile(
        key="stylized_3d_animation",
        displayName="Stylized 3D Animation",
        identityPreservationRules=_rules(
            "Upgrade the same character into stylized 3D animation while keeping identity anchors untouched.",
            "Topology, rigging, and shader changes must preserve recognizable facial structure, body proportions, wardrobe silhouette, and signature accessories.",
        ),
        renderingLanguage="Stylized 3D animation with polished shapes, expressive rigging appeal, cinematic surfacing, and production-quality character design.",
        anatomyLanguage="Animation-friendly anatomy with clean forms, readable joints, and faithful preservation of the original body plan.",
        faceLanguage="Appealing 3D facial design with preserved eye color, preserved silhouette, and expressive performance consistent with the same personality.",
        materialLanguage="Stylized shaders for skin, hair, cloth, wood, and circuitry details with clear separation and production-ready readability.",
        lightingLanguage="Animated feature-style lighting with shape-friendly rim light, readable keys, and elegant shadow control.",
        colorLanguage="Vibrant but disciplined palette design with preserved identity colors and strong form hierarchy.",
        cameraLanguage="Animated feature framing with lens clarity, readable staging, and no distortion that breaks continuity.",
        negativeConstraints=_negatives(
            "No mascot redesign, no toyification that removes anatomical identity, and no wardrobe simplification that deletes signature pieces.",
        ),
        qwen2512PromptRules=_prompt_rules(
            "Describe stylized 3D as a surfacing and rigging treatment applied to the same character design.",
        ),
    ),
    "graphic_novel": VisualStyleProfile(
        key="graphic_novel",
        displayName="Graphic Novel",
        identityPreservationRules=_rules(
            "Translate the same character into graphic-novel illustration without changing their locked visual identity.",
            "Heavy inks, halftones, and panel drama must support the same face, costume, body, and personality rather than inventing a new comic-book persona.",
        ),
        renderingLanguage="Graphic-novel illustration with bold inks, controlled hatching, dramatic shapes, and cinematic panel energy.",
        anatomyLanguage="Illustrative anatomy with strong silhouette readability, deliberate exaggeration, and stable body identity.",
        faceLanguage="Ink-driven facial rendering that preserves the eye color intent, face geometry, and signature emotional attitude.",
        materialLanguage="Stylized ink-and-tone material separation for cloth, skin, hair, wood, and circuitry, with readable graphic patterning.",
        lightingLanguage="High-contrast noir or dramatic comic lighting with crisp value design and shape-first clarity.",
        colorLanguage="Selective graphic color with preserved character palette anchors, deliberate spot colors, and print-aware contrast.",
        cameraLanguage="Panel-conscious composition with strong storytelling angles and identity-safe framing.",
        negativeConstraints=_negatives(
            "No superhero-costume rewrite, no comic-book age-up, and no generic noir replacement face.",
        ),
        qwen2512PromptRules=_prompt_rules(
            "Use explicit panel-art vocabulary such as inks, halftones, hatching, and splash-page drama after the identity lock.",
        ),
    ),
    "watercolor": VisualStyleProfile(
        key="watercolor",
        displayName="Watercolor",
        identityPreservationRules=_rules(
            "Apply watercolor treatment as a painterly medium shift only; do not soften away any locked identity traits.",
            "Edges may bloom and washes may feather, but the same character features, costume architecture, and personality must remain readable.",
        ),
        renderingLanguage="Luminous watercolor illustration with layered washes, paper texture, soft blooms, and elegant edge control.",
        anatomyLanguage="Painterly but disciplined anatomy that protects recognizable pose, proportions, and character structure.",
        faceLanguage="Watercolor facial rendering with preserved eye hue, preserved hair framing, and delicate but accurate emotional expression.",
        materialLanguage="Transparent wash handling for skin, fabric, wood, hair, and circuitry accents, preserving design boundaries despite soft transitions.",
        lightingLanguage="Atmospheric watercolor light with glowing highlights, subtle reflected color, and shape-preserving value control.",
        colorLanguage="Transparent layered color with preserved identity palette anchors and restrained muddy mixing.",
        cameraLanguage="Illustrative framing with airy composition, readable focal hierarchy, and no wash-heavy cropping that loses identity.",
        negativeConstraints=_negatives(
            "No facial dissolution, no washed-out eye color loss, and no costume simplification into anonymous shapes.",
        ),
        qwen2512PromptRules=_prompt_rules(
            "Mention paper, washes, blooms, and edge diffusion only after anchoring the immutable identity details.",
        ),
    ),
    "oil_painting": VisualStyleProfile(
        key="oil_painting",
        displayName="Oil Painting",
        identityPreservationRules=_rules(
            "Restyle the same character through oil-paint language without changing any locked identity traits.",
            "Brushwork, impasto, and painterly interpretation must preserve face recognition, body identity, wardrobe structure, circuitry, and personality.",
        ),
        renderingLanguage="Rich oil-paint rendering with confident brushwork, layered pigment, tactile surface depth, and gallery-grade composition.",
        anatomyLanguage="Painterly anatomy with strong structural draftsmanship and preserved body identity beneath expressive brushwork.",
        faceLanguage="Portrait-grade face handling with preserved eye color, preserved feature spacing, and emotional fidelity to the same character.",
        materialLanguage="Impasto and glaze treatment for skin, cloth, hair, wood, and circuitry details without swapping materials or costume logic.",
        lightingLanguage="Painterly chiaroscuro or luminous studio lighting with robust form modeling and elegant highlight control.",
        colorLanguage="Deep pigment relationships with preserved identity colors, rich harmonies, and no hue drift on critical features.",
        cameraLanguage="Portrait or narrative painting composition that centers recognizability and avoids identity-obscuring abstraction.",
        negativeConstraints=_negatives(
            "No historical-costume rewrite, no baroque character substitution, and no abstraction that erases signature features.",
        ),
        qwen2512PromptRules=_prompt_rules(
            "Use painterly terminology like impasto, glaze, and brush rhythm after specifying the non-negotiable identity locks.",
        ),
    ),
    "documentary_realism": VisualStyleProfile(
        key="documentary_realism",
        displayName="Documentary Realism",
        identityPreservationRules=_rules(
            "Present the same character through documentary realism without changing any canonical visual identity anchors.",
            "The image should feel observed and truthful, but still preserve species markers, wardrobe, circuitry, and personality instead of normalizing them away.",
        ),
        renderingLanguage="Observed documentary realism with unvarnished detail, truthful environment response, and restrained editorial styling.",
        anatomyLanguage="Naturalistic anatomy and posture that preserve the real character body without glamorization or distortion.",
        faceLanguage="Documentary face treatment with preserved eye color, honest skin detail, recognizable expression habits, and emotional authenticity.",
        materialLanguage="Real-world surfaces and wardrobe behavior rendered with evidence-based realism and no costume redesign.",
        lightingLanguage="Available-light or practically motivated documentary lighting with truthful contrast and minimal stylized artifice.",
        colorLanguage="Natural color response with preserved identity palette anchors and restrained grading that does not recode the character.",
        cameraLanguage="Observational camera language with grounded framing, truthful focal lengths, and no spectacle that overpowers identity.",
        negativeConstraints=_negatives(
            "No fashion-editorial glamour drift, no de-aging or age-up drift, and no removal of distinctive nonhuman or handcrafted identity features.",
        ),
        qwen2512PromptRules=_prompt_rules(
            "Frame the style as observational realism applied to the same character, with identity-first wording and restrained stylistic flourish.",
        ),
    ),
}


def get_profile(key: str) -> VisualStyleProfile:
    try:
        return STYLE_REGISTRY[key]
    except KeyError as exc:
        available = ", ".join(REQUIRED_STYLE_KEYS)
        raise KeyError(f"Unknown visual style '{key}'. Available styles: {available}") from exc


def list_profiles() -> tuple[VisualStyleProfile, ...]:
    return tuple(STYLE_REGISTRY[key] for key in REQUIRED_STYLE_KEYS)


def registry_as_dict() -> list[dict[str, Any]]:
    return [profile.to_dict() for profile in list_profiles()]
