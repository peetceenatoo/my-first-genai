from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class TextractDocument:
    """
    Canonical intermediate representation of Textract response.
    Preserves structure without apian flattening to string.
    """
    # Raw blocks from Textract (contains all relationships, geometry, IDs)
    raw_blocks: list[dict[str, Any]] = field(default_factory=list)

    # Canonical textual projection of OCR output.
    plain_text: str = ""

    # Page information
    page_number: int = 1
    num_pages: int = 1

    # Metadata
    textract_api_used: str = "DetectDocumentText"

    def to_context_string(self) -> str:
        """
        Generate a human-readable context string.
        """
        parts: list[str] = []

        if self.plain_text:
            parts.append("## OCR TEXT (CANONICAL)")
            parts.append(self.plain_text)

        return "\n".join(parts).strip()
