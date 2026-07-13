"""Package surface: exports, version consistency, import safety."""

from __future__ import annotations

import re
import socket
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


def test_all_exports_are_importable():
    import superbryn

    for name in superbryn.__all__:
        assert hasattr(superbryn, name), f"__all__ lists {name} but it is not importable"


def test_version_is_consistent_everywhere():
    import superbryn

    pyproject = (REPO_ROOT / "pyproject.toml").read_text()
    declared = re.search(r'^version = "(.+?)"', pyproject, re.MULTILINE).group(1)
    assert superbryn.__version__ == declared

    bumpversion = (REPO_ROOT / ".bumpversion.cfg").read_text()
    tracked = re.search(r"current_version = (.+)", bumpversion).group(1).strip()
    assert tracked == declared

    changelog = (REPO_ROOT / "CHANGELOG.md").read_text()
    assert f"## [{declared}]" in changelog, (
        "CHANGELOG.md must have a section for the declared version"
    )


def test_manifest_building_needs_no_env_or_network(monkeypatch):
    monkeypatch.delenv("SUPERBRYN_API_KEY", raising=False)
    monkeypatch.delenv("SUPERBRYN_BASE_URL", raising=False)

    def no_network(*args, **kwargs):
        raise AssertionError("network access attempted during manifest build")

    monkeypatch.setattr(socket.socket, "connect", no_network)

    from superbryn import Manifest
    from superbryn.livekit import build_manifest_from_agent
    from superbryn.pipecat import build_manifest_from_pipeline

    assert build_manifest_from_pipeline(object()) == {"source": "pipecat"}
    assert build_manifest_from_agent(object()) == {"source": "livekit"}
    built = Manifest.builder(source="custom").set_llm(provider="openai").build()
    assert built["llm"] == {"provider": "openai"}
