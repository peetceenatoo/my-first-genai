from __future__ import annotations

import base64
from pathlib import Path
import streamlit as st


def inject_branding(logo_path: str | Path, height: str = "64px") -> None:
    logo_path = Path(logo_path)
    if not logo_path.exists():
        return

    encoded = base64.b64encode(logo_path.read_bytes()).decode()
    st.markdown(
        f"""
        <style>
        [data-testid="stSidebarNav"]::before {{
            content: "";
            display: block;
            width: 100%;
            height: {height};
            background-image: url("data:image/svg+xml;base64,{encoded}");
            background-repeat: no-repeat;
            background-position: center;
            background-size: contain;
            margin-bottom: 1rem;
        }}
        </style>
        """,
        unsafe_allow_html=True,
    )


def inject_global_styles() -> None:
    st.markdown(
        """
        <style>
        :root {
            --extractly-border: rgba(148, 163, 184, 0.35);
            --extractly-card: rgba(15, 23, 42, 0.04);
            --extractly-accent: rgba(148, 163, 184, 0.25);
            --extractly-accent-strong: rgba(94, 234, 212, 0.25);
            --extractly-cta-text: #e2e8f0;
        }
        .extractly-hero {
            padding: 3rem 2rem;
            border-radius: 24px;
            background: linear-gradient(135deg, rgba(59,130,246,0.10), rgba(236,254,255,0.5));
            border: 1px solid var(--extractly-border);
            margin-bottom: 2.5rem;
        }
        .extractly-hero h1 {
            font-size: 3rem;
            margin-bottom: 0.5rem;
            line-height: 1.1;
        }
        .extractly-card {
            padding: 1.5rem;
            border-radius: 16px;
            border: 1px solid var(--extractly-border);
            background: var(--extractly-card);
        }
        .extractly-step {
            padding: 1rem 1.25rem;
            border-radius: 12px;
            background: rgba(15, 23, 42, 0.03);
            border: 1px dashed var(--extractly-border);
        }
        .extractly-section-title {
            font-size: 1.5rem;
            margin-bottom: 0.5rem;
            margin-top: 2rem;
        }
        .extractly-stepper {
            display: flex;
            flex-wrap: wrap;
            align-items: center;
            gap: 0.6rem;
        }
        .extractly-stepper-item {
            padding: 0.45rem 0.85rem;
            border-radius: 999px;
            border: 1px solid var(--extractly-border);
            background: var(--extractly-card);
            font-size: 0.9rem;
            font-weight: 600;
        }
        .extractly-stepper-sep {
            opacity: 0.5;
            font-size: 1rem;
        }
        .extractly-caption-space {
            margin-top: 0.85rem;
            margin-bottom: 0.5rem;
            font-size: 0.9rem;
            color: rgba(226, 232, 240, 0.8);
        }
        .extractly-meta-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(210px, 1fr));
            gap: 0.75rem;
        }
        .extractly-meta-card {
            padding: 0.75rem 1rem;
            border-radius: 14px;
            border: 1px solid var(--extractly-border);
            background: var(--extractly-card);
        }
        .extractly-meta-label {
            font-size: 0.7rem;
            text-transform: uppercase;
            letter-spacing: 0.08em;
            color: rgba(148, 163, 184, 0.8);
        }
        .extractly-meta-value {
            margin-top: 0.35rem;
            font-size: 0.95rem;
            color: rgba(226, 232, 240, 0.9);
            word-break: break-word;
            overflow-wrap: anywhere;
        }
        .extractly-detail-title {
            font-size: 1.6rem;
            font-weight: 700;
            margin: 1.5rem 0 0.6rem;
        }
        .extractly-detail-subtitle {
            font-size: 1rem;
            font-weight: 600;
            margin: 1rem 0 0.4rem;
            color: rgba(226, 232, 240, 0.85);
        }
        .extractly-spacer {
            height: 1.5rem;
        }
        .extractly-spacer-lg {
            height: 2.75rem;
        }
        a[data-testid^="stPageLink"],
        div[data-testid^="stPageLink"] a {
            display: flex;
            align-items: center;
            justify-content: center;
            text-decoration: none;
            padding: 0.85rem 1.1rem;
            border-radius: 16px;
            border: 1px solid rgba(148, 163, 184, 0.55);
            background: linear-gradient(
                135deg,
                var(--extractly-accent),
                var(--extractly-accent-strong)
            );
            color: var(--extractly-cta-text) !important;
            font-weight: 700;
            letter-spacing: 0.01em;
            box-shadow: 0 10px 24px rgba(15, 23, 42, 0.35);
            transition: transform 0.18s ease, box-shadow 0.18s ease;
        }
        a[data-testid^="stPageLink"]:hover,
        div[data-testid^="stPageLink"] a:hover {
            transform: translateY(-2px);
            box-shadow: 0 14px 30px rgba(15, 23, 42, 0.45);
        }
        a[data-testid^="stPageLink"]:active,
        div[data-testid^="stPageLink"] a:active {
            transform: translateY(0);
            box-shadow: 0 8px 20px rgba(15, 23, 42, 0.3);
        }
        @media (max-width: 768px) {
            a[data-testid^="stPageLink"],
            div[data-testid^="stPageLink"] a {
                padding: 0.75rem 1rem;
                border-radius: 14px;
            }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def section_title(title: str, subtitle: str | None = None) -> None:
    st.markdown(
        f"<div class='extractly-section-title'><strong>{title}</strong></div>",
        unsafe_allow_html=True,
    )
    if subtitle:
        st.caption(subtitle)


def section_spacer(size: str = "md") -> None:
    class_name = "extractly-spacer-lg" if size == "lg" else "extractly-spacer"
    st.markdown(f"<div class='{class_name}'></div>", unsafe_allow_html=True)
