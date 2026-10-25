from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest


MODULE_PATH = Path(__file__).resolve().parents[3] / "ops" / "deploy" / "local_config.py"
SPEC = importlib.util.spec_from_file_location("cyclops_local_config", MODULE_PATH)
assert SPEC and SPEC.loader
local_config = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(local_config)


def sample_config() -> dict:
    return {
        "coordinator": {
            "host": "brain.local",
            "url": "http://brain.local:8080",
            "ssh_user": "brain-admin",
        },
        "ssh": {"user": "default-admin", "public_key": "~/keys/eye.pub"},
        "nodes": {"camera-01": {"host": "eye.local"}},
        "secrets": {"enroll_token": "token with spaces"},
    }


def test_resolve_target_uses_default_ssh_user() -> None:
    assert local_config.resolve_target(sample_config(), "camera-01") == "default-admin@eye.local"


def test_resolve_target_allows_node_override() -> None:
    config = sample_config()
    config["nodes"]["camera-01"]["ssh_user"] = "eye-admin"
    assert local_config.resolve_target(config, "camera-01") == "eye-admin@eye.local"


def test_resolve_name_defaults_to_generic_id() -> None:
    assert local_config.resolve_name(sample_config(), "camera-01") == "camera-01"


def test_resolve_name_uses_private_override() -> None:
    config = sample_config()
    config["nodes"]["camera-01"]["name"] = "private-eye"
    assert local_config.resolve_name(config, "camera-01") == "private-eye"


def test_resolve_target_rejects_unknown_node() -> None:
    with pytest.raises(ValueError, match="no host configured"):
        local_config.resolve_target(sample_config(), "missing")


def test_shell_exports_quote_values_and_expand_paths(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HOME", "/home/test")
    output = local_config.shell_exports(sample_config())
    assert "export BRAIN=http://brain.local:8080" in output
    assert "export BRAIN_SSH=brain-admin@brain.local" in output
    assert "export CYCLOPS_ENROLL_TOKEN='token with spaces'" in output
    assert "export EYE_SSH_PUB=/home/test/keys/eye.pub" in output
