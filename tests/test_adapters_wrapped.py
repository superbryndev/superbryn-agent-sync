"""Wrapped/fallback component extraction and secret non-extraction."""

from __future__ import annotations

import json
from types import SimpleNamespace

from superbryn.livekit import build_manifest_from_agent
from superbryn.pipecat import build_manifest_from_pipeline

SECRET = "sk-live-EXTREMELY-SECRET-VALUE"


# ── livekit fakes ────────────────────────────────────────────────────────


def _lk_plugin(name: str, module: str, **attrs):
    cls = type(name, (), {})
    cls.__module__ = module
    obj = cls()
    for key, value in attrs.items():
        setattr(obj, key, value)
    return obj


def _lk_llm(provider="openai", model="gpt-4o", **attrs):
    return _lk_plugin("LLM", f"livekit.plugins.{provider}.llm", model=model, **attrs)


def _lk_tts(provider="elevenlabs", voice_id="voice-abc", **attrs):
    return _lk_plugin(
        "TTS",
        f"livekit.plugins.{provider}.tts",
        _opts=SimpleNamespace(model="eleven_turbo_v2", voice_id=voice_id),
        **attrs,
    )


class LkFallbackAdapter:
    """Mimics livekit.agents FallbackAdapter (list-holding attribute)."""

    def __init__(self, instances, attr):
        setattr(self, attr, list(instances))


class LkStreamAdapter:
    def __init__(self, wrapped):
        self._wrapped_tts = wrapped


class LkAgent:
    def __init__(self, **components):
        for key, value in components.items():
            setattr(self, key, value)


# ── livekit: wrappers and fallbacks ──────────────────────────────────────


def test_livekit_stream_adapter_unwrapped():
    agent = LkAgent(tts=LkStreamAdapter(_lk_tts()))
    manifest = build_manifest_from_agent(agent)
    assert manifest["tts"]["provider"] == "elevenlabs"
    assert manifest["tts"]["voice_id"] == "voice-abc"
    assert manifest["voice"]["voice_id"] == "voice-abc"


def test_livekit_fallback_adapter_primary_and_fallback():
    adapter = LkFallbackAdapter(
        [_lk_tts(voice_id="v-primary"), _lk_tts(provider="cartesia", voice_id="v-fallback")],
        "_tts_instances",
    )
    manifest = build_manifest_from_agent(LkAgent(tts=adapter))

    assert manifest["tts"]["voice_id"] == "v-primary"
    assert manifest["tts"]["fallback"]["provider"] == "cartesia"
    assert manifest["tts"]["fallback"]["voice_id"] == "v-fallback"
    assert manifest["voice"]["fallback"] == {"provider": "cartesia", "voice_id": "v-fallback"}


def test_livekit_llm_fallback_adapter():
    adapter = LkFallbackAdapter(
        [_lk_llm(), _lk_llm(provider="anthropic", model="claude-sonnet-4-5")],
        "_llm_instances",
    )
    manifest = build_manifest_from_agent(LkAgent(llm=adapter))
    assert manifest["llm"]["provider"] == "openai"
    assert manifest["llm"]["fallback"] == {"provider": "anthropic", "model": "claude-sonnet-4-5"}


def test_livekit_cyclic_wrapper_terminates():
    class Wrapper:
        _inner = None

    a, b = Wrapper(), Wrapper()
    a._inner, b._inner = b, a
    manifest = build_manifest_from_agent(LkAgent(tts=a))  # must not hang or raise
    assert "voice" not in manifest


def test_livekit_secrets_never_reach_manifest():
    llm = _lk_llm(api_key=SECRET, _api_key=SECRET)
    tts = _lk_tts(token=SECRET)
    tts._opts.api_key = SECRET
    manifest = build_manifest_from_agent(LkAgent(llm=llm, tts=tts))
    assert SECRET not in json.dumps(manifest)


# ── pipecat fakes ────────────────────────────────────────────────────────


def _pc_service(provider: str, role: str, **attrs):
    cls = type(f"Fake{role.upper()}", (), {})
    cls.__module__ = f"pipecat.services.{provider}.{role}"
    obj = cls()
    for key, value in attrs.items():
        setattr(obj, key, value)
    return obj


class PcPipeline:
    def __init__(self, processors):
        self._processors = list(processors)


class PcParallelPipeline:
    def __init__(self, *branches):
        self._pipelines = [PcPipeline(branch) for branch in branches]


class PcServiceSwitcher(PcParallelPipeline):
    def __init__(self, services):
        filt = SimpleNamespace()
        super().__init__(*[[filt, service, filt] for service in services])
        self._services = list(services)


class PcWrapper:
    def __init__(self, inner, attr="_service"):
        setattr(self, attr, inner)


# ── pipecat: nesting, wrappers, switchers ────────────────────────────────


def test_pipecat_nested_pipeline_recursed():
    inner = PcPipeline([_pc_service("openai", "llm", model_name="gpt-4o")])
    outer = PcPipeline([_pc_service("deepgram", "stt", model_name="nova-3"), inner])
    manifest = build_manifest_from_pipeline(outer)
    assert manifest["llm"]["provider"] == "openai"
    assert manifest["stt"]["provider"] == "deepgram"


def test_pipecat_custom_wrapper_unwrapped():
    wrapped = PcWrapper(
        _pc_service("cartesia", "tts", model_name="sonic-2", _voice_id="v1"), "_tts"
    )
    manifest = build_manifest_from_pipeline(PcPipeline([wrapped]))
    assert manifest["tts"] == {"provider": "cartesia", "model": "sonic-2", "voice_id": "v1"}


def test_pipecat_llm_switcher_primary_and_fallback():
    switcher = PcServiceSwitcher(
        [
            _pc_service("openai", "llm", model_name="gpt-4o"),
            _pc_service("anthropic", "llm", model_name="claude-sonnet-4-5"),
        ]
    )
    manifest = build_manifest_from_pipeline(PcPipeline([switcher]))
    assert manifest["llm"]["provider"] == "openai"
    assert manifest["llm"]["fallback"] == {"provider": "anthropic", "model": "claude-sonnet-4-5"}


def test_pipecat_tts_switcher_fallback_reaches_voice_block():
    switcher = PcServiceSwitcher(
        [
            _pc_service("elevenlabs", "tts", _voice_id="v-primary"),
            _pc_service("cartesia", "tts", _voice_id="v-fallback"),
        ]
    )
    manifest = build_manifest_from_pipeline(PcPipeline([switcher]))
    assert manifest["tts"]["voice_id"] == "v-primary"
    assert manifest["voice"]["fallback"] == {"provider": "cartesia", "voice_id": "v-fallback"}


def test_pipecat_cyclic_pipeline_terminates():
    pipeline = PcPipeline([])
    pipeline._processors.append(pipeline)
    manifest = build_manifest_from_pipeline(pipeline)
    assert manifest["source"] == "pipecat"


def test_pipecat_secrets_never_reach_manifest():
    llm = _pc_service(
        "openai", "llm", model_name="gpt-4o", api_key=SECRET, _settings={"api_key": SECRET}
    )
    manifest = build_manifest_from_pipeline(PcPipeline([llm]))
    assert SECRET not in json.dumps(manifest)


# ── allow-lists stay credential-free ─────────────────────────────────────


def test_attribute_allow_lists_contain_no_credential_names():
    from superbryn.livekit import _LANGUAGE_ATTRS, _MODEL_ATTRS, _VOICE_ATTRS
    from superbryn.pipecat.extractors import _shared

    forbidden = {
        "key",
        "apikey",
        "token",
        "secret",
        "password",
        "credential",
        "credentials",
        "auth",
    }
    for attrs in (
        _MODEL_ATTRS,
        _VOICE_ATTRS,
        _LANGUAGE_ATTRS,
        _shared.MODEL_ATTRS,
        _shared.VOICE_ATTRS,
    ):
        for candidate in attrs:
            segments = candidate.lower().replace(".", "_").split("_")
            assert not (set(segments) & forbidden), f"{candidate!r} looks credential-shaped"
