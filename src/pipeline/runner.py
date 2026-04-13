from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import base64
import io
import json
from typing import Any, Callable

from PIL import Image

from src.config import load_config
from src.domain.utils.schema_types import DocumentSchema
from src.domain.stores.run_store import ExtractionRun, RunDocument, RunStore
from src.pipeline.tasks.extraction import extract_metadata
from src.pipeline.tasks.ocr import run_ocr


@dataclass
class PipelineOptions:
    compute_confidence: bool = False
    improve_ocr: bool = True

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

    config = load_config()
    log = config.enable_logging

    run_id = run_store.create_run_id()
    documents: list[RunDocument] = []

    vote_runs = 7 if options.compute_confidence else 3

    total_docs = len(files)
    # OCR + schema + extraction for each document, plus one final save step.
    total_steps = max(total_docs * 3 + 1, 1)
    current_step = 0

    def report_progress(message: str) -> None:
        nonlocal current_step
        current_step += 1
        if progress_callback:
            progress = min(current_step / total_steps, 1.0)
            progress_callback(message, progress)

    def canonicalize(value: Any) -> str:
        if value is None:
            return "__NONE__"
        if isinstance(value, (dict, list)):
            return json.dumps(value, sort_keys=True, ensure_ascii=False)
        return str(value)

    def normalize_vote_value(value: Any) -> Any:
        if value is None:
            return None
        if isinstance(value, str):
            cleaned = value.strip()
            return cleaned if cleaned else None
        if isinstance(value, (list, dict)):
            return value if len(value) > 0 else None
        return value

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
                value = normalize_vote_value(vote.get(field_name, None))
                key = canonicalize(value)
                counts[key] = counts.get(key, 0) + 1
                if key not in samples:
                    samples[key] = value
            if not counts:
                merged[field_name] = None
                confidences[field_name] = None
                continue

            best = max(counts, key=lambda k: counts[k])
            best_value = samples.get(best, None)
            merged[field_name] = best_value
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
        images_for_llm = images

        report_progress(f"Running OCR {idx}/{total_docs} • {filename}")
        textract_doc = run_ocr(
            images_for_llm,
            improve_ocr=options.improve_ocr,
            ocr_payload=payload,
            log=log,
        )
        doc_type = default_schema.name
        report_progress(f"Applying schema {idx}/{total_docs} • {filename}")

        errors: list[str] = []
        extracted: dict[str, Any] = {}
        field_confidence: dict[str, float | None] = {}

        report_progress(f"Extracting {idx}/{total_docs} • {filename}")
        try:
            votes: list[dict[str, Any]] = []
            for _ in range(vote_runs):
                extraction = extract_metadata(
                    default_schema.fields,
                    textract_document=textract_doc,
                    log=log,
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
                extracted=extracted,
                corrected=extracted.copy(),
                preview_image=preview_image,
                field_confidence=field_confidence,
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
        compute_confidence=options.compute_confidence,
    )
    report_progress("Finalizing run")
    run_store.save(run)
    return run
