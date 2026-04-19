from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable

from src.config import load_config
from src.domain.utils.schema_types import DocumentSchema
from src.domain.stores.run_store import ExtractionRun, RunDocument, RunStore
from src.pipeline.tasks.extraction import extract_metadata
from src.pipeline.tasks.ocr import run_ocr
from src.pipeline.tasks.preprocess import preprocess
from src.pipeline.tasks.voting import run_vote_cycle


@dataclass
class PipelineOptions:
    compute_confidence: bool = False


@dataclass(frozen=True)
class PipelineDefinition:
    key: str
    label: str
    description: str


ID_SCHEMA_NAMES = {"carta d'identita", "carta d’identita"}
BOOKLET_SCHEMA_NAMES = {"carta di circolazione"}

PIPELINE_DEFINITIONS: dict[str, PipelineDefinition] = {
    "id_ocr": PipelineDefinition(
        key="id_ocr",
        label="OCR DetectText + Cheap LLM",
        description="Textract DetectDocumentText + Nova Lite extraction.",
    ),
    "booklet_ocr": PipelineDefinition(
        key="booklet_ocr",
        label="OCR DetectText + Powerful LLM",
        description="Textract DetectDocumentText + stronger LLM extraction.",
    ),
}

PIPELINE_VOTE_RUNS: dict[str, int] = {
    "id_ocr": 7,
    "booklet_ocr": 3,
}


def _normalize_schema_name(name: str) -> str:
    normalized = name.strip().lower()
    return normalized.replace("à", "a")


def get_pipeline_for_schema(schema_name: str) -> PipelineDefinition | None:
    normalized = _normalize_schema_name(schema_name)
    if normalized in ID_SCHEMA_NAMES:
        return PIPELINE_DEFINITIONS["id_ocr"]
    if normalized in BOOKLET_SCHEMA_NAMES:
        return PIPELINE_DEFINITIONS["booklet_ocr"]
    return None


def _extract_document_votes(
    ocr_text: str,
    schema_fields: list,
    pipeline: PipelineDefinition,
    config,
    options: PipelineOptions,
    log: bool,
) -> tuple[dict[str, Any], dict[str, float | None]]:
    """Extract metadata from OCR text with optional vote cycle."""
    field_names = [field.name for field in schema_fields]

    def extract_single_vote(vote_index: int) -> dict[str, Any]:
        if pipeline.key in {"id_ocr", "booklet_ocr"}:
            model = (
                config.id_extract_model if pipeline.key == "id_ocr"
                else config.booklet_extract_model
            )
            extraction = extract_metadata(
                schema_fields,
                ocr_text=ocr_text,
                model=model,
                log=log,
                log_prompt=(log and vote_index == 0),
                log_response=log,
            )
            return extraction.get("metadata", {})

        raise RuntimeError(f"Unsupported pipeline handler: {pipeline.key}")

    if options.compute_confidence:
        vote_runs = PIPELINE_VOTE_RUNS.get(pipeline.key)
        if vote_runs is None:
            raise RuntimeError(f"Unsupported pipeline handler: {pipeline.key}")

        return run_vote_cycle(
            field_names=field_names,
            vote_runs=vote_runs,
            extract_single_vote=extract_single_vote,
        )
    else:
        return extract_single_vote(0), {}


def run_pipeline(
    *,
    files: list[dict[str, Any]],
    default_schema: DocumentSchema,
    options: PipelineOptions,
    run_store: RunStore | None = None,
    schema_name: str | None = None,
    progress_callback: Callable[[str, float], None] | None = None,
) -> ExtractionRun:
    if default_schema is None:
        raise ValueError("A schema must be provided to run extraction.")

    pipeline = get_pipeline_for_schema(default_schema.name)
    if pipeline is None:
        raise ValueError(
            "Schema is not executable yet. Add a dedicated pipeline handler before running extraction."
        )

    config = load_config()
    log = config.enable_logging

    run_id = run_store.create_run_id()
    documents: list[RunDocument] = []

    total_docs = len(files)
    total_steps = max(total_docs * 3 + 1, 1)
    current_step = 0

    def report_progress(message: str) -> None:
        nonlocal current_step
        current_step += 1
        if progress_callback:
            progress = min(current_step / total_steps, 1.0)
            progress_callback(message, progress)

    # For each uploaded document, that could either contain raw_text or file_bytes
    for idx, payload in enumerate(files, start=1):
        # Get the filename and possibly the text (.txt)
        filename = payload["name"]
        ocr_text = payload.get("ocr_text")
        # If the text was not provided (.jpg, .pdf, etc), preprocess or raise an error 
        if ocr_text is None:
            file_bytes = payload.get("file_bytes")
            if file_bytes is None:
                raise ValueError(f"Missing ocr_text or file_bytes for '{filename}'.")
            images_for_llm = preprocess(file_bytes, filename)

        report_progress(f"Running OCR {idx}/{total_docs} • {filename}")

        # In case the image was not provided in form of text already, run OCR
        if ocr_text is None:
            ocr_text = run_ocr(images_for_llm, ocr_payload=payload, log=log)

        report_progress(f"Extracting {idx}/{total_docs} • {filename} [{pipeline.label}]")

        errors: list[str] = []
        extracted: dict[str, Any] = {}
        field_confidence: dict[str, float | None] = {}
        
        try:
            extracted, field_confidence = _extract_document_votes(
                ocr_text=ocr_text,
                schema_fields=default_schema.fields,
                pipeline=pipeline,
                config=config,
                options=options,
                log=log,
            )
        except Exception as exc:
            errors.append(str(exc))

        doc_type = default_schema.name
        documents.append(
            RunDocument(
                filename=filename,
                document_type=doc_type,
                extracted=extracted,
                corrected=extracted.copy(),
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
    if run_store is not None:
        run_store.save(run)
    return run
