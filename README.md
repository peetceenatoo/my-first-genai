# Extractly

Extractly is a Streamlit app for defining document schemas, classifying incoming files, and extracting structured metadata with traceable runs. It is designed to feel like a client-ready “Document Metadata Extraction Studio” with clear workflow steps and demo-friendly outputs.

## Quickstart

To run without Docker:

1. Configure AWS credentials with `aws configure` (this writes `~/.aws/credentials` and `~/.aws/config`).
2. Install dependencies (for example with `uv` or `pip`).
3. Run the app:

```
streamlit run Home.py
```

## Docker And AWS Credentials

To run with docker:

1. Mount your AWS profile directory into the container.
2. Run the app:

```bash
docker run --rm -p 8501:8501 -v ~/.aws:/root/.aws:ro extractly:latest
```

## Notes

- All extraction runs are stored in `data/runs/` with input filenames, output JSON, and logs.
- Custom schemas override prebuilt ones when names overlap.
- Keep AWS credentials in `~/.aws/credentials`; do not hardcode secrets.
