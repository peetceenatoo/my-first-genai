from __future__ import annotations

import base64
import io
import json
import re
from typing import Any

from PIL import Image

from src.config import load_config
from src.domain.models import SchemaField
from src.integrations.bedrock_client import get_chat_completion


DEFAULT_EXTRACTION_PROMPT = """You extract structured metadata from documents.
Return JSON only (no markdown, no commentary).
Rules:
- Keys must exactly match the provided field names.
- Use empty string when a value is missing or unreadable.
- Preserve the document's wording, casing, punctuation, and units.
- Do not infer or fabricate values not present in the document.
"""


def _image_to_data_uri(image: Image.Image) -> str:
    buf = io.BytesIO()
    image.save(buf, format="PNG")
    return f"data:image/png;base64,{base64.b64encode(buf.getvalue()).decode()}"


def _safe_json(text: str) -> dict[str, Any]:
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, re.S)
        if match:
            try:
                return json.loads(match[0])
            except json.JSONDecodeError:
                return {}
    return {}


def _render_field(field: SchemaField) -> str:
    required = "required" if field.required else "optional"
    enum_hint = f" enum: {', '.join(field.enum_values)}" if field.enum_values else ""
    description = f" - {field.description}" if field.description else ""
    return f"- {field.name} ({field.field_type}, {required}){enum_hint}{description}"


def extract_metadata(
    images: list[Image.Image],
    fields: list[SchemaField],
    *,
    ocr_text: str | None = None,
    with_confidence: bool = False,
    system_prompt: str | None = None,
) -> dict[str, Any]:
    config = load_config()
    prompt = system_prompt or DEFAULT_EXTRACTION_PROMPT

    field_lines = "\n".join(_render_field(field) for field in fields)
    instructions = "Return a JSON object with keys exactly matching the field names."
    if with_confidence:
        instructions = (
            "Return JSON with two objects: `metadata` (field values) and "
            "`confidence` (0-1 confidence per field)."
        )

    parts = [
        instructions,
        "Fields:",
        field_lines,
    ]
    if ocr_text:
        parts.extend(("OCR text:", ocr_text))
    content = [{"type": "text", "text": "\n".join(parts)}]
    for image in images or []:
        content.append(
            {"type": "image_url", "image_url": {"url": _image_to_data_uri(image)}}
        )

    messages = [
        {"role": "system", "content": prompt},
        {"role": "user", "content": content},
    ]

    response = get_chat_completion(messages, model=config.extract_model)
    payload = _safe_json(response)

    if with_confidence:
        metadata = payload.get("metadata", payload if isinstance(payload, dict) else {})
        confidence = payload.get("confidence", {})
    else:
        metadata = payload if isinstance(payload, dict) else {}
        confidence = {}

    return {"metadata": metadata, "confidence": confidence}
