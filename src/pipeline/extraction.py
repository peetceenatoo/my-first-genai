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
from src.logging import (
    get_logger,
    log_ocr_available,
    log_ocr_missing,
    log_extraction_response,
    log_extraction_payload,
    log_extraction_metadata,
    log_field_matched_exactly,
    log_field_matched_normalized,
    log_field_not_found,
    log_extraction_summary,
    log_extraction_empty_payload,
    log_extraction_payload_invalid_type,
)


logger = get_logger(__name__)


DEFAULT_EXTRACTION_PROMPT = """Estrai metadati strutturati dai documenti.
Restituisci solo JSON (niente markdown, nessun commento).
Regole:
- Le chiavi nel JSON devono essere SOLO il nome del campo, senza tipo né (required). Es: "Targa", NON "Targa (string, required)".
- Le chiavi devono corrispondere esattamente ai nomi dei campi forniti.
- Usa una stringa vuota quando un valore manca o non è leggibile.
- Mantieni formulazione, maiuscole/minuscole, punteggiatura e unità del documento.
- Non inferire né inventare valori non presenti nel documento.
- I valori possono comparire senza etichetta nell'immagine: cerca il valore stesso in base al suo significato, non solo l'etichetta.
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


def _norm_key(value: str) -> str:
    return re.sub(r"[^a-z0-9]", "", value.lower())


def _align_metadata(payload: dict[str, Any], fields: list[SchemaField]) -> dict[str, Any]:
    candidate = payload.get("metadata") if isinstance(payload.get("metadata"), dict) else payload
    if not isinstance(candidate, dict):
        log_extraction_payload_invalid_type(type(candidate).__name__)
        return {}

    normalized_map: dict[str, Any] = {}
    for key, value in candidate.items():
        if isinstance(key, str):
            normalized_map[_norm_key(key)] = value

    aligned: dict[str, Any] = {}
    for field in fields:
        if field.name in candidate:
            aligned[field.name] = candidate[field.name]
            log_field_matched_exactly(field.name)
            continue

        matched = normalized_map.get(_norm_key(field.name), "")
        if matched:
            aligned[field.name] = matched
            original_key = next(
                (k for k in candidate.keys() if _norm_key(k) == _norm_key(field.name)),
                "unknown",
            )
            log_field_matched_normalized(field.name, original_key)
        else:
            aligned[field.name] = ""
            log_field_not_found(field.name)

    return aligned


def _render_field(field: SchemaField) -> str:
    required = "required" if field.required else "optional"
    enum_hint = (
        f" enum: {', '.join(str(value) for value in field.enum_values)}"
        if field.enum_values
        else ""
    )
    description = f" - {field.description}" if field.description else ""
    return f"- {field.name} ({field.field_type}, {required}){enum_hint}{description}"


def extract_metadata(
    images: list[Image.Image],
    fields: list[SchemaField],
    *,
    ocr_text: str | None = None,
    system_prompt: str | None = None,
) -> dict[str, Any]:
    config = load_config()
    prompt = system_prompt or DEFAULT_EXTRACTION_PROMPT

    field_lines = "\n".join(_render_field(field) for field in fields)
    instructions = (
        "Restituisci un oggetto JSON con chiavi che corrispondono esattamente ai nomi dei campi."
    )

    parts = [
        instructions,
        "Campi:",
        field_lines,
    ]
    if ocr_text:
        log_ocr_available(len(ocr_text))
        parts.extend(("Testo OCR:", ocr_text))
    else:
        log_ocr_missing()

    content = [{"type": "text", "text": "\n".join(parts)}]
    
    # Usa solo il testo OCR se disponibile; fallback alle immagini se OCR non fornito
    if not ocr_text and images:
        for image in images:
            content.append(
                {"type": "image_url", "image_url": {"url": _image_to_data_uri(image)}}
            )

    messages = [
        {"role": "system", "content": prompt},
        {"role": "user", "content": content},
    ]

    response = get_chat_completion(messages, model=config.extract_model)
    log_extraction_response(response)

    payload = _safe_json(response)
    log_extraction_payload(payload)

    metadata = _align_metadata(payload, fields)
    log_extraction_metadata(metadata)

    if not metadata:
        log_extraction_empty_payload()
    else:
        filled_fields = sum(1 for v in metadata.values() if str(v).strip())
        log_extraction_summary(filled_fields, len(metadata))

    return {"metadata": metadata, "confidence": {}}
