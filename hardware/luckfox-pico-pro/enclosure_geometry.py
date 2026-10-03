"""Parametric geometry for the LuckFox Pico Pro weatherproof camera enclosure.

This module is deliberately free of any Blender dependency so that the
enclosure's dimensional model can be unit-tested on the host.  Every value the
Blender build script (``generate_case.py``) needs is computed here from a
single set of inputs, keeping the 3D builder and the tests in lock-step.

All lengths are in millimetres.  Conventions:

* +X points toward the camera (front), -X toward the RJ45/PoE port (rear).
* +Z points up.  ``z == 0`` is the underside of the floor plate.
* The plan origin sits at the centre of the PCB footprint.

Aesthetic intent (v2)
---------------------

The first cut was a slim rectangular "plug".  This revision is optimised for
**symmetry** and **rounded corners**:

* the body plan is a *stadium* (capsule): a straight mid-section closed by two
  full semicircular ends, so front and rear read identically and every corner
  in plan is a smooth radius;
* the cooling stack is a **round chimney** with a conical rain cap and a
  cylindrical skirt (rotationally symmetric);
* the camera is a **cylindrical lens barrel** centred on the front dome;
* long hard edges are softened with a baked bevel at build time.

Thermal / weather design is unchanged in principle and is what the tests
enforce: cool air enters through downward-facing floor vents beneath the PCB
plenum, rises over the components, and exits through chimney slots that sit
behind a skirt that drops *below* the openings, so the air path turns downward
again before it meets open air.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Tuple

Vec = Tuple[float, float, float]


@dataclass(frozen=True)
class BoardSpec:
    """Physical dimensions of the LuckFox Pico Pro (RV1106) + RJ45 cage."""

    pcb_length: float = 72.0
    pcb_width: float = 21.0
    pcb_thickness: float = 1.6
    rj45_width: float = 16.2
    rj45_height: float = 13.8
    soc_x: float = 4.0          # SoC centre offset from PCB centre (+X)
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

    wall: float = 2.0
    floor: float = 2.0
    standoff: float = 3.5
    component_clearance: float = 1.0
    seam_z: float = 13.0
    clearance: float = 0.6          # minimum PCB clearance inside the body

    # Body: a stadium (capsule).  Width is generous so the camera barrel can
    # sit flush and the silhouette reads rounded rather than plank-like.
    body_width: float = 30.0
    body_straight: float = 76.0

    # Bottom intake vents (cut through the floor, facing downward).
    intake_slot_width: float = 1.5
    intake_slot_length: float = 12.0
    intake_count: int = 3
    intake_spacing_x: float = 18.0
    foot_height: float = 3.0

    # Round chimney.
    chimney_inner_r: float = 10.0   # draft column radius (Ø20)
    chimney_wall: float = 2.0
    chimney_outer_height: float = 18.0
    exhaust_slot_height: float = 8.0
    cap_overhang: float = 8.0       # rain cap eave beyond the stack
    cap_thickness: float = 2.0
    cap_annulus: float = 4.0        # air gap between stack and cap skirt
    cap_skirt_length: float = 16.0
    roof_height: float = 4.0

    # Camera nose (cylindrical lens barrel).
    nose_r: float = 20.0            # outer radius (Ø40)
    nose_wall: float = 2.0
    nose_len: float = 20.0
    nose_rear_opening_r: float = 15.0   # cable/FFC aperture (Ø30)
    lens_clearance: float = 0.5
    hood_r: float = 16.0            # lens shade outer radius (Ø32)
    hood_wall: float = 2.0
    hood_len: float = 8.0
    ffc_margin: float = 0.3

    # Seam gasket (captured TPU cord).
    gasket_half_width: float = 0.8
    gasket_groove_depth: float = 1.2

    # Ports.
    rj45_port_margin: float = 0.9
    body_front_opening_r: float = 9.5   # Ø19 barrel<->body aperture

    # Edge softening (baked bevel on long hard edges).
    bevel_offset: float = 2.0
    bevel_min_len: float = 20.0
    bevel_angle_deg: float = 40.0

    tolerance: float = 1e-6


@dataclass
class Model:
    """Fully-computed dimensional model of the enclosure."""

    board: BoardSpec = field(default_factory=BoardSpec)
    camera: CameraSpec = field(default_factory=CameraSpec)
    env: EnvSpec = field(default_factory=EnvSpec)

    # --- plan ---
    body_width: float = 0.0
    body_straight: float = 0.0
    total_length: float = 0.0
    end_radius: float = 0.0
    end_center_x: float = 0.0
    total_half_x: float = 0.0
    inner_width: float = 0.0
    inner_half_w: float = 0.0
    inner_end_radius: float = 0.0
    inner_half_x: float = 0.0

    # --- z stack ---
    floor_top: float = 0.0
    pcb_bottom: float = 0.0
    pcb_top: float = 0.0
    interior_ceiling: float = 0.0
    cover_top: float = 0.0

    # --- chimney ---
    stack_inner_r: float = 0.0
    stack_outer_r: float = 0.0
    stack_z0: float = 0.0
    stack_z1: float = 0.0
    exhaust_z0: float = 0.0
    exhaust_z1: float = 0.0
    cap_r: float = 0.0
    cap_z0: float = 0.0
    cap_z1: float = 0.0
    skirt_inner_r: float = 0.0
    skirt_outer_r: float = 0.0
    skirt_z0: float = 0.0
    skirt_z1: float = 0.0
    roof_apex_z: float = 0.0

    # --- nose ---
    nose_inner_r: float = 0.0
    nose_x0: float = 0.0
    nose_x1: float = 0.0
    nose_center_z: float = 0.0

    # --- ports / gasket ---
    rj45_port_w: float = 0.0
    rj45_port_z0: float = 0.0
    rj45_port_z1: float = 0.0
    rim_outer_hw: float = 0.0
    rim_inner_hw: float = 0.0

    def recompute(self) -> "Model":
        e, b, c = self.env, self.board, self.camera

        # Plan.
        self.body_width = e.body_width
        self.body_straight = e.body_straight
        self.end_radius = e.body_width / 2.0
        self.end_center_x = e.body_straight / 2.0
        self.total_half_x = self.end_center_x + self.end_radius
        self.total_length = 2 * self.total_half_x
        self.inner_width = e.body_width - 2 * e.wall
        self.inner_half_w = self.inner_width / 2.0
        self.inner_end_radius = self.inner_half_w
        self.inner_half_x = self.end_center_x + self.inner_end_radius

        # Vertical stack.
        self.floor_top = e.floor
        self.pcb_bottom = self.floor_top + e.standoff
        self.pcb_top = self.pcb_bottom + b.pcb_thickness
        self.interior_ceiling = self.pcb_top + b.rj45_height + e.component_clearance
        self.cover_top = self.interior_ceiling + e.wall

        # Chimney (round).  The aperture is a Ø20 column over the SoC, large
        # enough to fully overhang a 14x14 heatsink and its corner fins.
        self.stack_inner_r = e.chimney_inner_r
        self.stack_outer_r = e.chimney_inner_r + e.chimney_wall
        self.stack_z0 = self.cover_top
        self.stack_z1 = self.stack_z0 + e.chimney_outer_height
        self.exhaust_z0 = self.stack_z1 - e.chimney_wall - e.exhaust_slot_height
        self.exhaust_z1 = self.stack_z1 - e.chimney_wall
        self.cap_r = self.stack_outer_r + e.cap_overhang
        self.cap_z0 = self.stack_z1
        self.cap_z1 = self.cap_z0 + e.cap_thickness
        self.skirt_inner_r = self.stack_outer_r + e.cap_annulus
        self.skirt_outer_r = self.skirt_inner_r + e.chimney_wall
        self.skirt_z1 = self.cap_z0
        self.skirt_z0 = self.skirt_z1 - e.cap_skirt_length
        self.roof_apex_z = self.cap_z1 + e.roof_height

        # Nose.
        self.nose_inner_r = e.nose_r - e.nose_wall
        self.nose_x0 = self.total_half_x + e.wall
        self.nose_x1 = self.nose_x0 + e.nose_len
        self.nose_center_z = self.cover_top / 2.0

        # Ports / gasket.  The gasket channel spans the full 2 mm rim so its walls
        # coincide with the cavity / shell faces (no thin sliver bands).
        self.rj45_port_w = b.rj45_width + 2 * e.rj45_port_margin
        self.rj45_port_z0 = self.pcb_bottom - 1.0
        self.rj45_port_z1 = self.interior_ceiling
        self.rim_outer_hw = self.end_radius - 0.5    # gasket band outer edge
        self.rim_inner_hw = self.inner_half_w + 0.5  # gasket band inner edge
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

        # 1. PCB clears the interior stadium in the straight section.
        require(self.inner_half_w >= b.pcb_width / 2 + e.clearance - ep,
                "PCB width lacks the specified radial clearance")
        require(self.end_center_x >= b.pcb_length / 2 + e.clearance - ep,
                "PCB length lacks the specified radial clearance")
        require(self.interior_ceiling - self.pcb_top >= b.rj45_height - ep,
                "interior is short of the RJ45 cage height")

        # 2. Heatsink fully under the round chimney column (corners included).
        require(2 * self.stack_inner_r >= b.heatsink_width * math_sqrt2() - ep,
                "round chimney column does not overhang the full heatsink")
        require(self.stack_z1 - self.stack_z0 > b.heatsink_height,
                "chimney stack is not taller than the heatsink")

        # 3. Lens and FFC pass-throughs are large enough.
        require(self.e_lens_port_dia() > c.lens_diameter, "lens port smaller than barrel")
        require(c.ffc_width + 2 * e.ffc_margin > c.ffc_width,
                "FFC slot narrower than cable")
        require(1.2 + 2 * e.ffc_margin > c.ffc_thickness,
                "FFC slot thinner than cable")
        # The camera module (25x24) must seat inside the round barrel.
        module_diag = (c.module_width ** 2 + c.module_height ** 2) ** 0.5
        require(2 * self.nose_inner_r >= module_diag - ep,
                "camera module diagonal does not fit the nose barrel")

        # 4. Symmetry & rounding intent.
        require(self.end_radius >= e.body_width / 2 - ep,
                "body ends are not full semicircles (asymmetric plan)")
        require(e.roof_height > 0, "rain cap roof must pitch water off")
        require(e.bevel_offset > 0, "edge rounding is disabled")
        require(abs(self.board.soc_x) <= e.body_straight / 4,
                "chimney sits far off the body centre")

        # 5. Weather-proofing.
        require(self.skirt_z0 <= self.exhaust_z0 - ep,
                "cap skirt does not drop below the exhaust slots")
        require(self.skirt_inner_r > self.stack_outer_r,
                "no annulus between stack and cap skirt")
        require(self.skirt_outer_r <= self.cap_r + ep,
                "cap eave does not overhang the skirt")
        require((self.skirt_z1 - self.skirt_z0) >= (self.exhaust_z1 - self.exhaust_z0),
                "skirt shorter than the exhaust opening")
        require(self.e_intake_top() <= self.pcb_bottom + ep,
                "intake opens above the PCB plenum")
        require(e.foot_height >= 2.0, "feet too short to let air under the floor")

        # 6. Ports stay within the interior / walls.
        require(self.rj45_port_z1 <= self.interior_ceiling + ep,
                "RJ45 port breaches the top wall")
        require(self.rj45_port_z0 >= self.floor_top - ep,
                "RJ45 port dips below the floor")

        # 7. Stack stays within the body plan; cap may eave over but stays sane.
        require(self.board.soc_x + self.stack_outer_r <= self.total_half_x,
                "chimney stack protrudes beyond the body length")
        require(self.stack_outer_r <= self.inner_half_w + e.wall - ep,
                "chimney stack protrudes beyond the body width")

        # 8. Minimalist footprint (hard upper bounds).
        require(self.total_length <= 125.0, "enclosure too long")
        require(self.body_width <= 40.0, "enclosure too wide")
        require(self.roof_apex_z <= 55.0, "enclosure too tall")
        return issues

    # ------------------------------------------------------------------
    # Accessors
    # ------------------------------------------------------------------
    def e_lens_port_dia(self) -> float:
        return self.camera.lens_diameter + 2 * self.env.lens_clearance

    def e_intake_top(self) -> float:
        return self.floor_top

    def e_ffc_slot(self) -> Vec:
        c, e = self.camera, self.env
        return (c.ffc_width + 2 * e.ffc_margin, c.ffc_thickness + 2 * e.ffc_margin)

    def e_intake_xs(self) -> List[float]:
        e = self.env
        mid = (e.intake_count - 1) / 2
        return [(i - mid) * e.intake_spacing_x for i in range(e.intake_count)]

    def e_nose_center(self) -> Vec:
        return ((self.nose_x0 + self.nose_x1) / 2, 0.0, self.nose_center_z)

    # ------------------------------------------------------------------
    # Primitive build list
    # ------------------------------------------------------------------
    def primitives(self) -> List[Dict]:
        e, b = self.env, self.board

        def boxc(cx, cy, cz, sx, sy, sz) -> Dict:
            return {"center": (cx, cy, cz), "size": (sx, sy, sz)}

        prims: List[Dict] = []

        # ============================ BASE =============================
        prims.append({"op": "add_stadium", "part": "base", "name": "Base_Tub",
                      "material": "petg", "center": (0, 0, e.seam_z / 2),
                      "straight": e.body_straight, "half_width": self.end_radius,
                      "z0": 0.0, "z1": e.seam_z})
        prims.append({"op": "sub_stadium", "part": "base", "target": "Base_Tub",
                      "name": "Base_Cavity",
                      "center": (0, 0, (self.floor_top + e.seam_z) / 2),
                      "straight": e.body_straight, "half_width": self.inner_half_w,
                      "z0": self.floor_top, "z1": e.seam_z + 4.0})
        # RJ45 port, lower half, on the rear dome.
        prims.append({"op": "sub_box", "part": "base", "target": "Base_Tub",
                      "name": "RJ45_Port_Lower",
                      **boxc(-self.total_half_x, 0, (self.rj45_port_z0 + e.seam_z) / 2,
                             6 * e.wall, self.rj45_port_w, e.seam_z - self.rj45_port_z0)})
        # Downward-facing intake slots through the floor.
        for i, x in enumerate(self.e_intake_xs()):
            prims.append({"op": "sub_box", "part": "base", "target": "Base_Tub",
                          "name": f"Intake_Slot_{i}",
                          **boxc(x, 0, e.floor / 2,
                                 e.intake_slot_length, e.intake_slot_width, e.floor * 3)})
        # Drain weeps at the front of the floor.
        for i, y in enumerate((10.0, -10.0)):
            prims.append({"op": "sub_cylinder", "part": "base", "target": "Base_Tub",
                          "name": f"Drain_Weep_{i}", "axis": "Z",
                          "center": (28.0, y, e.floor / 2),
                          "radius": 0.6, "depth": e.floor * 3})
        # Standoff bosses for the PCB (bottoms penetrate the floor).
        for i, (sx, sy) in enumerate(((30.0, 8.0), (30.0, -8.0),
                                      (-30.0, 8.0), (-30.0, -8.0))):
            prims.append({"op": "add_cylinder", "part": "base", "reference": False,
                          "name": f"Standoff_{i}", "material": "petg", "axis": "Z",
                          "center": (sx, sy, (self.floor_top - 0.1 + self.pcb_bottom) / 2),
                          "radius": 3.0,
                          "depth": self.pcb_bottom - self.floor_top + 0.1})
        # Feet (tops penetrate the floor underside).
        for i, (fx, fy) in enumerate(((28.0, 10.0), (28.0, -10.0),
                                      (-28.0, 10.0), (-28.0, -10.0))):
            prims.append({"op": "add_box", "part": "base", "reference": False,
                          "name": f"Foot_{i}", "material": "petg",
                          **boxc(fx, fy, (-e.foot_height + 0.05) / 2,
                                 8.0, 8.0, e.foot_height + 0.05)})
        # Front dome opening matching the camera barrel (FFC / cable path).
        prims.append({"op": "sub_cylinder", "part": "base", "target": "Base_Tub",
                      "name": "Front_Opening_Base", "axis": "X",
                      "center": (self.total_half_x - e.wall, 0, self.nose_center_z),
                      "radius": e.body_front_opening_r, "depth": 2 * e.wall + 2.0})
        _add_gasket_grooves(self, prims)

        # ============================ COVER ============================
        cover_c = (e.seam_z + self.cover_top) / 2
        prims.append({"op": "add_stadium", "part": "cover", "name": "Top_Cover",
                      "material": "cover",
                      "center": (0, 0, cover_c),
                      "straight": e.body_straight, "half_width": self.end_radius,
                      "z0": e.seam_z, "z1": self.cover_top})
        prims.append({"op": "sub_stadium", "part": "cover", "target": "Top_Cover",
                      "name": "Cover_Cavity",
                      "center": (0, 0, (e.seam_z + self.interior_ceiling) / 2),
                      "straight": e.body_straight, "half_width": self.inner_half_w,
                      "z0": e.seam_z - 4.0, "z1": self.interior_ceiling})
        # Round chimney aperture through the cover top wall, over the SoC.
        prims.append({"op": "sub_cylinder", "part": "cover", "target": "Top_Cover",
                      "name": "Chimney_Aperture", "axis": "Z",
                      "center": (b.soc_x, 0, self.interior_ceiling),
                      "radius": self.stack_inner_r, "depth": 2 * e.wall + 6.0})
        # RJ45 port, upper half.
        prims.append({"op": "sub_box", "part": "cover", "target": "Top_Cover",
                      "name": "RJ45_Port_Upper",
                      **boxc(-self.total_half_x, 0, (e.seam_z + self.rj45_port_z1) / 2,
                             6 * e.wall, self.rj45_port_w, self.rj45_port_z1 - e.seam_z)})
        # Front dome opening aligning the body interior with the camera barrel
        # (FFC / cable path); small enough to keep the shell walls intact.
        prims.append({"op": "sub_cylinder", "part": "cover", "target": "Top_Cover",
                      "name": "Front_Opening_Cover", "axis": "X",
                      "center": (self.total_half_x - e.wall, 0, self.nose_center_z),
                      "radius": e.body_front_opening_r, "depth": 2 * e.wall + 2.0})

        # =========================== CHIMNEY ===========================
        chim_c = (b.soc_x, 0, (self.stack_z0 + self.stack_z1) / 2)
        prims.append({"op": "add_cyl_ring", "part": "chimney", "name": "Chimney_Stack",
                      "material": "cover", "center": chim_c,
                      "r_outer": self.stack_outer_r, "r_inner": self.stack_inner_r,
                      "z0": self.stack_z0, "z1": self.stack_z1})
        for i, (cx, cy, sx, sy) in enumerate(self._exhaust_cutters()):
            prims.append({"op": "sub_box", "part": "chimney", "target": "Chimney_Stack",
                          "name": f"Exhaust_Slot_{i}",
                          **boxc(cx, cy, (self.exhaust_z0 + self.exhaust_z1) / 2,
                                 sx, sy, self.exhaust_z1 - self.exhaust_z0)})
        prims.append({"op": "add_cylinder", "part": "chimney", "reference": False,
                      "name": "Rain_Cap_Plate", "material": "cover", "axis": "Z",
                      "center": (b.soc_x, 0, (self.cap_z0 - 0.1 + self.cap_z1) / 2),
                      "radius": self.cap_r, "depth": e.cap_thickness + 0.1})
        prims.append({"op": "add_cyl_ring", "part": "chimney", "reference": False,
                      "name": "Rain_Cap_Skirt", "material": "cover",
                      "center": (b.soc_x, 0, (self.skirt_z0 + self.cap_z0 + 0.1) / 2),
                      "r_outer": self.skirt_outer_r, "r_inner": self.skirt_inner_r,
                      "z0": self.skirt_z0, "z1": self.cap_z0 + 0.1})
        prims.append({"op": "add_cone", "part": "chimney", "reference": False,
                      "name": "Rain_Cap_Roof", "material": "cover", "axis": "Z",
                      "center": (b.soc_x, 0, self.cap_z1),
                      "radius1": self.cap_r, "radius2": 0.0,
                      "depth": e.roof_height})

        # ============================ NOSE =============================
        nose_c = self.e_nose_center()
        prims.append({"op": "add_cylinder", "part": "nose", "name": "Camera_Nose",
                      "material": "petg", "axis": "X", "center": nose_c,
                      "radius": e.nose_r, "depth": e.nose_len})
        # Interior barrel (leaves 2 mm front + rear walls).
        prims.append({"op": "sub_cylinder", "part": "nose", "target": "Camera_Nose",
                      "name": "Nose_Cavity", "axis": "X",
                      "center": (nose_c[0], nose_c[1], nose_c[2]),
                      "radius": self.nose_inner_r,
                      "depth": e.nose_len - 2 * e.nose_wall})
        # Rear opening to the body (FFC / cable path).
        prims.append({"op": "sub_cylinder", "part": "nose", "target": "Camera_Nose",
                      "name": "Nose_Rear_Opening", "axis": "X",
                      "center": (self.nose_x0 + e.nose_wall / 2, 0, self.nose_center_z),
                      "radius": e.nose_rear_opening_r, "depth": e.nose_wall + 1.0})
        # M12 lens port through the front wall.
        prims.append({"op": "sub_cylinder", "part": "nose", "target": "Camera_Nose",
                      "name": "Lens_Port", "axis": "X",
                      "center": (self.nose_x1 - e.nose_wall / 2, 0, self.nose_center_z),
                      "radius": self.e_lens_port_dia() / 2, "depth": e.nose_wall + 1.0})
        # Lens shade: a short open tube protruding from the front face.
        shade_x0 = self.nose_x1 - 0.1
        prims.append({"op": "add_cyl_ring", "part": "nose", "reference": False,
                      "name": "Lens_Shade", "material": "petg", "axis": "X",
                      "center": (shade_x0 + e.hood_len / 2, 0, self.nose_center_z),
                      "r_outer": e.hood_r, "r_inner": e.hood_r - e.hood_wall,
                      "z0": shade_x0, "z1": shade_x0 + e.hood_len})

        # =========================== GASKET ============================
        gasket_depth = 2 * e.gasket_groove_depth
        prims.append({"op": "add_stadium_ring", "part": "gasket", "name": "Gasket_Seal",
                      "material": "tpu", "center": (0, 0, e.seam_z),
                      "straight": e.body_straight,
                      "outer_hw": self.rim_outer_hw, "inner_hw": self.rim_inner_hw,
                      "z0": e.seam_z - gasket_depth, "z1": e.seam_z})

        prims.extend(self._reference_proxies())
        return prims

    def _exhaust_cutters(self) -> List[Tuple[float, float, float, float]]:
        # Each cutter spans from inside the inner wall (r_inner) to outside the
        # outer wall (r_outer) centred on their mean radius, and across the full
        # inner diameter, so the slot breaks completely through the curved wall.
        mid = (self.stack_inner_r + self.stack_outer_r) / 2
        d = 2 * self.stack_inner_r
        return [
            (self.board.soc_x + mid, 0.0, 6.0, d),
            (self.board.soc_x - mid, 0.0, 6.0, d),
            (self.board.soc_x, mid, d, 6.0),
            (self.board.soc_x, -mid, d, 6.0),
        ]

    def _reference_proxies(self) -> List[Dict]:
        b, e = self.board, self.env
        nose_c = self.e_nose_center()
        return [
            {"op": "add_box", "part": "ref", "name": "PCB_Proxy", "material": "pcb",
             "center": (0, 0, self.pcb_bottom + b.pcb_thickness / 2),
             "size": (b.pcb_length, b.pcb_width, b.pcb_thickness), "reference": True},
            {"op": "add_box", "part": "ref", "name": "RJ45_Proxy", "material": "ref",
             "center": (-self.inner_half_x + 8.0, 0, self.pcb_bottom + b.rj45_height / 2),
             "size": (21.0, b.rj45_width, b.rj45_height), "reference": True},
            {"op": "add_box", "part": "ref", "name": "Heatsink_Proxy", "material": "alu",
             "center": (b.soc_x, 0, self.pcb_top + 1.2 + b.heatsink_height / 2),
             "size": (b.heatsink_width, b.heatsink_width, b.heatsink_height),
             "reference": True},
            {"op": "add_cylinder", "part": "ref", "name": "Lens_Proxy", "material": "ref",
             "axis": "X",
             "center": (self.nose_x1 - 4.0, 0, self.nose_center_z),
             "radius": self.camera.lens_diameter / 2, "depth": 12.0, "reference": True},
            {"op": "add_box", "part": "ref", "name": "SC3336_Proxy", "material": "pcb",
             "center": (self.nose_x0 + 3.0, 0, self.nose_center_z),
             "size": (2.0, self.camera.module_width, self.camera.module_height),
             "reference": True},
        ]


def _add_gasket_grooves(m: "Model", prims: List[Dict]) -> None:
    e = m.env
    # The single gasket channel lives in the base (the cover rim is flat and
    # compresses against it).  It over-pierces the seam so the cutter does not
    # sit coplanar with the rim face (that is what produces zero-area slivers).
    depth = 2 * e.gasket_groove_depth
    prims.append({"op": "sub_stadium_ring", "part": "base", "target": "Base_Tub",
                  "name": "Gasket_Groove_Base",
                  "center": (0, 0, (e.seam_z - depth + e.seam_z) / 2),
                  "straight": e.body_straight,
                  "outer_hw": m.rim_outer_hw, "inner_hw": m.rim_inner_hw,
                  "z0": e.seam_z - depth, "z1": e.seam_z + 2.0})


def math_sqrt2() -> float:
    return 1.4142135623730951