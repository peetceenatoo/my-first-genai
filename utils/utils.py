"""
Utilities shared among Streamlit pages.
"""

from __future__ import annotations
import json
from pathlib import Path

# Get the project root directory (parent of the src directory)
PROJECT_ROOT = Path(__file__).parent.parent
DATA_DIR = PROJECT_ROOT / "data"
SCHEMAS_DIR = PROJECT_ROOT / "schemas"
FEED_PATH = DATA_DIR / "feedback.jsonl"

# Ensure directories exist
DATA_DIR.mkdir(exist_ok=True)
SCHEMAS_DIR.mkdir(exist_ok=True)


# ---------- 💾  feedback persistence ----------
def load_feedback() -> list[dict]:
    if not FEED_PATH.exists():
        return []
    with FEED_PATH.open(encoding="utf-8") as fp:
        return [json.loads(ln) for ln in fp if ln.strip()]
