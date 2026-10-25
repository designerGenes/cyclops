# Private local configuration

Cyclops keeps real device names, addresses, SSH settings, and credentials outside Git. The public repository uses generic identifiers such as `coordinator`, `camera-01`, and `camera-02`; a local TOML file maps those identifiers to the actual deployment.

## Create the private file

```bash
mkdir -p "$HOME/.config/cyclops"
cp config/examples/config.example.toml "$HOME/.config/cyclops/config.toml"
chmod 600 "$HOME/.config/cyclops/config.toml"
```

Edit `$HOME/.config/cyclops/config.toml` with the real values. Do not copy this file into the repository. Set `CYCLOPS_LOCAL_CONFIG` to use a different location.

The file supports:

- `[coordinator]`: private host, base URL, SSH user, and SSH key.
- `[ssh]`: default SSH user and the eye's public-key path.
- `[nodes."camera-01"]`: private on-device `name`, `host`, and optional `ssh_user` overrides. Add more generic node sections as needed.
- `[secrets]`: enrollment and Tailscale auth tokens. Leave these empty to supply them through the environment instead.

## Resolve deployment values

Print a private SSH target for a generic node:

```bash
uv run python ops/deploy/local_config.py target camera-01
```

Resolve its private on-device name:

```bash
uv run python ops/deploy/local_config.py name camera-01
```

Load coordinator and credential defaults into the current shell:

```bash
eval "$(uv run python ops/deploy/local_config.py shell)"
```

The LuckFox provisioning script reads the same TOML file automatically. Explicit script arguments take precedence over local configuration, and existing `BRAIN`, `BRAIN_SSH`, `CYCLOPS_ENROLL_TOKEN`, and `EYE_SSH_PUB` environment values take precedence over TOML defaults.

No command in this document is required during a documentation or history-only release. Running deployment or provisioning scripts is a separate, explicit operation.
