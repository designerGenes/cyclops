"""Headless sanity check of the generated STL files.

For every part this verifies a watertight 2-manifold (no non-manifold edges,
no degenerate faces), reports bounding box and volume, and then probes a few
specific features with ray cast so a silently-failed boolean gets caught:

* ``cover``    — chimney aperture open over the SoC; RJ45 notch and the front
                 barrel opening both open at their ends
* ``chimney``  — exhaust slots open through the stack wall behind the skirt
* ``base``     — intake slots open through the floor beneath the PCB plenum
* ``nose``     — the lens/barrel tunnel is clear end to end
"""

import sys
from pathlib import Path

import bpy
import bmesh
from mathutils import Vector

STL_DIR = Path(sys.argv[sys.argv.index("--stl") + 1])

INTENT = {
    "base":    dict(x=(-55.0, 55.0), y=(-16.0, 16.0), z=(-4.0, 14.0)),
    "cover":   dict(x=(-55.0, 55.0), y=(-16.0, 16.0), z=(12.0, 25.0)),
    "chimney": dict(x=(-18.0, 26.0), y=(-21.0, 21.0), z=(23.0, 49.0)),
    "nose":    dict(x=(52.0, 82.0), y=(-21.0, 21.0), z=(-10.0, 33.0)),
    "gasket":  dict(x=(-54.0, 54.0), y=(-16.0, 16.0), z=(11.0, 15.0)),
}

failed = False


def report(ok: bool, part: str, msg: str) -> None:
    global failed
    if not ok:
        failed = True
    print(f"[{'OK' if ok else 'FAIL'}] {part}: {msg}")


def ray_hit(scene, depsgraph, origin, direction, distance=260.0):
    hit_ok, loc, normal, index, obj, matrix = scene.ray_cast(
        depsgraph, Vector(origin), Vector(direction), distance=distance)
    return (hit_ok, loc, obj)


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

    for axis, (lo, hi) in intent.items():
        idx = {"x": 0, "y": 1, "z": 2}[axis]
        if bounds[idx] < lo - 1.0 or bounds[idx + 3] > hi + 1.0:
            print(f"[WARN] {part}: {axis} bounds {bounds[idx]:.1f}..{bounds[idx + 3]:.1f} "
                  f"outside intent {lo}..{hi}")
            failed = True

    print(f"       {part}: {len(mesh.vertices)} verts / {len(mesh.polygons)} faces, "
          f"bounds x {bounds[0]:.1f}..{bounds[3]:.1f} y {bounds[1]:.1f}..{bounds[4]:.1f} "
          f"z {bounds[2]:.1f}..{bounds[5]:.1f}, volume {volume:.0f} mm^3")

    scene = bpy.context.scene
    depsgraph = bpy.context.evaluated_depsgraph_get()

    if part == "cover":
        hit, loc, _ = ray_hit(scene, depsgraph, (4.0, 0.0, 80.0), (0, 0, -1))
        report((not hit) or (loc[2] < 15.0), part, "chimney aperture open over SoC")

        hit, loc, _ = ray_hit(scene, depsgraph, (-56.0, 0.0, 17.0), (1, 0, 0))
        report((not hit) or (loc[0] > 40.0), part, "RJ45 notch open at rear")

        hit, loc, _ = ray_hit(scene, depsgraph, (49.0, 0.0, 17.0), (1, 0, 0))
        report((not hit) or (loc[0] < -40.0), part, "front barrel opening open")

    if part == "chimney":
        hit, loc, _ = ray_hit(scene, depsgraph, (19.0, 0.0, 35.0), (-1, 0, 0))
        report(hit and loc[0] < 0.0, part, "exhaust slots open through stack wall")

    if part == "base":
        hit, loc, _ = ray_hit(scene, depsgraph, (0.0, 0.0, 5.0), (0, 0, -1))
        report((not hit) or (loc[2] < 0.0), part, "intake slots open through floor")

        hit, loc, _ = ray_hit(scene, depsgraph, (49.0, 0.0, 8.0), (1, 0, 0))
        report((not hit) or (loc[0] < -40.0), part, "front barrel opening open")

    if part == "nose":
        hit, loc, _ = ray_hit(scene, depsgraph, (82.0, 0.0, 12.0), (-1, 0, 0))
        report(not hit, part, "lens/barrel tunnel clear end to end")

print("RESULT:", "FAIL" if failed else "PASS")
sys.exit(1 if failed else 0)