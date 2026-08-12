"""Substantive documentation pipeline with non-silent zero-candidate reasons."""

from __future__ import annotations

import re
from uuid import uuid4

from ...wiki_intelligence.classification import is_false_character_name
from ..relationship.schemas import CoDirectorRelationshipProfile
from .schemas import (
    DiscoveryWikiCandidate,
    DocumentationReason,
    DocumentationResult,
    WikiCandidateCategory,
)

_SUBSTANTIVE = re.compile(
    r"\b(character|protagonist|lives?|world|rule|when|after|before|theme|"
    r"tone|location|city|harbor|entity|event|season|story|follows)\b",
    re.I,
)
_CHAR = re.compile(
    r"\b(?:protagonist|character|hero|she|he|they)\s+(?:is|are|named|called)?\s*([A-Z][\w'’\-]{2,40})?",
    re.I,
)
_LOC = re.compile(r"\b(?:in|at|across|near)\s+(?:the\s+)?([a-z][\w'’\- ]{3,40})\b", re.I)
_RULE = re.compile(r"\b(must|never|always|rule|continuity|no\s+\w+)\b", re.I)
_EVENT = re.compile(r"\b(when|after|before|then)\b.+\b(call|arrives?|discovers?|meets?|hears?)\b", re.I)


def is_substantive_project_message(text: str) -> bool:
    t = (text or "").strip()
    if len(t) < 60:
        return False
    if t.endswith("?") and len(t) < 120:
        return False
    return bool(_SUBSTANTIVE.search(t)) or len(t) >= 160


def extract_documentation(
    user_message: str,
    *,
    project_id: str,
    source_id: str,
    relationship: CoDirectorRelationshipProfile | None = None,
) -> DocumentationResult:
    text = (user_message or "").strip()
    rel = relationship or CoDirectorRelationshipProfile()

    if rel.documentation_mode == "MANUAL_ONLY":
        return DocumentationResult(
            substantive=is_substantive_project_message(text),
            candidate_count=0,
            reason=DocumentationReason.DOCUMENTATION_DISABLED,
            summary_lines=["Documentation mode is manual-only; no automatic capture."],
        )

    if not is_substantive_project_message(text):
        return DocumentationResult(
            substantive=False,
            candidate_count=0,
            reason=DocumentationReason.NOT_SUBSTANTIVE,
            summary_lines=["Message not treated as substantive project narration."],
        )

    try:
        candidates: list[DiscoveryWikiCandidate] = []
        requires_approval = rel.documentation_mode == "PROPOSE_FOR_APPROVAL"
        status_confirmed = "CONFIRMED" if not requires_approval else "EMERGING"
        status_inferred = "INFERRED"

        # Characters — titled names and proper-name + verb patterns (format-agnostic).
        _STOP = {
            "the", "when", "after", "season", "this", "that", "with", "from", "into",
            "only", "both", "each", "what", "which", "their", "there", "these", "those",
            "interview", "reality", "history", "memory", "series", "documentary", "film",
        }
        named: list[re.Match[str]] = list(
            re.finditer(
                r"\b(?:Dr\.|Agent|Professor|Captain|Detective)?\s*([A-Z][a-z]{2,20}(?:\s+[A-Z][a-z]{2,20})?)\b",
                text,
            )
        )
        for m in named:
            name = (m.group(1) or "").strip()
            if not name or name.lower() in _STOP or len(name) < 3:
                continue
            # Prefer names that appear in narrative context (not every Capitalized Word).
            window = text[max(0, m.start() - 30) : m.end() + 90]
            if not re.search(
                r"\b(who|is|are|was|were|named|called|remembers|discovers|hears|controls|guides|interviews?|plays|portray)\b",
                window,
                re.I,
            ) and " " not in name:
                continue
            if is_false_character_name(name):
                continue
            candidates.append(
                DiscoveryWikiCandidate(
                    id=f"wiki-{uuid4().hex[:10]}",
                    project_id=project_id,
                    category=WikiCandidateCategory.CHARACTER,
                    title=name,
                    content=f"Character/person: {name}. Context: {window.strip()[:220]}",
                    status=status_confirmed,  # type: ignore[arg-type]
                    confidence=0.72,
                    source_message_ids=[source_id],
                    evidence_excerpts=[window.strip()[:160]],
                    requires_approval=requires_approval,
                )
            )
            if sum(1 for c in candidates if c.category == WikiCandidateCategory.CHARACTER) >= 8:
                break

        # Location / setting
        loc = _LOC.search(text)
        if loc:
            place = loc.group(1).strip()[:60]
            candidates.append(
                DiscoveryWikiCandidate(
                    project_id=project_id,
                    category=WikiCandidateCategory.LOCATION,
                    title=place.title(),
                    content=f"Setting/location: {place}",
                    status=status_confirmed,  # type: ignore[arg-type]
                    confidence=0.65,
                    source_message_ids=[source_id],
                    evidence_excerpts=[loc.group(0)[:160]],
                    requires_approval=requires_approval,
                )
            )

        # Event
        if _EVENT.search(text):
            snippet = text[:200]
            candidates.append(
                DiscoveryWikiCandidate(
                    project_id=project_id,
                    category=WikiCandidateCategory.EVENT,
                    title="Inciting / early event",
                    content=snippet,
                    status=status_confirmed,  # type: ignore[arg-type]
                    confidence=0.6,
                    source_message_ids=[source_id],
                    evidence_excerpts=[snippet[:160]],
                    requires_approval=requires_approval,
                )
            )

        # World rule / continuity
        if _RULE.search(text):
            candidates.append(
                DiscoveryWikiCandidate(
                    project_id=project_id,
                    category=WikiCandidateCategory.WORLD_RULE,
                    title="Continuity / world constraint",
                    content=next((s.strip() for s in re.split(r"[.!\n]", text) if _RULE.search(s)), text[:180]),
                    status=status_confirmed,  # type: ignore[arg-type]
                    confidence=0.65,
                    source_message_ids=[source_id],
                    evidence_excerpts=[text[:160]],
                    requires_approval=requires_approval,
                )
            )

        # Entity (unusual being/object)
        ent = re.search(r"\b(entity|lantern|creature|force|presence|voice)\b[^.!?]{0,80}", text, re.I)
        if ent:
            candidates.append(
                DiscoveryWikiCandidate(
                    project_id=project_id,
                    category=WikiCandidateCategory.ENTITY,
                    title="Unusual entity / presence",
                    content=ent.group(0).strip(),
                    status=status_confirmed,  # type: ignore[arg-type]
                    confidence=0.6,
                    source_message_ids=[source_id],
                    evidence_excerpts=[ent.group(0)[:160]],
                    requires_approval=requires_approval,
                )
            )

        # Theme as inferred unless explicit "theme is"
        theme_m = re.search(r"\btheme(?:s)?\s+(?:is|are|:)\s+([^.!?\n]+)", text, re.I)
        if theme_m:
            candidates.append(
                DiscoveryWikiCandidate(
                    project_id=project_id,
                    category=WikiCandidateCategory.THEME,
                    title="Theme",
                    content=theme_m.group(1).strip(),
                    status="CONFIRMED",
                    confidence=0.75,
                    source_message_ids=[source_id],
                    evidence_excerpts=[theme_m.group(0)[:160]],
                    requires_approval=requires_approval,
                )
            )
        elif any(k in text.lower() for k in ("memory", "identity", "belonging", "consequence")):
            candidates.append(
                DiscoveryWikiCandidate(
                    project_id=project_id,
                    category=WikiCandidateCategory.THEME,
                    title="Emerging theme (inferred)",
                    content="Possible thematic thread inferred from narration; not confirmed canon.",
                    status=status_inferred,  # type: ignore[arg-type]
                    confidence=0.4,
                    source_message_ids=[source_id],
                    evidence_excerpts=[text[:120]],
                    requires_approval=True,
                )
            )

        # Timeline / years (collect multiple distinct years/ranges; include near-future centuries)
        years = re.findall(r"\b((?:1[89]\d{2}|2\d{3})(?:\s*[–-]\s*(?:1[89]\d{2}|2\d{3}))?)\b", text)
        for y in list(dict.fromkeys(years))[:6]:
            candidates.append(
                DiscoveryWikiCandidate(
                    project_id=project_id,
                    category=WikiCandidateCategory.TIMELINE,
                    title=f"Timeline: {y}",
                    content=f"Chronology marker {y} appears in the project description.",
                    status=status_confirmed,  # type: ignore[arg-type]
                    confidence=0.7,
                    source_message_ids=[source_id],
                    evidence_excerpts=[y],
                    requires_approval=requires_approval,
                )
            )
        period = re.search(
            r"\b(season one|six[- ]day|final summer|period|era|episode|runtime|minutes?)\b[^.!?]{0,80}",
            text,
            re.I,
        )
        if period:
            candidates.append(
                DiscoveryWikiCandidate(
                    project_id=project_id,
                    category=WikiCandidateCategory.TIMELINE,
                    title="Period / structure note",
                    content=period.group(0).strip(),
                    status=status_confirmed,  # type: ignore[arg-type]
                    confidence=0.55,
                    source_message_ids=[source_id],
                    evidence_excerpts=[period.group(0)[:160]],
                    requires_approval=requires_approval,
                )
            )

        # Organizations / named groups (explicit lists + institutional suffixes)
        for listed in re.finditer(
            r"\b(?:organizations?|guilds?|agencies|studios?|cooperatives?)\s+include\s+([^.!\n]+)",
            text,
            re.I,
        ):
            for part in re.split(r",| and ", listed.group(1)):
                name = part.strip(" .")
                if len(name) < 3:
                    continue
                candidates.append(
                    DiscoveryWikiCandidate(
                        project_id=project_id,
                        category=WikiCandidateCategory.ENTITY,
                        title=name[:80],
                        content=f"Organization or named group: {name}",
                        status=status_confirmed,  # type: ignore[arg-type]
                        confidence=0.7,
                        source_message_ids=[source_id],
                        evidence_excerpts=[listed.group(0)[:160]],
                        requires_approval=requires_approval,
                    )
                )
        for listed in re.finditer(
            r"\b(?:locations?|settings?)\s+include\s+([^.!\n]+)",
            text,
            re.I,
        ):
            for part in re.split(r",| and ", listed.group(1)):
                place = part.strip(" .")
                if len(place) < 3:
                    continue
                candidates.append(
                    DiscoveryWikiCandidate(
                        project_id=project_id,
                        category=WikiCandidateCategory.LOCATION,
                        title=place[:80],
                        content=f"Setting/location: {place}",
                        status=status_confirmed,  # type: ignore[arg-type]
                        confidence=0.7,
                        source_message_ids=[source_id],
                        evidence_excerpts=[listed.group(0)[:160]],
                        requires_approval=requires_approval,
                    )
                )
        for org in re.finditer(
            r"\b([A-Z]{2,}(?:\d+)?(?:\s+[A-Z][a-z]+){0,3}|[A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,2}\s+(?:Research|Institute|Station|Agency|Corp|Company|Studio|Guild|Cooperative))\b",
            text,
        ):
            name = org.group(1).strip()
            if len(name) < 3 or name.lower() in _STOP:
                continue
            candidates.append(
                DiscoveryWikiCandidate(
                    project_id=project_id,
                    category=WikiCandidateCategory.ENTITY,
                    title=name,
                    content=f"Organization or named group: {name}",
                    status=status_confirmed,  # type: ignore[arg-type]
                    confidence=0.6,
                    source_message_ids=[source_id],
                    evidence_excerpts=[org.group(0)[:160]],
                    requires_approval=requires_approval,
                )
            )
            if sum(1 for c in candidates if "Organization" in c.content) >= 4:
                break

        # Theme lexicon (inferred, format-agnostic)
        theme_words = (
            "consciousness", "control", "guidance", "trust", "memory", "identity",
            "belonging", "consequence", "community", "service", "institutions",
            "humanity", "preparation", "protection", "altered history", "disclosure",
        )
        lower = text.lower()
        for tw in theme_words:
            if tw in lower:
                candidates.append(
                    DiscoveryWikiCandidate(
                        project_id=project_id,
                        category=WikiCandidateCategory.THEME,
                        title=f"Theme: {tw}",
                        content=f"Thematic thread present in the narration: {tw}.",
                        status=status_inferred,  # type: ignore[arg-type]
                        confidence=0.55,
                        source_message_ids=[source_id],
                        evidence_excerpts=[tw],
                        requires_approval=True,
                    )
                )
            if sum(1 for c in candidates if c.category == WikiCandidateCategory.THEME) >= 6:
                break

        # Project overview / format facts
        format_m = re.search(
            r"\b(six[- ]season|science[- ]fiction|mystery drama|documentary|music video|"
            r"feature film|web series|commercial|podcast|theatre|game|novel|"
            r"\d+[- ]minute)\b[^.!?]{0,100}",
            text,
            re.I,
        )
        if format_m:
            candidates.append(
                DiscoveryWikiCandidate(
                    project_id=project_id,
                    category=WikiCandidateCategory.PROJECT,
                    title="Project format / overview",
                    content=format_m.group(0).strip(),
                    status=status_confirmed,  # type: ignore[arg-type]
                    confidence=0.75,
                    source_message_ids=[source_id],
                    evidence_excerpts=[format_m.group(0)[:160]],
                    requires_approval=requires_approval,
                )
            )
        # Additional overview sentences (opening + explicit overview clause)
        if len(text) >= 160:
            sentences = [s.strip() for s in re.split(r"[.!?\n]", text) if len(s.strip()) >= 40]
            for idx, opener in enumerate(sentences[:3]):
                if idx == 0 or re.search(r"\b(overview|follows|set across|documentary|series)\b", opener, re.I):
                    candidates.append(
                        DiscoveryWikiCandidate(
                            project_id=project_id,
                            category=WikiCandidateCategory.PROJECT,
                            title=f"Project overview {idx + 1}" if idx else "Project overview",
                            content=opener[:280],
                            status=status_confirmed,  # type: ignore[arg-type]
                            confidence=0.7,
                            source_message_ids=[source_id],
                            evidence_excerpts=[opener[:160]],
                            requires_approval=requires_approval,
                        )
                    )

        # Story principle emerging
        if len(text) >= 120:
            principle = next(
                (s.strip() for s in re.split(r"[.!\n]", text) if re.search(r"\b(known by|guides?|without|in the name of)\b", s, re.I)),
                text[:220],
            )
            candidates.append(
                DiscoveryWikiCandidate(
                    project_id=project_id,
                    category=WikiCandidateCategory.STORY_PRINCIPLE,
                    title="Story principle",
                    content=principle[:220],
                    status="EMERGING",
                    confidence=0.5,
                    source_message_ids=[source_id],
                    evidence_excerpts=[principle[:160]],
                    requires_approval=True,
                )
            )

        # Extra world rules from modal clauses (sentences and semicolon lists)
        for s in re.split(r"[.!\n;]", text):
            s = s.strip()
            if len(s) < 18:
                continue
            if re.search(
                r"\b(must|never|always|only|cannot|can only|limits?|disclosure|costs? a memory|continuity)\b",
                s,
                re.I,
            ):
                candidates.append(
                    DiscoveryWikiCandidate(
                        project_id=project_id,
                        category=WikiCandidateCategory.WORLD_RULE,
                        title=f"World rule: {s[:48]}",
                        content=s[:220],
                        status=status_confirmed,  # type: ignore[arg-type]
                        confidence=0.62,
                        source_message_ids=[source_id],
                        evidence_excerpts=[s[:160]],
                        requires_approval=requires_approval,
                    )
                )
            if sum(1 for c in candidates if c.category == WikiCandidateCategory.WORLD_RULE) >= 6:
                break

        # Deduplicate by title+category
        uniq: list[DiscoveryWikiCandidate] = []
        seen: set[str] = set()
        for c in candidates:
            key = f"{c.category.value}:{c.title.lower()}"
            if key in seen:
                continue
            seen.add(key)
            uniq.append(c)

        if not uniq:
            # Ambiguous vs no facts
            if len(text) >= 80 and not _SUBSTANTIVE.search(text):
                reason = DocumentationReason.AMBIGUOUS_CONTENT
            else:
                reason = DocumentationReason.NO_PROJECT_FACTS_FOUND
            return DocumentationResult(
                substantive=True,
                candidate_count=0,
                reason=reason,
                summary_lines=[f"No Wiki candidates extracted ({reason.value})."],
            )

        confirmed = sum(1 for c in uniq if c.status == "CONFIRMED")
        emerging = sum(1 for c in uniq if c.status in {"EMERGING", "INFERRED"})
        summary = [
            f"Added: {confirmed} confirmed facts",
            f"{sum(1 for c in uniq if c.category == WikiCandidateCategory.CHARACTER)} character records",
            f"{sum(1 for c in uniq if c.category == WikiCandidateCategory.EVENT)} timeline/event notes",
            f"{emerging} emerging/inferred items",
        ]
        return DocumentationResult(
            substantive=True,
            candidate_count=len(uniq),
            candidates=uniq,
            reason=DocumentationReason.OK,
            confirmed_writes=confirmed,
            emerging_writes=emerging,
            summary_lines=summary,
        )
    except Exception:
        return DocumentationResult(
            substantive=True,
            candidate_count=0,
            reason=DocumentationReason.EXTRACTION_FAILED,
            summary_lines=["Documentation extraction failed."],
        )
