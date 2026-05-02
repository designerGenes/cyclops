# Deployment

Cyclops Phase 1 supports both a local build / remote deploy path and a pull-based deploy path.

## Release bundle workflow

1. Build a release bundle:

   ```bash
   bash /Users/jadennation/DEV/01_active_projects/cyclops/ops/deploy/build-release.sh
   ```

2. Deploy edge release to a target:

   ```bash
   bash /Users/jadennation/DEV/01_active_projects/cyclops/ops/deploy/deploy-edge.sh /Users/jadennation/DEV/01_active_projects/cyclops/dist/releases/<release>.tar.gz pi@nilescrane.local
   ```

3. Deploy coordinator release to a target:

   ```bash
   bash /Users/jadennation/DEV/01_active_projects/cyclops/ops/deploy/deploy-coordinator.sh /Users/jadennation/DEV/01_active_projects/cyclops/dist/releases/<release>.tar.gz admin@mindsofdunce.local
   ```

These scripts unpack to `/opt/cyclops/releases/<version>`, update `/opt/cyclops/current`, run `uv sync --frozen` on-device, install systemd units if needed, and restart the relevant service.

## Pull-based workflow

On the target host:

```bash
bash /Users/jadennation/DEV/01_active_projects/cyclops/ops/deploy/deploy-from-git.sh /opt/cyclops/current cyclops-coordinator
```

This performs `git pull --ff-only`, `uv sync --frozen`, rebuilds coordinator web assets when applicable, and restarts the named service.
