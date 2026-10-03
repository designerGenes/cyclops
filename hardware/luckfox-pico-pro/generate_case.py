"""Build the LuckFox Pico Pro weatherproof enclosure in Blender.

Consumes the pure-Python model in ``enclosure_geometry.py`` and turns it into a
native Blender assembly:

* parametric solids built from the model's primitive list,
* one manifold object per printable part (Base, Cover, Chimney, Nose, Gasket),
* reference proxies for the PCB / RJ45 / heatsink / lens / sensor,
* exported per-part STL files, and
* PNG preview renders.

Run headlessly from the repository root:

    blender --background --python hardware/luckfox-pico-pro/generate_case.py \
        -- --out hardware/luckfox-pico-pro/out

or use ``hardware/luckfox-pico-pro/generate.sh``.
"""

from __future__ import annotations

import math
import os
import sys
from pathlib import Path

import bpy
from mathutils import Vector

# ---------------------------------------------------------------------------
# Locate and import the geometry module (same directory as this script).
# ---------------------------------------------------------------------------
_SCRIPT_DIR = Path(__file__).resolve().parent
if str(_SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPT_DIR))

from enclosure_geometry import Model  # noqa: E402

MATERIAL_COLORS = {
    "petg": (0.16, 0.16, 0.17),
    "cover": (0.85, 0.24, 0.10),
    "tpu": (0.03, 0.03, 0.03),
    "alu": (0.55, 0.60, 0.68),
    "pcb": (0.10, 0.42, 0.19),
    "ref": (0.62, 0.62, 0.62),
}

# Parts exported as individual STL files.
EXPORTABLE_PARTS = ("base", "cover", "chimney", "nose", "gasket")

SOLVER = "EXACT"  # coplanar/subtractive geometry is reliable with the exact solver


def parse_output_dir() -> Path:
    out = Path.cwd() / "out"
    argv = list(sys.argv)
    if "--" in argv:
        tail = argv[argv.index("--") + 1:]
        args = iter(tail)
        for token in args:
            if token == "--out":
                out = Path(next(args))
    return out


def reset_scene() -> None:
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    scene.unit_settings.system = "METRIC"
    scene.unit_settings.length_unit = "MILLIMETERS"
    scene.unit_settings.scale_length = 0.001  # 1 Blender unit == 1 mm


def make_material(name: str, color) -> bpy.types.Material:
    mat = bpy.data.materials.new(name=name)
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    if bsdf:
        bsdf.inputs["Base Color"].default_value = (*color, 1.0)
        bsdf.inputs["Roughness"].default_value = 0.5 if name.startswith("Alu") else 0.4
        if name.startswith("Alu"):
            bsdf.inputs["Metallic"].default_value = 0.9
    return mat


def ensure_materials() -> dict:
    return {
        key: make_material(f"{key}_mat", color)
        for key, color in MATERIAL_COLORS.items()
    }


def _active_object() -> bpy.types.Object:
    return bpy.context.view_layer.objects.active


def add_cube(name: str, center, size, material=None):
    bpy.ops.mesh.primitive_cube_add(size=1.0, location=center)
    obj = _active_object()
    obj.name = name
    obj.dimensions = size
    bpy.ops.object.transform_apply(scale=True)
    if material is not None:
        obj.data.materials.append(material)
    return obj


def add_cylinder(name: str, center, radius, depth, axis, material=None):
    bpy.ops.mesh.primitive_cylinder_add(
        vertices=48, radius=radius, depth=depth, location=center
    )
    obj = _active_object()
    obj.name = name
    if axis == "X":
        obj.rotation_euler = (0.0, math.radians(90), 0.0)
    elif axis == "Y":
        obj.rotation_euler = (math.radians(90), 0.0, 0.0)
    if axis != "Z":
        bpy.ops.object.transform_apply(rotation=True)
    bpy.ops.object.transform_apply(scale=True)
    if material is not None:
        obj.data.materials.append(material)
    return obj


def add_pyramid(name: str, center, base_side, height, material=None):
    """Square pyramid whose base plane sits at ``center`` and apex points +Z."""
    radius = base_side / math.sqrt(2.0)
    bpy.ops.mesh.primitive_cone_add(
        vertices=4, radius1=radius, depth=height,
        location=(center[0], center[1], center[2] + height / 2.0 - 0.2),
    )
    obj = _active_object()
    obj.name = name
    obj.rotation_euler = (0.0, 0.0, math.radians(45))
    bpy.ops.object.transform_apply(rotation=True)
    bpy.ops.object.transform_apply(scale=True)
    if material is not None:
        obj.data.materials.append(material)
    return obj


def add_ring(name: str, center, outer_half, inner_half, z0, z1, material=None):
    """Rectangular ring (hollow column) built as outer box minus inner box."""
    outer = add_cube(
        f"{name}_outer", center,
        (outer_half[0] * 2, outer_half[1] * 2, z1 - z0), material,
    )
    inner = add_cube(
        f"{name}_inner", center,
        (inner_half[0] * 2, inner_half[1] * 2, z1 - z0 + 4.0),
    )
    apply_boolean(outer, inner, "DIFFERENCE", keep_operand=False)
    outer.name = name
    return outer


def apply_boolean(target, operand, operation, keep_operand=False) -> None:
    bpy.context.view_layer.objects.active = target
    mod = target.modifiers.new(name="Bool", type="BOOLEAN")
    mod.operation = operation
    mod.object = operand
    mod.solver = SOLVER
    bpy.ops.object.modifier_apply(modifier=mod.name)
    if not keep_operand:
        bpy.data.objects.remove(operand, do_unlink=True)
    bpy.context.view_layer.update()


def _remove_doubles(obj) -> None:
    import bmesh
    obj.select_set(False)
    bpy.context.view_layer.objects.active = obj
    obj.select_set(True)
    bpy.ops.object.mode_set(mode="EDIT")
    bm = bmesh.from_edit_mesh(obj.data)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=0.0005)
    degenerate = [
        f for f in bm.faces if f.calc_area() < 1e-6 and f.is_valid
    ]
    if degenerate:
        bmesh.ops.delete(bm, geom=degenerate, context="FACES")
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=0.0005)
    bmesh.update_edit_mesh(obj.data)
    bpy.ops.object.mode_set(mode="OBJECT")
    obj.select_set(False)


def build(materials: dict) -> dict:
    model = Model().recompute()
    issues = model.validate()
    if issues:
        for sev, msg in issues:
            print(f"[{sev.upper()}] {msg}")
        raise SystemExit(f"Refusing to build: {len(issues)} geometry issue(s)")

    scene = bpy.context.scene
    enclosure = bpy.data.collections.new("Luckfox_Enclosure")
    reference = bpy.data.collections.new("Reference_Proxies")
    scene.collection.children.link(enclosure)
    scene.collection.children.link(reference)

    anchors: dict = {}          # part -> anchor object
    by_name: dict = {}          # name -> object (for sub targets)

    part_names = {
        "base": "Base_Tub",
        "cover": "Top_Cover",
        "chimney": "Chimney_Stack",
        "nose": "Camera_Nose",
        "gasket": "Gasket_Seal",
    }

    def build_add(p):
        mat = materials[p["material"]]
        op = p["op"]
        if op == "add_box":
            return add_cube(p["name"], p["center"], p["size"], mat)
        if op == "add_cylinder":
            return add_cylinder(p["name"], p["center"], p["radius"], p["depth"],
                                p["axis"], mat)
        if op == "add_ring":
            return add_ring(p["name"], p["center"], p["outer_half"], p["inner_half"],
                            p["z0"], p["z1"], mat)
        if op == "add_pyramid":
            return add_pyramid(p["name"], p["center"], p["base_side"], p["height"], mat)
        raise ValueError(f"unknown add op {op}")

    def build_sub(p):
        op = p["op"]
        if op == "sub_box":
            return add_cube(p["name"], p["center"], p["size"])
        if op == "sub_cylinder":
            return add_cylinder(p["name"], p["center"], p["radius"], p["depth"],
                                p["axis"])
        if op == "sub_ring":
            return add_ring(p["name"], p["center"], p["outer_half"], p["inner_half"],
                            p["z0"], p["z1"])
        raise ValueError(f"unknown sub op {op}")

    for p in model.primitives():
        op = p["op"]
        if op.startswith("add_"):
            obj = build_add(p)
            by_name[p["name"]] = obj
            if p.get("reference") or p["part"] == "ref":
                reference.objects.link(obj)
                scene.collection.objects.unlink(obj)
                continue
            anchor = anchors.get(p["part"])
            if anchor is None:
                anchors[p["part"]] = obj
                enclosure.objects.link(obj)
                scene.collection.objects.unlink(obj)
            else:
                apply_boolean(anchor, obj, "UNION", keep_operand=False)
        elif op.startswith("sub_"):
            cutter = build_sub(p)
            by_name[p["name"]] = cutter
            target = by_name[p["target"]]
            apply_boolean(target, cutter, "DIFFERENCE", keep_operand=False)
        else:
            raise ValueError(f"unknown primitive op {op!r}")

    # Weld duplicate vertices so each part is a clean 2-manifold for printing.
    for part in EXPORTABLE_PARTS:
        obj = anchors.get(part)
        if obj is not None:
            _remove_doubles(obj)

    # Record per-part final objects for STL export.
    finals = {part: anchors.get(part) for part in EXPORTABLE_PARTS}
    return {"model": model, "finals": finals, "anchors": anchors}


def export_stls(out_dir: Path, finals: dict) -> None:
    stl_dir = out_dir / "stl"
    stl_dir.mkdir(parents=True, exist_ok=True)
    for part, obj in finals.items():
        if obj is None:
            continue
        bpy.ops.object.select_all(action="DESELECT")
        obj.select_set(True)
        path = stl_dir / f"luckfox_enclosure_{part}.stl"
        bpy.ops.wm.stl_export(
            filepath=str(path),
            export_selected_objects=True,
            global_scale=1.0,
            apply_modifiers=True,
        )
        print(f"[STL] {path}")
        obj.select_set(False)


def _look_at(cam, location, target) -> None:
    cam.location = location
    direction = Vector(target) - Vector(location)
    cam.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()


def render_previews(out_dir: Path) -> None:
    preview_dir = out_dir / "preview"
    preview_dir.mkdir(parents=True, exist_ok=True)

    scene = bpy.context.scene
    scene.render.engine = "BLENDER_EEVEE"
    scene.render.image_settings.file_format = "PNG"

    world = bpy.data.worlds.new("Studio")
    world.use_nodes = True
    bg = world.node_tree.nodes.get("Background")
    if bg:
        bg.inputs["Color"].default_value = (0.92, 0.93, 0.95, 1.0)
        bg.inputs["Strength"].default_value = 1.0
    scene.world = world

    bpy.ops.object.light_add(type="SUN", location=(30.0, -50.0, 60.0))
    sun = _active_object()
    sun.data.energy = 3.0

    bpy.ops.object.light_add(type="AREA", location=(-40.0, 30.0, 25.0))
    fill = _active_object()
    fill.data.energy = 120.0
    fill.data.size = 40.0

    views = {
        "iso": ((150.0, -130.0, 95.0), (0.0, 0.0, 14.0)),
        "front": ((160.0, 0.0, 14.0), (0.0, 0.0, 14.0)),
        "rear": ((-170.0, 0.0, 14.0), (0.0, 0.0, 14.0)),
        "top": ((0.0, 0.5, 170.0), (0.0, 0.0, 14.0)),
    }

    camera = bpy.data.cameras.new("PreviewCam")
    camera_object = bpy.data.objects.new("PreviewCam", camera)
    scene.collection.objects.link(camera_object)

    for name, (loc, target) in views.items():
        _look_at(camera_object, loc, target)
        scene.camera = camera_object
        scene.render.filepath = str(preview_dir / f"luckfox_enclosure_{name}.png")
        bpy.ops.render.render(write_still=True)
        print(f"[PREVIEW] {scene.render.filepath}")


def main() -> None:
    out_dir = parse_output_dir().resolve()
    reset_scene()
    materials = ensure_materials()
    result = build(materials)

    model = result["model"]
    print("[GEOMETRY]")
    print(f"  envelope LxW    : {model.outer_l:.1f} x {model.outer_w:.1f} mm")
    print(f"  interior LxW    : {model.inner_l:.1f} x {model.inner_w:.1f} mm")
    print(f"  roof apex Z     : {model.roof_apex_z:.1f} mm")
    print(f"  chimney aperture: {model.e_aperture():.1f} mm over SoC x={model.board.soc_x}")

    export_stls(out_dir, result["finals"])
    render_previews(out_dir)

    blend_path = out_dir / "luckfox_pico_pro_enclosure.blend"
    out_dir.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(blend_path))
    print(f"[BLEND] {blend_path}")


if __name__ == "__main__":
    main()