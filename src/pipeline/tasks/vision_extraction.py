from __future__ import annotations

from typing import Any

from PIL import Image

from src.domain.utils.schema_types import DocumentSchema
from src.pipeline.tasks.extraction import extract_metadata_from_images


def run_vision_extraction_vote(
    *,
    schema: DocumentSchema,
    images: list[Image.Image],
    model: str,
    vote_index: int,
    log: bool = True,
) -> dict[str, Any]:
    extraction = extract_metadata_from_images(
        schema.fields,
        images=images,
        model=model,
        log=log,
        log_prompt=(log and vote_index == 0),
        log_response=log,
    )
    return extraction.get("metadata", {})
