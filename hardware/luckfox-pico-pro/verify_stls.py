"""Manifold and feature checks for the top-hood enclosure STL parts."""

import sys
from pathlib import Path

import bpy
import bmesh
from mathutils import Vector

STL_DIR = Path(sys.argv[sys.argv.index("--stl") + 1])
PARTS = {
    "base": dict(x=(-55.0, 55.0), y=(-29.0, 29.0), z=(-1.0, 14.0)),
    "cover": dict(x=(-55.0, 55.0), y=(-29.0, 29.0), z=(9.0, 35.0)),
    "hood": dict(x=(-59.0, 65.0), y=(-32.0, 32.0), z=(31.0, 45.0)),
    "gasket": dict(x=(-55.0, 55.0), y=(-29.0, 29.0), z=(8.0, 11.0)),
    "thermal_seal": dict(x=(-10.0, 18.0), y=(-15.0, 15.0), z=(33.0, 35.0)),
    "thermal_insert": dict(x=(-11.0, 19.0), y=(-15.0, 15.0), z=(17.0, 39.0)),
}

failed = False


def report(ok: bool, part: str, message: str) -> None:
    global failed
    if not ok:
        failed = True
    print(f"[{'OK' if ok else 'FAIL'}] {part}: {message}")


def ray_hit(scene, depsgraph, origin, direction, distance):
    hit, location, normal, face_index, obj, matrix = scene.ray_cast(
        depsgraph, Vector(origin), Vector(direction), distance=distance)
    return hit, location, obj


for part, intent in PARTS.items():
    path = STL_DIR / f"luckfox_enclosure_{part}.stl"
    if not path.exists():
        report(False, part, f"missing {path}")
        continue

    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.wm.stl_import(filepath=str(path))
    obj = bpy.context.selected_objects[0] if bpy.context.selected_objects else None
    if obj is None:
        report(False, part, "STL could not be imported")
        continue

    bm = bmesh.new()
    bm.from_mesh(obj.data)
    non_manifold = [edge for edge in bm.edges if not edge.is_manifold]
    degenerate = [face for face in bm.faces if face.calc_area() < 1e-6]
    volume = abs(bm.calc_volume())
    bm.free()

    bbox = [obj.matrix_world @ Vector(corner) for corner in obj.bound_box]
    xs = [v.x for v in bbox]
    ys = [v.y for v in bbox]
    zs = [v.z for v in bbox]
    bounds = (min(xs), min(ys), min(zs), max(xs), max(ys), max(zs))

    report(not non_manifold, part, f"{len(non_manifold)} non-manifold edge(s)")
    report(not degenerate, part, f"{len(degenerate)} degenerate face(s)")
    report(volume > 0.0, part, f"volume {volume:.0f} mm^3")

    for axis, (lo, hi) in intent.items():
        index = {"x": 0, "y": 1, "z": 2}[axis]
        if bounds[index] < lo - 1.0 or bounds[index + 3] > hi + 1.0:
            report(False, part,
                   f"{axis} bounds {bounds[index]:.1f}..{bounds[index + 3]:.1f} "
                   f"outside intent {lo}..{hi}")

    print(f"       {len(obj.data.vertices)} verts / {len(obj.data.polygons)} faces; "
          f"bbox x {bounds[0]:.1f}..{bounds[3]:.1f}, "
          f"y {bounds[1]:.1f}..{bounds[4]:.1f}, "
          f"z {bounds[2]:.1f}..{bounds[5]:.1f}")

    scene = bpy.context.scene
    depsgraph = bpy.context.evaluated_depsgraph_get()
    if part == "cover":
        # The clear optics panel is a separate installed component. The shell's
        # window pocket must therefore be an actual opening at the front.
        hit, _, _ = ray_hit(scene, depsgraph, (55.0, 0.0, 16.0), (-1, 0, 0), 3.0)
        report(not hit, part, "recessed optical window pocket is open")
        # Thermal insert port must go through the roof, while the insert and
        # seal parts fill it in the assembled scene.
        hit, _, _ = ray_hit(scene, depsgraph, (4.0, 0.0, 34.0), (0, 0, -1), 5.0)
        report(not hit, part, "gasketed thermal insert port is open")
        hit, _, _ = ray_hit(scene, depsgraph, (-55.0, 0.0, 17.0), (1, 0, 0), 3.0)
        report(not hit, part, "upper RJ45 port is open")

    if part == "base":
        hit, _, _ = ray_hit(scene, depsgraph, (56.0, 0.0, 8.0), (-1, 0, 0), 3.0)
        report(hit, part, "front fascia remains solid below optical window")
        hit, _, _ = ray_hit(scene, depsgraph, (-56.0, 0.0, 7.0), (1, 0, 0), 3.0)
        report(not hit, part, "lower RJ45 port is open")

    if part == "hood":
        # It is a solid weather canopy; the clearance is under the plate at
        # the four support posts and remains open around the metal fins.
        hit, _, _ = ray_hit(scene, depsgraph, (4.0, 0.0, 38.0), (0, 0, 1), 1.5)
        report(not hit, part, "air gap remains above thermal fins")

print("RESULT:", "FAIL" if failed else "PASS")
sys.exit(1 if failed else 0)
