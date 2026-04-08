from __future__ import annotations

import io
import time

import boto3
from botocore.config import Config as BotoConfig
from botocore.exceptions import NoCredentialsError
from PIL import Image

from src.config import load_config
from src.logging import get_logger, log_ocr_text


logger = get_logger(__name__)


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


def _extract_text_from_analyze(blocks: list[dict]) -> str:
    """Extract text from AnalyzeDocument response (KEY_VALUE_SET, TABLE, LINE blocks)."""
    lines: list[str] = []
    
    # Build map of block IDs to text for relationship resolution
    block_map: dict[str, str] = {}
    for block in blocks:
        block_id = block.get("Id")
        text = block.get("Text", "")
        if block_id and text:
            block_map[block_id] = text
    
    # Extract key-value pairs from forms
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


def detect_text(image: Image.Image) -> str:
    """
    Extract text from image using AWS Textract AnalyzeDocument (primary) 
    or DetectDocumentText (fallback).
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

    attempts = config.max_retries + 1
    document_bytes = _image_to_bytes(image)

    for attempt in range(attempts):
        try:
            # Try AnalyzeDocument first (better for structured documents)
            response = client.analyze_document(
                Document={"Bytes": document_bytes},
                FeatureTypes=["FORMS", "TABLES"],
            )
            blocks = response.get("Blocks", [])
            if not isinstance(blocks, list):
                return ""

            ocr_text = _extract_text_from_analyze(blocks)
            log_ocr_text(ocr_text)
            return ocr_text
        except NoCredentialsError as exc:
            raise RuntimeError(
                "AWS credentials not found. Configure AWS_ACCESS_KEY_ID and "
                "AWS_SECRET_ACCESS_KEY (plus AWS_SESSION_TOKEN if temporary), "
                "or provide AWS_PROFILE with mounted ~/.aws credentials. "
                "If running in Docker, mount ~/.aws into the container."
            ) from exc
        except Exception as exc:
            logger.warning(
                "Textract AnalyzeDocument failed (attempt %s/%s): %s. Retrying...",
                attempt + 1,
                attempts,
                exc,
            )
            if attempt >= config.max_retries:
                logger.warning(
                    "AnalyzeDocument exhausted retries. Falling back to DetectDocumentText."
                )
                # Fallback: use DetectDocumentText
                try:
                    response = client.detect_document_text(
                        Document={"Bytes": document_bytes}
                    )
                    blocks = response.get("Blocks", [])
                    if not isinstance(blocks, list):
                        return ""
                    ocr_text = _extract_lines(blocks)
                    log_ocr_text(ocr_text)
                    return ocr_text
                except Exception as fallback_exc:
                    logger.error(
                        "Textract fallback (DetectDocumentText) also failed: %s",
                        fallback_exc,
                    )
                    raise
            time.sleep(config.retry_backoff_s * (attempt + 1))

    return ""