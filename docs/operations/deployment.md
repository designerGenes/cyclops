# Deployment

Cyclops Phase 1 supports both a local build / remote deploy path and a pull-based deploy path. Run the commands below from the repository root. Configure [private local node mappings](local-configuration.md) before deploying; do not put real device names or addresses in Git.

## Release bundle workflow

1. Build a release bundle:

   ```bash
   bash ops/deploy/build-release.sh
   ```

2. Deploy an edge release to a target:

   ```bash
   bash ops/deploy/deploy-edge.sh dist/releases/<release>.tar.gz \
  "$(uv run python ops/deploy/local_config.py target camera-01)"
   ```

3. Deploy a coordinator release to a target:

   ```bash
   bash ops/deploy/deploy-coordinator.sh dist/releases/<release>.tar.gz \
  "$(uv run python ops/deploy/local_config.py target coordinator)"
   ```

These scripts unpack to `/opt/cyclops/releases/<version>`, update `/opt/cyclops/current`, run `uv sync --frozen` on-device, install systemd units if needed, and restart the relevant service.

## Pull-based workflow

On the target host:

```bash
bash ops/deploy/deploy-from-git.sh /opt/cyclops/current cyclops-coordinator
```

This performs `git pull --ff-only`, `uv sync --frozen`, rebuilds coordinator web assets when applicable, and restarts the named service.
