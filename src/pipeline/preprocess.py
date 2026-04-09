from __future__ import annotations

import io
from pdf2image import convert_from_bytes
from PIL import Image


def preprocess(uploaded, filename: str) -> list[Image.Image]:
    data = uploaded.read()
    uploaded.seek(0)

    if filename.lower().endswith(".pdf"):
        return convert_from_bytes(data)
    return [Image.open(io.BytesIO(data))]
