from __future__ import annotations

import io
from typing import Any

import fitz
from PIL import Image


def _read_input_bytes(source: Any) -> bytes:
    if isinstance(source, bytes):
        return source
    if isinstance(source, bytearray):
        return bytes(source)

    if hasattr(source, "read"):
        data = source.read()
        if hasattr(source, "seek"):
            source.seek(0)
        if isinstance(data, bytes):
            return data
        if isinstance(data, bytearray):
            return bytes(data)

    raise TypeError("preprocess expects bytes or a file-like object with read().")


def preprocess(source: Any, filename: str) -> list[Image.Image]:
    data = _read_input_bytes(source)

    if filename.lower().endswith(".pdf"):
        images: list[Image.Image] = []
        with fitz.open(stream=data, filetype="pdf") as document:
            for page in document:
                pixmap = page.get_pixmap(matrix=fitz.Matrix(2, 2), alpha=False)
                images.append(Image.open(io.BytesIO(pixmap.tobytes("png"))))
        return images
    return [Image.open(io.BytesIO(data))]
