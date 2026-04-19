# Extractly

Extractly is a Streamlit app for extracting structured data from image with traceable runs. It is designed to feel like a “Document Data Extraction Studio” with user-friendly outputs.

This repository is built around a practical pipeline choice: use OCR + LLM across supported document types, with different model strengths depending on document complexity. The goal is to avoid expensive OCR processing, and leverage an targeted model depending on the complexity of the document to be read. Thus, the approach was cost-efficience driven, with a look on accuracy.

The backend leverages LLMs from the Amazon Bedrock catalogue, and uses Amazon Textract DetectDocumentText to implement the OCR function.

## Quickstart

### To run with docker:

1. Configure AWS credentials with `aws configure` (this writes `~/.aws/credentials` and `~/.aws/config`).

2. Build the image:

```bash
docker build -t extractly:latest .
```

3. Run the app:

```bash
docker run --rm -p 8501:8501 -v ~/.aws:/root/.aws:ro extractly:latest
```

4. Or run the app with extraction logging enabled:

```bash
docker run --rm -p 8501:8501 -v ~/.aws:/root/.aws:ro -e EXTRACTLY_ENABLE_LOGGING=1 extractly:latest
```

### To run locally, after installing all dependencies:

1. Run the streamlit app:

```bash
streamlit run Home.py
```

2. Or run the app with extraction logging enabled:

```powershell
$env:EXTRACTLY_ENABLE_LOGGING = "1"
streamlit run Home.py
```

## About

### Schema Studio
- New schemas can be created in the Schema Studio.
- All schemas are stored in a single file (`schemas/schemas.json`) with unique schema names.
- After a new schema is saved, an execution pipeline must be implemented to process any documents of such schema.

### Extraction Pipeline
- As said before, execution is enabled only for schemas with a registered pipeline handler.
- Current handlers:
  - `Carta d'Identità`: OCR pipeline with AWS Textract `DetectDocumentText` + cheap LLM extraction (Amazon Nova Lite).
  - `Carta di circolazione`: OCR pipeline with AWS Textract `DetectDocumentText` + powerful LLM extraction (Anthropic Sonnet 4).
  - Voting is enabled in case "Field confidence" is toggled. In this case, 7 iterations are currently run for `Carta d'Identità`, while only 3 for `Carta di circolazione`.
- Shared extraction contract:
  - The extraction prompt is currently shared across both pipelines.
  - Output must be strict JSON aligned to schema field names and types.
- **Output serialization:**
  - All extraction runs are stored in `data/runs/` with input filenames and output JSON.
  - Each run includes extracted data, confidence scores (optional), warnings, and errors.

## Project Structure

```
src/
├── config.py                  # AWS and app configuration
├── domain/                    # Core domain
├── integrations/              # Third-party integrations
├── pipeline/                  # Core extraction pipeline
└── ui/                        # Streamlit UI components

pages/
├── 1_Schema_Studio.py         # Schema definition and management
├── 2_Extract.py               # Document upload and run extraction
└── 3_Results.py               # Extraction results viewer
```

## Backend Interface

The `run_pipeline()` function in `src/pipeline/runner.py` is the **single entry point** for any frontend (Streamlit, REST API, CLI, etc.) to run document extraction. It provides a **frontend-agnostic interface** that handles all orchestration internally.

### Input Contract: File Preparation

Before calling `run_pipeline()`, prepare a list of document payloads. Each payload must contain **exactly one** of `ocr_text` or `file_bytes`:

```python
parsed_files = [
    {
        "name": "documento.pdf",           # filename with extension
        "file_bytes": b"...binary data..."  # raw file bytes (for PDF, JPG, PNG, JPEG)
    },
    {
        "name": "testo.txt",               # filename with extension
        "ocr_text": "Already extracted text..."  # pre-extracted text (for .txt files)
    },
]
```

### Function Signature

```python
from src.pipeline.runner import run_pipeline, PipelineOptions
from src.domain.stores.run_store import RunStore

run = run_pipeline(
    # REQUIRED parameters (3):
    files: list[dict[str, Any]],           # File payloads as above
    default_schema: DocumentSchema,        # Schema object (from domain.utils.schema_types)
    options: PipelineOptions,              # Options(compute_confidence=True/False)
    
    # OPTIONAL parameters (3):
    run_store: RunStore | None = None,     # Where to save run.json (None = no save)
    schema_name: str | None = None,        # Custom run label (default: schema.name)
    progress_callback: Callable[[str, float], None] | None = None,  # (msg, progress) callback
) -> ExtractionRun:
```

### Required Parameters Explained

| Parameter | Type | Description | Format |
|-----------|------|-------------|--------|
| `files` | `list[dict]` | Documents to process | Each dict must have `name` + (`ocr_text` OR `file_bytes`) |
| `default_schema` | `DocumentSchema` | Schema defining document type and fields | Import from `src.domain.utils.schema_types` |
| `options` | `PipelineOptions` | Extraction configuration | `PipelineOptions(compute_confidence=True/False)` |

### Optional Parameters Explained

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `run_store` | `RunStore \| None` | `None` | If provided, saves results to `data/runs/`. If `None`, returns only in-memory result. |
| `schema_name` | `str \| None` | `None` | Custom label for the run. If omitted, uses `default_schema.name`. |
| `progress_callback` | `Callable \| None` | `None` | Callback function `(message: str, progress: float)` for UI updates. Called as processing proceeds. |

### Return Value: `ExtractionRun` Structure

```json
{
  "run_id": "run_20260419T152651Z_1c215c",
  "started_at": "2026-04-19T15:26:51.123456+00:00",
  "schema_name": "carta d'identita",
  "status": "completed",
  "compute_confidence": true,
  "documents": [
    {
      "filename": "documento.pdf",
      "document_type": "carta d'identita",
      "extracted": {
        "nome": "Mario",
        "cognome": "Rossi",
        "data_nascita": "1990-05-15"
      },
      "corrected": {...},
      "field_confidence": {
        "nome": 0.98,
        "cognome": 0.95,
        "data_nascita": 0.87
      },
      "warnings": [],
      "errors": []
    }
  ]
}
```

Access the result using: `run.to_dict()` to serialize to JSON, or access attributes directly (e.g., `run.documents[0].extracted`).

## Notes

### Access
- Keep AWS credentials in `~/.aws/credentials`; do not hardcode secrets.
- Ensure IAM permissions include:
  - Bedrock runtime access (`bedrock:InvokeModel` or `bedrock-runtime:InvokeModel`)
  - Textract access (`textract:DetectDocumentText`)

### Language
Prompts were designed and written for documents in italian language. It is very likely that this project works better with documents in italian rather than in any other language.