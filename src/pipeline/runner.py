from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import base64
import io
from typing import Any, Callable

from PIL import Image

from src.config import load_config
from src.domain.utils.schema_types import DocumentSchema
from src.domain.stores.run_store import ExtractionRun, RunDocument, RunStore
from src.pipeline.tasks.extraction import extract_metadata
from src.pipeline.tasks.ocr import run_ocr
from src.pipeline.tasks.vision_extraction import run_vision_extraction_vote
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
    "booklet_vision": PipelineDefinition(
        key="booklet_vision",
        label="Vision + Extraction through Multimodal LLM",
        description="Direct image extraction with a stronger vision-capable model.",
    ),
}

PIPELINE_VOTE_RUNS: dict[str, int] = {
    "id_ocr": 7,
    "booklet_vision": 5,
}


def _normalize_schema_name(name: str) -> str:
    normalized = name.strip().lower()
    return normalized.replace("à", "a")


def get_pipeline_for_schema(schema_name: str) -> PipelineDefinition | None:
    normalized = _normalize_schema_name(schema_name)
    if normalized in ID_SCHEMA_NAMES:
        return PIPELINE_DEFINITIONS["id_ocr"]
    if normalized in BOOKLET_SCHEMA_NAMES:
        return PIPELINE_DEFINITIONS["booklet_vision"]
    return None


def supported_schema_status(schemas: list[DocumentSchema]) -> list[dict[str, str | bool]]:
    rows: list[dict[str, str | bool]] = []
    for schema in schemas:
        pipeline = get_pipeline_for_schema(schema.name)
        is_supported = pipeline is not None
        rows.append(
            {
                "schema": schema.name,
                "supported": "Supported" if is_supported else "Not supported",
                "pipeline": pipeline.label if pipeline else "Not implemented",
                "is_supported": is_supported,
            }
        )
    return rows

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
    if pipeline.key == "id_ocr":
        total_steps = max(total_docs * 3 + 1, 1)
    else:
        total_steps = max(total_docs * 2 + 1, 1)
    current_step = 0

    def report_progress(message: str) -> None:
        nonlocal current_step
        current_step += 1
        if progress_callback:
            progress = min(current_step / total_steps, 1.0)
            progress_callback(message, progress)

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
        textract_doc = payload.get("textract_document")

        if pipeline.key == "id_ocr":
            report_progress(f"Running OCR {idx}/{total_docs} • {filename}")
            textract_doc = run_ocr(
                images_for_llm,
                ocr_payload=payload,
                log=log,
            )
        doc_type = default_schema.name
        report_progress(f"Applying schema {idx}/{total_docs} • {filename}")

        errors: list[str] = []
        extracted: dict[str, Any] = {}
        field_confidence: dict[str, float | None] = {}

        report_progress(
            f"Extracting {idx}/{total_docs} • {filename} [{pipeline.label}]"
        )
        try:
            vote_runs = PIPELINE_VOTE_RUNS.get(pipeline.key)
            if vote_runs is None:
                raise RuntimeError(f"Unsupported pipeline handler: {pipeline.key}")

            field_names = [field.name for field in default_schema.fields]

            def extract_single_vote(vote_index: int) -> dict[str, Any]:
                if pipeline.key == "id_ocr":
                    if textract_doc is None:
                        raise RuntimeError("OCR document is missing for ID pipeline.")
                    extraction = extract_metadata(
                        default_schema.fields,
                        textract_document=textract_doc,
                        model=config.id_extract_model,
                        log=log,
                        log_prompt=(log and vote_index == 0),
                        log_response=log,
                    )
                    return extraction.get("metadata", {})

                if pipeline.key == "booklet_vision":
                    return run_vision_extraction_vote(
                        schema=default_schema,
                        images=images_for_llm,
                        model=config.booklet_extract_model,
                        vote_index=vote_index,
                        log=log,
                    )

                raise RuntimeError(f"Unsupported pipeline handler: {pipeline.key}")

            extracted, field_confidence = run_vote_cycle(
                field_names=field_names,
                vote_runs=vote_runs,
                extract_single_vote=extract_single_vote,
            )

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
