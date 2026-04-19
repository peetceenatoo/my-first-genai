from __future__ import annotations

import io

import boto3
from botocore.config import Config as BotoConfig
from botocore.exceptions import NoCredentialsError
from PIL import Image

from src.config import load_config


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


def detect_text(
    image: Image.Image,
    *,
    log: bool = True,
) -> str:
    """
    Extract text from image using AWS Textract DetectDocumentText.
    
    Args:
        image: PIL Image to process
        log: Enable fallback logs
    
    Returns:
        OCR plain text extracted
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
        response = client.detect_document_text(Document={"Bytes": document_bytes})
        blocks = response.get("Blocks", [])
        if not isinstance(blocks, list):
            return ""
        return _extract_lines(blocks)

    except NoCredentialsError as exc:
        raise RuntimeError(
            "AWS credentials not found. Configure AWS_ACCESS_KEY_ID and "
            "AWS_SECRET_ACCESS_KEY (plus AWS_SESSION_TOKEN if temporary), "
            "or provide AWS_PROFILE with mounted ~/.aws credentials. "
            "If running in Docker, mount ~/.aws into the container."
        ) from exc
    except Exception as exc:
        if log:
            print(
                "DetectDocumentText failed: "
                f"{exc.__class__.__name__}: {exc}",
                flush=True,
            )
        raise
