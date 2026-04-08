from __future__ import annotations

from PIL import Image

from src.integrations.textract_client import detect_text


def run_ocr(images: list[Image.Image]) -> str:
    chunks: list[str] = []

    for image in images:
        chunks.append(detect_text(image))

    return "\n".join(chunk.strip() for chunk in chunks if chunk)