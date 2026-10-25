#!/usr/bin/env python3
"""Resolve private Cyclops deployment settings without storing them in Git."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import shlex
import sys
import tomllib

DEFAULT_CONFIG = Path.home() / ".config" / "cyclops" / "config.toml"


def load_config(path: Path) -> dict:
    """Load a local TOML configuration, returning an empty mapping if absent."""
    if not path.exists():
        return {}
    with path.open("rb") as handle:
        return tomllib.load(handle)


def _expand_path(value: str) -> str:
    return os.path.expanduser(os.path.expandvars(value))


def _target(settings: dict, ssh_defaults: dict) -> str:
    host = str(settings.get("host", ""))
    user = str(settings.get("ssh_user") or ssh_defaults.get("user", ""))
    if user and host:
        return f"{user}@{host}"
    return host


def resolve_target(config: dict, node: str) -> str:
    """Return the SSH target for coordinator or a generic node identifier."""
    if node == "coordinator":
        settings = config.get("coordinator", {})
    else:
        settings = config.get("nodes", {}).get(node, {})
    target = _target(settings, config.get("ssh", {}))
    if not target:
        raise ValueError(f"no host configured for {node!r}")
    return target


def resolve_name(config: dict, node: str) -> str:
    """Return the private on-device name for a generic node identifier."""
    return str(config.get("nodes", {}).get(node, {}).get("name", node))


def shell_exports(config: dict) -> str:
    """Serialize deployment defaults as safely quoted POSIX shell exports."""
    coordinator = config.get("coordinator", {})
    ssh = config.get("ssh", {})
    secrets = config.get("secrets", {})
    values = {
        "CYCLOPS_COORDINATOR_HOST": coordinator.get("host", ""),
        "CYCLOPS_COORDINATOR_URL": coordinator.get("url", ""),
        "BRAIN": coordinator.get("url", ""),
        "BRAIN_SSH": resolve_target(config, "coordinator") if coordinator.get("host") else "",
        "CYCLOPS_SSH_KEY": _expand_path(str(coordinator.get("ssh_key") or ssh.get("key", ""))),
        "EYE_SSH_PUB": _expand_path(str(ssh.get("public_key", ""))),
        "CYCLOPS_ENROLL_TOKEN": secrets.get("enroll_token", ""),
        "TS_AUTHKEY": secrets.get("tailscale_auth_key", ""),
    }
    lines = [f"export {key}={shlex.quote(str(value))}" for key, value in values.items() if value]
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("shell", "target", "name"))
    parser.add_argument("node", nargs="?", help="coordinator, camera-01, camera-02, ...")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    args = parser.parse_args()

    config = load_config(args.config.expanduser())
    try:
        if args.command in {"target", "name"}:
            if not args.node:
                parser.error(f"{args.command} requires a node identifier")
            resolver = resolve_target if args.command == "target" else resolve_name
            print(resolver(config, args.node))
        else:
            output = shell_exports(config)
            if output:
                print(output)
    except (OSError, tomllib.TOMLDecodeError, ValueError) as exc:
        print(f"local configuration error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
