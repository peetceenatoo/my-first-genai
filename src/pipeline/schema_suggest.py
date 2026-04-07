from __future__ import annotations

import base64
import io
import json
import re
from typing import Any

from PIL import Image

from src.config import load_config
from src.integrations.bedrock_client import get_chat_completion


DEFAULT_SCHEMA_PROMPT = """
You design compact JSON schemas for metadata extraction.
Return JSON only with keys: name, description, fields.
Each field is an object with keys: name, type, required, description, example, enum.
Use types: string, number, integer, boolean, date, enum, object, array.
Keep field names short, lowercase, and underscore-separated.
Only include fields clearly supported by the document.
If unsure, leave description and example empty, and required false.
Do not add extra keys or commentary.
Aim for 6-12 fields when the document provides enough signals.
"""


def _image_to_data_uri(image: Image.Image) -> str:
    buf = io.BytesIO()
    image.save(buf, format="PNG")
    return f"data:image/png;base64,{base64.b64encode(buf.getvalue()).decode()}"


def _safe_json(text: str) -> dict[str, Any]:
    try:
        payload = json.loads(text)
        return payload if isinstance(payload, dict) else {}
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, re.S)
        if match:
            try:
                payload = json.loads(match[0])
                return payload if isinstance(payload, dict) else {}
            except json.JSONDecodeError:
                return {}
    return {}


def _normalize_field_name(label: str) -> str:
    name = label.strip().lower()
    name = re.sub(r"[^a-z0-9]+", "_", name)
    name = re.sub(r"_+", "_", name).strip("_")
    return name


def _humanize_name(label: str) -> str:
    base = re.sub(r"\.[a-zA-Z0-9]+$", "", label)
    base = re.sub(r"[_\-]+", " ", base).strip()
    return base.title() if base else "Generated Schema"


def _infer_field_type(label: str) -> str:
    lowered = label.lower()
    if "date" in lowered:
        return "date"
    if "amount" in lowered or "total" in lowered or "price" in lowered:
        return "number"
    if "qty" in lowered or "quantity" in lowered or "count" in lowered:
        return "integer"
    return "string"


def _extract_field_candidates(
    text: str | None, *, limit: int = 14
) -> list[dict[str, Any]]:
    if not text:
        return []
    candidates: list[str] = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        match = re.split(r"\s*[:\-]\s*", line, maxsplit=1)
        label = match[0].strip() if match else ""
        if len(label) < 3 or len(label) > 40:
            continue
        if not re.search(r"[a-zA-Z]", label):
            continue
        candidates.append(label)

    seen: set[str] = set()
    fields: list[dict[str, Any]] = []
    for label in candidates:
        field_name = _normalize_field_name(label)
        if not field_name or field_name in seen:
            continue
        seen.add(field_name)
        fields.append(
            {
                "name": field_name,
                "type": _infer_field_type(label),
                "required": False,
                "description": "",
                "example": "",
                "enum": [],
            }
        )
        if len(fields) >= limit:
            break
    return fields


def suggest_schema_from_sample(
    *,
    images: list[Image.Image],
    ocr_text: str | None = None,
    sample_name: str | None = None,
    system_prompt: str | None = None,
) -> dict[str, Any]:
    config = load_config()
    prompt = system_prompt or DEFAULT_SCHEMA_PROMPT

    parts = [
        "Analyze the document and propose a concise schema draft.",
        "Return JSON only.",
    ]
    if sample_name:
        parts.append(f"Filename hint: {sample_name}")
    if ocr_text:
        parts.extend(("OCR text:", ocr_text))
    content = [{"type": "text", "text": "\n".join(parts)}]
    content.extend(
        {"type": "image_url", "image_url": {"url": _image_to_data_uri(image)}}
        for image in images or []
    )
    messages = [
        {"role": "system", "content": prompt},
        {"role": "user", "content": content},
    ]
    response = get_chat_completion(messages, model=config.extract_model)
    payload = _safe_json(response) or {}

    raw_fields = payload.get("fields") if isinstance(payload, dict) else None
    if not isinstance(raw_fields, list) or not raw_fields:
        raw_fields = _extract_field_candidates(ocr_text)

    cleaned_fields: list[dict[str, Any]] = []
    seen_names: set[str] = set()
    for field in raw_fields:
        if not isinstance(field, dict):
            continue
        name = _normalize_field_name(str(field.get("name", "")))
        if not name or name in seen_names:
            continue
        seen_names.add(name)
        cleaned_fields.append(
            {
                "name": name,
                "type": field.get("type", field.get("field_type", "string")),
                "required": bool(field.get("required", False)),
                "description": field.get("description", ""),
                "example": field.get("example", ""),
                "enum": field.get("enum", field.get("enum_values", [])) or [],
            }
        )

    if not cleaned_fields:
        cleaned_fields = _extract_field_candidates(ocr_text)

    schema_name = (payload.get("name") if isinstance(payload, dict) else None) or _humanize_name(sample_name or "Generated Schema")

    schema_description = (
        payload.get("description", "") if isinstance(payload, dict) else ""
    )

    return {
        "name": schema_name,
        "description": schema_description,
        "fields": cleaned_fields,
    }
