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
- Valori stringa (type=string, date): SEMPRE racchiuse tra virgolette.
- Numeri (type=number, integer): è fondamentale che contengano SOLO cifre da 0 a 9, SENZA nessun altro tipo di carattere come virgolette, lettere o slash.
- Attieniti al tipo di campo indicato nello schema JSON per decidere se restituire un numero o una stringa.
- Stringhe vuote: "" (due virgolette, non null)
- Numeri vuoti: null (senza virgolette)

REGOLE DI ESTRAZIONE:
- Le chiavi JSON devono corrispondere esattamente e soltanto ai nomi dei campi forniti nello schema.
- Rispetta la formulazione, maiuscole/minuscole, punteggiatura e unità del documento nel valore.
- Non inferire né inventare valori non presenti nel documento: non inferire informazione nè dagli schemi, nè dalle regole.
- Alcuni valori potrebbero non essere presenti nel documento. Non cercare di ricavarli se non esplicitamente presenti.
- Alcuni valori potrebbero comparire nell'immagine senza etichetta del campo: cerca un valore anche se non è accompagnato dalla sua etichetta.
- Quando un campo fa riferimento a un'etichetta (es. "Cod. (A)"), privilegia SEMPRE il valore vicino a quella etichetta rispetto ad altri simili nel documento.
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
    enum_hint = (
        f" enum: {', '.join(str(value) for value in field.enum_values)}"
        if field.enum_values
        else ""
    )
    description = f" - {field.description}" if field.description else ""
    return f"- {field.name} ({field.field_type}){enum_hint}{description}"


def extract_metadata(
    fields: list[SchemaField],
    *,
    textract_document: TextractDocument,
    log: bool = True,
) -> dict[str, Any]:
    config = load_config()

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

    if log:
        print(
            "===== EXTRACTION PROMPT =====\n"
            "[SYSTEM]\n"
            f"{DEFAULT_EXTRACTION_PROMPT.strip()}\n\n"
            "[USER]\n"
            "## SCHEMA\n"
            f"{field_lines}\n\n"
            "## OUTPUT OCR\n"
            "Contenuto OCR passato al prompt (non stampato qui: vedi logging OCR).\n"
            "===== END EXTRACTION PROMPT =====",
            flush=True,
        )

    response = get_chat_completion(messages, model=config.extract_model)

    if log:
        print(
            "===== EXTRACTION RESPONSE =====\n"
            f"{response.strip() or '(empty)'}\n"
            "===== END EXTRACTION RESPONSE =====",
            flush=True,
        )

    payload = _safe_json(response)

    metadata = _align_metadata(payload, fields)

    return {"metadata": metadata, "confidence": {}}
