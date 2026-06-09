from __future__ import annotations

from pathlib import Path


def test_deploy_script_uses_repo_path_for_web_build_check() -> None:
    script_path = Path(__file__).resolve().parents[3] / "ops" / "deploy" / "deploy-from-git.sh"
    script = script_path.read_text()

    assert '${REPO_PATH}/apps/coordinator-web/package.json' in script
    assert '/Users/jadennation/DEV/01_active_projects/cyclops/apps/coordinator-web/package.json' not in script


def test_edge_deploy_script_links_prefixed_release_directory() -> None:
    script_path = Path(__file__).resolve().parents[3] / "ops" / "deploy" / "deploy-edge.sh"
    script = script_path.read_text()

    assert 'REMOTE_RELEASE_DIR="/opt/cyclops/releases/cyclops-${VERSION}"' in script


def test_edge_deploy_script_resolves_remote_uv_binary() -> None:
    script_path = Path(__file__).resolve().parents[3] / "ops" / "deploy" / "deploy-edge.sh"
    script = script_path.read_text()

    assert r'UV_BIN=\$(command -v uv || true)' in script
    assert '[ -x /home/jadennation/.local/bin/uv ]' in script
    assert r'\"\${UV_BIN}\" sync --frozen' in script


def test_edge_deploy_script_uses_sudo_for_systemd_actions() -> None:
    script_path = Path(__file__).resolve().parents[3] / "ops" / "deploy" / "deploy-edge.sh"
    script = script_path.read_text()

    assert 'sudo -n systemctl daemon-reload' in script
    assert 'sudo -n systemctl enable cyclops-edge.service' in script
    assert 'sudo -n systemctl restart cyclops-edge.service' in script


def test_coordinator_deploy_script_matches_hardened_release_pattern() -> None:
    script_path = Path(__file__).resolve().parents[3] / "ops" / "deploy" / "deploy-coordinator.sh"
    script = script_path.read_text()

    assert 'REMOTE_RELEASE_DIR="/opt/cyclops/releases/cyclops-${VERSION}"' in script
    assert r'UV_BIN=\$(command -v uv || true)' in script
    assert 'sudo -n systemctl daemon-reload' in script
    assert 'sudo -n systemctl enable cyclops-coordinator.service' in script
    assert 'sudo -n systemctl restart cyclops-coordinator.service' in script
