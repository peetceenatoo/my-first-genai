from __future__ import annotations

import base64
import time
from typing import Any

import boto3
from botocore.exceptions import NoCredentialsError
from botocore.config import Config as BotoConfig

from src.config import load_config


def _decode_image_block(image_url: str) -> dict[str, Any]:
    prefix = "data:image/"
    if not image_url.startswith(prefix) or ";base64," not in image_url:
        raise ValueError("Bedrock image blocks require data URI images.")

    header, encoded = image_url.split(";base64,", maxsplit=1)
    image_format = header.removeprefix(prefix).strip().lower()
    if not image_format:
        raise ValueError("Unable to infer image format from data URI.")

    return {
        "image": {
            "format": image_format,
            "source": {"bytes": base64.b64decode(encoded)},
        }
    }


def _normalize_content(content: Any) -> list[dict[str, Any]]:
    if content is None:
        return []
    if isinstance(content, str):
        return [{"text": content}]

    blocks: list[dict[str, Any]] = []
    for block in content:
        if not isinstance(block, dict):
            continue

        block_type = block.get("type")
        if block_type == "text":
            text = str(block.get("text", ""))
            if text:
                blocks.append({"text": text})
        elif block_type == "image_url":
            image_url = block.get("image_url", {}).get("url")
            if image_url:
                blocks.append(_decode_image_block(str(image_url)))

    return blocks


def _extract_text(response: dict[str, Any]) -> str:
    output = response.get("output", {})
    message = output.get("message", {}) if isinstance(output, dict) else {}
    content = message.get("content", []) if isinstance(message, dict) else []
    if not isinstance(content, list):
        return ""

    parts: list[str] = []
    for block in content:
        if isinstance(block, dict) and block.get("text"):
            parts.append(str(block["text"]))
    return "".join(parts)


def get_chat_completion(
    messages: list[dict[str, Any]],
    *,
    model: str,
    temperature: float = 0.0,
) -> str:
    config = load_config()
    client = boto3.client(
        "bedrock-runtime",
        region_name=config.aws_region,
        config=BotoConfig(
            connect_timeout=config.request_timeout_s,
            read_timeout=config.request_timeout_s,
            retries={"max_attempts": 1, "mode": "standard"},
        ),
    )

    attempts = config.max_retries + 1
    system_parts: list[str] = []
    bedrock_messages: list[dict[str, Any]] = []

    for message in messages:
        role = message.get("role")
        content = message.get("content")
        if role == "system":
            if isinstance(content, str) and content.strip():
                system_parts.append(content.strip())
            elif isinstance(content, list):
                for block in _normalize_content(content):
                    text = block.get("text")
                    if text:
                        system_parts.append(str(text))
        elif role in {"user", "assistant"}:
            blocks = _normalize_content(content)
            if blocks:
                bedrock_messages.append({"role": role, "content": blocks})

    request: dict[str, Any] = {
        "modelId": model,
        "messages": bedrock_messages,
        "inferenceConfig": {
            "temperature": temperature,
            "maxTokens": config.max_output_tokens,
        },
    }
    if system_parts:
        request["system"] = [{"text": "\n".join(system_parts)}]

    for attempt in range(attempts):
        try:
            response = client.converse(**request)
            return _extract_text(response)
        except NoCredentialsError as exc:
            raise RuntimeError(
                "AWS credentials not found. Configure AWS_ACCESS_KEY_ID and "
                "AWS_SECRET_ACCESS_KEY (plus AWS_SESSION_TOKEN if temporary), "
                "or provide AWS_PROFILE with mounted ~/.aws credentials. "
                "If running in Docker, mount ~/.aws into the container."
            ) from exc
        except Exception:
            if attempt >= config.max_retries:
                raise
            time.sleep(config.retry_backoff_s * (attempt + 1))

    return ""
