from superbryn.canonical import canonicalize, compute_manifest_hash, extract_sync_payload


def test_sorts_object_keys():
    assert canonicalize({"b": 1, "a": 2}) == '{"a":2,"b":1}'


def test_nested_sorting_and_arrays():
    assert (
        canonicalize({"z": {"y": 1, "x": [2, {"b": 3, "a": 4}]}, "a": None})
        == '{"a":null,"z":{"x":[2,{"a":4,"b":3}],"y":1}}'
    )


def test_scalars():
    assert canonicalize("hi") == '"hi"'
    assert canonicalize(1.5) == "1.5"
    assert canonicalize(2.0) == "2"  # integral floats serialize without fraction
    assert canonicalize(True) == "true"
    assert canonicalize(False) == "false"
    assert canonicalize(None) == "null"


def test_hash_stable_regardless_of_key_order():
    a = {"config": {"identity": {"name": "A", "type": "inbound"}}}
    b = {"config": {"identity": {"type": "inbound", "name": "A"}}}
    assert compute_manifest_hash(a) == compute_manifest_hash(b)


def test_hash_ignores_pipeline_blocks():
    base = {"llm": {"provider": "openai"}, "config": {"identity": {"name": "A"}}}
    pipeline_changed = {
        "llm": {"provider": "anthropic"},
        "stt": {"provider": "deepgram"},
        "config": {"identity": {"name": "A"}},
    }
    assert compute_manifest_hash(base) == compute_manifest_hash(pipeline_changed)


def test_hash_changes_when_config_changes():
    a = {"config": {"identity": {"name": "A"}}}
    b = {"config": {"identity": {"name": "B"}}}
    assert compute_manifest_hash(a) != compute_manifest_hash(b)


def test_hash_excludes_envelope_and_meta():
    bare = {"config": {"identity": {"name": "A"}}}
    enveloped = {
        "source": "pipecat",
        "source_agent_id": "abc",
        "config": {"identity": {"name": "A"}},
        "__meta": {"hash": "stale"},
    }
    assert compute_manifest_hash(bare) == compute_manifest_hash(enveloped)


def test_empty_manifest_matches_server_vector():
    # Server test vector: sha256 of the two-character string "{}"
    assert (
        compute_manifest_hash({})
        == "44136fa355b3678a1146ad16f7e8649e94fb4fc21fe77e8310c060f61caaff8a"
    )


def test_extract_payload_keeps_only_config():
    manifest = {
        "source": "livekit",
        "llm": {},
        "stt": {},
        "tts": {},
        "voice": {},
        "config": {},
        "__meta": {},
    }
    assert list(extract_sync_payload(manifest)) == ["config"]
