# Optional static inventory if you prefer `pyinfra inventory.py deploy_camnode.py`.
# scripts/add_camera.sh targets hosts ad-hoc, so this is just an example.
eyes = [
    ("front-door", {"node_name": "front-door"}),
    # ("driveway", {"node_name": "driveway"}),
]
