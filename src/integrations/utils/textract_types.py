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
class TextractTable:
    """Table extracted from document."""
    headers: list[str] = field(default_factory=list)
    rows: list[list[str]] = field(default_factory=list)


@dataclass
class TextractQuery:
    """Query result from QUERIES feature."""
    query_text: str
    answer: str
    confidence: float = 1.0


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
    tables: list[TextractTable] = field(default_factory=list)
    queries: list[TextractQuery] = field(default_factory=list)

    # Plain text as fallback
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
            "tables": [{"headers": t.headers, "rows": t.rows} for t in self.tables],
            "queries": [asdict(q) for q in self.queries],
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
        Generate a human-readable context string for LLM prompt.
        Structure: Forms, Tables, Query Results, Plain Text.
        """
        parts: list[str] = []

        if self.forms:
            parts.append("## FORM FIELDS (Key-Value Pairs)")
            for form in self.forms:
                conf = f" [confidence: {form.value_confidence:.1%}]" if form.value_confidence < 1.0 else ""
                parts.append(f"  {form.key}: {form.value}{conf}")
            parts.append("")

        if self.tables:
            parts.append("## TABLES")
            for i, table in enumerate(self.tables, start=1):
                parts.append(f"Table {i}:")
                if table.headers:
                    parts.append(f"  Headers: {' | '.join(table.headers)}")
                for row in table.rows:
                    parts.append(f"  {' | '.join(row)}")
                parts.append("")

        if self.queries:
            parts.append("## QUERY RESULTS (Field Lookup)")
            for query in self.queries:
                conf = f" [confidence: {query.confidence:.1%}]" if query.confidence < 1.0 else ""
                parts.append(f"  {query.query_text}: {query.answer}{conf}")
            parts.append("")

        if self.plain_text:
            parts.append("## PLAIN TEXT")
            parts.append(self.plain_text)

        return "\n".join(parts).strip()
