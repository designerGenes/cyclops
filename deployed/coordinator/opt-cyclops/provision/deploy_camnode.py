"""pyinfra deploy (ALTERNATIVE to deploy/bootstrap_eye.sh).

Both paths now call the same on-device installer
(provision/install_camnode.sh), so there's a single source of truth for
what "set up an eye" means. Use whichever fits your workflow — plain SSH
(deploy/bootstrap_eye.sh) needs only ssh+rsync on your Mac; this needs
pyinfra but gives you inventory files for fleets.

  pyinfra <host> provision/deploy_camnode.py \
      --data node_name=front-door \
      --data cyclops_url=http://cyclops:8080 \
      --data enroll_token=SECRET \
      --data advertise_host=front-door
"""
from pyinfra import host
from pyinfra.operations import files, server

node_name = host.data.get("node_name")
cyclops_url = host.data.get("cyclops_url", "http://cyclops:8080")
enroll_token = host.data.get("enroll_token", "CHANGE-ME")
advertise_host = host.data.get("advertise_host", node_name)
assert node_name, "--data node_name=... is required"

files.sync(
    name="Copy Cyclops repo to the node",
    src=".",
    dest="/tmp/cyclops",
    exclude_dir=[".git", "__pycache__"],
    _sudo=True,
)

run = server.shell(
    name="Run shared on-device installer",
    commands=[
        f"NODE_NAME={node_name} CYCLOPS_URL={cyclops_url} "
        f"ENROLL_TOKEN={enroll_token} ADVERTISE_HOST={advertise_host} "
        f"SRC_DIR=/tmp/cyclops bash /tmp/cyclops/provision/install_camnode.sh"
    ],
    _sudo=True,
)

server.shell(
    name="Reboot if the camera overlay was newly enabled",
    commands=["test -f /run/cyclops-reboot-needed && reboot || true"],
    _sudo=True,
)
