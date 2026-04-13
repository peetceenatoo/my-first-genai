from __future__ import annotations

import io

import boto3
from botocore.config import Config as BotoConfig
from botocore.exceptions import NoCredentialsError
from PIL import Image

from src.config import load_config
from src.integrations.utils.textract_types import (
    TextractDocument,
    TextractForm,
    TextractQuery,
)


def _image_to_bytes(image: Image.Image) -> bytes:
    buf = io.BytesIO()
    image.save(buf, format="PNG")
    return buf.getvalue()


def _extract_lines(blocks: list[dict]) -> str:
    """Extract text from DetectDocumentText response (LINE blocks)."""
    lines: list[str] = []
    for block in blocks:
        if block.get("BlockType") == "LINE":
            text = str(block.get("Text", "")).strip()
            if text:
                lines.append(text)
    return "\n".join(lines)


def _extract_queries_from_response(response: dict) -> list[TextractQuery]:
    """Extract query results from AnalyzeDocument QUERIES response."""
    queries: list[TextractQuery] = []
    
    query_blocks = [b for b in response.get("Blocks", []) if b.get("BlockType") == "QUERY"]
    for qblock in query_blocks:
        query_text = qblock.get("Query", {}).get("Text", "")
        confidence = qblock.get("Confidence", 100) / 100.0
        answer = ""
        
        # Find answer via ANSWER relationship
        for rel in qblock.get("Relationships", []):
            if rel.get("Type") == "ANSWER":
                answer_ids = rel.get("Ids", [])
                answer_texts = []
                for block in response.get("Blocks", []):
                    if block.get("Id") in answer_ids:
                        text = block.get("Text", "")
                        if text:
                            answer_texts.append(text)

                answer = " ".join(answer_texts) if answer_texts else ""
                break

        queries.append(TextractQuery(
            query_text=query_text,
            answer=answer,
            confidence=confidence,
        ))
    
    return queries


def _extract_forms_from_response(response: dict) -> list[TextractForm]:
    """Extract key-value form pairs from AnalyzeDocument FORMS response."""
    forms: list[TextractForm] = []
    blocks = response.get("Blocks", [])
    if not isinstance(blocks, list):
        return forms

    block_map = {block.get("Id"): block for block in blocks if block.get("Id")}

    for block in blocks:
        if block.get("BlockType") != "KEY_VALUE_SET":
            continue
        entity_types = block.get("EntityTypes", [])
        if "KEY" not in entity_types:
            continue

        key_text_parts: list[str] = []
        key_confidence = float(block.get("Confidence", 100)) / 100.0
        value_text = ""
        value_confidence = 1.0

        for rel in block.get("Relationships", []):
            if rel.get("Type") == "CHILD":
                for child_id in rel.get("Ids", []):
                    child_block = block_map.get(child_id)
                    if child_block and child_block.get("Text"):
                        key_text_parts.append(str(child_block.get("Text", "")))

            if rel.get("Type") == "VALUE":
                for value_block_id in rel.get("Ids", []):
                    value_block = block_map.get(value_block_id)
                    if not value_block:
                        continue
                    value_confidence = float(value_block.get("Confidence", 100)) / 100.0
                    value_text_parts: list[str] = []
                    for value_rel in value_block.get("Relationships", []):
                        if value_rel.get("Type") == "CHILD":
                            for child_id in value_rel.get("Ids", []):
                                child_block = block_map.get(child_id)
                                if child_block and child_block.get("Text"):
                                    value_text_parts.append(str(child_block.get("Text", "")))
                    value_text = " ".join(value_text_parts).strip()

        key_text = " ".join(key_text_parts).strip()
        if key_text or value_text:
            forms.append(
                TextractForm(
                    key=key_text,
                    value=value_text,
                    key_confidence=key_confidence,
                    value_confidence=value_confidence,
                )
            )

    return forms


def _extract_text_from_analyze(blocks: list[dict]) -> str:
    """Extract plain text from AnalyzeDocument response (LINE blocks)."""
    lines: list[str] = []

    # Build map of block IDs to text for relationship resolution
    block_map: dict[str, str] = {}
    for block in blocks:
        block_id = block.get("Id")
        text = block.get("Text", "")
        if block_id and text:
            block_map[block_id] = text

    # Extract key-value pairs text
    for block in blocks:
        if block.get("BlockType") == "KEY_VALUE_SET":
            entity_type = block.get("EntityTypes", [])
            if "KEY" in entity_type:
                # Get key text
                key_text = ""
                for rel in block.get("Relationships", []):
                    if rel.get("Type") == "CHILD":
                        for child_id in rel.get("Ids", []):
                            key_text += block_map.get(child_id, "")

                # Find corresponding value
                for rel in block.get("Relationships", []):
                    if rel.get("Type") == "VALUE":
                        for value_block_id in rel.get("Ids", []):
                            for value_block in blocks:
                                if value_block.get("Id") == value_block_id:
                                    value_text = ""
                                    for child_rel in value_block.get("Relationships", []):
                                        if child_rel.get("Type") == "CHILD":
                                            for child_id in child_rel.get("Ids", []):
                                                value_text += block_map.get(child_id, "")
                                    if key_text.strip() and value_text.strip():
                                        lines.append(f"{key_text.strip()}: {value_text.strip()}")

    # Extract table text
    for block in blocks:
        if block.get("BlockType") == "TABLE":
            for rel in block.get("Relationships", []):
                if rel.get("Type") == "CHILD":
                    for cell_id in rel.get("Ids", []):
                        cell_text = block_map.get(cell_id, "")
                        if cell_text.strip() and cell_text not in lines:
                            lines.append(cell_text.strip())

    # Fallback: extract all remaining LINE blocks
    for block in blocks:
        if block.get("BlockType") == "LINE":
            text = str(block.get("Text", "")).strip()
            if text and text not in lines:
                lines.append(text)

    return "\n".join(lines)


def detect_text(
    image: Image.Image,
    queries: list[str] | None = None,
    *,
    improve_ocr: bool = True,
) -> TextractDocument:
    """
    Extract text and structure from image using AWS Textract AnalyzeDocument (primary)
    or DetectDocumentText (fallback).
    
    Returns a canonical TextractDocument that preserves structure without flattening.
    
    Args:
        image: PIL Image to process
        queries: List of query strings to extract (e.g., ["Targa", "Numero telaio"])
        improve_ocr: If True uses AnalyzeDocument + QUERIES, otherwise DetectDocumentText only
    
    Returns:
        TextractDocument with query results and plain text
    """
    config = load_config()
    client = boto3.client(
        "textract",
        region_name=config.aws_region,
        config=BotoConfig(
            connect_timeout=config.request_timeout_s,
            read_timeout=config.request_timeout_s,
            retries={"max_attempts": 1, "mode": "standard"},
        ),
    )

    document_bytes = _image_to_bytes(image)

    try:
        if improve_ocr:
            # Use AnalyzeDocument + QUERIES for richer OCR guidance.
            kwargs: dict[str, object] = {
                "Document": {"Bytes": document_bytes},
                "FeatureTypes": ["FORMS", "QUERIES"],
            }
            if queries:
                kwargs["QueriesConfig"] = {"Queries": [{"Text": q} for q in queries]}

            response = client.analyze_document(**kwargs)
            blocks = response.get("Blocks", [])
            if not isinstance(blocks, list):
                return TextractDocument(
                    raw_blocks=[],
                    plain_text="",
                    textract_api_used="AnalyzeDocument",
                )

            query_results = _extract_queries_from_response(response) if queries else []
            form_results = _extract_forms_from_response(response)
            plain_text = _extract_text_from_analyze(blocks)

            return TextractDocument(
                raw_blocks=blocks,
                forms=form_results,
                queries=query_results,
                plain_text=plain_text,
                textract_api_used="AnalyzeDocument",
            )

        response = client.detect_document_text(Document={"Bytes": document_bytes})
        blocks = response.get("Blocks", [])
        if not isinstance(blocks, list):
            return TextractDocument(
                raw_blocks=[],
                plain_text="",
                textract_api_used="DetectDocumentText",
            )
        plain_text = _extract_lines(blocks)
        return TextractDocument(
            raw_blocks=blocks,
            plain_text=plain_text,
            textract_api_used="DetectDocumentText",
        )

    except NoCredentialsError as exc:
        raise RuntimeError(
            "AWS credentials not found. Configure AWS_ACCESS_KEY_ID and "
            "AWS_SECRET_ACCESS_KEY (plus AWS_SESSION_TOKEN if temporary), "
            "or provide AWS_PROFILE with mounted ~/.aws credentials. "
            "If running in Docker, mount ~/.aws into the container."
        ) from exc
    except Exception:
        # When AnalyzeDocument fails in improve mode, fallback to DetectDocumentText.
        if improve_ocr:
            response = client.detect_document_text(Document={"Bytes": document_bytes})
            blocks = response.get("Blocks", [])
            if not isinstance(blocks, list):
                return TextractDocument(
                    raw_blocks=[],
                    plain_text="",
                    textract_api_used="DetectDocumentText",
                )
            plain_text = _extract_lines(blocks)
            return TextractDocument(
                raw_blocks=blocks,
                plain_text=plain_text,
                textract_api_used="DetectDocumentText",
            )
        raise
