from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class AppConfig:
    aws_region: str
    extract_model: str
    max_output_tokens: int
    request_timeout_s: int
    max_retries: int
    retry_backoff_s: float
    run_store_dir: Path
    schemas_path: Path


def load_config() -> AppConfig:
    schema_dir = Path(os.getenv("EXTRACTLY_SCHEMAS_DIR", PROJECT_ROOT / "schemas"))
    aws_region = os.getenv(
        "EXTRACTLY_AWS_REGION",
        os.getenv("AWS_REGION", os.getenv("AWS_DEFAULT_REGION", "us-east-1")),
    )

    return AppConfig(
        aws_region=aws_region,
        extract_model=os.getenv("EXTRACT_MODEL", "amazon.nova-lite-v1:0"),
        max_output_tokens=int(os.getenv("EXTRACTLY_MAX_TOKENS", "4096")),
        request_timeout_s=int(os.getenv("EXTRACTLY_TIMEOUT_S", "40")),
        max_retries=int(os.getenv("EXTRACTLY_MAX_RETRIES", "2")),
        retry_backoff_s=float(os.getenv("EXTRACTLY_RETRY_BACKOFF_S", "1.5")),
        run_store_dir=Path(
            os.getenv("EXTRACTLY_RUNS_DIR", PROJECT_ROOT / "data" / "runs")
        ),
        schemas_path=Path(
            os.getenv(
                "EXTRACTLY_SCHEMAS_PATH",
                schema_dir / "schemas.json",
            )
        ),
    )
