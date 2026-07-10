"""Pipecat adapter — build an AgentSyncManifest from a running pipeline.

Lazy submodule: the base ``superbryn`` package does not depend on
Pipecat. Importing this module only makes sense in an environment where
the customer already runs Pipecat, but it does not itself import
``pipecat`` — extraction dispatches on module paths, so there is no hard
dependency either way.

>>> from superbryn import Superbryn
>>> from superbryn.pipecat import build_manifest_from_pipeline
>>> manifest = build_manifest_from_pipeline(
...     pipeline,
...     identity={"name": "Support Agent", "type": "inbound", "agent_modality": "voice"},
...     behavior={"prompt": open("prompt.txt").read()},
...     policy_guardrails=open("guardrails.md").read(),
... )
>>> Superbryn(api_key="sk_agent_...").sync(manifest)
"""

from __future__ import annotations

import logging
from typing import Any

from ..manifest import Manifest
from .extractors import extract_llm, extract_stt, extract_tts
from .extractors._shared import service_role

logger = logging.getLogger("superbryn.pipecat")

_EXTRACTORS = {"llm": extract_llm, "stt": extract_stt, "tts": extract_tts}


def _walk_processors(pipeline: Any) -> list[Any]:
    """Flatten a Pipecat pipeline into a processor list (best effort)."""
    processors = getattr(pipeline, "_processors", None) or getattr(pipeline, "processors", None)
    if not processors:
        return []
    flat: list[Any] = []
    for p in processors:
        flat.append(p)
        nested = getattr(p, "_processors", None)
        if nested:
            flat.extend(nested)
    return flat


def build_manifest_from_pipeline(
    pipeline: Any,
    *,
    source: str = "pipecat",
    identity: dict[str, Any] | None = None,
    behavior: dict[str, Any] | None = None,
    tools: list[dict[str, Any]] | None = None,
    language: dict[str, Any] | None = None,
    telephony: dict[str, Any] | None = None,
    policy_guardrails: str | None = None,
    additional_details: str | None = None,
    concurrency_calls: int | None = None,
) -> Manifest:
    """Build an :class:`superbryn.Manifest` from a Pipecat pipeline.

    Walks ``pipeline._processors``, dispatches each ``pipecat.services.*``
    processor to a known extractor, and fills top-level ``llm`` / ``stt`` /
    ``tts`` / ``voice`` automatically. Everything the pipeline can't tell
    us is supplied through the keyword overrides and passed through
    verbatim under ``config``. Extraction failures degrade to a sparser
    manifest, never an error.
    """
    manifest: dict[str, Any] = {"source": source}

    try:
        for processor in _walk_processors(pipeline):
            role = service_role(processor)
            if role is None or role in manifest:
                continue
            block = _EXTRACTORS[role](processor)
            if block:
                manifest[role] = block
    except Exception as exc:  # noqa: BLE001 — never break the customer's agent
        logger.debug("pipeline extraction failed: %s", exc)

    tts_block = manifest.get("tts")
    if isinstance(tts_block, dict) and tts_block.get("voice_id"):
        manifest["voice"] = {
            k: v
            for k, v in (
                ("provider", tts_block.get("provider")),
                ("voice_id", tts_block["voice_id"]),
            )
            if v
        }

    config: dict[str, Any] = {}
    if identity is not None:
        config["identity"] = identity
    if behavior is not None:
        config["behavior"] = behavior
    if tools is not None:
        config["tools"] = tools
    if language is not None:
        config["language"] = language
    if telephony is not None:
        config["telephony"] = telephony
    if policy_guardrails is not None:
        config["policy_guardrails"] = policy_guardrails
    if additional_details is not None:
        config["additional_details"] = additional_details
    if concurrency_calls is not None:
        config["concurrency_calls"] = concurrency_calls
    if config:
        manifest["config"] = config

    return Manifest(manifest)
