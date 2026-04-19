from __future__ import annotations

from datetime import datetime
from pathlib import Path
import streamlit as st

from src.config import load_config
from src.domain.stores.run_store import RunStore
from src.domain.stores.schema_store import SchemaStore
from src.pipeline.runner import (
    PipelineOptions,
    run_pipeline,
    get_pipeline_for_schema,
)
from src.ui.components import (
    inject_branding,
    inject_global_styles,
    section_spacer,
    section_title,
)


config = load_config()
store = SchemaStore(config.schemas_path)
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

status_rows = []
for schema in schemas:
    pipeline = get_pipeline_for_schema(schema.name)
    is_supported = pipeline is not None
    status_rows.append(
        {
            "schema": schema.name,
            "supported": "Supported" if is_supported else "Not supported",
            "pipeline": pipeline.label if pipeline else "Not implemented",
            "is_supported": is_supported,
        }
    )

supported_schema_names = [ str(row["schema"]) for row in status_rows if bool(row.get("is_supported")) ]

if not supported_schema_names:
    st.warning(
        "Schemas are available, but none is executable yet. "
        "Add a pipeline handler in code before running extraction."
    )
    st.dataframe(status_rows, width="stretch")
    st.stop()

schema_placeholder = "Select schema"

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

    selected_schema_name = st.selectbox(
        "Choose schema",
        options=[schema_placeholder] + supported_schema_names,
        key="extract_selected_schema",
    )
    st.caption("Select a schema with an implemented extraction pipeline.")

section_spacer()
section_title("Schema execution status")
st.dataframe(
    [{"schema": row["schema"], "supported": row["supported"], "pipeline": row["pipeline"]} for row in status_rows],
    width="stretch",
)

section_spacer("lg")

if st.button("Run extraction", type="primary", width="stretch"):
    if not files:
        st.error("Upload at least one document.")
        st.stop()

    schema_map = {schema.name: schema for schema in schemas}
    selected_schema = schema_map.get(selected_schema_name)
    if not selected_schema:
        st.error("Select a valid schema before running.")
        st.stop()

    parsed_files = []
    progress = st.progress(0.0, "Parsing files")

    for idx, upload in enumerate(files, start=1):
        filename = upload.name

        if filename.lower().endswith(".txt"):
            content = upload.read().decode("utf-8", errors="ignore")
            payload = {
                "name": filename,
                "ocr_text": content,
            }
        else:
            payload = {
                "name": filename,
                "file_bytes": upload.read(),
            }
        parsed_files.append(payload)

        progress.progress(idx / len(files), f"Parsed {filename}")

    progress.empty()
    options = PipelineOptions(
        compute_confidence=compute_conf,
    )

    run_schema_name = selected_schema_name
    progress = st.progress(0.0, "Starting pipeline...")

    def update_progress(label: str, value: float) -> None:
        progress.progress(value, label)

    run = run_pipeline(
        files=parsed_files,
        default_schema=selected_schema,
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
