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
from .extractors._shared import service_role, unwrap_service

logger = logging.getLogger("superbryn.pipecat")

_EXTRACTORS = {"llm": extract_llm, "stt": extract_stt, "tts": extract_tts}

# Attributes holding child processors on compound processors.
# ``_processors`` — Pipeline; ``_pipelines`` — ParallelPipeline (and its
# subclasses ServiceSwitcher / LLMSwitcher, whose branches wrap each service
# as Filter → Service → Filter inside a nested Pipeline).
_CHILD_LIST_ATTRS = ("_processors", "_pipelines", "processors")


def _walk_processors(pipeline: Any) -> list[Any]:
    """Recursively flatten a Pipecat pipeline into a processor list (best effort).

    Descends through nested ``Pipeline`` / ``ParallelPipeline`` /
    ``ServiceSwitcher`` structures (cycle-safe), so services buried inside
    switcher branches are found too. Order follows branch order — for a
    ``ServiceSwitcher`` the primary (initially active) service comes first.
    """
    flat: list[Any] = []
    visited: set[int] = set()

    def _walk(node: Any) -> None:
        if node is None or id(node) in visited:
            return
        visited.add(id(node))
        flat.append(node)
        for attr in _CHILD_LIST_ATTRS:
            children = getattr(node, attr, None)
            if isinstance(children, (list, tuple)) and children:
                for child in children:
                    _walk(child)
                break

    _walk(pipeline)
    return flat[1:] if flat and flat[0] is pipeline else flat


def _switcher_services(processor: Any) -> list[Any]:
    """The member services of a ServiceSwitcher/LLMSwitcher, or [] otherwise."""
    services = getattr(processor, "_services", None)
    if isinstance(services, (list, tuple)) and services:
        return list(services)
    return []


def _extract_block(processor: Any) -> tuple[str | None, dict[str, Any] | None]:
    """(role, block) for a processor, unwrapping custom wrappers first."""
    service = unwrap_service(processor)
    role = service_role(service)
    if role is None:
        return None, None
    return role, _EXTRACTORS[role](service)


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

    Recursively walks the pipeline (including ``ParallelPipeline`` branches
    and ``ServiceSwitcher`` / ``LLMSwitcher`` members, unwrapping custom
    wrapper classes), dispatches each ``pipecat.services.*`` processor to a
    known extractor, and fills top-level ``llm`` / ``stt`` / ``tts`` /
    ``voice`` automatically. For switchers, the primary member fills the
    block and the next member lands in its ``fallback`` sub-block.
    Everything the pipeline can't tell us is supplied through the keyword
    overrides and passed through verbatim under ``config``. Extraction
    failures degrade to a sparser manifest, never an error.
    """
    manifest: dict[str, Any] = {"source": source}

    try:
        for processor in _walk_processors(pipeline):
            members = _switcher_services(processor)
            if members:
                # ServiceSwitcher / LLMSwitcher: first member is the primary,
                # the next one is reported as the fallback.
                role, block = _extract_block(members[0])
                if role and role not in manifest and block:
                    if len(members) > 1:
                        fallback_role, fallback = _extract_block(members[1])
                        if fallback and fallback_role == role:
                            block["fallback"] = fallback
                    manifest[role] = block
                continue
            role, block = _extract_block(processor)
            if role is None or role in manifest:
                continue
            if block:
                manifest[role] = block
    except Exception as exc:  # noqa: BLE001 — never break the customer's agent
        logger.debug("pipeline extraction failed: %s", exc)

    tts_block = manifest.get("tts")
    if isinstance(tts_block, dict) and tts_block.get("voice_id"):
        voice_block = {
            k: v
            for k, v in (
                ("provider", tts_block.get("provider")),
                ("voice_id", tts_block["voice_id"]),
            )
            if v
        }
        tts_fallback = tts_block.get("fallback")
        if isinstance(tts_fallback, dict) and tts_fallback.get("voice_id"):
            voice_fallback = {
                k: v
                for k, v in (
                    ("provider", tts_fallback.get("provider")),
                    ("voice_id", tts_fallback["voice_id"]),
                )
                if v
            }
            if voice_fallback:
                voice_block["fallback"] = voice_fallback
        manifest["voice"] = voice_block

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
