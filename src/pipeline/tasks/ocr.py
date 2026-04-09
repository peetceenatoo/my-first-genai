from __future__ import annotations

from PIL import Image

from src.integrations.clients.textract_client import detect_text
from src.integrations.utils.textract_types import TextractDocument


def run_ocr(images: list[Image.Image], queries: list[str] | None = None) -> TextractDocument:
    if not images:
        return TextractDocument()
    
    documents: list[TextractDocument] = []
    
    for page_num, image in enumerate(images, start=1):
        doc = detect_text(image, queries=queries)
        doc.page_number = page_num
        doc.num_pages = len(images)
        documents.append(doc)
    
    # Aggregate all documents into a single canonical representation
    aggregated = TextractDocument(
        num_pages=len(images),
        textract_api_used=documents[0].textract_api_used if documents else "AnalyzeDocument",
    )
    
    # Merge all data
    for doc in documents:
        aggregated.raw_blocks.extend(doc.raw_blocks)
        aggregated.forms.extend(doc.forms)
        aggregated.tables.extend(doc.tables)
        aggregated.queries.extend(doc.queries)
        if doc.plain_text:
            if aggregated.plain_text:
                aggregated.plain_text += "\n---PAGE BREAK---\n" + doc.plain_text
            else:
                aggregated.plain_text = doc.plain_text
    
    return aggregated
