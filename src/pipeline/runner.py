from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import base64
import io
import json
from typing import Any, Callable

from PIL import Image

from src.domain.models import DocumentSchema
from src.domain.run_store import ExtractionRun, RunDocument, RunStore
from src.pipeline.classification import classify_document
from src.pipeline.extraction import extract_metadata
from src.pipeline.ocr import run_ocr


@dataclass
class PipelineOptions:
    enable_ocr: bool = False
    compute_confidence: bool = False
    use_classification: bool = False
    classifier_prompt: str | None = None
    extraction_prompt: str | None = None


def run_pipeline(
    *,
    files: list[dict[str, Any]],
    default_schema: DocumentSchema | None,
    schema_map: dict[str, DocumentSchema],
    candidates: list[str],
    run_store: RunStore,
    options: PipelineOptions,
    schema_name: str | None = None,
    progress_callback: Callable[[str, float], None] | None = None,
) -> ExtractionRun:  # sourcery skip: low-code-quality
    run_id = run_store.create_run_id()
    documents: list[RunDocument] = []

    max_pages = None
    vote_runs = 3 if not options.compute_confidence else 7
    class_votes = 3 # if options.use_classification... else 0

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

    def aggregate_votes(
        votes: list[dict[str, Any]], field_names: list[str]
    ) -> tuple[dict[str, Any], dict[str, float | None]]:
        merged: dict[str, Any] = {}
        confidences: dict[str, float | None] = {}
        for field_name in field_names:
            counts: dict[str, int] = {}
            samples: dict[str, Any] = {}
            for vote in votes:
                value = vote.get(field_name, "")
                key = canonicalize(value)
                counts[key] = counts.get(key, 0) + 1
                if key not in samples:
                    samples[key] = value
            if not counts:
                merged[field_name] = ""
                confidences[field_name] = None
                continue
            best = max(
                counts,
                key=lambda k: (counts[k], 1 if str(k).strip() else 0),
            )
            best_value = samples.get(best, "")
            merged[field_name] = best_value
            if best_value is None or not str(best_value).strip():
                confidences[field_name] = None
            else:
                confidences[field_name] = counts[best] / max(len(votes), 1)
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

        ocr_text = payload.get("ocr_text") # in case input document was text already
        if ocr_text is None and options.enable_ocr:
            ocr_text = run_ocr(images)

        if options.use_classification:
            report_progress(f"Classifying {idx}/{total_docs} • {filename}")
            classification = classify_document(
                images_for_llm,
                candidates,
                use_confidence=options.compute_confidence,
                n_votes=class_votes,
                system_prompt=options.classifier_prompt,
                text=ocr_text,
            )
            doc_type = classification.get("doc_type", "Unknown")
            confidence = classification.get("confidence")
        else:
            doc_type = default_schema.name if default_schema else "Unknown"
            confidence = None
            report_progress(f"Applying schema {idx}/{total_docs} • {filename}")

        warnings: list[str] = []
        errors: list[str] = []
        extracted: dict[str, Any] = {}
        field_confidence: dict[str, float | None] = {}

        if doc_type in {"Unknown", "Other"}:
            warnings.append("Document type is unknown. Extraction skipped.")
            report_progress(f"Skipping extraction {idx}/{total_docs} • {filename}")
        else:
            schema_for_doc = default_schema
            if options.use_classification:
                schema_for_doc = schema_map.get(doc_type, default_schema)
            if not schema_for_doc:
                warnings.append("No matching schema found. Extraction skipped.")
                report_progress(f"No schema match {idx}/{total_docs} • {filename}")
            else:
                report_progress(f"Extracting {idx}/{total_docs} • {filename}")
                try:
                    if vote_runs > 1:
                        votes: list[dict[str, Any]] = []
                        for _ in range(vote_runs):
                            extraction = extract_metadata(
                                images_for_llm,
                                schema_for_doc.fields,
                                ocr_text=ocr_text,
                                system_prompt=options.extraction_prompt,
                            )
                            votes.append(extraction.get("metadata", {}))
                        field_names = [field.name for field in schema_for_doc.fields]
                        extracted, field_confidence = aggregate_votes(
                            votes, field_names
                        )
                        if not options.compute_confidence:
                            field_confidence = {}
                    else:
                        extraction = extract_metadata(
                            images_for_llm,
                            schema_for_doc.fields,
                            ocr_text=ocr_text,
                            system_prompt=options.extraction_prompt,
                        )
                        extracted = extraction.get("metadata", {})
                except Exception as exc:
                    errors.append(str(exc))

        preview_image = encode_preview(images)
        documents.append(
            RunDocument(
                filename=filename,
                document_type=doc_type,
                document_type_original=doc_type,
                document_type_corrected=doc_type,
                confidence=confidence,
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
            else (default_schema.name if default_schema else "Classified")
        ),
        documents=documents,
        use_classification=options.use_classification,
    )
    run_store.save(run)
    return run
