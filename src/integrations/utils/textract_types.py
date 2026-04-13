from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any
import json


@dataclass
class TextractForm:
    """Key-value pair extracted from forms."""
    key: str
    value: str
    key_confidence: float = 1.0
    value_confidence: float = 1.0


@dataclass
class TextractDocument:
    """
    Canonical intermediate representation of Textract response.
    Preserves structure without apian flattening to string.
    """
    # Raw blocks from Textract (contains all relationships, geometry, IDs)
    raw_blocks: list[dict[str, Any]] = field(default_factory=list)

    # Extracted structured data
    forms: list[TextractForm] = field(default_factory=list)

    # Canonical textual projection of OCR output.
    plain_text: str = ""

    # Page information
    page_number: int = 1
    num_pages: int = 1

    # Metadata
    textract_api_used: str = "AnalyzeDocument"  # or DetectDocumentText
    extraction_confidence: float | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "forms": [asdict(f) for f in self.forms],
            "plain_text": self.plain_text,
            "page_number": self.page_number,
            "num_pages": self.num_pages,
            "textract_api_used": self.textract_api_used,
            "extraction_confidence": self.extraction_confidence,
        }

    def to_json(self) -> str:
        """Convert to JSON string (raw_blocks excluded for readability)."""
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)

    def to_context_string(self) -> str:
        """
        Generate a human-readable context string.
        Structure: Forms, Canonical OCR Text.
        """
        parts: list[str] = []

        if self.forms:
            parts.append("## FORM FIELDS (Key-Value Pairs)")
            for form in self.forms:
                conf = f" [confidence: {form.value_confidence:.1%}]" if form.value_confidence < 1.0 else ""
                parts.append(f"  {form.key}: {form.value}{conf}")
            parts.append("")

        if self.plain_text:
            parts.append("## OCR TEXT (CANONICAL)")
            parts.append(self.plain_text)

        return "\n".join(parts).strip()
