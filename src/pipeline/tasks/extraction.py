from __future__ import annotations

import json
import re
from typing import Any

from src.config import load_config
from src.domain.utils.schema_types import SchemaField
from src.integrations.clients.bedrock_client import get_chat_completion
from src.integrations.utils.textract_types import TextractDocument


DEFAULT_EXTRACTION_PROMPT = \
"""
Estrai metadati strutturati dal documento. Restituisci SOLO JSON valido (niente markdown, nessun commento, nessun testo extra).

REGOLE CRITICHE DI FORMATTAZIONE JSON:
- Rispetta il tipo di campo indicato nello schema JSON: valori stringa (type=string, date) SEMPRE racchiusi tra virgolette, valori numerici (type=number, integer) mai racchiusi tra virgolette.
- Rispetta il tipo di campo anche nel caso di valori vuoti: stringhe vuote "" (due virgolette, non null), numeri vuoti null (senza virgolette).

REGOLE DI ESTRAZIONE CRITICHE:
- Le chiavi JSON presenti nella tua risposta devono corrispondere ESATTAMENTE ai nomi dei campi forniti nello schema. In generale, è FONDAMENTALE che nella chiave del JSON fornito come risposta non sia aggiunto nè rimosso nulla al nome del campo nello schema fornito. 
- I campi individuati devono essere identici in numero a quelli indicati nello schema: non devono esserci campi aggiuntivi, nè mancanti. 
- Rispetta la formulazione, le maiuscole/minuscole, la punteggiatura e le unità dei valori estratti dal testo del documento.
- PRIORITÀ ASSOLUTA alle etichette con codici alfanumerici (es. "(A)", "(D.1)", ecc.), se utilizzate dal documento: cerca SEMPRE il valore immediatamente associato a queste etichette.
- Se una etichetta non è seguita da un valore o il valore non rispetta la descrizione del campo, restituisci un valore vuoto piuttosto che inferire o utilizzare valori trovati altrove.
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
    return f"- Name: {field.name} - Type: {field.field_type} - Description: {description}"


def extract_metadata(
    fields: list[SchemaField],
    *,
    textract_document: TextractDocument,
    log: bool = True,
    log_prompt: bool | None = None,
    log_response: bool | None = None,
) -> dict[str, Any]:
    config = load_config()

    should_log_prompt = log if log_prompt is None else log_prompt
    should_log_response = log if log_response is None else log_response

    field_lines = "\n".join(_render_field(field) for field in fields)

    parts = [
        "## SCHEMA",
        field_lines,
        "",
        "## OUTPUT OCR",
        textract_document.to_context_string(),
    ]

    content = [{"type": "text", "text": "\n".join(parts)}]

    messages = [
        {"role": "system", "content": DEFAULT_EXTRACTION_PROMPT},
        {"role": "user", "content": content},
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

    response = get_chat_completion(messages, model=config.extract_model)

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
