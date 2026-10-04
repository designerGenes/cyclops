"""Host-side tests for the top-hood camera enclosure geometry."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from enclosure_geometry import BoardSpec, CameraSpec, EnvSpec, Model  # noqa: E402


def model_with(env=None) -> Model:
    return Model(env=env or EnvSpec()).recompute()


def test_default_design_validates():
    assert model_with().validate() == []


def test_broad_rounded_body_contains_board_and_camera_module():
    m = model_with()
    assert m.env.body_width == 58.0
    assert m.env.body_length == 110.0
    assert m.inner_length >= m.board.pcb_length + 2 * m.env.wall
    assert m.inner_width >= m.board.pcb_width + 2 * m.env.wall
    assert m.env.body_width - 2 * m.env.corner_radius >= m.env.window_width
    assert m.env.window_width >= m.camera.lens_diameter + 4.0
    assert m.env.window_height >= m.camera.lens_diameter + 2.0


def test_body_uses_rounded_rectangle_not_pill_or_bulb():
    m = model_with()
    assert m.env.corner_radius < m.env.body_width / 2
    assert m.env.corner_radius <= 12.0
    # Flat front fascia remains wide enough for the optical window.
    assert m.env.body_width - 2 * m.env.corner_radius > m.env.window_width


def test_window_is_recessed_inside_front_face():
    m = model_with()
    assert m.window_x + m.env.window_recess / 2 < m.half_x
    assert m.window_z0 >= m.env.floor
    assert m.window_z1 <= m.interior_ceiling
    assert m.window_y0 > -m.half_y
    assert m.window_y1 < m.half_y
    assert m.lens_port_diameter > m.camera.lens_diameter
    assert m.env.lens_z - (m.env.window_height - 0.4) / 2 >= m.env.seam_z


def test_sc3336_board_fits_internal_height_and_width():
    m = model_with()
    assert m.camera.module_width <= m.inner_width
    assert m.env.lens_z - m.camera.module_height / 2 >= m.env.floor
    assert m.env.lens_z + m.camera.module_height / 2 <= m.interior_ceiling


def test_no_bulbous_camera_barrel_or_chimney_parts():
    m = model_with()
    parts = {p["part"] for p in m.primitives()}
    assert "nose" not in parts
    assert "chimney" not in parts
    # The M12 optical axis stays behind the fascia; no projecting lens part is
    # emitted at all, only a recessed glass panel and a reference lens proxy.
    assert "window" in parts
    assert all(p["part"] != "nose" for p in m.primitives())


def test_visible_m12_optics_stay_recessed_inside_body_envelope():
    m = model_with()
    bezel = next(p for p in m.primitives() if p["name"] == "M12_Lens_Bezel")
    lens = next(p for p in m.primitives() if p["name"] == "M12_Lens_Element")
    assert bezel["part"] == lens["part"] == "window"
    assert bezel["center"][0] + bezel["depth"] / 2 < m.half_x
    assert lens["center"][0] + lens["depth"] / 2 < m.half_x
    assert 2 * bezel["r_outer"] < m.env.body_width


def test_thermal_insert_stays_inside_body_plan():
    m = model_with()
    assert m.board.soc_x + m.env.thermal_flange_length / 2 < m.half_x
    assert m.env.thermal_flange_width < m.env.body_width


def test_top_canopy_shades_window_and_has_eaves():
    m = model_with()
    assert m.hood_x_max > m.half_x
    assert m.hood_x_max - m.half_x >= m.env.hood_front_overhang - 1e-6
    assert m.hood_width > m.env.body_width
    assert m.hood_bottom - m.cover_top >= 5.0
    assert m.env.hood_slope_x < 0  # drains toward the front drip lip


def test_canopy_posts_fit_body_roof():
    m = model_with()
    assert m.hood_post_x < m.half_x - m.env.wall
    assert m.hood_post_y < m.half_y - m.env.wall
    assert m.env.hood_post_radius > 0


def test_optical_window_and_drain_channels_do_not_collide():
    m = model_with()
    outside_window = m.env.window_width / 2
    channel_inner = m.env.face_channel_y - m.env.face_channel_width / 2
    assert channel_inner > outside_window
    assert m.env.face_channel_y + m.env.face_channel_width / 2 < (
        m.half_y - m.env.corner_radius)


def test_thermal_insert_bridges_soc_to_roof_and_fits_under_canopy():
    m = model_with()
    sink_top = m.pcb_top + 1.2 + m.board.heatsink_height
    assert m.env.thermal_stem_bottom >= sink_top
    assert m.env.thermal_stem_bottom - sink_top < 1.0  # TIM interface allowance
    assert m.thermal_fin_top < m.hood_bottom
    assert m.hood_bottom - m.thermal_fin_top > 1.0
    assert m.env.thermal_port_width < m.env.thermal_flange_width
    assert m.env.thermal_port_length < m.env.thermal_flange_length


def test_metal_seal_surrounds_thermal_port():
    m = model_with()
    assert m.thermal_seal_outer_width > m.thermal_seal_inner_width
    assert m.thermal_seal_outer_length > m.thermal_seal_inner_length
    assert m.thermal_seal_inner_width > m.env.thermal_port_width
    assert m.thermal_seal_inner_length > m.env.thermal_port_length


def test_gasket_path_follows_rounded_shell_seam():
    m = model_with()
    assert m.seam_path_length < m.env.body_length
    assert m.seam_path_width < m.env.body_width
    assert m.seam_path_radius > 0
    assert m.env.gasket_depth > 0


def test_rj45_port_remains_within_shell_and_clears_cage():
    m = model_with()
    assert m.rj45_port_width > m.board.rj45_width
    assert m.rj45_port_z0 >= m.env.floor
    assert m.rj45_port_z1 <= m.interior_ceiling
    assert m.interior_ceiling - m.pcb_top >= m.board.rj45_height


def test_primitive_names_are_unique_and_boolean_targets_exist():
    m = model_with()
    primitives = m.primitives()
    names = [p["name"] for p in primitives]
    assert len(names) == len(set(names))
    anchors = set()
    for primitive in primitives:
        if primitive["op"].startswith("add_"):
            anchors.add(primitive["name"])
        elif primitive["op"].startswith("sub_"):
            assert primitive["target"] in anchors, primitive
        else:
            raise AssertionError(primitive["op"])


def test_hardware_proxies_are_not_case_solids():
    m = model_with()
    refs = [p for p in m.primitives() if p["part"] == "ref"]
    assert refs
    assert all(p.get("reference") for p in refs)
    assert any(p["name"] == "RV1106_Heatsink_Proxy" for p in refs)
    assert any(p["name"] == "SC3336_Board_Proxy" for p in refs)


def test_small_canopy_gap_is_rejected():
    issues = model_with(EnvSpec(hood_gap=3.0)).validate()
    assert any("airflow gap" in message for _, message in issues)


def test_undersized_window_is_rejected():
    issues = model_with(EnvSpec(window_width=16.0)).validate()
    assert any("insufficient margin around the lens" in message for _, message in issues)


def test_seam_through_optical_panel_is_rejected():
    issues = model_with(EnvSpec(seam_z=12.0)).validate()
    assert any("seam crosses the optical panel" in message for _, message in issues)


def test_camera_module_too_tall_for_shell_is_rejected():
    issues = model_with(EnvSpec(body_height=28.0)).validate()
    assert any("SC3336 board height" in message for _, message in issues)


def test_undersized_thermal_flange_is_rejected():
    issues = model_with(EnvSpec(thermal_flange_width=18.0,
                                thermal_flange_length=18.0)).validate()
    assert any("flange does not overlap" in message for _, message in issues)


def test_unpitched_hood_is_rejected():
    issues = model_with(EnvSpec(hood_slope_x=0.0)).validate()
    assert any("pitch toward" in message for _, message in issues)


def test_default_board_and_camera_specs_are_supported():
    m = Model(board=BoardSpec(), camera=CameraSpec(), env=EnvSpec()).recompute()
    assert m.validate() == []
