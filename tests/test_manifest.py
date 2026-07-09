import pytest

from superbryn import Manifest, load_manifest_schema


def test_builder_full_manifest_shape():
    manifest = (
        Manifest.builder(source="custom")
        .set_identity(name="Support Agent", type="inbound", agent_modality="voice", gender="female")
        .set_behavior(prompt="You are helpful.")
        .set_llm(provider="openai", model="gpt-4o", temperature=0.7, max_tokens=1024)
        .set_stt(provider="deepgram", model="nova-2", language="en-US")
        .set_tts(provider="cartesia", model="sonic-2")
        .set_voice(provider="cartesia", voice_id="v1")
        .add_tool(
            name="lookup_order",
            description="Look up an order",
            schema={"type": "object"},
            server={"type": "http", "url": "https://api.example.com/orders"},
        )
        .set_language(primary_language="en-US", additional_languages=[{"code": "es-US", "priority": 1}])
        .set_telephony(phone_number="+15551234567", ivr_config={"enabled": True, "number": "1"})
        .set_additional_details("Tier 1 support only")
        .set_policy_guardrails("# Guardrails")
        .set_concurrency_calls(10)
        .build()
    )

    assert manifest["source"] == "custom"
    assert manifest["llm"] == {"provider": "openai", "model": "gpt-4o", "temperature": 0.7, "max_tokens": 1024}
    assert manifest["stt"]["language"] == "en-US"
    assert manifest["voice"]["voice_id"] == "v1"
    config = manifest["config"]
    assert config["identity"]["name"] == "Support Agent"
    assert config["behavior"] == {"prompt": "You are helpful."}
    assert config["tools"][0]["server"] == {"type": "http", "url": "https://api.example.com/orders"}
    assert config["language"]["additional_languages"] == [{"code": "es-US", "priority": 1}]
    assert config["telephony"]["phone_number"] == "+15551234567"
    assert config["policy_guardrails"] == "# Guardrails"
    assert config["concurrency_calls"] == 10


def test_empty_builder_produces_source_only_manifest():
    manifest = Manifest.builder(source="pipecat").build()
    assert manifest == {"source": "pipecat"}


def test_omitted_fields_are_absent_but_explicit_none_is_kept():
    manifest = Manifest.builder().set_identity(name="A", pain_point=None).build()
    identity = manifest["config"]["identity"]
    assert identity == {"name": "A", "pain_point": None}
    assert "gender" not in identity


def test_invalid_source_rejected():
    with pytest.raises(ValueError):
        Manifest.builder(source="not-a-source")


def test_manifest_hash_property_matches_module_function():
    from superbryn import compute_manifest_hash

    manifest = Manifest.builder().set_llm(provider="openai").build()
    assert manifest.hash == compute_manifest_hash(manifest)


def test_bundled_schema_loads_and_matches_manifest_shape():
    schema = load_manifest_schema()
    assert schema["title"] == "AgentSyncManifest"
    assert set(schema["properties"]) >= {"source", "llm", "stt", "tts", "voice", "config"}
