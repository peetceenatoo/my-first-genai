from __future__ import annotations

import base64
import io
from statistics import StatisticsError, mode
from typing import Any

from PIL import Image

from src.config import load_config
from src.integrations.bedrock_client import get_chat_completion


DEFAULT_CLASSIFIER_PROMPT = """Sei un classificatore di documenti rigoroso.
Scegli esattamente un'etichetta dalla lista fornita in base a layout, indizi visivi e testo.
Se nulla corrisponde, restituisci "Unknown".
Restituisci solo la stringa dell'etichetta, senza parole aggiuntive o punteggiatura.
"""


def _image_to_data_uri(image: Image.Image) -> str:
    buf = io.BytesIO()
    image.save(buf, format="PNG")
    return f"data:image/png;base64,{base64.b64encode(buf.getvalue()).decode()}"


def classify_document(
    images: list[Image.Image],
    candidates: list[str],
    *,
    use_confidence: bool = False,
    n_votes: int = 3,
    text: str | None = None,
) -> dict[str, Any]:
    config = load_config()

    def _single_vote() -> str:
        content = [
            {
                "type": "text",
                "text": f"Scegli un solo tipo tra: {candidates}.",
            }
        ]
        if text:
            text_snippet = text.strip()
            if len(text_snippet) > 4000:
                text_snippet = text_snippet[:4000]
            content.append(
                {"type": "text", "text": f"Testo del documento:\n{text_snippet}"}
            )
        for image in images or []:
            content.append(
                {
                    "type": "image_url",
                    "image_url": {"url": _image_to_data_uri(image)},
                }
            )

        messages = [
            {"role": "system", "content": DEFAULT_CLASSIFIER_PROMPT},
            {"role": "user", "content": content},
        ]
        return get_chat_completion(messages, model=config.classify_model).strip()

    vote_count = max(1, n_votes)
    if vote_count == 1:
        result = _single_vote()
        if use_confidence:
            return {"doc_type": result, "confidence": 1.0}
        return {"doc_type": result}

    votes = [_single_vote() for _ in range(vote_count)]
    try:
        best = mode(votes)
        confidence = votes.count(best) / vote_count
    except StatisticsError:
        best, confidence = votes[0], 1 / vote_count

    if use_confidence:
        return {"doc_type": best, "confidence": confidence}
    return {"doc_type": best}
