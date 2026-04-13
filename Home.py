from __future__ import annotations

from pathlib import Path
import streamlit as st

from src.ui.components import (
    inject_branding,
    inject_global_styles,
    section_spacer,
    section_title,
)

st.set_page_config(page_title="Extractly", page_icon="✨", layout="wide")

inject_branding(Path("data/assets/data_reply.svg"))
inject_global_styles()

st.markdown(
    """
    <div class="extractly-hero">
        <h1>Extractly: Metadata Extraction Studio</h1>
        <p>Design schemas and extract structured metadata in minutes. Built for
        client-ready demos with traceability, exports, and run history baked in.</p>
    </div>
    """,
    unsafe_allow_html=True,
)

cta_cols = st.columns([3, 2, 2, 3])
with cta_cols[1]:
    st.page_link("pages/1_Schema_Studio.py", label="🚀 Build a schema", width="stretch")
with cta_cols[2]:
    st.page_link("pages/2_Extract.py", label="⚡ Run extraction", width="stretch")

section_spacer()

section_title(
    "How it works", "A streamlined workflow your clients understand in seconds."
)
steps = st.columns(3)
steps[0].markdown(
    """
    <div class="extractly-step">
        <strong>Step A — Define a schema</strong>
        <p>Design fields, types, and requirements of documents in the Schema Studio.</p>
    </div>
    """,
    unsafe_allow_html=True,
)
steps[1].markdown(
    """
    <div class="extractly-step">
        <strong>Step B — Upload documents</strong>
        <p>Batch PDFs, images, or text. Select a schema and run extraction pipeline.</p>
    </div>
    """,
    unsafe_allow_html=True,
)
steps[2].markdown(
    """
    <div class="extractly-step">
        <strong>Step C — Review results</strong>
        <p>View extracted data, confidence scores, warnings and export tables.</p>
    </div>
    """,
    unsafe_allow_html=True,
)

section_spacer("lg")

section_title(
    "Product highlights", "Purpose-built for metadata extraction teams and demos."
)
features = st.columns(3)
features[0].markdown(
    """
    <div class="extractly-card">
        <h4>Schema Studio</h4>
        <p>Field editor, JSON preview, schemas, and validation in one place.</p>
    </div>
    """,
    unsafe_allow_html=True,
)
features[1].markdown(
    """
    <div class="extractly-card">
        <h4>Extraction Pipeline</h4>
        <p>Schema-driven extraction with validation, confidence review, and export.</p>
    </div>
    """,
    unsafe_allow_html=True,
)
features[2].markdown(
    """
    <div class="extractly-card">
        <h4>Run History</h4>
        <p>Every run is stored locally with artifacts for traceability and demos.</p>
    </div>
    """,
    unsafe_allow_html=True,
)

section_spacer("lg")
section_spacer("md")
