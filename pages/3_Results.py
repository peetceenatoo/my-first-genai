from __future__ import annotations

import base64
import csv
import io
import json
from datetime import datetime
import html
from pathlib import Path
import streamlit as st

from src.config import load_config
from src.domain.stores.run_store import RunStore
from src.ui.components import (
    inject_branding,
    inject_global_styles,
    section_spacer,
    section_title,
)


config = load_config()
run_store = RunStore(config.run_store_dir)

st.set_page_config(page_title="Results", page_icon="📊", layout="wide")

inject_branding(Path("data/assets/data_reply.svg"))
inject_global_styles()

st.title("📊 Results")
st.caption("Browse extraction runs, review outputs, and export data.")

runs = run_store.list_runs()
if not runs:
    st.info("No runs yet. Run an extraction first.")
    st.stop()

run_ids = [run["run_id"] for run in runs]
latest_id = st.session_state.get("latest_run_id")
selected_id = st.selectbox(
    "Select a run",
    options=run_ids,
    index=run_ids.index(latest_id) if latest_id in run_ids else 0,
)

run = run_store.load(selected_id)
if not run:
    st.error("Run not found.")
    st.stop()

documents = run.get("documents", [])
if not documents:
    st.info("This run has no documents to display.")
    st.stop()


def _boolean_presence_label(value: object) -> str:
    if isinstance(value, bool):
        return "Yes" if value else "No"
    return str(value)

section_spacer("lg")
section_title("Run summary")
started_at_label = "—"
started_at = run.get("started_at")
if started_at:
    try:
        started_at_label = datetime.fromisoformat(started_at).strftime(
            "%Y-%m-%d %H:%M UTC"
        )
    except ValueError:
        started_at_label = started_at

st.markdown(
    f"""
    <div class="extractly-meta-grid">
        <div class="extractly-meta-card">
            <div class="extractly-meta-label">Started</div>
            <div class="extractly-meta-value">{html.escape(started_at_label)}</div>
        </div>
        <div class="extractly-meta-card">
            <div class="extractly-meta-label">Schema</div>
            <div class="extractly-meta-value">{html.escape(str(run.get("schema_name", "—")))}</div>
        </div>
        <div class="extractly-meta-card">
            <div class="extractly-meta-label">Documents</div>
            <div class="extractly-meta-value">{len(documents)}</div>
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)

section_spacer("lg")

section_title("Documents")
run_compute_confidence = run.get("compute_confidence")
if isinstance(run_compute_confidence, bool):
    confidence_enabled = run_compute_confidence
else:
    # Backward-compatible fallback for runs created before run-level flag persistence.
    confidence_enabled = any(
        bool((doc.get("field_confidence") or {})) for doc in documents
    )

review_threshold = 0.0
only_needs_review = False
if confidence_enabled:
    review_threshold = st.slider(
        "Needs review threshold",
        min_value=0.0,
        max_value=1.0,
        value=0.00,
        step=0.05,
        help="Flags documents with low field confidence.",
    )
    only_needs_review = st.checkbox("Show only needs review", value=False)
doc_rows = []
doc_rows.extend(
    (
        {
            "filename": doc.get("filename"),
            "document_type": (
                doc.get("document_type_corrected") or doc.get("document_type") or "—"
            ),
            "warnings": len(doc.get("warnings", [])),
            "errors": len(doc.get("errors", [])),
        }
    )
    for doc in documents
)
if confidence_enabled:
    for row, doc in zip(doc_rows, documents):
        field_conf = doc.get("field_confidence", {}) or {}
        needs_review = any(
            isinstance(value, (int, float)) and value < review_threshold
            for value in field_conf.values()
        )
        row["review"] = "⚠️ Needs review" if needs_review else ""

if only_needs_review:
    doc_rows = [row for row in doc_rows if row.get("review") == "⚠️ Needs review"]

doc_column_config = {
    "filename": st.column_config.TextColumn("File", width="medium"),
    "document_type": st.column_config.TextColumn("Schema", width="small"),
    "warnings": st.column_config.NumberColumn("Warnings", width="small"),
    "errors": st.column_config.NumberColumn("Errors", width="small"),
}
if confidence_enabled:
    doc_column_config["review"] = st.column_config.TextColumn("Review", width="small")

st.dataframe(
    doc_rows,
    width="stretch",
    column_config=doc_column_config,
)

section_spacer()
st.markdown(
    "<div class='extractly-detail-title'>View document details</div>",
    unsafe_allow_html=True,
)
selected_doc_name = st.selectbox(
    "Document",
    options=[doc["filename"] for doc in documents],
    label_visibility="collapsed",
)

selected_doc = next(
    (doc for doc in documents if doc["filename"] == selected_doc_name),
    None,
)

if selected_doc:
    preview_b64 = selected_doc.get("preview_image")
    if preview_b64:
        with st.expander("Document preview", expanded=True):
            st.image(
                base64.b64decode(preview_b64),
                width="stretch",
                caption=selected_doc_name,
            )
    else:
        st.caption("No preview available for this run.")

    doc_type_current = (
        selected_doc.get("document_type_corrected")
        or selected_doc.get("document_type")
        or ""
    )
    original_type = selected_doc.get("document_type_original") or selected_doc.get(
        "document_type"
    )
    if original_type and original_type != doc_type_current:
        st.caption(f"Original: {original_type}")

    corrected_payload = selected_doc.get("corrected") or selected_doc.get(
        "extracted", {}
    )
    field_confidence = selected_doc.get("field_confidence", {}) or {}

    if confidence_enabled:
        low_conf_fields = [
            field
            for field, value in field_confidence.items()
            if isinstance(value, (int, float)) and value < review_threshold
        ]
        if low_conf_fields:
            st.caption("Low confidence: " + ", ".join(sorted(low_conf_fields)))

    field_rows = []
    for key, value in corrected_payload.items():
        display_value = _boolean_presence_label(value)
        if confidence_enabled:
            confidence_value = field_confidence.get(key, "")
            status_label = ""
            if (
                isinstance(confidence_value, (int, float))
                and confidence_value < review_threshold
            ):
                status_label = "⚠️"
            field_rows.append(
                {
                    "field": key,
                    "value": display_value,
                    "confidence": confidence_value,
                    "status": status_label,
                }
            )
        else:
            field_rows.append(
                {
                    "field": key,
                    "value": display_value,
                }
            )

    field_column_config = {
        "field": st.column_config.TextColumn("Field", width="small"),
        "value": st.column_config.TextColumn("Value", width="large"),
    }
    disabled_columns = ["field", "value"]
    if confidence_enabled:
        field_column_config["confidence"] = st.column_config.NumberColumn(
            "Confidence", width="small"
        )
        field_column_config["status"] = st.column_config.TextColumn(
            "Flag", width="small"
        )
        disabled_columns.extend(["confidence", "status"])

    st.markdown(
        "<div class='extractly-detail-subtitle'>Extracted fields</div>",
        unsafe_allow_html=True,
    )
    st.data_editor(
        field_rows,
        num_rows="fixed",
        width="stretch",
        column_config=field_column_config,
        disabled=disabled_columns,
        key=f"field_editor_{selected_doc_name}",
    )

    if selected_doc.get("warnings"):
        st.warning("\n".join(selected_doc.get("warnings")))
    if selected_doc.get("errors"):
        st.error("\n".join(selected_doc.get("errors")))

section_spacer("lg")
section_title("Exports")

json_payload = json.dumps(run, indent=2, ensure_ascii=False)

st.download_button(
    "Download run JSON",
    data=json_payload,
    file_name=f"{selected_id}.json",
    mime="application/json",
)

csv_buffer = io.StringIO()
fieldnames = {
    "filename",
    "document_type",
    "document_type_original",
    "document_type_corrected",
}
for doc in documents:
    fieldnames.update(doc.get("corrected", {}).keys())

writer = csv.DictWriter(csv_buffer, fieldnames=sorted(fieldnames))
writer.writeheader()
for doc in documents:
    doc_type_original = doc.get("document_type_original", doc.get("document_type"))
    doc_type_corrected = doc.get("document_type_corrected", doc.get("document_type"))
    row = {
        "filename": doc.get("filename"),
        "document_type": doc_type_corrected,
        "document_type_original": doc_type_original,
        "document_type_corrected": doc_type_corrected,
    }
    row |= doc.get("corrected", {})
    writer.writerow(row)

st.download_button(
    "Download CSV",
    data=csv_buffer.getvalue(),
    file_name=f"{selected_id}.csv",
    mime="text/csv",
)
