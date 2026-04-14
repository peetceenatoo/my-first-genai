from __future__ import annotations

from typing import Any

from PIL import Image

from src.integrations.clients.textract_client import detect_text
from src.integrations.utils.textract_types import TextractDocument


def run_ocr(
    images: list[Image.Image],
    *,
    improve_ocr: bool = True,
    ocr_payload: dict[str, Any] | None = None,
    log: bool = True,
) -> TextractDocument:
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
                    f"Improve OCR: {improve_ocr}",
                ]
            )
            + "\n===== END OCR INPUT =====",
            flush=True,
        )

    payload_textract_document = ocr_payload.get("textract_document") if ocr_payload else None
    payload_ocr_text = ocr_payload.get("ocr_text") if ocr_payload else None

    if payload_textract_document is not None:
        aggregated = payload_textract_document
        if images and aggregated.num_pages <= 1:
            aggregated.num_pages = len(images)
    elif payload_ocr_text is not None:
        aggregated = TextractDocument(
            plain_text=str(payload_ocr_text),
            num_pages=len(images) if images else 1,
            textract_api_used="InputText",
        )
    elif not images:
        aggregated = TextractDocument()
    else:
        documents: list[TextractDocument] = []

        for page_num, image in enumerate(images, start=1):
            doc = detect_text(image, improve_ocr=improve_ocr, log=log)
            doc.page_number = page_num
            doc.num_pages = len(images)
            documents.append(doc)

        # Aggregate all data into a single canonical OCR output.
        aggregated = TextractDocument(
            num_pages=len(images),
            textract_api_used=documents[0].textract_api_used if documents else "AnalyzeDocument",
        )

        for doc in documents:
            aggregated.raw_blocks.extend(doc.raw_blocks)
            aggregated.forms.extend(doc.forms)
            if doc.plain_text:
                if aggregated.plain_text:
                    aggregated.plain_text += "\n---PAGE BREAK---\n" + doc.plain_text
                else:
                    aggregated.plain_text = doc.plain_text

    if log:
        print(
            "===== OCR OUTPUT =====\n"
            f"Textract API: {aggregated.textract_api_used}\n"
            f"Pages: {aggregated.num_pages}\n"
            "## FORMS\n"
            + (
                "\n".join(
                    [
                        f"  {form.key}: {form.value}"
                        + (
                            f" [confidence: {form.value_confidence:.1%}]"
                            if form.value_confidence < 1.0
                            else ""
                        )
                        for form in aggregated.forms
                    ]
                )
                if aggregated.forms
                else "(none)"
            )
            + "\n\n"
            + "## OCR TEXT (CANONICAL)\n"
            + (aggregated.plain_text or "(empty)")
            + "\n"
            "===== END OCR OUTPUT =====\n\n",
            flush=True,
        )

    return aggregated
