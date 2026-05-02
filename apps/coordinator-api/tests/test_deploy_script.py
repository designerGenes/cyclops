from __future__ import annotations

from pathlib import Path


def test_deploy_script_uses_repo_path_for_web_build_check() -> None:
    script_path = Path(__file__).resolve().parents[3] / "ops" / "deploy" / "deploy-from-git.sh"
    script = script_path.read_text()

    assert '${REPO_PATH}/apps/coordinator-web/package.json' in script
    assert '/Users/jadennation/DEV/01_active_projects/cyclops/apps/coordinator-web/package.json' not in script
