from __future__ import annotations

import base64
import io

from PIL import Image

from src.config import load_config
from src.integrations.bedrock_client import get_chat_completion


DEFAULT_OCR_PROMPT = """
Sei un motore OCR. Trascrivi tutto il testo leggibile nel naturale ordine di lettura.
Mantieni le interruzioni di riga e gli spazi quando utile.
Restituisci solo testo semplice, senza commenti.
"""


def _image_to_data_uri(image: Image.Image) -> str:
    buf = io.BytesIO()
    image.save(buf, format="PNG")
    return f"data:image/png;base64,{base64.b64encode(buf.getvalue()).decode()}"


def run_ocr(images: list[Image.Image]) -> str:
    config = load_config()
    chunks: list[str] = []

    for image in images:
        messages = [
            {"role": "system", "content": DEFAULT_OCR_PROMPT},
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "Estrai tutto il testo."},
                    {
                        "type": "image_url",
                        "image_url": {"url": _image_to_data_uri(image)},
                    },
                ],
            },
        ]
        chunks.append(get_chat_completion(messages, model=config.ocr_model))

    return "\n".join(chunk.strip() for chunk in chunks if chunk)