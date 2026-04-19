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

## Notes

### Access
- Keep AWS credentials in `~/.aws/credentials`; do not hardcode secrets.
- Ensure IAM permissions include:
  - Bedrock runtime access (`bedrock:InvokeModel` or `bedrock-runtime:InvokeModel`)
  - Textract access (`textract:DetectDocumentText`)

### Language
Prompts were designed and written for documents in italian language. It is very likely that this project works better with documents in italian rather than in any other language.
