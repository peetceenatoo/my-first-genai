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

### Pipeline
- Input documents are pre-processed.
- OCR is performed with AWS Textract (`DetectDocumentText`) to extract text from images.
- Metadata extraction from textual context uses Amazon Bedrock models.

### Output
- All extraction runs are stored in `data/runs/` with input filenames and output JSON.

## Notes

### Access
- Keep AWS credentials in `~/.aws/credentials`; do not hardcode secrets.
- Ensure IAM permissions include both Bedrock runtime access and `textract:DetectDocumentText`.



