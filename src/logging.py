from __future__ import annotations

import json
import logging
import os


def _env_enabled(name: str, default: str = "false") -> bool:
    return os.getenv(name, default).strip().lower() in {"1", "true", "yes", "on"}


def should_log_extraction_raw() -> bool:
    return _env_enabled("EXTRACTLY_EXTRACT_LOG_RAW", "false")


def setup_logging() -> None:
    level = os.getenv("EXTRACTLY_LOG_LEVEL", "INFO").upper()
    sdk_level = os.getenv("EXTRACTLY_SDK_LOG_LEVEL", "WARNING").upper()
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    # Keep third-party SDK logs quieter unless explicitly requested.
    for logger_name in (
        "botocore",
        "boto3",
        "urllib3",
        "s3transfer",
        "watchdog",
        "PIL",
    ):
        logging.getLogger(logger_name).setLevel(sdk_level)


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)


# ============================================================================
# Structured logging helpers - all logging logic centralized here
# ============================================================================

_textract_logger = get_logger("src.integrations.textract_client")
_extraction_logger = get_logger("src.pipeline.extraction")


def log_ocr_text(text: str) -> None:
    """Log OCR plain text extracted from Textract."""
    if text:
        _textract_logger.debug("Textract OCR plain text:\n%s", text)
    else:
        _textract_logger.debug("Textract OCR plain text: [empty]")


def log_ocr_available(char_count: int) -> None:
    """Log that OCR text is available for extraction."""
    _extraction_logger.debug("OCR text available for extraction: %d chars", char_count)


def log_ocr_missing() -> None:
    """Log warning when OCR text is not provided."""
    _extraction_logger.warning("No OCR text provided to extraction. Check enable_ocr flag.")


def log_extraction_response(response: str) -> None:
    """Log the raw model response from extraction."""
    if should_log_extraction_raw():
        _extraction_logger.debug("Extraction model response: %s", response)


def log_extraction_payload(payload: dict) -> None:
    """Log the parsed JSON payload after JSON parsing."""
    _extraction_logger.debug(
        "Extraction parsed JSON payload: %s",
        json.dumps(payload, ensure_ascii=False, default=str),
    )


def log_extraction_metadata(metadata: dict) -> None:
    """Log the final metadata after key alignment."""
    _extraction_logger.debug(
        "Extraction final metadata (after key alignment): %s",
        json.dumps(metadata, ensure_ascii=False, default=str),
    )


def log_field_matched_exactly(field_name: str) -> None:
    """Log when a field matches exactly in the payload."""
    _extraction_logger.debug("Field '%s' matched exactly in payload.", field_name)


def log_field_matched_normalized(field_name: str, original_key: str) -> None:
    """Log when a field matches via key normalization."""
    _extraction_logger.debug(
        "Field '%s' matched via key normalization to '%s'.",
        field_name,
        original_key,
    )


def log_field_not_found(field_name: str) -> None:
    """Log when a field is not found in the payload."""
    _extraction_logger.debug("Field '%s' not found in payload.", field_name)


def log_extraction_summary(filled_count: int, total_count: int) -> None:
    """Log extraction summary with filled fields count."""
    _extraction_logger.debug("Extraction filled %d/%d fields.", filled_count, total_count)


def log_extraction_empty_payload() -> None:
    """Log warning when extraction returns empty/unparseable payload."""
    _extraction_logger.warning("Extraction returned empty/unparseable JSON payload.")


def log_extraction_payload_invalid_type(type_name: str) -> None:
    """Log warning when payload is not a dict."""
    _extraction_logger.warning(
        "Cannot align metadata: payload is not dict or nested dict. Type: %s",
        type_name,
    )

