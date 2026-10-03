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
    # 72 + 2*0.6 inner + 2*2.0 wall
    assert m.inner_l == 73.2
    assert m.inner_w == 22.2
    assert m.outer_l == 77.2
    assert m.outer_w == 26.2


def test_z_stack_ordering():
    m = make_model()
    zs = [
        m.floor_top,
        m.pcb_bottom,
        m.pcb_top,
        m.interior_ceiling,
        m.cover_top,
        m.stack_z0,
        m.stack_z1,
    ]
    # cover_top and stack_z0 coincide by design (the stack sits on the cover).
    assert all(zs[i] <= zs[i + 1] for i in range(len(zs) - 1)), zs


# ---------------------------------------------------------------------------
# Fit checks
# ---------------------------------------------------------------------------
def test_pcb_fits_with_clearance():
    m = make_model()
    eps = 1e-6
    assert m.inner_l - m.board.pcb_length >= 2 * m.env.clearance - eps
    assert m.inner_w - m.board.pcb_width >= 2 * m.env.clearance - eps
    # tallest component (RJ45 cage) clears the interior ceiling
    assert m.interior_ceiling - m.pcb_top >= m.board.rj45_height


def test_heatsink_fits_chimney_aperture():
    m = make_model()
    assert m.e_aperture() - m.board.heatsink_width >= 2.0
    assert m.stack_z1 - m.stack_z0 > m.board.heatsink_height


def test_lens_and_ffc_pass_throughs():
    m = make_model()
    assert m.e_lens_port_dia() > m.camera.lens_diameter
    fw, ft = m.e_ffc_slot()[:2]
    assert fw > m.camera.ffc_width
    assert ft > m.camera.ffc_thickness


# ---------------------------------------------------------------------------
# Weather-proofing invariants
# ---------------------------------------------------------------------------
def test_exhaust_slots_shielded_by_cap_skirt():
    m = make_model()
    # The skirt must drop below the top of the exhaust openings so the air
    # path turns downward before reaching open air.
    assert m.skirt_z0 <= m.exhaust_z0
    # There must be an annular gap between stack and skirt for the air to flow.
    assert m.skirt_inner > m.stack_outer
    # The skirt is at least as long as the exhaust opening is tall.
    assert (m.skirt_z1 - m.skirt_z0) >= (m.exhaust_z1 - m.exhaust_z0)


def test_rain_cap_pitches_water():
    m = make_model()
    assert m.env.roof_rise > 0
    # Eave overhang covers the stack.
    assert m.cap_outer >= m.stack_outer + 2 * m.env.cap_overhang


def test_intakes_face_downward_below_pcb():
    m = make_model()
    # Intake slots are cut through the floor (z 0..floor) and therefore open
    # downward; their top edge stays beneath the PCB stand-off plenum.
    assert m.e_intake_top() <= m.pcb_bottom
    assert m.env.foot_height >= 2.0
    # Slots must not break out of the inner envelope.
    assert m.env.intake_slot_length <= m.inner_l - 4 * m.env.wall


def test_chimney_within_cover_plan():
    m = make_model()
    assert m.e_chimney_max_x() <= m.outer_l / 2
    assert m.stack_outer / 2 <= m.outer_w / 2


def test_rj45_port_within_interior():
    m = make_model()
    assert m.rj45_port_z1 <= m.interior_ceiling
    assert m.rj45_port_z0 >= m.floor_top
    assert m.rj45_port_w >= m.board.rj45_width + 2 * m.env.rj45_port_margin


def test_minimalist_footprint():
    m = make_model()
    assert m.outer_l <= 85.0
    assert m.outer_w <= 32.0
    assert m.roof_apex_z <= 55.0


# ---------------------------------------------------------------------------
# Regression guards against loosening the weather-proofing
# ---------------------------------------------------------------------------
def test_shrinking_skirt_fails_validation():
    m = make_model()
    m.env = EnvSpec(cap_skirt_length=4.0)
    m.recompute()
    assert any("skirt" in msg for _, msg in m.validate())


def test_removing_roof_pitch_fails_validation():
    m = make_model()
    m.env = EnvSpec(roof_rise=0.0)
    m.recompute()
    assert any("pitch" in msg for _, msg in m.validate())


def test_short_feet_fail_validation():
    m = make_model()
    m.env = EnvSpec(foot_height=1.0)
    m.recompute()
    assert any("feet" in msg for _, msg in m.validate())


# ---------------------------------------------------------------------------
# Primitive list integrity
# ---------------------------------------------------------------------------
def test_primitives_are_well_formed():
    m = make_model()
    prims = m.primitives()
    names = [p["name"] for p in prims]
    assert len(names) == len(set(names)), "primitive names must be unique"

    # Every subtract op must reference an anchor that is added earlier.
    anchors: set = set()
    for p in prims:
        if p["op"].startswith("add_"):
            anchors.add(p["name"])
        elif p["op"].startswith("sub_"):
            assert p["target"] in anchors, (
                f"{p['name']} targets missing anchor {p['target']}"
            )
        else:
            raise AssertionError(f"unknown op {p['op']!r}")


def test_reference_proxies_flagged():
    m = make_model()
    refs = [p for p in m.primitives() if p["part"] == "ref"]
    assert refs and all(p.get("reference") for p in refs)


def test_custom_specs_recompute_end_to_end():
    m = Model(
        board=BoardSpec(pcb_length=72.0, pcb_width=21.0),
        camera=CameraSpec(),
        env=EnvSpec(),
    ).recompute()
    assert m.validate() == []