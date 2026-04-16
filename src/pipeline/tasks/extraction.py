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


DEFAULT_EXTRACTION_PROMPT = \
"""
Estrai metadati strutturati dal documento. Restituisci SOLO JSON valido (niente markdown, nessun commento, nessun testo extra).

CONTESTO DI INPUT:
- Potresti ricevere testo OCR/Textract oppure direttamente una o piu immagini del documento.
- In entrambi i casi devi estrarre i campi richiesti usando solo evidenza presente nel documento.

REGOLE CRITICHE DI FORMATTAZIONE JSON:
- Rispetta il tipo di campo indicato nello schema JSON: valori stringa (type=string, date) SEMPRE racchiusi tra virgolette, valori numerici (type=number, integer) mai racchiusi tra virgolette.
- Rispetta il tipo di campo anche nel caso di valori vuoti: stringhe vuote "" (due virgolette, non null), numeri vuoti null (senza virgolette).

REGOLE DI ESTRAZIONE CRITICHE:
- Le chiavi JSON presenti nella tua risposta devono corrispondere ESATTAMENTE ai nomi dei campi forniti nello schema. In generale, è FONDAMENTALE che nella chiave del JSON fornito come risposta non sia aggiunto nè rimosso nulla al nome del campo nello schema fornito. 
- I campi individuati devono essere identici in numero a quelli indicati nello schema: non devono esserci campi aggiuntivi, nè mancanti. 
- Rispetta la formulazione, le maiuscole/minuscole, la punteggiatura e le unità dei valori estratti dal testo del documento.
- PRIORITÀ ASSOLUTA alle etichette con codici alfanumerici (es. "(A)", "(D.1)", ecc.), se utilizzate dal documento: cerca SEMPRE il valore immediatamente associato a queste etichette.
- Se una etichetta non è seguita da un valore o il valore non rispetta la descrizione del campo, restituisci un valore vuoto piuttosto che inferire o utilizzare valori trovati altrove.
- Non inventare mai valori mancanti.
"""

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
    description = f" - {field.description}" if field.description else ""
    return f"- Name: {field.name} - Type: {field.field_type}{description}"


def _encode_data_uri(image: Image.Image) -> str:
    buf = io.BytesIO()
    image.save(buf, format="PNG")
    encoded = base64.b64encode(buf.getvalue()).decode()
    return f"data:image/png;base64,{encoded}"


def _build_schema_block(fields: list[SchemaField]) -> str:
    return "\n".join(_render_field(field) for field in fields)


def _run_extraction_request(
    *,
    fields: list[SchemaField],
    user_content: list[dict[str, Any]],
    model: str,
    should_log_prompt: bool,
    should_log_response: bool,
) -> dict[str, Any]:
    field_lines = _build_schema_block(fields)

    messages = [
        {"role": "system", "content": DEFAULT_EXTRACTION_PROMPT},
        {"role": "user", "content": user_content},
    ]

    if should_log_prompt:
        print(
            "===== EXTRACTION PROMPT =====\n"
            "[SYSTEM - START]\n"
            f"{DEFAULT_EXTRACTION_PROMPT}\n"
            "[SYSTEM - END]\n\n"
            "[SCHEMA - START]\n"
            f"{field_lines}\n"
            "[SCHEMA - END]\n\n"
            "===== END EXTRACTION PROMPT =====\n",
            flush=True,
        )

    response = get_chat_completion(messages, model=model)

    if should_log_response:
        print(
            "===== EXTRACTION RESPONSE =====\n"
            f"{response.strip() or '(empty)'}\n"
            "===== END EXTRACTION RESPONSE =====\n\n\n",
            flush=True,
        )

    payload = _safe_json(response)
    metadata = _align_metadata(payload, fields)
    return {"metadata": metadata}


def extract_metadata(
    fields: list[SchemaField],
    *,
    textract_document: TextractDocument,
    model: str | None = None,
    log: bool = True,
    log_prompt: bool | None = None,
    log_response: bool | None = None,
) -> dict[str, Any]:
    config = load_config()

    should_log_prompt = log if log_prompt is None else log_prompt
    should_log_response = log if log_response is None else log_response

    field_lines = _build_schema_block(fields)
    context_text = textract_document.to_context_string() or "(empty OCR context)"
    user_text = "\n".join(
        [
            "## SCHEMA",
            field_lines,
            "",
            "## INPUT TYPE",
            "OCR_TEXT",
            "",
            "## DOCUMENT CONTEXT",
            context_text,
        ]
    )

    return _run_extraction_request(
        fields=fields,
        user_content=[{"type": "text", "text": user_text}],
        model=model or config.id_extract_model or config.extract_model,
        should_log_prompt=should_log_prompt,
        should_log_response=should_log_response,
    )


def extract_metadata_from_images(
    fields: list[SchemaField],
    *,
    images: list[Image.Image],
    model: str,
    log: bool = True,
    log_prompt: bool | None = None,
    log_response: bool | None = None,
) -> dict[str, Any]:
    should_log_prompt = log if log_prompt is None else log_prompt
    should_log_response = log if log_response is None else log_response

    field_lines = _build_schema_block(fields)
    intro = "\n".join(
        [
            "## SCHEMA",
            field_lines,
            "",
            "## INPUT TYPE",
            "DOCUMENT_IMAGES",
            "",
            "## TASK",
            "Estrai i campi richiesti leggendo direttamente le immagini allegate.",
        ]
    )

    user_content: list[dict[str, Any]] = [{"type": "text", "text": intro}]
    for image in images:
        user_content.append(
            {
                "type": "image_url",
                "image_url": {"url": _encode_data_uri(image)},
            }
        )

    if should_log_prompt:
        print(
            "===== VISION EXTRACTION INPUT =====\n"
            f"Image pages: {len(images)}\n"
            "===== END VISION EXTRACTION INPUT =====\n",
            flush=True,
        )

    return _run_extraction_request(
        fields=fields,
        user_content=user_content,
        model=model,
        should_log_prompt=should_log_prompt,
        should_log_response=should_log_response,
    )
