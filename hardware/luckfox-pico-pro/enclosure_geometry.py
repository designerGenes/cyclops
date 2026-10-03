"""Parametric geometry for the LuckFox Pico Pro weatherproof camera enclosure.

This module is deliberately free of any Blender dependency so that the
enclosure's dimensional model can be unit-tested on the host.  Every value the
Blender build script (``generate_case.py``) needs is computed here from a
single set of inputs, keeping the 3D builder and the tests in lock-step.

All lengths are in millimetres.  The convention used throughout the project is:

* +X points toward the camera (the "front" of the enclosure).
* -X points toward the RJ45/PoE connector (the "rear").
* +Z points up.  ``z == 0`` is the underside of the floor plate.
* The plan origin sits at the centre of the PCB footprint.

Design intent
-------------

The enclosure is a passive, three-piece "chimney" housing that must survive
being mounted outdoors as a security camera:

* Convective air enters through downward-facing intake slots cut through the
  floor (raised on feet), travels up through the stand-off plenum beneath the
  PCB, over the components, and out through a chimney stack sat directly over
  the RV1106 SoC.
* The chimney exhausts sideways through slots near its top; those slots are
  sealed from rain by a solid "rain cap" whose skirt drops *below* the slots,
  so the air path turns downward again before it reaches open air.
* The base/cover seam carries a rectangular TPU gasket captured in matching
  grooves on both halves; the RJ45 port and the M12 lens both get protective
  hoods and drip edges so running water is shed away from the openings.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Sequence, Tuple

Vec = Tuple[float, float, float]


@dataclass(frozen=True)
class BoardSpec:
    """Physical dimensions of the LuckFox Pico Pro (RV1106) + RJ45 cage."""

    pcb_length: float = 72.0
    pcb_width: float = 21.0
    pcb_thickness: float = 1.6
    # RJ45 magnetic jack / connector opening
    rj45_width: float = 16.2
    rj45_height: float = 13.8
    # SoC centre offset from PCB centre toward the camera (front, +X).
    soc_x: float = 4.0
    # Heatsink bonded to the RV1106 package.
    heatsink_width: float = 14.0
    heatsink_height: float = 6.0


@dataclass(frozen=True)
class CameraSpec:
    """Physical dimensions of the LuckFox SC3336 camera module."""

    module_width: float = 25.0
    module_height: float = 24.0
    lens_diameter: float = 15.0
    ffc_width: float = 16.0
    ffc_thickness: float = 1.2


@dataclass(frozen=True)
class EnvSpec:
    """Manufacturing / design parameters for the enclosure itself."""

    clearance: float = 0.6          # radial PCB clearance to inner walls
    wall: float = 2.0               # shell wall thickness
    floor: float = 2.0              # floor plate thickness
    standoff: float = 3.5           # air plenum height beneath the PCB
    component_clearance: float = 1.0  # headroom above the tallest part
    seam_z: float = 13.0            # split plane between base and cover

    # Bottom intake vents (cut through the floor, facing downward).
    intake_slot_width: float = 1.5
    intake_slot_length: float = 12.0
    intake_count: int = 3
    intake_spacing_x: float = 18.0
    foot_height: float = 3.0        # feet that raise the floor off the mount

    # Chimney stack.
    chimney_aperture: float = 16.0  # open box over the SoC / heatsink
    chimney_wall: float = 2.0
    chimney_outer_height: float = 18.0
    exhaust_slot_height: float = 8.0
    cap_overhang: float = 6.0       # rain cap eave beyond the stack
    cap_thickness: float = 2.0
    cap_annulus: float = 4.0        # air gap between stack and cap skirt
    cap_skirt_length: float = 16.0  # how far the skirt drops past the cap
    roof_rise: float = 3.0          # pyramid roof pitch

    # Seam gasket.
    gasket_half_width: float = 0.8  # gasket is 1.6 mm square in plan
    gasket_groove_depth: float = 1.2

    # Ports.
    rj45_port_margin: float = 0.9   # added to each side of the jack opening
    lens_clearance: float = 0.5     # radial clearance around the M12 barrel
    ffc_margin: float = 0.3

    # Nose (camera bracket).
    nose_depth: float = 12.0
    lens_hood_length: float = 12.0

    # Wall plate.
    plate_thickness: float = 4.0

    tolerance: float = 1e-6


@dataclass
class Model:
    """Fully-computed dimensional model of the enclosure.

    ``Model(..., frozen=False)`` leaves the derived fields writable by
    ``recompute()``; callers treat the result as read-only afterwards.
    """

    board: BoardSpec = field(default_factory=BoardSpec)
    camera: CameraSpec = field(default_factory=CameraSpec)
    env: EnvSpec = field(default_factory=EnvSpec)

    # --- plan ---
    inner_l: float = 0.0
    inner_w: float = 0.0
    outer_l: float = 0.0
    outer_w: float = 0.0

    # --- z stack ---
    floor_top: float = 0.0
    pcb_bottom: float = 0.0
    pcb_top: float = 0.0
    interior_ceiling: float = 0.0
    cover_top: float = 0.0

    # --- chimney ---
    stack_outer: float = 0.0
    stack_z0: float = 0.0
    stack_z1: float = 0.0
    exhaust_z0: float = 0.0
    exhaust_z1: float = 0.0
    cap_outer: float = 0.0
    cap_z0: float = 0.0
    cap_z1: float = 0.0
    skirt_inner: float = 0.0
    skirt_outer: float = 0.0
    skirt_z0: float = 0.0
    skirt_z1: float = 0.0
    roof_apex_z: float = 0.0

    # --- ports / gasket / rims ---
    rj45_port_w: float = 0.0
    rj45_port_z0: float = 0.0
    rj45_port_z1: float = 0.0
    rim_x: float = 0.0
    rim_y: float = 0.0

    def recompute(self) -> "Model":
        e, b, c = self.env, self.board, self.camera

        self.inner_l = b.pcb_length + 2 * e.clearance
        self.inner_w = b.pcb_width + 2 * e.clearance
        self.outer_l = self.inner_l + 2 * e.wall
        self.outer_w = self.inner_w + 2 * e.wall

        self.floor_top = e.floor
        self.pcb_bottom = self.floor_top + e.standoff
        self.pcb_top = self.pcb_bottom + b.pcb_thickness
        self.interior_ceiling = self.pcb_top + b.rj45_height + e.component_clearance
        self.cover_top = self.interior_ceiling + e.wall

        # Chimney: sits directly over the RV1106 package.
        self.stack_outer = e.chimney_aperture + 2 * e.chimney_wall
        self.stack_z0 = self.cover_top
        self.stack_z1 = self.stack_z0 + e.chimney_outer_height
        self.exhaust_z0 = self.stack_z1 - e.chimney_wall - e.exhaust_slot_height
        self.exhaust_z1 = self.stack_z1 - e.chimney_wall
        self.cap_outer = self.stack_outer + 2 * e.cap_overhang
        self.cap_z0 = self.stack_z1
        self.cap_z1 = self.cap_z0 + e.cap_thickness
        self.skirt_inner = self.stack_outer + 2 * e.cap_annulus
        self.skirt_outer = self.skirt_inner + 2 * e.chimney_wall
        self.skirt_z1 = self.cap_z0
        self.skirt_z0 = self.skirt_z1 - e.cap_skirt_length
        self.roof_apex_z = self.cap_z1 + e.roof_rise

        # RJ45 port (rear wall), sized around the jack plus a seal margin.
        self.rj45_port_w = b.rj45_width + 2 * e.rj45_port_margin
        self.rj45_port_z0 = self.pcb_bottom - 1.0
        self.rj45_port_z1 = self.interior_ceiling

        # Seam rim: centre-line of the 2 mm wall around the opening.
        self.rim_x = self.inner_l / 2 + e.wall / 2
        self.rim_y = self.inner_w / 2 + e.wall / 2
        return self

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------
    def validate(self) -> List[Tuple[str, str]]:
        """Return ``(severity, message)`` issues; empty list == fully valid."""
        e, b, c = self.env, self.board, self.camera
        issues: List[Tuple[str, str]] = []

        def require(cond: bool, msg: str) -> None:
            if not cond:
                issues.append(("error", msg))

        ep = e.tolerance

        # 1. PCB clears the inner envelope in all three axes.
        if self.inner_l - b.pcb_length < 2 * e.clearance - ep:
            issues.append(("error", "PCB length lacks the specified radial clearance"))
        if self.inner_w - b.pcb_width < 2 * e.clearance - ep:
            issues.append(("error", "PCB width lacks the specified radial clearance"))
        if self.interior_ceiling - self.pcb_top < b.rj45_height - ep:
            issues.append(("error", "interior is short of the RJ45 cage height"))

        # 2. Heatsink clears the chimney with room for draft.
        require(self.e_aperture() - b.heatsink_width >= 2.0,
                "chimney aperture has <2 mm gap around the heatsink")
        require(self.stack_z1 - self.stack_z0 > b.heatsink_height,
                "chimney stack is not taller than the heatsink")

        # 3. Lens and FFC pass-throughs are large enough.
        lens_port = c.lens_diameter + 2 * e.lens_clearance
        require(lens_port > c.lens_diameter, "lens port smaller than barrel")
        require(c.ffc_width + 2 * e.ffc_margin > c.ffc_width,
                "FFC slot narrower than cable")
        require(1.2 + 2 * e.ffc_margin > c.ffc_thickness,
                "FFC slot thinner than cable")

        # 4. Weather-proofing: exhaust slots are behind the cap skirt and air
        #    exits downward through the annulus.
        require(self.skirt_z0 <= self.exhaust_z0 - ep,
                "cap skirt does not drop below the exhaust slots")
        require(self.skirt_inner > self.stack_outer,
                "no annulus between stack and cap skirt")
        require(self.skirt_outer <= self.cap_outer + ep,
                "cap eave does not overhang the skirt")
        require((self.skirt_z1 - self.skirt_z0) >= (self.exhaust_z1 - self.exhaust_z0),
                "skirt shorter than the exhaust opening")
        require(e.roof_rise > 0, "rain cap roof must pitch water off")

        # 5. Intakes face downward beneath the PCB, raised off the mount.
        require(e.intake_slot_length <= self.inner_l - 4 * e.wall,
                "intake slots reach the outer wall")
        require(e.foot_height >= 2.0, "feet too short to let air under the floor")
        require(self.e_intake_top() <= self.pcb_bottom + ep,
                "intake opens above the PCB plenum")

        # 6. RJ45 port stays within the interior, sealed by its hood.
        require(self.rj45_port_z1 <= self.interior_ceiling + ep,
                "RJ45 port breaches the top wall")
        require(self.rj45_port_z0 >= self.floor_top - ep,
                "RJ45 port dips below the floor")

        # 7. Chimney aperture lies fully inside the cover plan.
        require(self.e_chimney_max_x() <= self.outer_l / 2,
                "chimney stack protrudes beyond the enclosure length")
        require(self.stack_outer / 2 <= self.outer_w / 2 - ep,
                "chimney stack protrudes beyond the enclosure width")

        # 8. Seam gasket is captured on both halves.
        require(e.gasket_groove_depth > 0, "gasket groove has no depth")

        # 9. Minimalist footprint (hard upper bounds).
        require(self.outer_l <= 85.0, "enclosure too long")
        require(self.outer_w <= 32.0, "enclosure too wide")
        require(self.roof_apex_z <= 55.0, "enclosure too tall")
        return issues

    # ------------------------------------------------------------------
    # Accessors used by tests and the Blender builder
    # ------------------------------------------------------------------
    def e_aperture(self) -> float:
        return self.env.chimney_aperture

    def e_intake_top(self) -> float:
        # Intake slots are cut through the floor: they span z 0 .. floor and
        # exit on the underside, i.e. the highest point of the opening is the
        # top face of the floor plate.
        return self.floor_top

    def e_chimney_max_x(self) -> float:
        # Furthest +X the chimney reaches (SoC offset + half the stack face).
        return self.board.soc_x + self.stack_outer / 2

    def e_port_center_z(self) -> float:
        return (self.rj45_port_z0 + self.rj45_port_z1) / 2

    def e_seam_mid_z(self) -> float:
        return self.env.seam_z

    def e_nose_center_z(self) -> float:
        # Centre the camera nose vertically on the enclosure body.
        return self.cover_top / 2.0

    def e_nose_outer(self) -> Vec:
        c, e = self.camera, self.env
        return (e.nose_depth, c.module_width + 2 * e.wall,
                c.module_height + 2 * e.wall)

    def e_nose_front_x(self) -> float:
        return self.outer_l / 2 + self.env.nose_depth

    def e_nose_cavity(self) -> Vec:
        e, c = self.env, self.camera
        return (e.nose_depth - 2 * e.wall, c.module_width, c.module_height)

    def e_lens_port_dia(self) -> float:
        return self.camera.lens_diameter + 2 * self.env.lens_clearance

    def e_ffc_slot(self) -> Vec:
        c, e = self.camera, self.env
        return (c.ffc_width + 2 * e.ffc_margin, c.ffc_thickness + 2 * e.ffc_margin)

    def e_intake_xs(self) -> List[float]:
        e = self.env
        mid = (e.intake_count - 1) / 2
        return [(i - mid) * e.intake_spacing_x for i in range(e.intake_count)]

    # ------------------------------------------------------------------
    # Primitive build list
    # ------------------------------------------------------------------
    def primitives(self) -> List[Dict]:
        """Emit the ordered list of mesh operations for the Blender builder.

        Each entry is a dict understood by ``generate_case.py``:

        * ``add_box`` / ``add_cylinder`` / ``add_ring`` / ``add_pyramid``
          create solids (the first add in a part is its anchor object).
        * ``sub_box`` / ``sub_cylinder`` / ``sub_ring`` create cutters that are
          boolean-subtracted from the anchor named by ``target``.
        """
        e, b = self.env, self.board

        def box(center: Vec, size: Vec) -> Dict:
            return {"center": center, "size": size}

        prims: List[Dict] = []

        # ============================ BASE =============================
        prims.append({"op": "add_box", "part": "base", "name": "Base_Tub",
                      "material": "petg",
                      **box((0, 0, e.seam_z / 2), (self.outer_l, self.outer_w, e.seam_z))})
        prims.append({"op": "sub_box", "part": "base", "target": "Base_Tub",
                      "name": "Base_Cavity",
                      **box((0, 0, (self.floor_top + e.seam_z) / 2),
                            (self.inner_l, self.inner_w, e.seam_z - self.floor_top))})
        # RJ45 port, lower half.
        prims.append({"op": "sub_box", "part": "base", "target": "Base_Tub",
                      "name": "RJ45_Port_Lower",
                      **box((-self.outer_l / 2, 0, (self.rj45_port_z0 + e.seam_z) / 2),
                            (4 * e.wall, self.rj45_port_w, e.seam_z - self.rj45_port_z0))})
        # Downward-facing intake slots cut through the floor.
        slot = (e.intake_slot_length, e.intake_slot_width, e.floor * 3)
        for i, x in enumerate(self.e_intake_xs()):
            prims.append({"op": "sub_box", "part": "base", "target": "Base_Tub",
                          "name": f"Intake_Slot_{i}",
                          **box((x, 0, e.floor / 2), slot)})
        # Drain weeps at the front corners of the floor (low point when wall
        # mounted with the camera nose tipped down).
        for i, y in enumerate((8.0, -8.0)):
            prims.append({"op": "sub_cylinder", "part": "base", "target": "Base_Tub",
                          "name": f"Drain_Weep_{i}",
                          "axis": "Z", "center": (30.0, y, e.floor / 2),
                          "radius": 0.6, "depth": e.floor * 3})
        # Standoff bosses for the PCB.  Bottoms penetrate the floor plate by
        # 0.1 mm so their base is not coplanar with the floor (avoids
        # degenerate boolean faces).
        for i, (sx, sy) in enumerate(((30.0, 8.0), (30.0, -8.0),
                                      (-30.0, 8.0), (-30.0, -8.0))):
            prims.append({"op": "add_cylinder", "part": "base", "reference": False,
                          "name": f"Standoff_{i}", "material": "petg",
                          "axis": "Z",
                          "center": (sx, sy, (self.floor_top - 0.1 + self.pcb_bottom) / 2),
                          "radius": 3.0,
                          "depth": self.pcb_bottom - self.floor_top + 0.1})
        # Feet that raise the floor off the mounting surface; tops penetrate
        # the floor underside by 0.05 mm to avoid coplanar union faces.
        for i, (fx, fy) in enumerate(((self.outer_l / 2 - 3, self.outer_w / 2 - 3),
                                      (self.outer_l / 2 - 3, -(self.outer_w / 2 - 3)),
                                      (-(self.outer_l / 2 - 3), self.outer_w / 2 - 3),
                                      (-(self.outer_l / 2 - 3), -(self.outer_w / 2 - 3)))):
            prims.append({"op": "add_box", "part": "base", "reference": False,
                          "name": f"Foot_{i}", "material": "petg",
                          **box((fx, fy, (-e.foot_height + 0.05) / 2),
                                (6.0, 6.0, e.foot_height + 0.05))})
        # Gasket groove cut into the upper rim of the base.
        prims.append(self._rim_groove("base", "Gasket_Groove_Base",
                                      self.e_seam_mid_z() - e.gasket_groove_depth,
                                      self.e_seam_mid_z()))
        # FFC cable pass-through in the base front wall.
        fw, ft = self.e_ffc_slot()[:2]
        prims.append({"op": "sub_box", "part": "base", "target": "Base_Tub",
                      "name": "FFC_Slot_Base",
                      **box((self.outer_l / 2, 0, 6.0), (4 * e.wall, fw, ft))})

        # ============================ COVER ============================
        cover_z0, cover_z1 = e.seam_z, self.cover_top
        cover_c = (cover_z0 + cover_z1) / 2
        prims.append({"op": "add_box", "part": "cover", "name": "Top_Cover",
                      "material": "cover",
                      **box((0, 0, cover_c), (self.outer_l, self.outer_w, cover_z1 - cover_z0))})
        prims.append({"op": "sub_box", "part": "cover", "target": "Top_Cover",
                      "name": "Cover_Cavity",
                      **box((0, 0, (cover_z0 + self.interior_ceiling) / 2),
                            (self.inner_l, self.inner_w, self.interior_ceiling - cover_z0))})
        # Chimney aperture through the cover's top wall, over the SoC.
        prims.append({"op": "sub_box", "part": "cover", "target": "Top_Cover",
                      "name": "Chimney_Aperture",
                      **box((b.soc_x, 0, self.interior_ceiling + e.wall / 2),
                            (e.chimney_aperture, e.chimney_aperture, e.wall + 4.0))})
        # RJ45 port, upper half.
        prims.append({"op": "sub_box", "part": "cover", "target": "Top_Cover",
                      "name": "RJ45_Port_Upper",
                      **box((-self.outer_l / 2, 0, (cover_z0 + self.rj45_port_z1) / 2),
                            (4 * e.wall, self.rj45_port_w, self.rj45_port_z1 - cover_z0))})
        # Gasket groove cut into the lower rim of the cover.
        prims.append(self._rim_groove("cover", "Gasket_Groove_Cover",
                                      self.e_seam_mid_z(),
                                      self.e_seam_mid_z() + e.gasket_groove_depth))

        # =========================== CHIMNEY ===========================
        chim_c = (b.soc_x, 0, (self.stack_z0 + self.stack_z1) / 2)
        prims.append({"op": "add_ring", "part": "chimney", "name": "Chimney_Stack",
                      "material": "cover",
                      "center": chim_c,
                      "outer_half": (self.stack_outer / 2, self.stack_outer / 2),
                      "inner_half": (e.chimney_aperture / 2, e.chimney_aperture / 2),
                      "z0": self.stack_z0, "z1": self.stack_z1})
        # Exhaust slots on all four faces, high on the stack.
        slot_h = self.exhaust_z1 - self.exhaust_z0
        for i, (cx, cy, sx, sy) in enumerate(self._exhaust_cutters()):
            prims.append({"op": "sub_box", "part": "chimney", "target": "Chimney_Stack",
                          "name": f"Exhaust_Slot_{i}",
                          **box((cx, cy, (self.exhaust_z0 + self.exhaust_z1) / 2),
                                (sx, sy, slot_h))})
        # Rain cap plate (penetrates 0.1 mm into the stack top to avoid coplanar
        # union faces).
        prims.append({"op": "add_box", "part": "chimney", "reference": False,
                      "name": "Rain_Cap_Plate", "material": "cover",
                      **box((b.soc_x, 0, (self.cap_z0 - 0.1 + self.cap_z1) / 2),
                            (self.cap_outer, self.cap_outer, e.cap_thickness + 0.1))})
        # Cap skirt (hollow column) that shields the exhaust slots; its top
        # edge penetrates 0.1 mm into the cap plate.
        prims.append({"op": "add_ring", "part": "chimney", "reference": False,
                      "name": "Rain_Cap_Skirt", "material": "cover",
                      "center": (b.soc_x, 0, (self.skirt_z0 + self.cap_z0 + 0.1) / 2),
                      "outer_half": (self.skirt_outer / 2, self.skirt_outer / 2),
                      "inner_half": (self.skirt_inner / 2, self.skirt_inner / 2),
                      "z0": self.skirt_z0, "z1": self.cap_z0 + 0.1})
        # Pitched pyramid roof to shed water (inset 0.1 mm so its corners do not
        # coincide with the cap plate corners, avoiding sliver faces).
        prims.append({"op": "add_pyramid", "part": "chimney", "reference": False,
                      "name": "Rain_Cap_Roof", "material": "cover",
                      "center": (b.soc_x, 0, self.cap_z1),
                      "base_side": self.cap_outer - 0.2, "height": e.roof_rise})

        # ============================ NOSE =============================
        nose = self.e_nose_outer()
        ncx = (self.outer_l / 2 + self.e_nose_front_x()) / 2
        ncy, ncz = 0.0, self.e_nose_center_z()
        prims.append({"op": "add_box", "part": "nose", "name": "Camera_Nose",
                      "material": "petg", **box((ncx, ncy, ncz), nose)})
        cav = self.e_nose_cavity()
        prims.append({"op": "sub_box", "part": "nose", "target": "Camera_Nose",
                      "name": "Nose_Cavity",
                      **box((ncx, ncy, ncz), cav)})
        # M12 lens port through the front wall.
        prims.append({"op": "sub_cylinder", "part": "nose", "target": "Camera_Nose",
                      "name": "Lens_Port", "axis": "X",
                      "center": (self.e_nose_front_x() - 2.0, ncy, ncz),
                      "radius": self.e_lens_port_dia() / 2, "depth": 8.0})
        # FFC pass-through in the nose rear wall.
        fw, ft = self.e_ffc_slot()[:2]
        prims.append({"op": "sub_box", "part": "nose", "target": "Camera_Nose",
                      "name": "FFC_Slot_Nose",
                      **box((self.outer_l / 2 + e.wall, ncy, 6.0), (4 * e.wall, fw, ft))})
        # Sun/rain hood over the lens (rear edge penetrates 0.2 mm so it does not
        # sit coplanar with the nose cavity's front wall).
        hood_len = e.lens_hood_length
        hood_x0 = self.e_nose_front_x() - 2.2
        prims.append({"op": "add_box", "part": "nose", "reference": False,
                      "name": "Lens_Hood", "material": "petg",
                      **box((hood_x0 + (hood_len + 0.4) / 2, ncy, ncz + 8.0),
                            (hood_len + 0.4, camera_module_hood_width(self), 2.0))})

        # =========================== GASKET ============================
        prims.append({"op": "add_ring", "part": "gasket", "name": "Gasket_Seal",
                      "material": "tpu",
                      "center": (0, 0, self.e_seam_mid_z()),
                      "outer_half": (self.rim_x + e.gasket_half_width,
                                     self.rim_y + e.gasket_half_width),
                      "inner_half": (self.rim_x - e.gasket_half_width,
                                     self.rim_y - e.gasket_half_width),
                      "z0": self.e_seam_mid_z() - e.gasket_groove_depth,
                      "z1": self.e_seam_mid_z() + e.gasket_groove_depth})

        # ===================== REFERENCE PROXIES ========================
        prims.extend(self._reference_proxies())
        return prims

    def _exhaust_cutters(self) -> List[Tuple[float, float, float, float]]:
        e, b = self.env, self.board
        half = e.chimney_aperture / 2 + e.chimney_wall / 2
        return [
            (b.soc_x + half, 0.0, e.chimney_wall, e.chimney_aperture),
            (b.soc_x - half, 0.0, e.chimney_wall, e.chimney_aperture),
            (b.soc_x, half, e.chimney_aperture, e.chimney_wall),
            (b.soc_x, -half, e.chimney_aperture, e.chimney_wall),
        ]

    def _rim_groove(self, part: str, name: str, z0: float, z1: float) -> Dict:
        e = self.env
        return {"op": "sub_ring", "part": part,
                "target": "Base_Tub" if part == "base" else "Top_Cover",
                "name": name,
                "center": (0, 0, (z0 + z1) / 2),
                "outer_half": (self.rim_x + e.gasket_half_width,
                               self.rim_y + e.gasket_half_width),
                "inner_half": (self.rim_x - e.gasket_half_width,
                               self.rim_y - e.gasket_half_width),
                "z0": z0, "z1": z1}

    def _reference_proxies(self) -> List[Dict]:
        """Non-exported solids used for fit visualization."""
        b = self.board
        return [
            {"op": "add_box", "part": "ref", "name": "PCB_Proxy", "material": "pcb",
             "center": (0, 0, self.pcb_bottom + b.pcb_thickness / 2),
             "size": (b.pcb_length, b.pcb_width, b.pcb_thickness), "reference": True},
            {"op": "add_box", "part": "ref", "name": "RJ45_Proxy", "material": "ref",
             "center": (-self.inner_l / 2 - 4.0, 0, self.pcb_bottom + b.rj45_height / 2),
             "size": (21.0, b.rj45_width, b.rj45_height), "reference": True},
            {"op": "add_box", "part": "ref", "name": "Heatsink_Proxy", "material": "alu",
             "center": (b.soc_x, 0, self.pcb_top + 1.2 + b.heatsink_height / 2),
             "size": (b.heatsink_width, b.heatsink_width, b.heatsink_height),
             "reference": True},
            {"op": "add_cylinder", "part": "ref", "name": "Lens_Proxy", "material": "ref",
             "axis": "X", "center": (self.e_nose_front_x() - 6.0, 0.0, self.e_nose_center_z()),
             "radius": self.camera.lens_diameter / 2, "depth": 12.0, "reference": True},
            {"op": "add_box", "part": "ref", "name": "SC3336_Proxy", "material": "pcb",
             "center": (self.outer_l / 2 + 2.0, 0.0, self.e_nose_center_z()),
             "size": (2.0, self.camera.module_width, self.camera.module_height),
             "reference": True},
        ]


def camera_module_hood_width(m: Model) -> float:
    """Width (Y extent) of the lens hood, slightly narrower than the nose."""
    return m.camera.module_width + m.env.wall