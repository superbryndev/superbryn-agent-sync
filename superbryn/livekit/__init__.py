"""LiveKit adapter — build an AgentSyncManifest from a LiveKit Agent.

Lazy submodule: the base ``superbryn`` package does not depend on
LiveKit. Extraction reads ``agent.llm`` / ``agent.stt`` / ``agent.tts``
(works for both ``Agent`` and ``AgentSession``), unwrapping
``FallbackAdapter`` / ``StreamAdapter`` / custom wrapper classes to the
base ``livekit.plugins.<provider>`` instance first; ``FallbackAdapter``
fallbacks are represented in the manifest's ``fallback`` sub-blocks.

Extraction reads a fixed allow-list of configuration attributes —
including private fields such as ``_opts``, ``_model`` and ``_voice``
where LiveKit plugins keep their settings. Credential attributes (API
keys, tokens, secrets) are never part of that list and are never read
or transmitted.

>>> from superbryn import Superbryn
>>> from superbryn.livekit import build_manifest_from_agent
>>> manifest = build_manifest_from_agent(
...     agent,
...     identity={"name": "Support Agent", "type": "inbound", "agent_modality": "voice"},
...     policy_guardrails=open("guardrails.md").read(),
... )
>>> Superbryn(api_key="sk_agent_...").sync(manifest)
"""

from __future__ import annotations

import logging
from typing import Any

from ..manifest import Manifest

logger = logging.getLogger("superbryn.livekit")

_MODEL_ATTRS = ("model", "_model", "model_name", "_opts.model", "opts.model")
_VOICE_ATTRS = (
    "voice",
    "_voice",
    "voice_id",
    "_voice_id",
    "_opts.voice",
    "opts.voice",
    "_opts.voice_id",
    "opts.voice_id",
)
_LANGUAGE_ATTRS = ("language", "_language", "_opts.language", "opts.language")

# Attribute names commonly used by TTS/STT/LLM wrappers to reference the
# underlying instance, in priority order. ``_*_instances`` are the list
# attributes used by LiveKit's FallbackAdapter (first entry = primary).
_INNER_ATTRS_BY_ROLE: dict[str, tuple[str, ...]] = {
    "tts": ("_tts_instances", "_wrapped_tts", "_inner_tts", "_inner", "_base_tts", "tts"),
    "stt": ("_stt_instances", "_wrapped_stt", "_inner_stt", "_inner", "_base_stt", "stt"),
    "llm": ("_llm_instances", "_inner_llm", "_inner", "_base_llm", "llm"),
}


def _unwrap_component(component: Any, inner_attrs: tuple[str, ...]) -> Any:
    """Descend through wrappers (FallbackAdapter, StreamAdapter, custom
    classes) to the base ``livekit.plugins.*`` instance. Cycle-safe."""
    visited: set[int] = set()
    current = component
    while current is not None and id(current) not in visited:
        visited.add(id(current))
        module = getattr(current, "__module__", "") or ""
        if module.startswith("livekit.plugins."):
            return current
        next_inner: Any = None
        for attr in inner_attrs:
            candidate = getattr(current, attr, None)
            if candidate is None:
                continue
            if isinstance(candidate, (list, tuple)):
                if not candidate:
                    continue
                candidate = candidate[0]
            if candidate is current:
                continue
            next_inner = candidate
            break
        if next_inner is None:
            return current
        current = next_inner
    return current


def _fallback_instances(component: Any, inner_attrs: tuple[str, ...]) -> list[Any]:
    """Non-primary FallbackAdapter members ([] for other wrappers). Walks the
    wrapper chain so an adapter nested inside a custom wrapper is found."""
    visited: set[int] = set()
    current = component
    while current is not None and id(current) not in visited:
        visited.add(id(current))
        next_inner: Any = None
        for attr in inner_attrs:
            candidate = getattr(current, attr, None)
            if candidate is None:
                continue
            if isinstance(candidate, (list, tuple)):
                if len(candidate) > 1:
                    return list(candidate[1:])
                if not candidate:
                    continue
                candidate = candidate[0]
            if candidate is current:
                continue
            next_inner = candidate
            break
        current = next_inner
    return []


def _read_attr_chain(source: Any, *names: str) -> Any:
    for name in names:
        cur: Any = source
        for part in name.split("."):
            cur = getattr(cur, part, None)
            if cur is None:
                break
        if cur not in (None, ""):
            return cur
    return None


def _provider_from_plugin(obj: Any) -> str | None:
    """Extract the provider from a livekit.plugins.<provider>.* module path."""
    module = type(obj).__module__ or ""
    parts = module.split(".")
    if "plugins" in parts:
        idx = parts.index("plugins")
        if idx + 1 < len(parts):
            return parts[idx + 1]
    return None


def _extract_component_fields(obj: Any, role: str) -> dict[str, Any]:
    block: dict[str, Any] = {}

    provider = _provider_from_plugin(obj)
    if provider:
        block["provider"] = provider

    model = _read_attr_chain(obj, *_MODEL_ATTRS)
    if isinstance(model, str) and model:
        block["model"] = model

    if role == "stt":
        language = _read_attr_chain(obj, *_LANGUAGE_ATTRS)
        if isinstance(language, str) and language:
            block["language"] = language

    if role == "tts":
        voice = _read_attr_chain(obj, *_VOICE_ATTRS)
        if isinstance(voice, str) and voice:
            block["voice_id"] = voice

    return block


def _extract_component(obj: Any, role: str) -> dict[str, Any] | None:
    """Extract a {provider, model, ...} block from a LiveKit component.

    Components are often not the plugin itself but a wrapper —
    ``FallbackAdapter``, ``StreamAdapter``, or a custom class holding the
    real plugin in an inner attribute. Those wrappers carry no provider
    module path and no model/voice attributes, so extraction on the wrapper
    yields nothing. Unwrap to the base plugin first (cycle-safe), and for
    ``FallbackAdapter`` report the first non-primary instance in the
    manifest's ``fallback`` sub-block.
    """
    if obj is None:
        return None

    inner_attrs = _INNER_ATTRS_BY_ROLE[role]
    base = _unwrap_component(obj, inner_attrs)
    block = _extract_component_fields(base if base is not None else obj, role)

    fallbacks = _fallback_instances(obj, inner_attrs)
    if fallbacks:
        fallback_base = _unwrap_component(fallbacks[0], inner_attrs)
        fallback_block = _extract_component_fields(
            fallback_base if fallback_base is not None else fallbacks[0], role
        )
        if fallback_block:
            block["fallback"] = fallback_block

    return block or None


def build_manifest_from_agent(
    agent: Any,
    *,
    source: str = "livekit",
    identity: dict[str, Any] | None = None,
    behavior: dict[str, Any] | None = None,
    tools: list[dict[str, Any]] | None = None,
    language: dict[str, Any] | None = None,
    telephony: dict[str, Any] | None = None,
    policy_guardrails: str | None = None,
    additional_details: str | None = None,
    concurrency_calls: int | None = None,
) -> Manifest:
    """Build an :class:`superbryn.Manifest` from a LiveKit Agent / AgentSession.

    Reads ``agent.llm`` / ``agent.stt`` / ``agent.tts`` for the pipeline
    blocks and ``agent.instructions`` as the behavior prompt unless an
    explicit ``behavior`` override is given. Extraction failures degrade
    to a sparser manifest, never an error.
    """
    manifest: dict[str, Any] = {"source": source}

    try:
        for role in ("llm", "stt", "tts"):
            block = _extract_component(getattr(agent, role, None), role)
            if block:
                manifest[role] = block
    except Exception as exc:  # noqa: BLE001 — never break the customer's agent
        logger.debug("agent extraction failed: %s", exc)

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

    if behavior is None:
        try:
            instructions = getattr(agent, "instructions", None)
            if isinstance(instructions, str) and instructions.strip():
                behavior = {"prompt": instructions}
        except Exception as exc:  # noqa: BLE001 — never break the customer's agent
            logger.debug("instructions extraction failed: %s", exc)

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
