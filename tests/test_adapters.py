from superbryn.livekit import build_manifest_from_agent
from superbryn.pipecat import build_manifest_from_pipeline

# ── pipecat ──────────────────────────────────────────────────────────────────


class PipecatLLM:
    __module__ = "pipecat.services.openai.llm"
    model_name = "gpt-4o"


class PipecatSTT:
    __module__ = "pipecat.services.deepgram.stt"
    _model = "nova-3"
    language = "en"


class PipecatTTS:
    __module__ = "pipecat.services.cartesia.tts"
    model = "sonic-2"
    _voice_id = "voice-xyz"


class Aggregator:
    __module__ = "pipecat.processors.aggregators.llm_response_universal"


class FakePipeline:
    _processors = [PipecatSTT(), Aggregator(), PipecatLLM(), PipecatTTS()]


def test_pipecat_extraction():
    manifest = build_manifest_from_pipeline(
        FakePipeline(),
        identity={"name": "P"},
        behavior={"prompt": "hi"},
        policy_guardrails="g",
    )
    assert manifest["source"] == "pipecat"
    assert manifest["llm"] == {"provider": "openai", "model": "gpt-4o"}
    assert manifest["stt"] == {"provider": "deepgram", "model": "nova-3", "language": "en"}
    assert manifest["tts"] == {"provider": "cartesia", "model": "sonic-2", "voice_id": "voice-xyz"}
    assert manifest["voice"] == {"provider": "cartesia", "voice_id": "voice-xyz"}
    assert manifest["config"]["behavior"] == {"prompt": "hi"}


def test_pipecat_extraction_never_raises():
    assert build_manifest_from_pipeline(object()) == {"source": "pipecat"}


# ── livekit ──────────────────────────────────────────────────────────────────


class LiveKitLLM:
    __module__ = "livekit.plugins.openai.llm"
    model = "gpt-4o"


class LiveKitSTT:
    __module__ = "livekit.plugins.deepgram.stt"
    _opts = type("O", (), {"model": "nova-3", "language": "en"})()


class LiveKitTTS:
    __module__ = "livekit.plugins.cartesia.tts"
    model = "sonic-2"
    voice = "voice-abc"


class FakeAgent:
    llm = LiveKitLLM()
    stt = LiveKitSTT()
    tts = LiveKitTTS()
    instructions = "You are a helpful agent."


def test_livekit_extraction():
    manifest = build_manifest_from_agent(FakeAgent(), identity={"name": "A"})
    assert manifest["source"] == "livekit"
    assert manifest["llm"] == {"provider": "openai", "model": "gpt-4o"}
    assert manifest["stt"] == {"provider": "deepgram", "model": "nova-3", "language": "en"}
    assert manifest["tts"] == {"provider": "cartesia", "model": "sonic-2", "voice_id": "voice-abc"}
    assert manifest["voice"] == {"provider": "cartesia", "voice_id": "voice-abc"}
    # instructions become the behavior prompt when no explicit behavior given
    assert manifest["config"]["behavior"] == {"prompt": "You are a helpful agent."}


def test_livekit_explicit_behavior_wins():
    manifest = build_manifest_from_agent(FakeAgent(), behavior={"prompt": "override"})
    assert manifest["config"]["behavior"] == {"prompt": "override"}


def test_livekit_extraction_never_raises():
    assert build_manifest_from_agent(object()) == {"source": "livekit"}
