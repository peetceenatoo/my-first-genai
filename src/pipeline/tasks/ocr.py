from __future__ import annotations

from typing import Any

from PIL import Image

from src.integrations.clients.textract_client import detect_text


def run_ocr(
    images: list[Image.Image],
    *,
    ocr_payload: dict[str, Any] | None = None,
    log: bool = True,
) -> str:
    image_lines = [f"Pages: {len(images)}"]
    if images:
        image_lines.append("Image sizes:")
        for page_number, image in enumerate(images, start=1):
            image_lines.append(f"  Page {page_number}: {image.width}x{image.height}")

    if log:
        print(
            "===== OCR INPUT =====\n"
            + "\n".join(
                [
                    *image_lines,
                    "Mode: DetectDocumentText",
                ]
            )
            + "\n===== END OCR INPUT =====\n",
            flush=True,
        )

    payload_ocr_text = ocr_payload.get("ocr_text") if ocr_payload else None

    if payload_ocr_text is not None:
        plain_text = str(payload_ocr_text)
    elif not images:
        plain_text = ""
    else:
        page_texts: list[str] = []

        for image in images:
            page_texts.append(detect_text(image, log=log))

        plain_text = "\n---PAGE BREAK---\n".join(
            text for text in page_texts if text
        )

    if log:
        print(
            "===== OCR OUTPUT =====\n"
            f"Textract API: {'InputText' if payload_ocr_text is not None else 'DetectDocumentText'}\n"
            f"Pages: {len(images) if images else 1}\n"
            "## OCR TEXT (CANONICAL)\n"
            + (plain_text or "(empty)")
            + "\n"
            "===== END OCR OUTPUT =====\n\n\n",
            flush=True,
        )

    return plain_text
