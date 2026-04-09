from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4


@dataclass
class RunDocument:
    filename: str
    document_type: str
    extracted: dict[str, Any]
    corrected: dict[str, Any]
    document_type_original: str | None = None
    document_type_corrected: str | None = None
    preview_image: str | None = None
    field_confidence: dict[str, float | None] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


@dataclass
class ExtractionRun:
    run_id: str
    started_at: str
    schema_name: str
    documents: list[RunDocument]
    status: str = "completed"
    compute_confidence: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "started_at": self.started_at,
            "schema_name": self.schema_name,
            "status": self.status,
            "compute_confidence": self.compute_confidence,
            "documents": [
                {
                    "filename": doc.filename,
                    "document_type": doc.document_type,
                    "document_type_original": doc.document_type_original,
                    "document_type_corrected": doc.document_type_corrected,
                    "preview_image": doc.preview_image,
                    "extracted": doc.extracted,
                    "corrected": doc.corrected,
                    "field_confidence": doc.field_confidence,
                    "warnings": doc.warnings,
                    "errors": doc.errors,
                }
                for doc in self.documents
            ],
        }


class RunStore:
    def __init__(self, base_dir: Path):
        self.base_dir = base_dir
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def create_run_id(self) -> str:
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        return f"run_{timestamp}_{uuid4().hex[:6]}"

    def save(self, run: ExtractionRun) -> Path:
        run_dir = self.base_dir / run.run_id
        run_dir.mkdir(parents=True, exist_ok=True)
        run_path = run_dir / "run.json"
        with run_path.open("w", encoding="utf-8") as fp:
            json.dump(run.to_dict(), fp, indent=2, ensure_ascii=False)
        return run_path

    def list_runs(self) -> list[dict[str, Any]]:
        runs: list[dict[str, Any]] = []
        for run_dir in sorted(self.base_dir.glob("run_*"), reverse=True):
            run_path = run_dir / "run.json"
            if not run_path.exists():
                continue
            with run_path.open("r", encoding="utf-8") as fp:
                payload = json.load(fp)
            runs.append(payload)
        return runs

    def load(self, run_id: str) -> dict[str, Any] | None:
        run_path = self.base_dir / run_id / "run.json"
        if not run_path.exists():
            return None
        with run_path.open("r", encoding="utf-8") as fp:
            return json.load(fp)
