from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import base64
import io
import json
from typing import Any, Callable

from PIL import Image

from src.domain.utils.schema_types import DocumentSchema
from src.domain.stores.run_store import ExtractionRun, RunDocument, RunStore
from src.pipeline.tasks.extraction import extract_metadata
from src.pipeline.tasks.ocr import run_ocr


@dataclass
class PipelineOptions:
    compute_confidence: bool = False


def run_pipeline(
    *,
    files: list[dict[str, Any]],
    default_schema: DocumentSchema,
    run_store: RunStore,
    options: PipelineOptions,
    schema_name: str | None = None,
    progress_callback: Callable[[str, float], None] | None = None,
) -> ExtractionRun:  # sourcery skip: low-code-quality
    if default_schema is None:
        raise ValueError("A schema must be provided to run extraction.")

    run_id = run_store.create_run_id()
    documents: list[RunDocument] = []

    max_pages = None
    vote_runs = 7 if options.compute_confidence else 3

    total_docs = len(files)
    total_steps = max(total_docs * 2, 1)
    current_step = 0

    def report_progress(message: str) -> None:
        nonlocal current_step
        current_step += 1
        if progress_callback:
            progress = min(current_step / total_steps, 1.0)
            progress_callback(message, progress)

    def canonicalize(value: Any) -> str:
        if value is None:
            return ""
        if isinstance(value, (dict, list)):
            return json.dumps(value, sort_keys=True, ensure_ascii=False)
        return str(value)

    def has_meaningful_value(value: Any) -> bool:
        if value is None:
            return False
        if isinstance(value, bool):
            return True
        if isinstance(value, (int, float)):
            return True
        if isinstance(value, str):
            return bool(value.strip())
        if isinstance(value, (list, dict)):
            return len(value) > 0
        return bool(str(value).strip())

    def aggregate_votes(
        votes: list[dict[str, Any]], field_names: list[str]
    ) -> tuple[dict[str, Any], dict[str, float | None]]:
        merged: dict[str, Any] = {}
        confidences: dict[str, float | None] = {}
        total_votes = max(len(votes), 1)
        for field_name in field_names:
            counts: dict[str, int] = {}
            samples: dict[str, Any] = {}
            for vote in votes:
                value = vote.get(field_name, "")
                if not has_meaningful_value(value):
                    continue
                key = canonicalize(value)
                counts[key] = counts.get(key, 0) + 1
                if key not in samples:
                    samples[key] = value
            if not counts:
                merged[field_name] = ""
                confidences[field_name] = None
                continue

            best = max(counts, key=lambda k: counts[k])
            best_value = samples.get(best, "")
            merged[field_name] = best_value
            if best_value is None or not str(best_value).strip():
                confidences[field_name] = None
            else:
                confidences[field_name] = counts[best] / total_votes
        return merged, confidences

    def encode_preview(images: list[Image.Image]) -> str | None:
        if not images:
            return None
        preview = images[0].copy()
        preview.thumbnail((720, 720))
        buf = io.BytesIO()
        preview.save(buf, format="PNG")
        return base64.b64encode(buf.getvalue()).decode()

    for idx, payload in enumerate(files, start=1):
        filename = payload["name"]
        images: list[Image.Image] = payload["images"]
        images_for_llm = images if max_pages is None else images[:max_pages]

        ocr_text = payload.get("ocr_text")  # in case input document was text already
        if ocr_text is None:
            ocr_text = run_ocr(images)

        doc_type = default_schema.name
        report_progress(f"Applying schema {idx}/{total_docs} • {filename}")

        warnings: list[str] = []
        errors: list[str] = []
        extracted: dict[str, Any] = {}
        field_confidence: dict[str, float | None] = {}

        report_progress(f"Extracting {idx}/{total_docs} • {filename}")
        try:
            votes: list[dict[str, Any]] = []
            for _ in range(vote_runs):
                extraction = extract_metadata(
                    images_for_llm,
                    default_schema.fields,
                    ocr_text=ocr_text,
                )
                vote_payload = extraction.get("metadata", {})
                votes.append(vote_payload)

            field_names = [field.name for field in default_schema.fields]
            extracted, field_confidence = aggregate_votes(votes, field_names)
            if not options.compute_confidence:
                field_confidence = {}
        except Exception as exc:
            errors.append(str(exc))

        preview_image = encode_preview(images)
        documents.append(
            RunDocument(
                filename=filename,
                document_type=doc_type,
                document_type_original=doc_type,
                document_type_corrected=doc_type,
                extracted=extracted,
                corrected=extracted.copy(),
                preview_image=preview_image,
                field_confidence=field_confidence,
                warnings=warnings,
                errors=errors,
            )
        )

    run = ExtractionRun(
        run_id=run_id,
        started_at=datetime.now(timezone.utc).isoformat(),
        schema_name=(
            schema_name
            if schema_name is not None
            else default_schema.name
        ),
        documents=documents,
    )
    run_store.save(run)
    return run
