# Extractly

Extractly is a Streamlit app for defining document schemas and extracting structured metadata with traceable runs. It is designed to feel like a client-ready “Document Metadata Extraction Studio” with clear workflow steps and demo-friendly outputs.

## Quickstart

### Without Docker

To run without Docker:

1. Configure AWS credentials with `aws configure` (this writes `~/.aws/credentials` and `~/.aws/config`).
2. Install dependencies (for example with `uv` or `pip`).
3. Run the app:

```
streamlit run Home.py
```

### With Docker

To run with docker:

1. Configure AWS credentials with `aws configure` (this writes `~/.aws/credentials` and `~/.aws/config`).
2. Build the image:

```bash
docker build -t extractly:latest .
```

3. Run the app:

```bash
docker run --rm -p 8501:8501 -v ~/.aws:/root/.aws:ro extractly:latest
```

## About

### Schema Studio
- New schemas can be created in the Schema Studio.
- All schemas are stored in a single file (`schemas/schemas.json`) with unique schema names.

### Extraction Pipeline
- Input documents are pre-processed.
- **OCR is performed with AWS Textract:**
  - Primary: `AnalyzeDocument` with `FORMS`, `TABLES`, and `QUERIES` generated dynamically from schema field names for targeted extraction.
  - Fallback: `DetectDocumentText` for OCR-only mode if AnalyzeDocument fails for any reason.
  - For multi-page files, OCR runs page by page, then all results are aggregated into a `TextractDocument`.
- **Metadata extraction from structured context:**
  - The `TextractDocument` is serialized into a rich prompt context for Bedrock models.
  - Bedrock extracts and validates metadata against the schema using JSON Schema constraints.
  - Multiple votes (configurable, default 3–7) are aggregated for confidence scoring.
- **Output serialization:**
  - All extraction runs are stored in `data/runs/` with input filenames and output JSON.
  - Each run includes extracted metadata, confidence scores (optional), warnings, and errors.

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

## Notes

### Access
- Keep AWS credentials in `~/.aws/credentials`; do not hardcode secrets.
- Ensure IAM permissions include:
  - Bedrock runtime access (`bedrock:InvokeModel` or `bedrock-runtime:InvokeModel`)
  - Textract access (`textract:AnalyzeDocument`, `textract:DetectDocumentText`)

### Language

Prompts were designed and written for documents in italian language. It is very likely that this project works better with documents in italian rather than in any other language.