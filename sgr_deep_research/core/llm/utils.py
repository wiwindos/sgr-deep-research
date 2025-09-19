from __future__ import annotations

import json
from typing import Any, Iterable


def coerce_content_to_str(content: Any) -> str | None:
    """Best-effort conversion of provider message content into string."""

    if content is None:
        return None
    if isinstance(content, str):
        return content
    if isinstance(content, bytes):
        return content.decode("utf-8", errors="ignore")
    if isinstance(content, Iterable) and not isinstance(content, (dict, str, bytes)):
        parts = [part for item in content if (part := coerce_content_to_str(item))]
        if not parts:
            return None
        return "".join(parts)
    if hasattr(content, "model_dump"):
        return coerce_content_to_str(content.model_dump())
    if isinstance(content, dict):
        if "text" in content and isinstance(content["text"], str):
            return content["text"]
        parts = [part for value in content.values() if (part := coerce_content_to_str(value))]
        if not parts:
            return None
        return "".join(parts)
    return str(content)


def iter_json_chunks(payload: str, chunk_size: int = 128) -> Iterable[str]:
    """Split JSON payload into deterministic chunks for emulated streaming."""

    for idx in range(0, len(payload), chunk_size):
        yield payload[idx : idx + chunk_size]


def soft_json_parse(raw: str) -> Any:
    """Parse JSON with relaxed heuristics for trailing text."""

    raw = raw.strip()
    if not raw:
        raise ValueError("Empty JSON payload")
    try:
        return json.loads(raw)
    except json.JSONDecodeError as err:
        start = raw.find("{")
        end = raw.rfind("}")
        if start != -1 and end != -1 and end > start:
            candidate = raw[start : end + 1]
            try:
                return json.loads(candidate)
            except json.JSONDecodeError:
                pass
        raise err


def rename_key(data: dict[str, Any], old: str, new: str) -> None:
    """Rename key if present in mapping."""

    if old in data and new not in data:
        data[new] = data.pop(old)
