"""Headless sanity check of the generated STL files.

For every part this verifies a watertight 2-manifold (no non-manifold edges,
no degenerate faces), reports bounding box and volume, and then probes a few
specific features with ray cast so a silently-failed boolean gets caught:

* ``cover``  — chimney aperture open over the SoC, RJ45 notch open at the rear
* ``chimney``— exhaust slots open through the stack walls behind the skirt
* ``base``   — intake slots open through the floor beneath the PCB plenum
"""

import sys
from pathlib import Path

import bpy
import bmesh
from mathutils import Vector

STL_DIR = Path(sys.argv[sys.argv.index("--stl") + 1])

INTENT = {
    "base":    dict(x=(-40.0, 40.0), y=(-15.0, 15.0), z=(-4.0, 14.0)),
    "cover":   dict(x=(-40.0, 40.0), y=(-15.0, 15.0), z=(12.0, 25.0)),
    "chimney": dict(x=(-14.0, 22.0), y=(-17.0, 17.0), z=(23.0, 48.0)),
    "nose":    dict(x=(37.0, 62.0), y=(-16.0, 16.0), z=(-3.0, 28.0)),
    "gasket":  dict(x=(-40.0, 40.0), y=(-14.0, 14.0), z=(11.0, 15.0)),
}

# Solid-block reference volumes (mm^3) to confirm void features were removed.
SOLID_VOLUME = {
    "base":    77.2 * 26.2 * 13.0,
    "cover":   77.2 * 26.2 * 10.9,
    "chimney": 32.0 * 32.0 * 23.0,   # bounding solid around stack + cap
    "nose":    12.0 * 29.4 * 28.4,
}

failed = False


def report(ok: bool, part: str, msg: str) -> None:
    global failed
    tag = "OK" if ok else "FAIL"
    if not ok:
        failed = True
    print(f"[{tag}] {part}: {msg}")


def ray_hit(scene, depsgraph, origin, direction, distance=200.0):
    result, loc, normal, index, obj, matrix = scene.ray_cast(
        depsgraph, Vector(origin), Vector(direction), distance=distance
    )
    return (result, loc, obj)


for part, intent in INTENT.items():
    path = STL_DIR / f"luckfox_enclosure_{part}.stl"
    if not path.exists():
        report(False, part, f"missing {path}")
        continue

    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.wm.stl_import(filepath=str(path))
    obj = bpy.context.selected_objects[0] if bpy.context.selected_objects else None
    if obj is None:
        report(False, part, "nothing imported")
        continue

    mesh = obj.data
    bm = bmesh.new()
    bm.from_mesh(mesh)
    non_manifold = [e for e in bm.edges if not e.is_manifold]
    degenerate = [f for f in bm.faces if f.calc_area() < 1e-6]
    volume = abs(bm.calc_volume())
    bm.free()

    bb = [obj.matrix_world @ Vector(c) for c in obj.bound_box]
    xs = [v.x for v in bb]; ys = [v.y for v in bb]; zs = [v.z for v in bb]
    bounds = (min(xs), min(ys), min(zs), max(xs), max(ys), max(zs))

    report(not non_manifold, part, f"{len(non_manifold)} non-manifold edge(s)")
    report(not degenerate, part, f"{len(degenerate)} degenerate face(s)")

    vol_info = ""
    if part in SOLID_VOLUME:
        vol_info = f", volume {volume:.0f} mm^3 (solid {SOLID_VOLUME[part]:.0f})"
    print(f"       {part}: {len(mesh.vertices)} verts / {len(mesh.polygons)} faces, "
          f"bounds x {bounds[0]:.1f}..{bounds[3]:.1f} y {bounds[1]:.1f}..{bounds[4]:.1f} "
          f"z {bounds[2]:.1f}..{bounds[5]:.1f}{vol_info}")

    # ---- feature probes -------------------------------------------------
    scene = bpy.context.scene
    depsgraph = bpy.context.evaluated_depsgraph_get()

    if part == "cover":
        # Chimney aperture: a ray down the stack centre must not hit the top
        # wall and must fall straight through (hit <= rim or nothing).
        hit, loc, _ = ray_hit(scene, depsgraph, (4.0, 0.0, 50.0), (0, 0, -1))
        open_ = (not hit) or (loc[2] < 15.0)
        report(open_, part, "chimney aperture open over SoC")

        # RJ45 notch: from the rear, a ray at port height must clear the rear
        # wall and strike the far (front) wall instead.
        hit, loc, _ = ray_hit(scene, depsgraph, (-45.0, 0.0, 17.0), (1, 0, 0))
        report(hit and loc[0] > 30.0, part, "RJ45 notch open at rear wall")

    if part == "chimney":
        # Exhaust slot: from just inside the skirt, a ray at slot height must
        # pass through the stack wall and stop at the far inner wall (x < 0).
        hit, loc, _ = ray_hit(scene, depsgraph, (17.5, 0.0, 35.0), (-1, 0, 0))
        report(hit and loc[0] < 0.0, part, "exhaust slots open through stack wall")

    if part == "base":
        # Intake slot: straight down through (0,0) must pass the floor plate
        # (centre slot) and either miss or land below the floor underside.
        hit, loc, _ = ray_hit(scene, depsgraph, (0.0, 0.0, 5.0), (0, 0, -1))
        open_ = (not hit) or (loc[2] < 0.0)
        report(open_, part, "intake slots open through floor")

print("RESULT:", "FAIL" if failed else "PASS")
sys.exit(1 if failed else 0)