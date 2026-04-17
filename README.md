# Extractly

Extractly is a Streamlit app for defining document schemas and extracting structured metadata with traceable runs. It is designed to feel like a client-ready “Document Metadata Extraction Studio” with clear workflow steps and demo-friendly outputs.

This repository is built around a practical pipeline choice: use OCR + LLM across supported document types, with different model strengths depending on document complexity. The goal is to avoid relying on expensive OCR AnalyzeDocument-style processing, which in this setup is considered both cost-inefficient and no longer necessary.

## Quickstart

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

4. Run the app with extraction logging enabled:

```bash
docker run --rm -p 8501:8501 -v ~/.aws:/root/.aws:ro -e EXTRACTLY_ENABLE_LOGGING=1 extractly:latest
```

## About

### Schema Studio
- New schemas can be created in the Schema Studio.
- All schemas are stored in a single file (`schemas/schemas.json`) with unique schema names.
- A schema can be saved even if execution is not implemented yet.

### Extraction Pipeline
- Execution is enabled only for schemas with a registered pipeline handler.
- Current handlers:
  - `Carta d'Identità`: OCR pipeline with AWS Textract `DetectDocumentText` + cheap LLM extraction (Amazon Nova Lite).
  - `Carta di circolazione`: OCR pipeline with AWS Textract `DetectDocumentText` + powerful LLM extraction (Anthropic Haiku 4.5` by default), with 3 votes.
- Shared extraction contract:
  - The extraction prompt is shared across both OCR-based pipelines.
  - Output must be strict JSON aligned to schema field names and types.
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
  - Textract access (`textract:DetectDocumentText`)

### Language

Prompts were designed and written for documents in italian language. It is very likely that this project works better with documents in italian rather than in any other language.