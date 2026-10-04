"""Build the LuckFox top-hood camera enclosure in Blender.

The builder consumes ``enclosure_geometry.py`` and creates a sealed, broad
rounded body with a recessed camera window, raised rain canopy and a separate
metal thermal insert. No projecting camera barrel or exposed chimney is used.

Run from the repository root:

    blender --background --python hardware/luckfox-pico-pro/generate_case.py \\
        -- --out hardware/luckfox-pico-pro/out

or call ``hardware/luckfox-pico-pro/generate.sh``.
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

import bpy
import bmesh
from mathutils import Vector

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from enclosure_geometry import Model, rectangle_loop  # noqa: E402


MATERIAL_COLORS = {
    "petg": (0.12, 0.14, 0.16),
    "cover": (0.16, 0.18, 0.20),
    "tpu": (0.025, 0.025, 0.03),
    "alu": (0.58, 0.62, 0.68),
    "pcb": (0.08, 0.38, 0.17),
    "ref": (0.50, 0.53, 0.56),
    "glass": (0.018, 0.035, 0.055),
    "lens": (0.018, 0.065, 0.09),
}

EXPORTABLE_PARTS = ("base", "cover", "hood", "gasket", "thermal_seal", "thermal_insert")
SOLVER = "EXACT"


def parse_output_dir() -> Path:
    out = Path.cwd() / "out"
    argv = list(sys.argv)
    if "--" in argv:
        args = iter(argv[argv.index("--") + 1:])
        for token in args:
            if token == "--out":
                out = Path(next(args))
    return out


def reset_scene() -> None:
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    scene.unit_settings.system = "METRIC"
    scene.unit_settings.length_unit = "MILLIMETERS"
    scene.unit_settings.scale_length = 0.001


def make_material(name: str, color) -> bpy.types.Material:
    mat = bpy.data.materials.new(name=name)
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    if bsdf:
        bsdf.inputs["Base Color"].default_value = (*color, 1.0)
        bsdf.inputs["Roughness"].default_value = 0.36
        if name.startswith("alu"):
            bsdf.inputs["Metallic"].default_value = 0.82
        if name.startswith("glass"):
            bsdf.inputs["Metallic"].default_value = 0.05
            bsdf.inputs["Roughness"].default_value = 0.12
            bsdf.inputs["Alpha"].default_value = 0.2
            bsdf.inputs["Transmission Weight"].default_value = 0.78
            mat.surface_render_method = "BLENDED"
        if name.startswith("lens"):
            bsdf.inputs["Metallic"].default_value = 0.52
            bsdf.inputs["Roughness"].default_value = 0.12
    return mat


def ensure_materials() -> dict:
    return {key: make_material(key, color) for key, color in MATERIAL_COLORS.items()}


def _active() -> bpy.types.Object:
    return bpy.context.view_layer.objects.active


def _link(obj) -> bpy.types.Object:
    bpy.context.scene.collection.objects.link(obj)
    return obj


def add_box(name, center, size, material=None) -> bpy.types.Object:
    bpy.ops.mesh.primitive_cube_add(size=1.0, location=center)
    obj = _active()
    obj.name = name
    obj.dimensions = size
    bpy.ops.object.transform_apply(scale=True)
    if material is not None:
        obj.data.materials.append(material)
    return obj


def add_rounded_box(name, center, size, radius, material=None) -> bpy.types.Object:
    """Rounded rectangular cutter/window panel with baked bevel geometry."""
    obj = add_box(name, center, size, material)
    bevel = obj.modifiers.new("Rounded_Corners", "BEVEL")
    bevel.width = min(radius, min(size) * 0.45)
    bevel.segments = 4
    bevel.limit_method = "ANGLE"
    bevel.angle_limit = math.radians(20.0)
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.modifier_apply(modifier=bevel.name)
    return obj


def add_cylinder(name, center, radius, depth, axis="Z", material=None,
                 vertices=48) -> bpy.types.Object:
    bpy.ops.mesh.primitive_cylinder_add(vertices=vertices, radius=radius,
                                        depth=depth, location=center)
    obj = _active()
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


def build_cylinder_ring(name, center, outer_radius, inner_radius, depth,
                        axis="Z", material=None) -> bpy.types.Object:
    """Thin annular bezel; boolean operands overrun slightly to avoid caps."""
    outer = add_cylinder(name + "_outer", center, outer_radius, depth,
                         axis, material, vertices=64)
    inner = add_cylinder(name + "_inner", center, inner_radius, depth + 1.0,
                         axis, vertices=64)
    apply_boolean(outer, inner, "DIFFERENCE")
    outer.name = name
    return outer


def build_roundrect(name, center, length, width, radius, z0, z1,
                    material=None, slope_x=0.0) -> bpy.types.Object:
    """Manifold rounded-rectangle prism; optional top slope drains to +X."""
    cx, cy = center[0], center[1]
    pts = rectangle_loop(length, width, radius, segments=10)
    bm = bmesh.new()
    bottom = [bm.verts.new((cx + x, cy + y, z0)) for x, y in pts]
    top = [bm.verts.new((cx + x, cy + y, z1 + slope_x * x)) for x, y in pts]
    bm.faces.new(bottom)
    bm.faces.new(list(reversed(top)))
    count = len(bottom)
    for i in range(count):
        j = (i + 1) % count
        bm.faces.new((bottom[i], bottom[j], top[j], top[i]))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.normal_update()
    mesh = bpy.data.meshes.new(name)
    bm.to_mesh(mesh)
    bm.free()
    obj = bpy.data.objects.new(name, mesh)
    _link(obj)
    if material is not None:
        obj.data.materials.append(material)
    return obj


def build_roundrect_ring(name, center, outer_length, outer_width, outer_radius,
                         inner_length, inner_width, inner_radius, z0, z1,
                         material=None) -> bpy.types.Object:
    """Sliver-free ring built from one face with a reversed inner loop."""
    cx, cy = center[0], center[1]
    outer_pts = rectangle_loop(outer_length, outer_width, outer_radius, segments=10)
    inner_pts = list(reversed(rectangle_loop(inner_length, inner_width,
                                             inner_radius, segments=10)))
    bm = bmesh.new()
    outer = [bm.verts.new((cx + x, cy + y, z0)) for x, y in outer_pts]
    inner = [bm.verts.new((cx + x, cy + y, z0)) for x, y in inner_pts]
    face = bm.faces.new(outer + inner)
    face.normal_update()
    ret = bmesh.ops.extrude_face_region(bm, geom=[face])
    top_verts = [g for g in ret["geom"] if isinstance(g, bmesh.types.BMVert)]
    bmesh.ops.translate(bm, verts=top_verts, vec=(0, 0, z1 - z0))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.normal_update()
    mesh = bpy.data.meshes.new(name)
    bm.to_mesh(mesh)
    bm.free()
    obj = bpy.data.objects.new(name, mesh)
    _link(obj)
    if material is not None:
        obj.data.materials.append(material)
    return obj


def apply_boolean(target, operand, operation="DIFFERENCE") -> None:
    bpy.context.view_layer.objects.active = target
    mod = target.modifiers.new(name=f"Boolean_{operation}", type="BOOLEAN")
    mod.operation = operation
    mod.object = operand
    mod.solver = SOLVER
    bpy.ops.object.modifier_apply(modifier=mod.name)
    bpy.data.objects.remove(operand, do_unlink=True)
    bpy.context.view_layer.update()


def build_roundrect_ring_cutter(name, center, outer_length, outer_width,
                                outer_radius, inner_length, inner_width,
                                inner_radius, z0, z1):
    outer = build_roundrect(name + "_outer", center, outer_length, outer_width,
                            outer_radius, z0, z1)
    inner = build_roundrect(name + "_inner", center, inner_length, inner_width,
                            inner_radius, z0 - 2.0, z1 + 2.0)
    apply_boolean(outer, inner, "DIFFERENCE")
    outer.name = name
    return outer


def cleanup(obj) -> None:
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=0.0005)
    tiny = [face for face in bm.faces if face.calc_area() < 1e-5 and face.is_valid]
    if tiny:
        for face in tiny:
            if face.is_valid:
                bmesh.ops.pointmerge(bm, verts=face.verts[:],
                                     merge_co=face.calc_center_median())
        bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=0.0005)
    bmesh.ops.dissolve_degenerate(bm, edges=list(bm.edges), dist=0.001)
    bm.to_mesh(obj.data)
    bm.free()


def bake_bevel(obj, offset, min_len, angle_deg, seam_z) -> None:
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bm.edges.ensure_lookup_table()
    edges = []
    for edge in bm.edges:
        if edge.calc_length() < min_len or len(edge.link_faces) != 2:
            continue
        if math.degrees(edge.link_faces[0].normal.angle(edge.link_faces[1].normal)) < angle_deg:
            continue
        midpoint = (edge.verts[0].co + edge.verts[1].co) * 0.5
        if abs(midpoint.z - seam_z) < 1.0:
            continue
        edges.append(edge)
    if edges:
        bmesh.ops.bevel(bm, geom=edges, offset=offset, offset_type="OFFSET",
                        segments=3, profile=0.5, affect="EDGES")
        bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=0.0005)
    bm.to_mesh(obj.data)
    bm.free()


def build(materials: dict) -> dict:
    model = Model().recompute()
    issues = model.validate()
    if issues:
        for severity, message in issues:
            print(f"[{severity.upper()}] {message}")
        raise SystemExit(f"Refusing to build: {len(issues)} geometry issue(s)")

    scene = bpy.context.scene
    enclosure = bpy.data.collections.new("Luckfox_Enclosure")
    optics = bpy.data.collections.new("Recessed_Optics")
    references = bpy.data.collections.new("Reference_Proxies")
    scene.collection.children.link(enclosure)
    scene.collection.children.link(optics)
    scene.collection.children.link(references)
    references.hide_render = True

    anchors: dict = {}
    objects_by_name: dict = {}

    def build_shape(primitive):
        op = primitive["op"]
        mat = materials.get(primitive.get("material"))
        if op in ("add_box", "sub_box"):
            return add_box(primitive["name"], primitive["center"], primitive["size"],
                           mat if op == "add_box" else None)
        if op in ("add_rounded_box", "sub_rounded_box"):
            return add_rounded_box(primitive["name"], primitive["center"],
                                   primitive["size"], primitive["radius"],
                                   mat if op == "add_rounded_box" else None)
        if op in ("add_cylinder", "sub_cylinder"):
            return add_cylinder(primitive["name"], primitive["center"],
                                primitive["radius"], primitive["depth"],
                                primitive.get("axis", "Z"),
                                mat if op == "add_cylinder" else None)
        if op == "add_cyl_ring":
            return build_cylinder_ring(primitive["name"], primitive["center"],
                                       primitive["r_outer"], primitive["r_inner"],
                                       primitive["depth"], primitive.get("axis", "Z"), mat)
        if op in ("add_roundrect", "sub_roundrect"):
            return build_roundrect(primitive["name"], primitive["center"],
                                   primitive["length"], primitive["width"],
                                   primitive["radius"], primitive["z0"],
                                   primitive["z1"],
                                   mat if op == "add_roundrect" else None,
                                   primitive.get("slope_x", 0.0))
        if op == "add_roundrect_ring":
            return build_roundrect_ring(
                primitive["name"], primitive["center"],
                primitive["outer_length"], primitive["outer_width"],
                primitive["outer_radius"], primitive["inner_length"],
                primitive["inner_width"], primitive["inner_radius"],
                primitive["z0"], primitive["z1"], mat)
        if op == "sub_roundrect_ring":
            return build_roundrect_ring_cutter(
                primitive["name"], primitive["center"],
                primitive["outer_length"], primitive["outer_width"],
                primitive["outer_radius"], primitive["inner_length"],
                primitive["inner_width"], primitive["inner_radius"],
                primitive["z0"], primitive["z1"])
        raise ValueError(f"unknown primitive operation {op!r}")

    for primitive in model.primitives():
        op = primitive["op"]
        if op.startswith("add_"):
            obj = build_shape(primitive)
            objects_by_name[primitive["name"]] = obj
            if primitive.get("reference") or primitive["part"] == "ref":
                references.objects.link(obj)
                scene.collection.objects.unlink(obj)
                continue
            if primitive["part"] == "window":
                optics.objects.link(obj)
                scene.collection.objects.unlink(obj)
                continue
            anchor = anchors.get(primitive["part"])
            if anchor is None:
                anchors[primitive["part"]] = obj
                enclosure.objects.link(obj)
                scene.collection.objects.unlink(obj)
            else:
                apply_boolean(anchor, obj, "UNION")
        elif op.startswith("sub_"):
            cutter = build_shape(primitive)
            objects_by_name[primitive["name"]] = cutter
            target = objects_by_name[primitive["target"]]
            apply_boolean(target, cutter, "DIFFERENCE")
        else:
            raise ValueError(f"unknown primitive operation {op!r}")

    for part in EXPORTABLE_PARTS:
        obj = anchors.get(part)
        if obj is None:
            continue
        cleanup(obj)
        if part in ("base", "cover", "hood"):
            bake_bevel(obj, model.env.bevel_offset, model.env.bevel_min_len,
                       model.env.bevel_angle_deg, model.env.seam_z)
            cleanup(obj)
        if part in ("gasket", "thermal_seal"):
            for polygon in obj.data.polygons:
                polygon.use_smooth = True

    return {"model": model, "anchors": anchors}


def export_stls(out_dir: Path, anchors: dict) -> None:
    stl_dir = out_dir / "stl"
    stl_dir.mkdir(parents=True, exist_ok=True)
    for part in EXPORTABLE_PARTS:
        obj = anchors.get(part)
        if obj is None:
            continue
        bpy.ops.object.select_all(action="DESELECT")
        obj.select_set(True)
        path = stl_dir / f"luckfox_enclosure_{part}.stl"
        bpy.ops.wm.stl_export(filepath=str(path), export_selected_objects=True,
                              global_scale=1.0, apply_modifiers=True)
        print(f"[STL] {path}")
        obj.select_set(False)


def _look_at(camera, location, target) -> None:
    camera.location = location
    camera.rotation_euler = (Vector(target) - Vector(location)).to_track_quat(
        "-Z", "Y").to_euler()


def render_previews(out_dir: Path) -> None:
    preview = out_dir / "preview"
    preview.mkdir(parents=True, exist_ok=True)
    scene = bpy.context.scene
    scene.render.engine = "BLENDER_EEVEE"
    scene.render.image_settings.file_format = "PNG"
    scene.render.resolution_x = 1600
    scene.render.resolution_y = 1000
    scene.render.resolution_percentage = 100

    world = bpy.data.worlds.new("Soft_Studio")
    world.use_nodes = True
    bg = world.node_tree.nodes.get("Background")
    if bg:
        bg.inputs["Color"].default_value = (0.88, 0.91, 0.94, 1.0)
        bg.inputs["Strength"].default_value = 0.8
    scene.world = world

    bpy.ops.object.light_add(type="SUN", location=(50.0, -90.0, 120.0))
    _active().data.energy = 2.0
    bpy.ops.object.light_add(type="AREA", location=(-70.0, 60.0, 50.0))
    _active().data.energy = 250.0
    _active().data.size = 80.0

    views = {
        "iso": ((165.0, -175.0, 140.0), (2.0, 0.0, 22.0)),
        "front": ((190.0, 0.0, 23.0), (0.0, 0.0, 23.0)),
        "rear": ((-200.0, 0.0, 22.0), (0.0, 0.0, 22.0)),
        "top": ((0.0, 0.0, 190.0), (2.0, 0.0, 20.0)),
        "side": ((0.0, -190.0, 22.0), (2.0, 0.0, 22.0)),
    }
    cam_data = bpy.data.cameras.new("Preview_Camera")
    cam_obj = bpy.data.objects.new("Preview_Camera", cam_data)
    scene.collection.objects.link(cam_obj)
    cam_data.type = "ORTHO"
    cam_data.ortho_scale = 158.0
    for name, (location, target) in views.items():
        _look_at(cam_obj, location, target)
        scene.camera = cam_obj
        scene.render.filepath = str(preview / f"luckfox_enclosure_{name}.png")
        bpy.ops.render.render(write_still=True)
        print(f"[PREVIEW] {scene.render.filepath}")


def main() -> None:
    out_dir = parse_output_dir().resolve()
    reset_scene()
    result = build(ensure_materials())
    model = result["model"]
    e = model.env

    print("[GEOMETRY]")
    print(f"  body           : {e.body_length:.1f} x {e.body_width:.1f} x {e.body_height:.1f} mm")
    print(f"  canopy         : {model.hood_length:.1f} x {model.hood_width:.1f} mm; "
          f"front overhang {e.hood_front_overhang:.1f} mm")
    print(f"  optical window : recessed {e.window_recess:.1f} mm, "
          f"{e.window_width:.1f} x {e.window_height:.1f} mm")
    print(f"  thermal insert : {e.thermal_port_length:.1f} x {e.thermal_port_width:.1f} mm port; "
          f"fin clearance {model.hood_bottom - model.thermal_fin_top:.1f} mm")

    export_stls(out_dir, result["anchors"])
    render_previews(out_dir)

    out_dir.mkdir(parents=True, exist_ok=True)
    blend_path = out_dir / "luckfox_pico_pro_enclosure.blend"
    bpy.ops.wm.save_as_mainfile(filepath=str(blend_path))
    print(f"[BLEND] {blend_path}")


if __name__ == "__main__":
    main()
