"""
ATLAS Schema — Pydantic-Modelle für strukturierte Agent-I/O.

Inspiriert vom Agno/Phidata Team-Agent-Pattern:
- Strukturierte Antworten mit Confidence, Delegationen und Wissenslücken
- Signal-Extraktion aus freiem Text ohne JSON-Zwang
"""

from __future__ import annotations

import re
from typing import Optional
from pydantic import BaseModel, Field, field_validator


class Delegation(BaseModel):
    to_agent: str
    task: str
    context: str = ""


class KnowledgeGap(BaseModel):
    topic: str
    reason: str = ""


class AgentResponse(BaseModel):
    """Strukturierte Antwort eines ATLAS Hermes-Agenten."""

    output: str = Field(description="Vollständiger Ausgabetext des Agenten")
    confidence: float = Field(default=0.8, ge=0.0, le=1.0)
    delegations: list[Delegation] = Field(default_factory=list)
    gaps: list[KnowledgeGap] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)

    @field_validator("confidence", mode="before")
    @classmethod
    def clamp_confidence(cls, v):
        try:
            return max(0.0, min(1.0, float(v)))
        except (TypeError, ValueError):
            return 0.8

    @classmethod
    def from_raw_text(cls, text: str, agent_name: str = "") -> "AgentResponse":
        """
        Parst eine Agent-Antwort aus freiem Text.
        Extrahiert DELEGATION:, GAP:, CONFIDENCE: Marker ohne JSON-Zwang.
        """
        delegations: list[Delegation] = []
        gaps: list[KnowledgeGap] = []
        confidence = 0.8
        clean_lines = []

        # DELEGATION: agent_name | task beschreibung
        delegation_pattern = re.compile(
            r"^DELEGATION:\s*(\w+)\s*\|\s*(.+)$", re.IGNORECASE
        )
        # GAP: thema | grund
        gap_pattern = re.compile(
            r"^(?:WISSENSL[ÜU]CKE|GAP|L[ÜU]CKE):\s*(.+?)(?:\s*\|\s*(.+))?$",
            re.IGNORECASE,
        )
        # CONFIDENCE: 0.9
        confidence_pattern = re.compile(
            r"^CONFIDENCE:\s*([\d.]+)$", re.IGNORECASE
        )

        for line in text.splitlines():
            stripped = line.strip()
            if m := delegation_pattern.match(stripped):
                delegations.append(
                    Delegation(to_agent=m.group(1).strip(), task=m.group(2).strip())
                )
            elif m := gap_pattern.match(stripped):
                gaps.append(
                    KnowledgeGap(
                        topic=m.group(1).strip(),
                        reason=(m.group(2) or "").strip(),
                    )
                )
            elif m := confidence_pattern.match(stripped):
                try:
                    confidence = float(m.group(1))
                except ValueError:
                    pass
            else:
                clean_lines.append(line)

        output = "\n".join(clean_lines).strip()

        # Einfache Tag-Extraktion aus Themenfeldern
        tags = _extract_tags(output, agent_name)

        return cls(
            output=output,
            confidence=confidence,
            delegations=delegations,
            gaps=gaps,
            tags=tags,
        )


class BlackboardSignal(BaseModel):
    """Ein Signal auf dem ATLAS Blackboard (Pheromon-Prinzip)."""

    id: str
    timestamp: str
    agent: str
    type: str  # "learning" | "gap" | "delegation" | "spawn_request"
    content: dict
    consumed: bool = False
    priority: int = Field(default=5, ge=1, le=10)
    ttl_hours: Optional[int] = None


class LearningEntry(BaseModel):
    """Eine destillierte Erkenntnis im globalen Schwarm-Pool."""

    id: str
    timestamp: str
    agent: str
    rule: str
    context: str
    confidence: float = 0.75


class RunRecord(BaseModel):
    """Vollständiger Lauf-Record für History und Analyse."""

    id: str
    timestamp: str
    agent: str
    input: str
    output: str
    confidence: float = 0.8
    delegations: list[Delegation] = Field(default_factory=list)
    duration_ms: Optional[int] = None
    feedback: Optional[str] = None


# ── Tag-Extraktion ───────────────────────────────────────────────────────────

_DOMAIN_TAGS = {
    "CATIA": ["catia"],
    "ENOVIA": ["enovia"],
    "3DEXPERIENCE": ["3dx", "3dexperience"],
    "SAP": ["sap"],
    "P&ID": ["p&id", "p&id"],
    "Power Automate": ["power automate", "powerautomate"],
    "Python": ["python"],
    "VBA": ["vba"],
    "Service Request": ["service request", "sr ", "bug report"],
    "IT Demand": ["it demand", "demand"],
    "PLM": ["plm"],
    "JLM": ["jlm"],
}


def _extract_tags(text: str, agent_name: str) -> list[str]:
    text_lower = text.lower()
    found = []
    for tag, keywords in _DOMAIN_TAGS.items():
        if any(kw in text_lower for kw in keywords):
            found.append(tag)
    if agent_name:
        found.append(agent_name)
    return list(dict.fromkeys(found))  # dedupliziert, reihenfolge erhalten
