"""LLM block extractor for Pipecat services."""

from __future__ import annotations

from typing import Any

from ._shared import MODEL_ATTRS, provider_from_module, read_attr_chain


def extract_llm(processor: Any) -> dict[str, Any] | None:
    module = type(processor).__module__ or ""
    block: dict[str, Any] = {}

    provider = provider_from_module(module)
    if provider:
        block["provider"] = provider

    model = read_attr_chain(processor, *MODEL_ATTRS)
    if isinstance(model, str) and model:
        block["model"] = model

    temperature = read_attr_chain(processor, "temperature", "_settings.temperature", "settings.temperature")
    if isinstance(temperature, (int, float)):
        block["temperature"] = float(temperature)

    max_tokens = read_attr_chain(processor, "max_tokens", "_settings.max_tokens", "settings.max_tokens")
    if isinstance(max_tokens, int):
        block["max_tokens"] = max_tokens

    return block or None
