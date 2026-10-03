"""Build the LuckFox Pico Pro weatherproof enclosure in Blender.

Consumes the pure-Python model in ``enclosure_geometry.py`` and turns it into
a native Blender assembly of symmetric, rounded forms:

* a capsule (stadium) body closed by two semicircular ends,
* a round chimney stack with a conical rain cap,
* a cylindrical lens barrel centred on the front dome,
* baked edge bevels that soften the remaining long hard edges,
* one manifold object per printable part, exported as STL,
* reference proxies for the PCB / RJ45 / heatsink / lens / sensor,
* PNG preview renders.

Run headlessly from the repository root:

    blender --background --python hardware/luckfox-pico-pro/generate_case.py \\
        -- --out hardware/luckfox-pico-pro/out

or use ``hardware/luckfox-pico-pro/generate.sh``.
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

import bpy
import bmesh
from mathutils import Vector

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

EXPORTABLE_PARTS = ("base", "cover", "chimney", "nose", "gasket")
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
        bsdf.inputs["Roughness"].default_value = 0.5 if name.startswith("Alu") else 0.4
        if name.startswith("Alu"):
            bsdf.inputs["Metallic"].default_value = 0.9
    return mat


def ensure_materials() -> dict:
    return {k: make_material(f"{k}_mat", c) for k, c in MATERIAL_COLORS.items()}


def _link(obj) -> bpy.types.Object:
    bpy.context.scene.collection.objects.link(obj)
    return obj


def _active() -> bpy.types.Object:
    return bpy.context.view_layer.objects.active


def add_box(name, center, size, material=None) -> bpy.types.Object:
    bpy.ops.mesh.primitive_cube_add(size=1.0, location=center)
    obj = _active()
    obj.name = name
    obj.dimensions = size
    bpy.ops.object.transform_apply(scale=True)
    if material is not None:
        obj.data.materials.append(material)
    return obj


def add_cylinder(name, center, radius, depth, axis, material=None) -> bpy.types.Object:
    bpy.ops.mesh.primitive_cylinder_add(
        vertices=48, radius=radius, depth=depth, location=center)
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


def add_cone(name, center, radius1, radius2, depth, axis, material=None) -> bpy.types.Object:
    """Cone/frustum whose widest (``radius1``) end sits at ``center`` and tapers
    along ``+axis``.  The base penetrates its parent by 0.2 mm to keep the
    boolean union clean."""
    bpy.ops.mesh.primitive_cone_add(
        vertices=48, radius1=radius1, radius2=radius2, depth=depth)
    obj = _active()
    obj.name = name
    # local +Z half-offset: -depth/2 is the radius1 (base) end
    ax = {"X": Vector((1, 0, 0)), "Y": Vector((0, 1, 0)), "Z": Vector((0, 0, 1))}[axis]
    base = Vector(center) - ax * 0.2
    obj.location = base + ax * (depth / 2.0)
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


def _stadium_ring_pts(straight, halfw, segments=16):
    """Counter-clockwise (from +Z) outline of a stadium centred at the origin."""
    half = straight / 2.0
    pts = []
    # bottom edge, left -> right
    pts.append((-half, -halfw))
    pts.append((half, -halfw))
    # right semicircle, bottom -> top
    for i in range(1, segments):
        ang = -math.pi / 2 + math.pi * i / segments
        pts.append((half + halfw * math.cos(ang), halfw * math.sin(ang)))
    pts.append((half, halfw))
    # top edge, right -> left
    pts.append((-half, halfw))
    # left semicircle, top -> bottom
    for i in range(1, segments):
        ang = math.pi / 2 + math.pi * i / segments
        pts.append((-half + halfw * math.cos(ang), halfw * math.sin(ang)))
    return pts


def build_stadium(name, center, straight, halfw, z0, z1, material=None) -> bpy.types.Object:
    """A clean stadium prism, constructed directly (no coplanar unions)."""
    bm = bmesh.new()
    pts = _stadium_ring_pts(straight, halfw)
    cx, cy = center[0], center[1]
    bottom = [bm.verts.new((cx + x, cy + y, z0)) for (x, y) in pts]
    face = bm.faces.new(bottom)
    ret = bmesh.ops.extrude_face_region(bm, geom=[face])
    up = [g for g in ret["geom"] if isinstance(g, bmesh.types.BMVert)]
    bmesh.ops.translate(bm, vec=(0, 0, z1 - z0), verts=up)
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


def build_cyl_ring(name, center, r_outer, r_inner, lo, hi, material=None,
                   axis="Z") -> bpy.types.Object:
    outer = add_cylinder(f"{name}_outer", center, r_outer, hi - lo, axis, material)
    inner = add_cylinder(f"{name}_inner", center, r_inner, hi - lo + 4.0, axis)
    apply_boolean(outer, inner, "DIFFERENCE")
    outer.name = name
    return outer


def _stadium_loop(straight, halfw, ccw=True, segments=16):
    """Closed stadium outline; ``ccw``/``False`` gives the reversed (hole) loop."""
    half = straight / 2.0
    out = []
    if ccw:
        for i in range(segments + 1):
            a = math.radians(-90 + 180 * i / segments)
            out.append((half + halfw * math.cos(a), halfw * math.sin(a)))
        out.append((-half, halfw))
        for i in range(1, segments + 1):
            a = math.radians(90 + 180 * i / segments)
            out.append((-half + halfw * math.cos(a), halfw * math.sin(a)))
    else:
        for i in range(segments + 1):
            a = math.radians(-90 - 180 * i / segments)
            out.append((half + halfw * math.cos(a), halfw * math.sin(a)))
        out.append((-half, halfw))
        for i in range(1, segments + 1):
            a = math.radians(90 - 180 * i / segments)
            out.append((-half + halfw * math.cos(a), halfw * math.sin(a)))
    return out


def build_stadium_ring(name, center, straight, outer_hw, inner_hw, z0, z1,
                       material=None) -> bpy.types.Object:
    """Stadium ring cutter built by outer-minus-inner boolean (triangle mesh),
    which the exact boolean subtracts cleanly from the shell."""
    outer = build_stadium(f"{name}_outer", center, straight, outer_hw, z0, z1, material)
    inner = build_stadium(f"{name}_inner", center, straight, inner_hw, z0 - 2.0, z1 + 2.0)
    apply_boolean(outer, inner, "DIFFERENCE")
    outer.name = name
    return outer


def build_stadium_annulus(name, center, straight, outer_hw, inner_hw, z0, z1,
                          material=None) -> bpy.types.Object:
    """Stadium ring built directly as a face-with-hole extrusion (no boolean),
    used for the standalone gasket so its curved tangencies stay sliver-free."""
    bm = bmesh.new()
    cx, cy = center[0], center[1]
    outer = [bm.verts.new((cx + x, cy + y, z0))
             for x, y in _stadium_loop(straight, outer_hw, ccw=True)]
    inner = [bm.verts.new((cx + x, cy + y, z0))
             for x, y in _stadium_loop(straight, inner_hw, ccw=False)]
    face = bm.faces.new(outer + inner)
    face.normal_update()
    ret = bmesh.ops.extrude_face_region(bm, geom=[face])
    up = [g for g in ret["geom"] if isinstance(g, bmesh.types.BMVert)]
    bmesh.ops.translate(bm, vec=(0, 0, z1 - z0), verts=up)
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


def apply_boolean(target, operand, operation) -> None:
    bpy.context.view_layer.objects.active = target
    mod = target.modifiers.new(name="Bool", type="BOOLEAN")
    mod.operation = operation
    mod.object = operand
    mod.solver = SOLVER
    bpy.ops.object.modifier_apply(modifier=mod.name)
    bpy.data.objects.remove(operand, do_unlink=True)
    bpy.context.view_layer.update()


def cleanup(obj) -> None:
    """Weld double vertices and collapse zero-area slivers left by booleans."""
    bpy.context.view_layer.objects.active = obj
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=0.0005)
    tiny = [f for f in bm.faces if f.calc_area() < 1e-5 and f.is_valid]
    if tiny:
        for f in tiny:
            if f.is_valid:
                bmesh.ops.pointmerge(bm, verts=f.verts[:],
                                     merge_co=f.calc_center_median())
        bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=0.0005)
    bm.to_mesh(obj.data)
    bm.free()


def bake_bevel(obj, offset, min_len, angle_deg, seam_z) -> None:
    """Round long hard edges, skipping the seam plane so the halves still mate."""
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bm.edges.ensure_lookup_table()
    edges = []
    for e in bm.edges:
        if e.calc_length() < min_len:
            continue
        if len(e.link_faces) != 2:
            continue
        n1, n2 = e.link_faces[0].normal, e.link_faces[1].normal
        if math.degrees(n1.angle(n2)) < angle_deg:
            continue
        mid = (e.verts[0].co + e.verts[1].co) * 0.5
        if abs(mid.z - seam_z) < 1.0:
            continue
        edges.append(e)
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
        for sev, msg in issues:
            print(f"[{sev.upper()}] {msg}")
        raise SystemExit(f"Refusing to build: {len(issues)} geometry issue(s)")

    scene = bpy.context.scene
    enclosure = bpy.data.collections.new("Luckfox_Enclosure")
    reference = bpy.data.collections.new("Reference_Proxies")
    scene.collection.children.link(enclosure)
    scene.collection.children.link(reference)

    anchors: dict = {}
    by_name: dict = {}
    e = model.env

    def build_shape(p):
        op = p["op"]
        mat = materials[p["material"]] if "material" in p else None
        if op in ("add_box", "sub_box"):
            return add_box(p["name"], p["center"], p["size"],
                           mat if op == "add_box" else None)
        if op in ("add_cylinder", "sub_cylinder"):
            return add_cylinder(p["name"], p["center"], p["radius"], p["depth"],
                                p["axis"], mat if op == "add_cylinder" else None)
        if op == "add_cone":
            return add_cone(p["name"], p["center"], p["radius1"], p["radius2"],
                            p["depth"], p["axis"], mat)
        if op == "add_stadium":
            return build_stadium(p["name"], p["center"], p["straight"],
                                 p["half_width"], p["z0"], p["z1"], mat)
        if op == "sub_stadium":
            return build_stadium(p["name"], p["center"], p["straight"],
                                 p["half_width"], p["z0"], p["z1"])
        if op == "add_cyl_ring":
            return build_cyl_ring(p["name"], p["center"], p["r_outer"], p["r_inner"],
                                  p["z0"], p["z1"], mat, p.get("axis", "Z"))
        if op == "add_stadium_ring":
            return build_stadium_annulus(p["name"], p["center"], p["straight"],
                                         p["outer_hw"], p["inner_hw"], p["z0"],
                                         p["z1"], mat)
        if op == "sub_stadium_ring":
            return build_stadium_ring(p["name"], p["center"], p["straight"],
                                      p["outer_hw"], p["inner_hw"], p["z0"], p["z1"])
        raise ValueError(f"unknown op {op}")

    for p in model.primitives():
        if p["op"].startswith("add_"):
            obj = build_shape(p)
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
                apply_boolean(anchor, obj, "UNION")
        elif p["op"].startswith("sub_"):
            cutter = build_shape(p)
            by_name[p["name"]] = cutter
            apply_boolean(by_name[p["target"]], cutter, "DIFFERENCE")
        else:
            raise ValueError(f"unknown primitive op {p['op']!r}")

    for part in EXPORTABLE_PARTS:
        obj = anchors.get(part)
        if obj is not None:
            cleanup(obj)
            bake_bevel(obj, e.bevel_offset, e.bevel_min_len,
                       e.bevel_angle_deg, e.seam_z)
            cleanup(obj)

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
        bg.inputs["Color"].default_value = (0.90, 0.91, 0.94, 1.0)
        bg.inputs["Strength"].default_value = 1.0
    scene.world = world

    bpy.ops.object.light_add(type="SUN", location=(40.0, -60.0, 80.0))
    _active().data.energy = 2.5
    bpy.ops.object.light_add(type="AREA", location=(-50.0, 40.0, 30.0))
    fill = _active()
    fill.data.energy = 120.0
    fill.data.size = 50.0

    views = {
        "iso": ((170.0, -150.0, 100.0), (0.0, 0.0, 16.0)),
        "front": ((190.0, 0.0, 14.0), (0.0, 0.0, 14.0)),
        "rear": ((-200.0, 0.0, 14.0), (0.0, 0.0, 14.0)),
        "top": ((0.0, 0.5, 190.0), (0.0, 0.0, 14.0)),
    }
    camera_object = bpy.data.objects.new("PreviewCam", bpy.data.cameras.new("PreviewCam"))
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
    result = build(ensure_materials())
    model = result["model"]

    print("[GEOMETRY]")
    print(f"  body plan      : {model.total_length:.1f} x {model.body_width:.1f} mm "
          f"(capsule, r={model.end_radius:.1f})")
    print(f"  interior       : {model.inner_width:.1f} mm wide "
          f"x {model.interior_ceiling:.1f} mm tall")
    print(f"  chimney        : Ø{2 * model.stack_outer_r:.0f} over SoC "
          f"(cap Ø{2 * model.cap_r:.0f}, apex z={model.roof_apex_z:.1f})")
    print(f"  nose barrel    : Ø{2 * model.env.nose_r:.0f} x {model.env.nose_len:.0f} mm")

    export_stls(out_dir, result["anchors"])
    render_previews(out_dir)

    blend_path = out_dir / "luckfox_pico_pro_enclosure.blend"
    out_dir.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(blend_path))
    print(f"[BLEND] {blend_path}")


if __name__ == "__main__":
    main()