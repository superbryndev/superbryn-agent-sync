import textwrap
from pathlib import Path

import pytest

from superbryn.codescan import build_manifest_from_source, fill_manifest_gaps, scan_source

PY_AGENT = textwrap.dedent(
    '''
    from hooman import HoomanAgent
    from pipecat.services.deepgram.stt import DeepgramSTTService
    from pipecat.services.cartesia.tts import CartesiaTTSService

    SYSTEM_PROMPT = """You are a support agent for Acme Corp.
    Always be polite, verify the caller identity, and never
    reveal internal account notes to the caller."""

    stt = DeepgramSTTService(model="nova-3", language="en-US")
    tts = CartesiaTTSService(model="sonic-2", voice_id="voice-abc")

    agent = HoomanAgent(
        prompt=SYSTEM_PROMPT,
        model="gpt-4o",
        temperature=0.6,
        max_tokens=512,
        phone_number="+15551234567",
    )
    '''
)

JS_AGENT = textwrap.dedent(
    """
    import { ShunyaAgent } from "@shunyalabs/sdk";

    const agent = new ShunyaAgent({
      systemPrompt: "You are a helpful voice agent that books restaurant tables for callers.",
      model: "gpt-4o-mini",
      voiceId: "shunya-voice-1",
      language: "en-IN",
      temperature: 0.5,
    });
    """
)


@pytest.fixture
def py_project(tmp_path):
    (tmp_path / "agent.py").write_text(PY_AGENT)
    # noise that must be skipped
    (tmp_path / "node_modules").mkdir()
    (tmp_path / "node_modules" / "junk.js").write_text('const prompt = "ignore me";')
    return tmp_path


def test_python_extraction(py_project):
    manifest = build_manifest_from_source(py_project, source="hooman-labs")
    assert manifest["source"] == "hooman-labs"
    assert manifest["llm"]["model"] == "gpt-4o"
    assert manifest["llm"]["temperature"] == 0.6
    assert manifest["llm"]["max_tokens"] == 512
    assert manifest["stt"] == {"provider": "deepgram", "model": "nova-3", "language": "en-US"}
    assert manifest["tts"] == {"provider": "cartesia", "model": "sonic-2", "voice_id": "voice-abc"}
    assert manifest["voice"] == {"voice_id": "voice-abc", "provider": "cartesia"}
    config = manifest["config"]
    # variable reference SYSTEM_PROMPT resolved to the long string constant
    assert "Acme Corp" in config["behavior"]["prompt"]
    assert config["language"] == {"primary_language": "en-US"}
    assert config["telephony"] == {"phone_number": "+15551234567"}


def test_js_extraction(tmp_path):
    (tmp_path / "agent.ts").write_text(JS_AGENT)
    manifest = build_manifest_from_source(tmp_path, source="shunya-labs")
    assert manifest["source"] == "shunya-labs"
    assert manifest["llm"]["model"] == "gpt-4o-mini"
    assert manifest["llm"]["temperature"] == 0.5
    assert manifest["voice"]["voice_id"] == "shunya-voice-1"
    assert "books restaurant tables" in manifest["config"]["behavior"]["prompt"]
    assert manifest["config"]["language"] == {"primary_language": "en-IN"}


def test_single_file_scan(py_project):
    findings = scan_source(py_project / "agent.py")
    assert findings.files_scanned == 1
    assert any("Acme Corp" in f.value for f in findings.prompts if isinstance(f.value, str))


def test_node_modules_skipped(py_project):
    findings = scan_source(py_project)
    # only agent.py is scanned; the junk.js inside node_modules is skipped
    assert findings.files_scanned == 1
    assert all(Path(f.file).name == "agent.py" for f in findings.prompts)


def test_empty_scan_produces_source_only_manifest(tmp_path):
    manifest = build_manifest_from_source(tmp_path, source="custom")
    assert manifest == {"source": "custom"}


def test_overrides_win(py_project):
    manifest = build_manifest_from_source(
        py_project,
        source="hooman-labs",
        identity={"name": "HL Agent", "type": "inbound"},
        telephony={"phone_number": "+19998887777"},
        policy_guardrails="# Rules",
    )
    assert manifest["config"]["identity"] == {"name": "HL Agent", "type": "inbound"}
    assert manifest["config"]["telephony"] == {"phone_number": "+19998887777"}
    assert manifest["config"]["policy_guardrails"] == "# Rules"


def test_unknown_source_rejected(tmp_path):
    with pytest.raises(ValueError):
        build_manifest_from_source(tmp_path, source="nope")


def test_fill_manifest_gaps_api_values_win(py_project):
    # Sparse translator output (API returned almost nothing useful)
    api_manifest = {
        "source": "vapi",
        "llm": {"model": "gpt-4.1"},  # API value must win over scanned gpt-4o
    }
    merged = fill_manifest_gaps(api_manifest, py_project)
    assert merged["source"] == "vapi"
    assert merged["llm"]["model"] == "gpt-4.1"
    # gaps filled from code: temperature, prompt, tts
    assert merged["llm"]["temperature"] == 0.6
    assert "Acme Corp" in merged["config"]["behavior"]["prompt"]
    assert merged["tts"]["voice_id"] == "voice-abc"


def test_broken_python_file_is_skipped(tmp_path):
    (tmp_path / "broken.py").write_text("def oops(:\n")
    (tmp_path / "ok.py").write_text('agent = Agent(prompt="A perfectly reasonable and long system prompt for testing.")')
    manifest = build_manifest_from_source(tmp_path)
    assert "system prompt for testing" in manifest["config"]["behavior"]["prompt"]
