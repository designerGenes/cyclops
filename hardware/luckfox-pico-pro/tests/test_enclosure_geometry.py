"""Unit tests for the LuckFox Pico Pro enclosure geometry model.

These tests exercise the pure-Python dimensional model only; no Blender
installation is required to run them.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from enclosure_geometry import (  # noqa: E402
    BoardSpec,
    CameraSpec,
    EnvSpec,
    Model,
)


def make_model(**overrides) -> Model:
    m = Model().recompute()
    for key, value in overrides.items():
        setattr(m, key, value)
    return m


# ---------------------------------------------------------------------------
# Default model sanity
# ---------------------------------------------------------------------------
def test_default_model_validates_clean():
    issues = make_model().validate()
    assert issues == [], f"default model should validate cleanly, got {issues}"


def test_derived_envelope_dimensions():
    m = make_model()
    assert m.body_width == 30.0
    assert m.body_straight == 76.0
    assert m.end_radius == 15.0
    assert m.total_length == 106.0
    assert m.inner_width == 26.0


def test_z_stack_ordering():
    m = make_model()
    zs = [m.floor_top, m.pcb_bottom, m.pcb_top, m.interior_ceiling,
          m.cover_top, m.stack_z0, m.stack_z1]
    assert all(zs[i] <= zs[i + 1] for i in range(len(zs) - 1)), zs


# ---------------------------------------------------------------------------
# Fit checks
# ---------------------------------------------------------------------------
def test_pcb_fits_with_clearance():
    m = make_model()
    assert m.inner_half_w >= m.board.pcb_width / 2 + m.env.clearance - 1e-6
    assert m.end_center_x >= m.board.pcb_length / 2 + m.env.clearance - 1e-6
    assert m.interior_ceiling - m.pcb_top >= m.board.rj45_height


def test_heatsink_fully_under_chimney_column():
    m = make_model()
    # The round column must overhang every corner fin of the square heatsink.
    heatsink_diag = m.board.heatsink_width * 1.4142135623730951
    assert 2 * m.stack_inner_r >= heatsink_diag - 1e-6
    assert m.stack_z1 - m.stack_z0 > m.board.heatsink_height


def test_sc3336_module_fits_nose_barrel():
    m = make_model()
    diag = (m.camera.module_width ** 2 + m.camera.module_height ** 2) ** 0.5
    assert 2 * m.nose_inner_r >= diag - 1e-6


def test_lens_and_ffc_pass_throughs():
    m = make_model()
    assert m.e_lens_port_dia() > m.camera.lens_diameter
    fw, ft = m.e_ffc_slot()[:2]
    assert fw > m.camera.ffc_width
    assert ft > m.camera.ffc_thickness


# ---------------------------------------------------------------------------
# Symmetry and rounding invariants
# ---------------------------------------------------------------------------
def test_body_is_symmetric_capsule():
    m = make_model()
    assert m.end_radius >= m.body_width / 2 - 1e-6   # full semicircle ends
    assert abs(m.board.soc_x) <= m.body_straight / 4  # chimney near centre
    # front and rear ends are geometrically identical (mirror about x=0)
    assert m.end_center_x == m.body_straight / 2


def test_rounding_is_enabled():
    m = make_model()
    assert m.env.bevel_offset > 0
    assert m.env.bevel_min_len > 0
    assert m.env.bevel_angle_deg > 0


def test_rain_cap_pitches_water():
    m = make_model()
    assert m.env.roof_height > 0
    assert m.cap_r >= m.stack_outer_r + m.env.cap_overhang - 1e-6


# ---------------------------------------------------------------------------
# Weather-proofing invariants
# ---------------------------------------------------------------------------
def test_exhaust_slots_shielded_by_cap_skirt():
    m = make_model()
    assert m.skirt_z0 <= m.exhaust_z0
    assert m.skirt_inner_r > m.stack_outer_r
    assert (m.skirt_z1 - m.skirt_z0) >= (m.exhaust_z1 - m.exhaust_z0)


def test_intakes_face_downward_below_pcb():
    m = make_model()
    assert m.e_intake_top() <= m.pcb_bottom
    assert m.env.foot_height >= 2.0
    assert m.env.intake_slot_length <= 2 * m.end_center_x - 4 * m.env.wall


def test_chimney_within_body_plan():
    m = make_model()
    assert m.board.soc_x + m.stack_outer_r <= m.total_half_x
    assert m.stack_outer_r <= m.inner_half_w + m.env.wall - 1e-6


def test_rj45_port_within_interior():
    m = make_model()
    assert m.rj45_port_z1 <= m.interior_ceiling
    assert m.rj45_port_z0 >= m.floor_top
    assert m.rj45_port_w >= m.board.rj45_width + 2 * m.env.rj45_port_margin


def test_minimalist_footprint():
    m = make_model()
    assert m.total_length <= 125.0
    assert m.body_width <= 40.0
    assert m.roof_apex_z <= 55.0


# ---------------------------------------------------------------------------
# Regression guards against loosening the design
# ---------------------------------------------------------------------------
def test_shrinking_skirt_fails_validation():
    m = make_model()
    m.env = EnvSpec(cap_skirt_length=4.0)
    m.recompute()
    assert any("skirt" in msg for _, msg in m.validate())


def test_removing_roof_pitch_fails_validation():
    m = make_model()
    m.env = EnvSpec(roof_height=0.0)
    m.recompute()
    assert any("pitch" in msg for _, msg in m.validate())


def test_short_feet_fail_validation():
    m = make_model()
    m.env = EnvSpec(foot_height=1.0)
    m.recompute()
    assert any("feet" in msg for _, msg in m.validate())


def test_undersized_chimney_column_fails_validation():
    m = make_model()
    m.env = EnvSpec(chimney_inner_r=7.0)
    m.recompute()
    assert any("heatsink" in msg for _, msg in m.validate())


# ---------------------------------------------------------------------------
# Primitive list integrity
# ---------------------------------------------------------------------------
def test_primitives_are_well_formed():
    m = make_model()
    prims = m.primitives()
    names = [p["name"] for p in prims]
    assert len(names) == len(set(names)), "primitive names must be unique"

    anchors: set = set()
    for p in prims:
        if p["op"].startswith("add_"):
            anchors.add(p["name"])
        elif p["op"].startswith("sub_"):
            assert p["target"] in anchors, (
                f"{p['name']} targets missing anchor {p['target']}")
        else:
            raise AssertionError(f"unknown op {p['op']!r}")


def test_reference_proxies_flagged():
    m = make_model()
    refs = [p for p in m.primitives() if p["part"] == "ref"]
    assert refs and all(p.get("reference") for p in refs)


def test_custom_specs_recompute_end_to_end():
    m = Model(board=BoardSpec(), camera=CameraSpec(), env=EnvSpec()).recompute()
    assert m.validate() == []