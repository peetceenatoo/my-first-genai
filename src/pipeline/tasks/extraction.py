from __future__ import annotations

import base64
import io
import json
import re
from typing import Any

from PIL import Image

from src.config import load_config
from src.domain.utils.schema_types import SchemaField
from src.integrations.clients.bedrock_client import get_chat_completion
from src.integrations.utils.textract_types import TextractDocument


DEFAULT_EXTRACTION_PROMPT = """Estrai metadati strutturati dai documenti.
Restituisci SOLO JSON valido (niente markdown, nessun commento, nessun testo extra).

REGOLE CRITICHE DI FORMATTAZIONE JSON:
- Stringhe (type=string, date): SEMPRE racchiuse tra virgolette. Ad esempio "Targa": "AA00000" e "Data": "31.07.2002"
- Numeri (type=number, integer): è fondamentale che contengano SOLO cifre da 0 a 9, SENZA nessun altro tipo di carattere come virgole, lettere o slash. Ad esempio "Massa": 1985 va bene. Qualora un numero contenga caratteri non numerici (ad esempio "11P2" o "1,385"), deve essere trattato come stringa e quindi racchiuso tra virgolette, come "11P2", "1,385" o "1/2".
- Stringhe vuote: "" (due virgolette, non null)

REGOLE DI ESTRAZIONE:
- Le chiavi nel JSON devono essere SOLO il nome del campo, senza tipo.
- Le chiavi devono corrispondere esattamente ai nomi dei campi forniti nello schema.
- Se un campo non è leggibile o non è presente, restituisci "" per quel campo (mai null), e non inventare nulla.
- Mantieni formulazione, maiuscole/minuscole, punteggiatura e unità del documento nel valore, non nella struttura JSON.
- Non inferire né inventare valori non presenti nel documento.
- I valori possono comparire senza etichetta nell'immagine: cerca il valore stesso in base al suo significato, non solo l'etichetta.
"""

def _image_to_data_uri(image: Image.Image) -> str:
    buf = io.BytesIO()
    image.save(buf, format="PNG")
    return f"data:image/png;base64,{base64.b64encode(buf.getvalue()).decode()}"


def _safe_json(text: str) -> dict[str, Any]:
    candidate = text.strip()
    fenced = re.fullmatch(r"```(?:json)?\s*(.*?)\s*```", candidate, re.S | re.I)
    if fenced:
        candidate = fenced.group(1).strip()

    try:
        parsed = json.loads(candidate)
    except json.JSONDecodeError:
        return {}

    return parsed if isinstance(parsed, dict) else {}


def _align_metadata(payload: dict[str, Any], fields: list[SchemaField]) -> dict[str, Any]:
    if not isinstance(payload, dict):
        return {}

    return {field.name: payload.get(field.name, "") for field in fields}


def _render_field(field: SchemaField) -> str:
    enum_hint = (
        f" enum: {', '.join(str(value) for value in field.enum_values)}"
        if field.enum_values
        else ""
    )
    description = f" - {field.description}" if field.description else ""
    return f"- {field.name} ({field.field_type}){enum_hint}{description}"


def extract_metadata(
    images: list[Image.Image],
    fields: list[SchemaField],
    *,
    ocr_text: str | None = None,
    textract_document: TextractDocument | None = None,
) -> dict[str, Any]:
    config = load_config()

    field_lines = "\n".join(_render_field(field) for field in fields)
    instructions = (
        "Restituisci un oggetto JSON con chiavi che corrispondono esattamente ai nomi dei campi."
    )

    parts = [
        instructions,
        "Campi:",
        field_lines,
    ]
    
    # Use TextractDocument if available (preferred), otherwise fall back to plain text or images
    if textract_document:
        # Serialize the canonical TextractDocument into a rich context
        parts.append("")
        parts.append("## DOCUMENTO STRUTTURATO ESTRATTO")
        parts.append(textract_document.to_context_string())
        # Also include metadata
        parts.append("")
        parts.append(f"Motore Textract: {textract_document.textract_api_used}")
        if textract_document.extraction_confidence is not None:
            parts.append(f"Confidence: {textract_document.extraction_confidence:.1%}")
    elif ocr_text:
        # Legacy: plain text OCR
        parts.append("")
        parts.append("## TESTO OCR")
        parts.append(ocr_text)

    content = [{"type": "text", "text": "\n".join(parts)}]

    # Use only extracted text if available; fallback to images if no OCR data provided
    if not textract_document and not ocr_text and images:
        for image in images:
            content.append(
                {"type": "image_url", "image_url": {"url": _image_to_data_uri(image)}}
            )

    messages = [
        {"role": "system", "content": DEFAULT_EXTRACTION_PROMPT},
        {"role": "user", "content": content},
    ]

    response = get_chat_completion(messages, model=config.extract_model)

    payload = _safe_json(response)

    metadata = _align_metadata(payload, fields)

    return {"metadata": metadata, "confidence": {}}
