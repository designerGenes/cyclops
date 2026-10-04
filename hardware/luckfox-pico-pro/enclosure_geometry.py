"""Parametric geometry for the LuckFox Pico Pro top-hood camera enclosure.

This module has no Blender dependency. It owns the dimensions and emits a
primitive list consumed by ``generate_case.py``; the same model is exercised by
the host unit tests.

Coordinates are millimetres: +X is the camera/front, -X is the RJ45/rear, +Z
is up, and the board lies in the XY plane.

The design takes a broad, sheltered-window approach rather than copying any
specific camera housing: a wide rounded-rectangle body, a recessed flat optical
window, a full-width raised canopy with a front drip brow, and a sealed thermal
insert linking the RV1106 heatsink to a low-profile external fin pack beneath
the canopy. The electronics enclosure stays sealed; ambient air can circulate
around the external fins through the canopy's down-facing side gap.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Dict, List, Tuple


Vec = Tuple[float, float, float]


@dataclass(frozen=True)
class BoardSpec:
    pcb_length: float = 72.0
    pcb_width: float = 21.0
    pcb_thickness: float = 1.6
    rj45_width: float = 16.2
    rj45_height: float = 13.8
    soc_x: float = 4.0
    heatsink_width: float = 14.0
    heatsink_height: float = 9.0


@dataclass(frozen=True)
class CameraSpec:
    module_width: float = 25.0
    module_height: float = 24.0
    module_thickness: float = 2.0
    lens_diameter: float = 15.0


@dataclass(frozen=True)
class EnvSpec:
    wall: float = 2.0
    floor: float = 2.0
    standoff: float = 3.5
    seam_z: float = 9.5

    # Broad, subtly rounded body. Front/rear edges stay flat for ports and a
    # recessed optical window; this is intentionally not a pill/doorbell shape.
    body_length: float = 110.0
    body_width: float = 58.0
    body_height: float = 34.0
    corner_radius: float = 9.0

    # Recessed optical window / lens position.
    window_width: float = 20.0
    window_height: float = 17.0
    window_corner_radius: float = 2.0
    window_recess: float = 1.2
    lens_clearance: float = 0.5
    lens_z: float = 18.0

    # Broad raised roof canopy. The roof floats on four integrated support
    # posts, shielding the top/optics while leaving a protected airflow channel.
    hood_front_overhang: float = 10.0
    hood_rear_overhang: float = 4.0
    hood_side_overhang: float = 3.0
    hood_thickness: float = 3.0
    hood_gap: float = 8.0
    hood_corner_radius: float = 12.0
    hood_slope_x: float = -0.015  # drains toward +X/front
    hood_post_radius: float = 2.5
    hood_post_inset_x: float = 8.0
    hood_post_inset_y: float = 6.0

    # External metal thermal insert seated through a gasketed roof port.
    thermal_port_width: float = 20.0
    thermal_port_length: float = 20.0
    thermal_stem_width: float = 18.0
    thermal_stem_length: float = 18.0
    thermal_stem_bottom: float = 17.5
    thermal_flange_width: float = 28.0
    thermal_flange_length: float = 26.0
    thermal_flange_thickness: float = 1.2
    thermal_fin_height: float = 3.0
    thermal_fin_thickness: float = 1.2
    thermal_fin_count: int = 6
    thermal_seal_width: float = 0.8

    # Gasket and face drainage.
    gasket_width: float = 1.6
    gasket_depth: float = 1.2
    face_channel_y: float = 15.0
    face_channel_width: float = 1.2
    face_channel_depth: float = 1.0

    # Rear connector.
    rj45_margin: float = 0.9

    # Printed shell edge softening.
    bevel_offset: float = 1.5
    bevel_min_len: float = 28.0
    bevel_angle_deg: float = 40.0
    tolerance: float = 1e-6


@dataclass
class Model:
    board: BoardSpec = field(default_factory=BoardSpec)
    camera: CameraSpec = field(default_factory=CameraSpec)
    env: EnvSpec = field(default_factory=EnvSpec)

    # Derived shell dimensions.
    half_x: float = 0.0
    half_y: float = 0.0
    inner_length: float = 0.0
    inner_width: float = 0.0
    inner_radius: float = 0.0
    cover_top: float = 0.0
    interior_ceiling: float = 0.0
    floor_top: float = 0.0
    pcb_bottom: float = 0.0
    pcb_top: float = 0.0

    # Hood envelope.
    hood_length: float = 0.0
    hood_width: float = 0.0
    hood_center_x: float = 0.0
    hood_x_min: float = 0.0
    hood_x_max: float = 0.0
    hood_y_max: float = 0.0
    hood_bottom: float = 0.0
    hood_top: float = 0.0
    hood_post_x: float = 0.0
    hood_post_y: float = 0.0

    # Thermal geometry.
    thermal_center_z: float = 0.0
    thermal_flange_bottom: float = 0.0
    thermal_flange_top: float = 0.0
    thermal_fin_top: float = 0.0
    thermal_seal_outer_width: float = 0.0
    thermal_seal_outer_length: float = 0.0
    thermal_seal_inner_width: float = 0.0
    thermal_seal_inner_length: float = 0.0

    # Face / port geometry.
    window_x: float = 0.0
    window_z0: float = 0.0
    window_z1: float = 0.0
    window_y0: float = 0.0
    window_y1: float = 0.0
    lens_port_diameter: float = 0.0
    rj45_port_width: float = 0.0
    rj45_port_z0: float = 0.0
    rj45_port_z1: float = 0.0
    seam_path_length: float = 0.0
    seam_path_width: float = 0.0
    seam_path_radius: float = 0.0

    def recompute(self) -> "Model":
        e, b, c = self.env, self.board, self.camera
        self.half_x = e.body_length / 2
        self.half_y = e.body_width / 2
        self.inner_length = e.body_length - 2 * e.wall
        self.inner_width = e.body_width - 2 * e.wall
        self.inner_radius = e.corner_radius - e.wall

        self.floor_top = e.floor
        self.pcb_bottom = self.floor_top + e.standoff
        self.pcb_top = self.pcb_bottom + b.pcb_thickness
        self.interior_ceiling = e.body_height - e.wall
        self.cover_top = e.body_height

        self.hood_length = e.body_length + e.hood_front_overhang + e.hood_rear_overhang
        self.hood_width = e.body_width + 2 * e.hood_side_overhang
        self.hood_center_x = (e.hood_front_overhang - e.hood_rear_overhang) / 2
        self.hood_x_min = self.hood_center_x - self.hood_length / 2
        self.hood_x_max = self.hood_center_x + self.hood_length / 2
        self.hood_y_max = self.hood_width / 2
        self.hood_bottom = e.body_height + e.hood_gap
        self.hood_top = self.hood_bottom + e.hood_thickness
        self.hood_post_x = self.half_x - e.hood_post_inset_x
        self.hood_post_y = self.half_y - e.hood_post_inset_y

        # The thermal flange is sealed against the roof; its fins stay under
        # the canopy with a free gap above for protected ambient convection.
        self.thermal_flange_bottom = self.cover_top - 0.15
        self.thermal_flange_top = self.thermal_flange_bottom + e.thermal_flange_thickness
        self.thermal_fin_top = self.thermal_flange_top + e.thermal_fin_height
        self.thermal_center_z = (self.thermal_flange_bottom + self.thermal_flange_top) / 2
        self.thermal_seal_outer_width = e.thermal_flange_width - 1.0
        self.thermal_seal_outer_length = e.thermal_flange_length - 1.0
        self.thermal_seal_inner_width = e.thermal_port_width + 0.4
        self.thermal_seal_inner_length = e.thermal_port_length + 0.4

        self.window_x = self.half_x - 1.5 * e.window_recess
        self.window_z0 = e.lens_z - e.window_height / 2
        self.window_z1 = e.lens_z + e.window_height / 2
        self.window_y0 = -e.window_width / 2
        self.window_y1 = e.window_width / 2
        self.lens_port_diameter = c.lens_diameter + 2 * e.lens_clearance

        self.rj45_port_width = b.rj45_width + 2 * e.rj45_margin
        self.rj45_port_z0 = self.pcb_bottom - 0.5
        self.rj45_port_z1 = self.pcb_bottom + b.rj45_height + 0.5

        # Gasket track on the horizontal seam; its centreline sits mid-wall.
        self.seam_path_length = e.body_length - e.wall
        self.seam_path_width = e.body_width - e.wall
        self.seam_path_radius = e.corner_radius - e.wall / 2
        return self

    def validate(self) -> List[Tuple[str, str]]:
        e, b, c = self.env, self.board, self.camera
        issues: List[Tuple[str, str]] = []

        def require(condition: bool, message: str) -> None:
            if not condition:
                issues.append(("error", message))

        ep = e.tolerance
        require(self.inner_length >= b.pcb_length + 2 * e.wall,
                "PCB length does not fit with shell clearance")
        require(self.inner_width >= b.pcb_width + 2 * e.wall,
                "PCB width does not fit with shell clearance")
        require(self.interior_ceiling - self.pcb_top >= b.rj45_height,
                "rear connector exceeds internal headroom")
        require(c.module_width <= self.inner_width,
                "SC3336 board is wider than the internal shell")
        require(e.lens_z - c.module_height / 2 >= e.floor - ep and
                e.lens_z + c.module_height / 2 <= self.interior_ceiling + ep,
                "SC3336 board height exceeds the internal shell")

        # Lens/module are fully behind the front fascia, with the window inside
        # the flat portion of the rounded front face.
        require(e.window_width <= e.body_width - 2 * e.corner_radius,
                "optical window reaches the front corner radii")
        require(e.window_height <= e.body_height - 2 * e.wall,
                "optical window breaks through the top or bottom face")
        require(e.window_width >= c.lens_diameter + 4.0,
                "optical window leaves insufficient margin around the lens")
        require(e.window_height >= c.lens_diameter + 2.0,
                "optical window leaves insufficient vertical lens margin")
        require(self.window_z0 >= e.floor + ep and self.window_z1 <= self.interior_ceiling + ep,
                "optical window is not contained by the front shell")
        actual_panel_z0 = e.lens_z - (e.window_height - 0.4) / 2
        require(actual_panel_z0 >= e.seam_z - ep,
                "shell seam crosses the optical panel")
        require(self.lens_port_diameter > c.lens_diameter,
                "M12 lens port has no clearance")

        # The canopy is deliberately the only external overhang.  Optics and
        # thermal hardware stay inside the body footprint.
        require(self.hood_x_max >= self.half_x + e.hood_front_overhang - ep,
                "canopy does not project over the lens face")
        require(self.hood_width >= e.body_width + 2 * e.hood_side_overhang - ep,
                "canopy is narrower than the body plus eaves")
        require(self.hood_bottom - self.cover_top >= 5.0,
                "canopy airflow gap is too small")
        require(self.thermal_fin_top < self.hood_bottom - 1.0,
                "thermal fins collide with the canopy")
        require(e.hood_slope_x < 0,
                "hood roof must pitch toward the front drip edge")

        require(e.thermal_port_width < e.thermal_flange_width,
                "thermal insert flange does not overlap its roof port")
        require(e.thermal_port_length < e.thermal_flange_length,
                "thermal insert flange does not overlap its roof port")
        require(self.board.soc_x - e.thermal_stem_length / 2 >= -self.half_x + e.wall,
                "thermal stem approaches the rear wall")
        require(self.board.soc_x + e.thermal_stem_length / 2 <= self.half_x - e.wall,
                "thermal stem approaches the front wall")
        require(self.thermal_fin_top < self.hood_bottom - ep,
                "thermal fin pack has no air clearance")

        require(self.rj45_port_z0 >= e.floor - ep and
                self.rj45_port_z1 <= self.interior_ceiling + ep,
                "RJ45 port falls outside the body walls")
        require(e.face_channel_y + e.face_channel_width / 2 < self.half_y - e.corner_radius,
                "front water channels cross into the rounded corners")
        require(e.gasket_width > 0 and e.gasket_depth > 0,
                "main housing gasket dimensions must be positive")

        require(e.body_length >= b.pcb_length + 2 * e.wall + 20,
                "body lacks room for front optics and rear connector")
        require(e.body_width >= e.window_width + 2 * e.corner_radius,
                "body does not contain the full recessed window")
        return issues

    def primitives(self) -> List[Dict]:
        e, b, c = self.env, self.board, self.camera
        px = self.half_x
        wmid = e.lens_z
        p: List[Dict] = []

        def add_round(op, part, name, center, length, width, radius, z0, z1,
                      material=None, **extra):
            item = {"op": op, "part": part, "name": name, "center": center,
                    "length": length, "width": width, "radius": radius,
                    "z0": z0, "z1": z1, **extra}
            if material is not None:
                item["material"] = material
            return item

        def box(center, size):
            return {"center": center, "size": size}

        # ---------------------------- lower shell ----------------------------
        p.append(add_round("add_roundrect", "base", "Base_Tub", (0, 0, 0),
                           e.body_length, e.body_width, e.corner_radius,
                           0.0, e.seam_z, "petg"))
        p.append(add_round("sub_roundrect", "base", "Base_Cavity", (0, 0, 0),
                           self.inner_length, self.inner_width, self.inner_radius,
                           e.floor, e.seam_z + 1.0, target="Base_Tub"))

        # The flat recessed optical panel crosses the shell split.  Cut both
        # halves so the clear panel can seat in one continuous rounded pocket.
        win_size = (4 * e.wall, e.window_width, e.window_height + 0.4)
        win_c = (px, 0, wmid)

        # Bottom half of the RJ45 opening in the rear wall.
        p.append({"op": "sub_box", "part": "base", "target": "Base_Tub",
                  "name": "RJ45_Port_Lower",
                  **box((-px, 0, (self.rj45_port_z0 + e.seam_z) / 2),
                        (6 * e.wall, self.rj45_port_width,
                         e.seam_z - self.rj45_port_z0))})

        # Drainage grooves beside the optical window, running from under the
        # hood to the lower fascia.  Each half lines up at the seam.
        for side in (-1, 1):
            y = side * e.face_channel_y
            p.append({"op": "sub_box", "part": "base", "target": "Base_Tub",
                      "name": f"Front_Drain_Channel_Lower_{side}",
                      **box((px, y, (e.floor + e.seam_z) / 2),
                            (2 * e.face_channel_depth, e.face_channel_width,
                             e.seam_z - e.floor))})

        # Gasket groove in the lower shell rim only.  The cover's rim stays
        # flat and compresses the gasket bead.
        p.append({"op": "sub_roundrect_ring", "part": "base", "target": "Base_Tub",
                  "name": "Main_Gasket_Groove",
                  "center": (0, 0, e.seam_z - e.gasket_depth / 2),
                  "outer_length": self.seam_path_length + e.gasket_width,
                  "outer_width": self.seam_path_width + e.gasket_width,
                  "outer_radius": self.seam_path_radius + e.gasket_width / 2,
                  "inner_length": self.seam_path_length - e.gasket_width,
                  "inner_width": self.seam_path_width - e.gasket_width,
                  "inner_radius": self.seam_path_radius - e.gasket_width / 2,
                  "z0": e.seam_z - e.gasket_depth, "z1": e.seam_z + 0.3})

        # ---------------------------- upper shell ----------------------------
        p.append(add_round("add_roundrect", "cover", "Top_Cover", (0, 0, 0),
                           e.body_length, e.body_width, e.corner_radius,
                           e.seam_z, e.body_height, "cover"))
        p.append(add_round("sub_roundrect", "cover", "Cover_Cavity", (0, 0, 0),
                           self.inner_length, self.inner_width, self.inner_radius,
                           e.seam_z - 0.3, self.interior_ceiling, target="Top_Cover"))

        p.append({"op": "sub_rounded_box", "part": "cover", "target": "Top_Cover",
                  "name": "Optical_Window_Pocket_Upper",
                  **box(win_c, win_size), "radius": e.window_corner_radius})

        # Flush/recessed optical glass panel. It is a visual/optical component,
        # not a printed housing part.
        p.append({"op": "add_rounded_box", "part": "window", "name": "Optical_Window",
                  "material": "glass",
                  "center": (px - 1.5 * e.window_recess, 0, wmid),
                  "size": (e.window_recess, e.window_width - 0.4,
                           e.window_height - 0.4),
                  "radius": e.window_corner_radius})
        p.append({"op": "add_cyl_ring", "part": "window", "name": "M12_Lens_Bezel",
                  "material": "alu", "axis": "X",
                  "center": (self.window_x - 0.85, 0, wmid),
                  "r_outer": 8.6, "r_inner": 7.8, "depth": 0.3})
        p.append({"op": "add_cylinder", "part": "window", "name": "M12_Lens_Element",
                  "material": "lens", "axis": "X",
                  "center": (self.window_x - 1.0, 0, wmid),
                  "radius": self.lens_port_diameter / 2 - 0.2, "depth": 0.3})

        # Upper half of the optical pocket, rear RJ45 port, and front drains.
        p.append({"op": "sub_box", "part": "cover", "target": "Top_Cover",
                  "name": "RJ45_Port_Upper",
                  **box((-px, 0, (e.seam_z + self.rj45_port_z1) / 2),
                        (6 * e.wall, self.rj45_port_width,
                         self.rj45_port_z1 - e.seam_z))})
        for side in (-1, 1):
            y = side * e.face_channel_y
            p.append({"op": "sub_box", "part": "cover", "target": "Top_Cover",
                      "name": f"Front_Drain_Channel_Upper_{side}",
                      **box((px, y, (e.seam_z + self.window_z1 + 1.0) / 2),
                            (2 * e.face_channel_depth, e.face_channel_width,
                             self.window_z1 + 1.0 - e.seam_z))})

        # Gasketed thermal port through the roof over the RV1106 SoC.
        p.append({"op": "sub_box", "part": "cover", "target": "Top_Cover",
                  "name": "Thermal_Insert_Port",
                  **box((b.soc_x, 0, e.body_height - e.wall / 2),
                        (e.thermal_port_length, e.thermal_port_width,
                         e.wall + 4.0))})

        # Four recessed post sockets. They are blind and stay outside the
        # gasketed electronics cavity.
        for ix, x in enumerate((-self.hood_post_x, self.hood_post_x)):
            for iy, y in enumerate((-self.hood_post_y, self.hood_post_y)):
                p.append({"op": "sub_cylinder", "part": "cover", "target": "Top_Cover",
                          "name": f"Hood_Post_Socket_{ix}_{iy}", "axis": "Z",
                          "center": (x, y, e.body_height - 0.45),
                          "radius": e.hood_post_radius + 0.25, "depth": 1.2})

        # ---------------------------- top canopy -----------------------------
        hood_z0 = self.hood_bottom
        hood_z1 = self.hood_top
        p.append(add_round("add_roundrect", "hood", "Canopy_Roof",
                           (self.hood_center_x, 0, 0), self.hood_length,
                           self.hood_width, e.hood_corner_radius,
                           hood_z0, hood_z1, "cover",
                           slope_x=e.hood_slope_x))
        # Pilasters terminate just inside the roof and the blind sockets.
        for ix, x in enumerate((-self.hood_post_x, self.hood_post_x)):
            for iy, y in enumerate((-self.hood_post_y, self.hood_post_y)):
                p.append({"op": "add_cylinder", "part": "hood", "reference": False,
                          "name": f"Canopy_Pillar_{ix}_{iy}", "material": "cover",
                          "axis": "Z", "center": (x, y, (self.cover_top + hood_z0) / 2),
                          "radius": e.hood_post_radius,
                          "depth": hood_z0 - self.cover_top + 0.2})

        # ------------------------- main seam gasket --------------------------
        ring_center_z = e.seam_z - e.gasket_depth / 2
        p.append({"op": "add_roundrect_ring", "part": "gasket", "name": "Main_Gasket",
                  "material": "tpu", "center": (0, 0, ring_center_z),
                  "outer_length": self.seam_path_length + e.gasket_width,
                  "outer_width": self.seam_path_width + e.gasket_width,
                  "outer_radius": self.seam_path_radius + e.gasket_width / 2,
                  "inner_length": self.seam_path_length - e.gasket_width,
                  "inner_width": self.seam_path_width - e.gasket_width,
                  "inner_radius": self.seam_path_radius - e.gasket_width / 2,
                  "z0": e.seam_z - e.gasket_depth,
                  "z1": e.seam_z + 0.2})

        # A second thin seal below the thermal-insert flange. Directly-built
        # ring geometry, not a subtractive cutter.
        p.append({"op": "add_roundrect_ring", "part": "thermal_seal",
                  "name": "Thermal_Insert_Seal", "material": "tpu",
                  "center": (b.soc_x, 0, self.thermal_flange_bottom + 0.05),
                  "outer_length": self.thermal_seal_outer_length,
                  "outer_width": self.thermal_seal_outer_width,
                  "outer_radius": 2.0,
                  "inner_length": self.thermal_seal_inner_length,
                  "inner_width": self.thermal_seal_inner_width,
                  "inner_radius": 1.0,
                  "z0": self.thermal_flange_bottom - 0.35,
                  "z1": self.thermal_flange_bottom + 0.45})

        # ---------------------- metal thermal insert -------------------------
        # A separate metal part bridges the SoC heatsink through the sealed
        # roof port; its low fins live in the ventilated, rain-sheltered canopy.
        p.append({"op": "add_box", "part": "thermal_insert", "name": "Thermal_Stem",
                  "material": "alu", "center": (b.soc_x, 0,
                  (e.thermal_stem_bottom + self.thermal_flange_bottom + 0.2) / 2),
                  "size": (e.thermal_stem_length, e.thermal_stem_width,
                           self.thermal_flange_bottom - e.thermal_stem_bottom + 0.2)})
        p.append({"op": "add_box", "part": "thermal_insert", "reference": False,
                  "name": "Thermal_Flange", "material": "alu",
                  "center": (b.soc_x, 0, self.thermal_center_z),
                  "size": (e.thermal_flange_length, e.thermal_flange_width,
                           e.thermal_flange_thickness)})
        # Fin positions spread evenly across the plate's Y dimension.
        fin_span = e.thermal_flange_width - 4.0
        if e.thermal_fin_count > 1:
            step = fin_span / (e.thermal_fin_count - 1)
        else:
            step = 0.0
        for i in range(e.thermal_fin_count):
            fy = -fin_span / 2 + i * step
            p.append({"op": "add_box", "part": "thermal_insert", "reference": False,
                      "name": f"Thermal_Fin_{i}", "material": "alu",
                      "center": (b.soc_x, fy,
                                 self.thermal_flange_top + e.thermal_fin_height / 2 - 0.05),
                      "size": (e.thermal_flange_length - 4.0,
                               e.thermal_fin_thickness,
                               e.thermal_fin_height + 0.1)})

        # ------------------------- visual references -------------------------
        p.extend(self._reference_proxies())
        return p

    def _reference_proxies(self) -> List[Dict]:
        b, c, e = self.board, self.camera, self.env
        pcb_z = self.pcb_bottom + b.pcb_thickness / 2
        sink_bottom = self.pcb_top + 1.2
        sink_top = sink_bottom + b.heatsink_height
        cam_board_x = self.half_x - e.wall - c.module_thickness / 2 - 1.0
        refs = [
            {"op": "add_box", "part": "ref", "name": "PCB_Proxy", "material": "pcb",
             "center": (0, 0, pcb_z), "size": (b.pcb_length, b.pcb_width,
                                                  b.pcb_thickness), "reference": True},
            {"op": "add_box", "part": "ref", "name": "RJ45_Proxy", "material": "ref",
             "center": (-self.half_x + 10.0, 0,
                        self.pcb_bottom + b.rj45_height / 2),
             "size": (20.0, b.rj45_width, b.rj45_height), "reference": True},
            {"op": "add_box", "part": "ref", "name": "SC3336_Board_Proxy", "material": "pcb",
             "center": (cam_board_x, 0, e.lens_z),
             "size": (c.module_thickness, c.module_width, c.module_height),
             "reference": True},
            {"op": "add_cylinder", "part": "ref", "name": "M12_Lens_Proxy",
             "material": "ref", "axis": "X",
             "center": (self.half_x - e.wall - 5.0, 0, e.lens_z),
             "radius": c.lens_diameter / 2, "depth": 7.0, "reference": True},
            {"op": "add_box", "part": "ref", "name": "RV1106_Heatsink_Proxy",
             "material": "alu", "center": (b.soc_x, 0,
                         sink_bottom + b.heatsink_height / 2),
             "size": (b.heatsink_width, b.heatsink_width,
                      b.heatsink_height), "reference": True},
            {"op": "add_box", "part": "ref", "name": "Thermal_Contact_Pad_Proxy",
             "material": "ref", "center": (b.soc_x, 0, sink_top + 0.15),
             "size": (e.thermal_stem_length - 1.0,
                      e.thermal_stem_width - 1.0, 0.3), "reference": True},
        ]
        return refs


def rectangle_loop(length: float, width: float, radius: float, segments: int = 8):
    """Return a CCW rounded-rectangle outline centered at the origin."""
    hx, hy = length / 2, width / 2
    r = min(radius, hx, hy)
    out = []
    corners = ((hx - r, hy - r, 0), (-hx + r, hy - r, 90),
               (-hx + r, -hy + r, 180), (hx - r, -hy + r, 270))
    for cx, cy, start_deg in corners:
        for i in range(segments + 1):
            a = (start_deg + 90 * i / segments) * 3.141592653589793 / 180
            out.append((cx + r * math.cos(a), cy + r * math.sin(a)))
    return out
