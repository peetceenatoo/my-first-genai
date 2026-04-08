from __future__ import annotations

from datetime import datetime
from pathlib import Path
import streamlit as st
from PIL import Image

from src.config import load_config
from src.domain.run_store import RunStore
from src.domain.schema_store import SchemaStore
from src.integrations.preprocess import preprocess
from src.pipeline.classification import DEFAULT_CLASSIFIER_PROMPT
from src.pipeline.extraction import DEFAULT_EXTRACTION_PROMPT
from src.pipeline.runner import PipelineOptions, run_pipeline
from src.logging import setup_logging
from src.ui.components import (
    inject_branding,
    inject_global_styles,
    section_spacer,
    section_title,
)


config = load_config()
setup_logging()
store = SchemaStore(config.prebuilt_schemas_path, config.custom_schemas_path)
run_store = RunStore(config.run_store_dir)

st.set_page_config(page_title="Extract", page_icon="⚡", layout="wide")

inject_branding(Path("data/assets/data_reply.svg"))
inject_global_styles()

st.title("⚡ Run Extraction")
st.caption("Upload documents and run the extraction pipeline.")

schemas = store.list_schemas()
if not schemas:
    st.warning("No schemas found. Create one in Schema Studio first.")
    st.stop()

schema_names = [schema.name for schema in schemas]
schema_placeholder = "Select schema"

if "extract_use_classification_prev" not in st.session_state:
    st.session_state["extract_use_classification_prev"] = False
if "extract_selected_schema" not in st.session_state:
    st.session_state["extract_selected_schema"] = schema_placeholder

section_spacer()

left, _, right = st.columns([5, 1, 4])
with left:
    files = st.file_uploader(
        "Upload documents",
        type=["pdf", "png", "jpg", "jpeg", "txt"],
        accept_multiple_files=True,
    )

with right:
    section_title("Pipeline options")
    compute_conf = st.toggle("Field confidence", value=True)
    enable_ocr = st.toggle("Enable OCR", value=False)
    use_classification = st.toggle("Classify", value=False)

    prev_use_classification = st.session_state.get("extract_use_classification_prev", False)
    if use_classification and not prev_use_classification:
        st.session_state["extract_selected_schema"] = schema_placeholder

    selected_schema_name = st.selectbox(
        "Choose schema",
        options=[schema_placeholder] + schema_names,
        key="extract_selected_schema",
        disabled=use_classification,
    )
    st.session_state["extract_use_classification_prev"] = use_classification
    if use_classification:
        st.caption("Schema selection is locked while Classify is enabled.")

with st.sidebar:
    st.subheader("Used prompts")
    with st.expander("Edit prompts", expanded=False):
        classifier_prompt = st.text_area(
            "Classifier prompt",
            value=st.session_state.get("classifier_prompt", DEFAULT_CLASSIFIER_PROMPT),
            height=140,
        )
        extractor_prompt = st.text_area(
            "Extraction prompt",
            value=st.session_state.get("extractor_prompt", DEFAULT_EXTRACTION_PROMPT),
            height=160,
        )
        if st.button("Save prompts"):
            st.session_state["classifier_prompt"] = classifier_prompt
            st.session_state["extractor_prompt"] = extractor_prompt
            st.success("Prompts saved.")

section_spacer("lg")

if st.button("Run extraction", type="primary", width="stretch"):
    if not files:
        st.error("Upload at least one document.")
        st.stop()

    schema_map = {schema.name: schema for schema in schemas}
    selected_schema = schema_map.get(selected_schema_name)
    if not use_classification and not selected_schema:
        st.error("Select a valid schema before running.")
        st.stop()

    parsed_files = []
    progress = st.progress(0.0, "Parsing files")

    for idx, upload in enumerate(files, start=1):
        filename = upload.name

        if filename.lower().endswith(".txt"):
            content = upload.read().decode("utf-8", errors="ignore")
            blank_image = Image.new("RGB", (800, 1000), color="white")
            images = [blank_image]
            payload = {
                "name": filename,
                "images": images,
                "ocr_text": content,
            }
        else:
            images = preprocess(upload, filename)
            payload = {"name": filename, "images": images}
        parsed_files.append(payload)

        progress.progress(idx / len(files), f"Parsed {filename}")

    progress.empty()
    options = PipelineOptions(
        enable_ocr=enable_ocr,
        compute_confidence=compute_conf,
        use_classification=use_classification,
        classifier_prompt=st.session_state.get("classifier_prompt"),
        extraction_prompt=st.session_state.get("extractor_prompt"),
    )

    pipeline_default_schema = None if use_classification else selected_schema
    run_schema_name = "Classify" if use_classification else selected_schema_name
    progress = st.progress(0.0, "Starting pipeline...")

    def update_progress(label: str, value: float) -> None:
        progress.progress(value, label)

    run = run_pipeline(
        files=parsed_files,
        default_schema=pipeline_default_schema,
        schema_map=schema_map,
        candidates=schema_names + ["Unknown", "Other"],
        run_store=run_store,
        options=options,
        schema_name=run_schema_name,
        progress_callback=update_progress,
    )
    progress.empty()

    st.session_state["latest_run_id"] = run.run_id
    section_spacer()
    completed_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    st.success(f"Extraction completed • {completed_at}")
    st.page_link("pages/3_Results.py", label="View results", width="stretch")
