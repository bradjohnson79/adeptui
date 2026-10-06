"""Spoken language for a Film Timeline shot.

The dropdown is the authority. Audio heard in an earlier batch is evidence
of what the model did, not a new language for the next batch.

Video models on this Timeline take that authority as prompt conditioning.
MiniMax H3 has no language input on the reference node, so the sentence
below is how the renderer is told. The same sentence is appended for every
other model that reads the generation prompt.
"""

from __future__ import annotations

from dataclasses import dataclass

# Codes match the Timeline V1 inspector. Mandarin keeps ``zh``. Cantonese,
# Arabic, Russian, and a custom name are the Timeline V2 additions.
OPTIONS: tuple[tuple[str, str], ...] = (
    ("en", "English"),
    ("fr", "French"),
    ("es", "Spanish"),
    ("de", "German"),
    ("it", "Italian"),
    ("pt", "Portuguese"),
    ("ja", "Japanese"),
    ("ko", "Korean"),
    ("zh", "Mandarin Chinese"),
    ("yue", "Cantonese"),
    ("hi", "Hindi"),
    ("ar", "Arabic"),
    ("ru", "Russian"),
    ("custom", "Other / Custom"),
)

_LABELS = dict(OPTIONS)


@dataclass(frozen=True)
class SpokenLanguage:
    code: str
    custom: str
    label: str


def normalize(code: str | None, custom: str | None = None) -> SpokenLanguage:
    token = str(code or "").strip().lower().replace("_", "-").split("-")[0]
    if token in {"mandarin", "chinese"}:
        token = "zh"
    if token == "cantonese":
        token = "yue"
    extra = " ".join(str(custom or "").split())[:80]
    if token == "custom":
        if not extra:
            return SpokenLanguage("en", "", "English")
        return SpokenLanguage("custom", extra, extra)
    if token in _LABELS:
        return SpokenLanguage(token, "", _LABELS[token])
    return SpokenLanguage("en", "", "English")


def clause(language: SpokenLanguage) -> str:
    name = language.label
    return (
        f"All spoken dialogue in this scene is in {name}. "
        "Do not introduce another spoken language unless the Timed Prompt explicitly asks for it. "
        "Speech heard in a reference or an earlier batch does not change this language. "
        "If nobody speaks, keep the scene silent."
    )


def apply_to_prompt(prompt: str, language: SpokenLanguage) -> str:
    line = clause(language)
    body = str(prompt or "").strip()
    if line in body:
        return body
    if not body:
        return line
    return f"{body}\n\n{line}"
