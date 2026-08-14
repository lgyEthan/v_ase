from pathlib import Path
import runpy

import numpy as np
import pytest
from ase.constraints import FixedLine, FixedPlane, Hookean
from ase.io import read
from ase.neighborlist import neighbor_list
from ase.units import Bohr
from PIL import Image

from examples.readme_scenes import (
    SCENE_NAMES,
    make_ai_pyridinic_graphene_scene,
    make_amorphous_cuzr_rdf_scene,
    make_atom_colorscale_trajectory,
    make_graphene_pi_volumetric_scene,
    make_black_phosphorene_unit_cell,
    make_copper_oxide_bond_scene,
    make_cu5o4_appearance_scene,
    make_crowded_c60_relaxation_scene,
    make_ferrocene_scene,
    make_material_preset_scene,
    make_layered_water_channel_scene,
    make_phosphorene_twist_scene,
    make_random_addition_scene,
    write_scene_assets,
)
from v_ase.io import atom_labels
from v_ase.analysis import calculate_rdf

ROOT = Path(__file__).resolve().parents[1]


def test_readme_scene_assets_write_reopenable_traj_files(tmp_path):
    written = write_scene_assets(tmp_path)
    written_names = {path.name for path in written}

    assert set(SCENE_NAMES) == {
        "add-atoms",
        "add-molecules",
        "phosphorene",
        "commensurate",
        "ai-edit",
        "bonding",
        "materials",
        "fixedline",
        "fixedplane",
        "hookean",
        "relaxation",
        "measurement",
        "ferrocene",
        "showcase",
    }
    assert "README.md" in written_names
    assert "graphene_hbn_commensurate.traj" in written_names
    assert "fixedline.traj" in written_names
    assert "fixedplane.traj" in written_names
    assert "hookean.traj" in written_names
    assert "ferrocene.traj" in written_names
    assert "showcase.traj" in written_names
    assert "phosphorene_nanosheet.cif" in written_names
    assert "phosphorene_twisted_nanoribbon_13p85deg.cif" in written_names
    assert "phosphorene_twist_13p85deg.traj" in written_names
    assert "crowded_c60_initial.cif" in written_names
    assert "crowded_c60_relaxed.cif" in written_names
    assert "crowded_c60_relaxation.traj" in written_names
    assert "ethane_measurement.cif" in written_names
    assert "ai_graphene_source.cif" in written_names
    assert "ai_pyridinic_n3_graphene.cif" in written_names
    assert "ai_pyridinic_n3_li_graphene.cif" in written_names
    assert "ai_pyridinic_n3_li_graphene.traj" in written_names
    assert "cu2o111_on_cu111_pairwise_bonds.traj" in written_names
    assert "material_presets.traj" in written_names
    assert "cu111_oxygen_add_atoms.traj" in written_names
    assert "layered_water_channel.traj" in written_names
    assert not any(path.name.endswith("_motion.traj") for path in written)

    fixedline = read(tmp_path / "fixedline.traj")
    fixedplane = read(tmp_path / "fixedplane.traj")
    hookean = read(tmp_path / "hookean.traj")
    showcase = read(tmp_path / "showcase.traj")
    phosphorene_frames = read(tmp_path / "phosphorene_twist_13p85deg.traj", index=":")

    assert any(isinstance(constraint, FixedLine) for constraint in fixedline.constraints)
    assert any(isinstance(constraint, FixedPlane) for constraint in fixedplane.constraints)
    assert any(isinstance(constraint, Hookean) for constraint in hookean.constraints)
    assert any(isinstance(constraint, Hookean) for constraint in showcase.constraints)
    assert len(phosphorene_frames) == 19
    assert all(
        frame.info["twist_target_degrees"] == pytest.approx(13.85)
        for frame in phosphorene_frames
    )


def test_phosphorene_scene_uses_published_cell_angle_and_single_puckered_ridges():
    unit = make_black_phosphorene_unit_cell()
    source, twisted, frames, metadata = make_phosphorene_twist_scene()

    assert unit.cell.lengths() == pytest.approx(
        [8.628 * Bohr, 6.243 * Bohr, 51.930 * Bohr],
        abs=1e-8,
    )
    assert len(source) == len(twisted) == 120
    assert len(frames) == 19
    assert metadata["axis"] == "X"
    assert metadata["ribbon_direction"] == "armchair"
    assert metadata["target_twist_degrees"] == pytest.approx(13.85)
    assert metadata["angle_increment_degrees"] == pytest.approx(13.85 / 9.0)
    assert metadata["ridge_count"] == 10
    assert len(metadata["selected_ridge"]) == 12
    assert len(metadata["operations"]) == 9
    assert [operation["ridge_start"] for operation in metadata["operations"]] == list(range(1, 10))
    assert [len(operation["selected_indices"]) for operation in metadata["operations"]] == [
        108, 96, 84, 72, 60, 48, 36, 24, 12,
    ]
    assert all(
        operation["angle_degrees"] == pytest.approx(13.85 / 9.0)
        for operation in metadata["operations"]
    )
    assert np.max(np.linalg.norm(twisted.positions - source.positions, axis=1)) > 1.0
    assert np.allclose(frames[0].positions, source.positions)
    assert np.allclose(frames[-1].positions, twisted.positions)
    assert set(atom_labels(source)) == {"P_upper", "P_lower"}
    assert metadata["sublayer_colors"] == {
        "P_upper": "#6faf68",
        "P_lower": "#8064a2",
    }

    ridge_ids = np.asarray(metadata["ridge_ids"])
    sublayer_ids = np.asarray(metadata["sublayer_ids"])
    assert np.bincount(ridge_ids).tolist() == [12] * 10
    assert [
        int(np.unique(sublayer_ids[ridge_ids == ridge_id]).item())
        for ridge_id in range(10)
    ] == [1, 0] * 5
    assert np.allclose(
        source.positions[ridge_ids == 0],
        twisted.positions[ridge_ids == 0],
    )
    last_ridge = np.flatnonzero(ridge_ids == 9)
    same_x = last_ridge[
        np.isclose(
            source.positions[last_ridge, 0],
            np.min(source.positions[last_ridge, 0]),
        )
    ]
    lower_y = same_x[np.argmin(source.positions[same_x, 1])]
    upper_y = same_x[np.argmax(source.positions[same_x, 1])]
    initial_vector = source.positions[upper_y, 1:3] - source.positions[lower_y, 1:3]
    final_vector = twisted.positions[upper_y, 1:3] - twisted.positions[lower_y, 1:3]
    accumulated_angle = np.degrees(np.arctan2(
        initial_vector[0] * final_vector[1] - initial_vector[1] * final_vector[0],
        np.dot(initial_vector, final_vector),
    ))
    assert accumulated_angle == pytest.approx(13.85, abs=1e-8)

    bond_i, bond_j = neighbor_list("ij", source, 2.45)
    unique_bonds = bond_i < bond_j
    bond_i, bond_j = bond_i[unique_bonds], bond_j[unique_bonds]
    initial_lengths = np.linalg.norm(
        source.positions[bond_j] - source.positions[bond_i],
        axis=1,
    )
    final_lengths = np.linalg.norm(
        twisted.positions[bond_j] - twisted.positions[bond_i],
        axis=1,
    )
    bond_strain_percent = 100.0 * (final_lengths / initial_lengths - 1.0)
    assert np.max(np.abs(bond_strain_percent)) < 10.1

    for operation_index in range(len(metadata["operations"])):
        start = frames[operation_index * 2].positions
        end = frames[(operation_index + 1) * 2].positions
        ridge_start = operation_index + 1
        frozen = ridge_ids < ridge_start
        moving = ridge_ids >= ridge_start
        assert np.allclose(start[frozen], end[frozen])
        assert np.max(np.linalg.norm(end[moving] - start[moving], axis=1)) > 0.01


def test_random_addition_readme_host_is_cu111_surface_and_reproducible():
    host, metadata = make_random_addition_scene()
    repeated, repeated_metadata = make_random_addition_scene()

    assert len(host) == 210
    assert host.pbc.tolist() == [True, True, False]
    assert abs(float(np.linalg.det(host.cell.array))) > 1.0
    assert set(atom_labels(host)) == {"Cu_surface"}
    assert metadata["entries"] == [
        {"element": "O", "label": "O_subsurface", "count": 18},
    ]
    assert metadata["seed"] == 2021
    assert metadata["coverage_monolayer"] == pytest.approx(18 / 42)
    assert metadata["surface_reference"] == (
        "https://doi.org/10.1016/S0039-6028(01)01464-9"
    )
    np.testing.assert_array_equal(host.positions, repeated.positions)
    assert metadata == repeated_metadata
    z_layers, layer_counts = np.unique(
        np.round(host.positions[:, 2], 8),
        return_counts=True,
    )
    assert len(z_layers) == 5
    assert layer_counts.tolist() == [42, 42, 42, 42, 42]
    allow = np.asarray(metadata["allow_region"]["bounds"], dtype=float)
    assert z_layers[0] < allow[4] < z_layers[1]
    assert z_layers[-2] < allow[5] < z_layers[-1]
    assert allow[5] - allow[4] > 3.0 * np.diff(z_layers).mean() - 1e-7
    assert "reject_region" not in metadata


def test_layered_water_channel_scene_is_periodic_graphene_oxide_with_exact_solvent_volume():
    host, metadata = make_layered_water_channel_scene()
    assert len(host) == 132
    assert host.pbc.tolist() == [True, True, True]
    assert set(atom_labels(host)) == {
        "C_GO_lower", "C_GO_upper",
        "O_GO_lower", "O_GO_upper",
        "H_GO_lower", "H_GO_upper",
    }
    assert host.get_chemical_formula() == "C84H24O24"
    assert metadata["interlayer_spacing_angstrom"] == pytest.approx(6.0)
    assert host.cell.lengths()[2] == pytest.approx(12.0)
    assert metadata["molecules"] == [{"name": "H2O", "label": "water", "count": 1}]
    assert metadata["target_density_g_cm3"] == pytest.approx(1.0)
    assert metadata["expected_molecule_count"] == 64
    assert [region["role"] for region in metadata["regions"]] == ["reject", "reject"]
    lower, upper = metadata["regions"]
    assert lower["bounds"][4:6] == pytest.approx([2.0, 4.0])
    assert upper["bounds"][4:6] == pytest.approx([8.0, 10.0])
    assert metadata["reject_region_thickness_angstrom"] == pytest.approx(2.0)
    assert metadata["left_chamber_width_angstrom"] == pytest.approx(5.15)
    assert metadata["right_chamber_width_angstrom"] == pytest.approx(5.15)
    assert lower["bounds"][0] > 0.0
    assert lower["bounds"][1] < host.cell.lengths()[0]
    assert metadata["edge_hydroxyls_per_layer"] == 6
    assert metadata["basal_hydroxyls_per_layer"] == 6
    assert metadata["accessible_volume_angstrom3"] == pytest.approx(1926.683435276361)
    assert metadata["actual_density_g_cm3"] == pytest.approx(0.9936947024274073)
    assert metadata["placement_mode"] == "random"
    assert metadata["coordinate_basis"] == "cartesian"

    for sites in metadata["basal_hydroxyl_sites"].values():
        sites = np.asarray(sites, dtype=float)
        assert len(sites) == 6
        assert np.ptp(sites[:, 0]) > 6.0
        assert len(np.unique(np.round(sites[:, 1], decimals=6))) >= 3

    layer_size = len(host) // 2
    carbon_count = 42
    hydroxyls_per_layer = 12
    for layer_index, layer_name in enumerate(("lower", "upper")):
        offset = layer_index * layer_size
        carbon_indices = metadata["hydroxyl_carbon_indices"][layer_name]
        assert len(carbon_indices) == hydroxyls_per_layer
        for hydroxyl_index, local_carbon in enumerate(carbon_indices):
            oxygen = offset + carbon_count + 2 * hydroxyl_index
            hydrogen = oxygen + 1
            carbon = offset + int(local_carbon)
            c_o = host.get_distance(carbon, oxygen, mic=True)
            o_h = host.get_distance(oxygen, hydrogen, mic=True)
            angle = host.get_angle(carbon, oxygen, hydrogen, mic=True)
            assert c_o == pytest.approx(1.36 if hydroxyl_index < 6 else 1.42)
            assert o_h == pytest.approx(0.97)
            assert angle == pytest.approx(np.degrees(np.arccos(-0.32)))


def test_cu5o4_appearance_scene_partitions_substrate_without_changing_elements():
    atoms, groups = make_cu5o4_appearance_scene()

    assert atoms.get_chemical_formula() == "Cu37O4"
    assert len(groups["substrate_copper"]) == 32
    assert len(groups["oxide_copper"]) == 5
    assert len(groups["oxide_oxygen"]) == 4
    assert all(atoms[index].symbol == "Cu" for index in groups["substrate_copper"])
    assert max(atoms.positions[groups["substrate_copper"], 2]) < 7.0
    assert min(atoms.positions[groups["oxide_copper"], 2]) >= 7.0


def test_atom_colorscale_readme_trajectory_colors_every_atom_with_matching_forces():
    frames = make_atom_colorscale_trajectory()
    assert len(frames) == 14
    assert all(len(frame) == 193 for frame in frames)
    assert all(frame.get_chemical_symbols().count("Cu") == 192 for frame in frames)
    assert all(frame.get_chemical_symbols().count("O") == 1 for frame in frames)
    assert all(frame.pbc.tolist() == [True, True, False] for frame in frames)

    surface_positions = frames[0].positions[:-1].copy()
    probe_positions = []
    all_norms = []
    for frame in frames:
        forces = frame.get_forces()
        force_norms = np.linalg.norm(forces, axis=1)
        assert np.count_nonzero(force_norms > 0.01) > 100
        assert force_norms.max() < 0.23
        assert force_norms[-1] == pytest.approx(0.0)
        np.testing.assert_allclose(frame.positions[:-1], surface_positions, atol=0.0)
        probe_positions.append(frame.positions[-1])
        all_norms.extend(np.linalg.norm(forces, axis=1))
        assert frame.info["force_model"] == "Gaussian-screened external probe field"
        assert frame.info["force_calculator"] == "analytic external field stored in SinglePointCalculator"
        assert frame.get_potential_energy() > 0
    assert np.ptp(np.asarray(probe_positions), axis=0).max() > 3.0
    assert np.ptp(all_norms) > 0.18

    capture = (ROOT / "scripts" / "capture_readme_screenshots.py").read_text()
    colorscale = capture.split("def capture_atom_colorscale_media", 1)[1].split(
        "def capture_rdf_media", 1
    )[0]
    assert "scope: 'all'" in colorscale
    assert "map: 'turbo'" in colorscale
    assert "193 / 193 atoms mapped" in colorscale
    assert "neighbour-shell force response" in colorscale
    assert "arg=len(frames[0])" in colorscale
    assert "duration=230" in colorscale


def test_relaxation_scene_is_an_actual_fire_trajectory_with_lower_repulsion():
    initial, relaxed, frames, metrics = make_crowded_c60_relaxation_scene()

    assert len(initial) == len(relaxed) == 60
    assert len(frames) >= 20
    assert metrics["final_energy"] < metrics["initial_energy"] * 0.01
    assert metrics["final_fmax"] < 0.05
    assert not np.allclose(initial.positions, relaxed.positions)


def test_ai_graphene_scene_is_generated_and_matches_the_n3_vacancy_edit():
    source, final, metadata = make_ai_pyridinic_graphene_scene()
    intermediate = metadata["intermediate"]

    assert len(source) == 72
    assert len(intermediate) == 71
    assert len(final) == 72
    assert source.get_chemical_formula() == "C72"
    assert final.get_chemical_symbols().count("N") == 3
    assert final.get_chemical_symbols().count("Li") == 1
    assert atom_labels(final).count("N_pyridinic") == 3
    assert atom_labels(final).count("Li_site") == 1
    assert final.positions[metadata["li_index"]] == pytest.approx(
        metadata["li_position"]
    )
    assert metadata["li_position"][2] - metadata["vacancy_position"][2] == pytest.approx(
        2.15
    )
    assert len(metadata["neighbors_before"]) == 3
    assert len(metadata["neighbors_after"]) == 3
    assert all(
        source.get_distance(
            metadata["vacancy_index"],
            index,
            mic=True,
        ) == pytest.approx(1.42028166, abs=1e-6)
        for index in metadata["neighbors_before"]
    )


def test_copper_oxide_bond_scene_is_coherent_cu2o111_on_cu111():
    atoms, groups = make_copper_oxide_bond_scene()

    assert len(groups["substrate_copper"]) == 196
    assert len(groups["oxide_copper"]) == 72
    assert len(groups["oxide_oxygen"]) == 36
    assert set(atom_labels(atoms)) == {
        "Cu_substrate",
        "Cu_oxide",
        "O_oxide",
    }
    assert set(atoms.get_chemical_symbols()) == {"Cu", "O"}
    assert atoms.get_chemical_formula() == "Cu268O36"
    assert atoms.info["in_plane_oxide_strain_percent"] == pytest.approx(
        -1.2202548,
        abs=1e-5,
    )
    assert len(groups["interfacial_oxygen"]) == 9
    assert len(groups["registry_anchor"]) == 2
    substrate_anchor, oxygen_anchor = groups["registry_anchor"]
    assert atoms.positions[oxygen_anchor, :2] == pytest.approx(
        atoms.positions[substrate_anchor, :2],
        abs=1e-10,
    )
    assert atoms.info["interface_anchor_lateral_distance_angstrom"] == pytest.approx(
        0.0,
        abs=1e-10,
    )
    assert "6x6 primitive Cu2O(111)" in atoms.info["model"]
    assert "top-anchored" in atoms.info["interface_registry"]
    assert "10.1021/acs.jpcc.0c04453" in " ".join(atoms.info["references"])

    primitive_surface_cell = np.array([
        atoms.cell[0, :2] / 7.0,
        atoms.cell[1, :2] / 7.0,
    ])
    interface_offsets = (
        atoms.positions[groups["interfacial_oxygen"], :2]
        - atoms.positions[oxygen_anchor, :2]
    )
    primitive_coordinates = np.linalg.solve(
        primitive_surface_cell.T,
        interface_offsets.T,
    ).T
    phase_coordinates = np.mod(
        np.round(primitive_coordinates, decimals=8),
        1.0,
    )
    phase_coordinates[np.isclose(phase_coordinates, 1.0)] = 0.0
    expected_phases = {
        (first, second)
        for first in (0.0, 1.0 / 3.0, 2.0 / 3.0)
        for second in (0.0, 1.0 / 3.0, 2.0 / 3.0)
    }
    assert {
        tuple(np.round(phase, decimals=6))
        for phase in phase_coordinates
    } == {
        tuple(np.round(phase, decimals=6))
        for phase in expected_phases
    }
    oxide_bonds = sum(
        np.count_nonzero(
            atoms.get_distances(index, groups["oxide_copper"], mic=True) < 2.08
        )
        for index in groups["oxide_oxygen"]
    )
    interface_bonds = sum(
        np.count_nonzero(
            atoms.get_distances(index, groups["substrate_copper"], mic=True) < 2.08
        )
        for index in groups["oxide_oxygen"]
    )
    assert oxide_bonds == 108
    assert interface_bonds == 7


def test_material_scene_keeps_elements_equal_while_labels_separate_presets():
    atoms, groups = make_material_preset_scene()

    assert len(atoms) == 39
    assert set(atoms.get_chemical_symbols()) == {"Cu"}
    assert list(groups) == ["Cu_standard", "Cu_metal", "Cu_rubber"]
    assert all(len(indices) == 13 for indices in groups.values())
    assert set(atom_labels(atoms)) == set(groups)


def test_analysis_examples_show_signed_isosurfaces_and_a_flat_amorphous_rdf_tail():
    molecule, values = make_graphene_pi_volumetric_scene()
    assert molecule.get_chemical_formula() == "C24"
    assert set(atom_labels(molecule)) == {"C_pi_A", "C_pi_B"}
    assert values.dtype == np.float32
    assert values.shape == (104, 104, 104)
    assert float(values.min()) < 0 < float(values.max())
    assert float(values.max()) == pytest.approx(-float(values.min()), rel=1e-6)

    amorphous = make_amorphous_cuzr_rdf_scene()
    assert len(amorphous) == 900
    assert np.all(amorphous.pbc)
    assert set(atom_labels(amorphous)) == {"Cu_glass", "Zr_glass"}
    result = calculate_rdf(
        amorphous,
        cutoff=11.0,
        bins=180,
        pair_mode="none",
    )
    tail = result.total[result.radius > 7.0]
    assert np.mean(tail) == pytest.approx(1.0, abs=0.05)
    assert np.std(tail) < 0.08
    assert result.total.max() > 1.4


def test_brand_logo_is_native_high_resolution_transparent_png():
    docs_logo = ROOT / "docs" / "assets" / "v_ase-logo.png"
    static_logo = ROOT / "v_ase" / "static" / "v_ase-logo.png"

    assert docs_logo.read_bytes() == static_logo.read_bytes()
    with Image.open(docs_logo) as image:
        assert image.size == (6144, 1890)
        assert image.mode == "RGBA"
        assert image.getchannel("A").getextrema() == (0, 255)
        alpha = np.asarray(image.getchannel("A"))
        partial_alpha = np.count_nonzero((alpha > 8) & (alpha < 247))
        opaque_alpha = np.count_nonzero(alpha >= 247)
        assert partial_alpha / opaque_alpha < 0.05


def test_brand_logo_generation_uses_approved_palette_and_separated_letter_atoms():
    source = (ROOT / "scripts" / "capture_readme_screenshots.py").read_text()
    assert 'LOGO_SUBSTRATE_COLOR", "#71493f"' in source
    assert 'LOGO_LETTER_COLOR", "#d7f26f"' in source
    assert 'LOGO_LETTER_RADIUS", "0.67"' in source
    assert "def sync_github_readme_assets()" in source
    assert "shutil.copy2(source, github_dir / source.name)" in source


def test_readme_presents_real_manipulation_and_analysis_workflows():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    structure = readme.index("## Edit Structures")
    select = readme.index("### Select", structure)
    move = readme.index("### Move", select)
    add_atoms = readme.index("### Add Atoms", move)
    rotate = readme.index("### Rotate Selected Atoms", add_atoms)
    ferrocene = readme.index("#### Ferrocene: Use Fe As The Active Pivot", rotate)
    phosphorene = readme.index("#### Phosphorene: Build The Twist One Edit At A Time", ferrocene)
    periodic = readme.index("## Periodic Cells And Interfaces", phosphorene)
    commensurate = readme.index(
        "### Commensurate Atoms: Match Periodic 2D Cells",
        periodic,
    )
    measurement = readme.index("## Analyze Structures And Fields", commensurate)
    ai = readme.index("## Work With An AI Agent", measurement)

    assert structure < select < move < add_atoms < rotate < ferrocene < phosphorene
    assert "#### Add Molecules" in readme[add_atoms:rotate]
    assert "Available Since" not in readme[add_atoms:rotate]
    assert phosphorene < periodic < commensurate < measurement < ai
    normalized_readme = " ".join(
        line.lstrip("> ").strip() for line in readme.lower().splitlines()
    )
    assert "from pristine 6 × 6 graphene, create a pyridinic n3 vacancy" in normalized_readme
    assert "`N_pyridinic`" in readme
    assert "`Li_site`" in readme
    assert "Li 2.15 Å" in readme
    assert "render a 4K +Z view with +Y up" in readme
    assert "1." in readme[ai:]
    assert "2." in readme[ai:]
    assert "3." in readme[ai:]
    assert "external ai agent" in normalized_readme
    assert "same document stays open in one live gui" in normalized_readme
    assert "does not contain an llm or interpret natural language" in normalized_readme
    assert "structured cli/api" in normalized_readme
    assert "a manual gui edit becomes the next document revision" in normalized_readme
    assert "reduce repeated image interpretation" in normalized_readme
    assert "Standard Metal and Rubber atom materials" in readme
    assert "Cu_substrate-Cu_substrate" in readme
    assert "Cu_oxide-O_oxide" in readme
    assert "Materials affect rendering only." in readme
    assert "reaches 100% once" in readme
    assert "structure and visualization-setting changes" in readme
    assert "camera navigation is excluded" in readme
    assert "Try the exact assets" not in readme
    assert "playback of a finished model" not in readme
    assert "long sequence of repetitive steps" not in readme
    assert "production `left-drag`" not in readme
    assert "visible amber box" in readme
    assert "from the **second ridge through the end**" in normalized_readme
    assert "from the **third ridge through the end**" in normalized_readme
    assert "**Rotate Selection**" in readme
    assert "**Active atom (last selected)**" in readme
    assert "Shift-select Fe last" in readme
    assert "`5 x 6` model contains 10 puckered ridges" in readme
    assert "12 atoms per ridge" in normalized_readme
    assert "backend commits" not in readme
    assert "final ridge is rotated by exactly 13.85 degrees" in readme
    assert "from above to below" in normalized_readme
    assert "green and purple distinguish" in normalized_readme
    assert "the upper and lower p sublayers" in normalized_readme
    assert "`6 x 6 Cu2O(111)` film on `7 x 7 Cu(111)`" in readme
    assert "substrate Cu top site" in readme
    assert "in-plane compression" not in readme
    assert "10.1021/acs.jpcc.0c04453" not in readme
    assert "**Axes** and **Unit Cell** switches update the working viewport" in readme
    assert "**Field smearing σ**" in readme
    assert "**Mesh smoothing passes**" in readme
    assert "source scalar field" in readme
    assert "eighteen `o_subsurface` atoms start" in normalized_readme
    assert "three bulk-like interior layers" in normalized_readme
    assert "entering `o` chooses oxygen immediately" in normalized_readme
    assert "Cu(111)/O placement example" in readme
    assert "separate Reject-region example" not in readme
    assert "half-open primary periodic cell" in readme
    assert "every pre-existing coordinate, array" in readme
    assert "ASE G2" in readme
    assert "Randomize molecular orientation" in readme
    assert "Preserve molecular geometry" in readme
    assert "native coordinate origin" in readme
    assert "64 rigid h2o molecules" in normalized_readme
    assert "1926.683 å³" in normalized_readme
    assert "`2 å`-thick" in normalized_readme
    assert "distinct left and right solvent chambers" in normalized_readme
    assert "viewport box-selection around the 32 substrate cu atoms" in normalized_readme
    assert "rectangular graphene `(√7 × √21) R±19.11°` host" in readme
    assert "MoS2 `2 × 2` guest" in readme
    assert "192-atom Cu(111) slab" in readme
    assert "second, and third lateral neighbor shells" in readme
    assert "one complete\n  `AdditionRepulsionCalculator`" in readme
    assert "every FIRE optimizer step" in readme

    for filename in (
        "readme_phosphorene_twist.gif",
        "readme_ferrocene_pivot.gif",
        "readme_commensurate.gif",
        "readme_ai_edit.gif",
        "readme_ai_collaboration.gif",
        "readme_ai_collaboration.png",
        "readme_ai_collaboration_live.png",
        "readme_materials.png",
        "readme_measurement.gif",
        "readme_displacement.png",
        "readme_volumetric.png",
        "readme_rdf.png",
        "readme_add_atoms.gif",
        "readme_add_atoms_allowed.gif",
        "readme_add_atoms.png",
        "readme_add_molecules.gif",
        "readme_add_molecules.png",
        "readme_cu5o4_view_appearance.gif",
        "readme_cu5o4_view_appearance.png",
        "readme_commensurate_host_guest.gif",
    ):
        assert (ROOT / "docs" / "assets" / filename).is_file()
        assert (ROOT / "docs" / "assets" / "github" / filename).is_file()

    with Image.open(ROOT / "docs" / "assets" / "readme_ai_collaboration.png") as figure:
        assert figure.size == (1800, 1080)

    figure_source = (
        ROOT / "docs" / "design" / "ai_collaboration_figure.html"
    ).read_text(encoding="utf-8")
    for required in (
        "You direct the work. The AI Agent operates v_ase. The GUI stays live.",
        '<div class="actor-kicker">Human</div><h2>You</h2>',
        '<div class="actor-kicker">Interprets the request</div><h2>AI Agent</h2>',
        '<div class="actor-kicker">One shared structure</div><h2>Live v_ase GUI</h2>',
        "Natural language",
        ">CLI<",
        ">GUI<",
        "Natural-language intent",
        "CLI operations",
        "agent-reply",
        "human-edit",
        "element-legend",
        "natural-reply",
        "from +Z with +Y up",
        "delete 42 · 29,41,30 → N",
        "add Li · z = center + 2.15 Å",
        "view +Z · screen up +Y",
        "You refine the result directly in the GUI",
        "GUI revision received · radius 0.64 · bond 0.20 Å",
    ):
        assert required in figure_source
    assert figure_source.count('class="flow-path ') == 6
    for flow in ("natural", "cli", "gui"):
        assert f'class="channel-label label-{flow}"' in figure_source
        assert figure_source.count(f'class="flow-path channel-{flow}"') == 2
        assert f'marker-end="url(#arrow-{flow})"' in figure_source
    assert 'class="vase-logo"' in figure_source
    assert "LIVE FEEDBACK LOOP" not in figure_source
    assert 'class="feedback"' not in figure_source


def test_phosphorene_capture_drives_the_production_selection_and_rotation_ui():
    source = (ROOT / "scripts" / "capture_readme_screenshots.py").read_text()

    assert "page.mouse.down(button=\"left\")" in source
    assert "page.mouse.move(" in source
    assert "page.mouse.up(button=\"left\")" in source
    assert "selected != expected" in source


def test_full_readme_capture_does_not_repeat_the_analysis_group():
    source = (ROOT / "scripts" / "capture_readme_screenshots.py").read_text()
    default_capture = source.split("if args.only:", 1)[1].split(
        "finally:", 1
    )[0]

    assert 'for name, capture in captures.items()' in default_capture
    assert 'if name == "analysis":' in default_capture
    assert "continue" in default_capture
    assert 'page.select_option("#selection-rotate-axis", "X")' in source
    assert 'page.locator("#selection-rotate-angle")' in source
    assert 'page.locator("#btn-rotate-selection-exact")' in source
    assert "detailed = operation_index < 2" in source
    assert "np.allclose(actual_positions, twisted.positions" in source


def test_ai_collaboration_recording_is_self_contained_and_controllable(tmp_path):
    from playwright.sync_api import sync_playwright

    capture = runpy.run_path(str(ROOT / "scripts/capture_readme_screenshots.py"))
    write_ai_collaboration_recording_html = capture[
        "write_ai_collaboration_recording_html"
    ]

    source = """<!doctype html>
<html><body data-flow="request">
<img id="gui-image" src="../assets/readme_ai_collaboration_live.png">
<div id="operation"></div>
<script>
window.setCollaborationStage = async record => {
  document.body.dataset.flow = record.flow;
  document.getElementById('operation').textContent = record.operation;
  if (record.image) document.getElementById('gui-image').src = record.image;
};
</script>
</body></html>"""
    pixel = (
        "data:image/gif;base64,"
        "R0lGODlhAQABAIAAAAAAAP///ywAAAAAAQABAAACAUwAOw=="
    )
    records = [
        {"stage": "human", "flow": "request", "operation": "request", "image": pixel},
        {"stage": "agent", "flow": "command", "operation": "apply", "image": pixel},
    ]
    output = tmp_path / "recording.html"
    write_ai_collaboration_recording_html(source, records, output)
    html = output.read_text(encoding="utf-8")

    assert "../assets/" not in html
    assert 'id="v-ase-collaboration-records"' in html
    assert "window.v_aseCollaborationRecording" in html
    assert "event.code === 'Space'" in html
    assert "event.key.toLowerCase() === 'r'" in html
    assert html.count(pixel) == 3

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 900, "height": 540})
        requests = []
        page.on("request", lambda request: requests.append(request.url))
        page.goto(output.as_uri(), wait_until="load")
        page.wait_for_function("window.v_aseCollaborationRecording?.records.length === 2")
        page.wait_for_function("document.documentElement.dataset.recordingStage === '1'")
        assert page.locator("#operation").inner_text() == "request"
        assert requests == [output.as_uri()]

        page.keyboard.press("Space")
        assert page.evaluate("window.v_aseCollaborationRecording.playing") is False
        paused_index = page.evaluate("window.v_aseCollaborationRecording.index")
        page.wait_for_timeout(1900)
        assert page.evaluate("window.v_aseCollaborationRecording.index") == paused_index

        page.keyboard.press("Space")
        page.wait_for_function("window.v_aseCollaborationRecording.index === 1")
        page.keyboard.press("r")
        page.wait_for_function("window.v_aseCollaborationRecording.index === 0")
        assert page.evaluate("window.v_aseCollaborationRecording.playing") is True
        browser.close()


def test_add_atoms_capture_uses_the_real_batch_workspace_and_optimizer():
    source = (ROOT / "scripts" / "capture_readme_screenshots.py").read_text()
    capture = source.split("def _capture_add_atoms_variant", 1)[1].split(
        "def capture_measurement_media", 1
    )[0]

    assert 'page.click("#btn-create-atom-toggle")' in capture
    assert 'page.click("#add-atoms-tab-batch")' in capture
    assert 'page.click("#btn-add-atoms-scatter")' in capture
    assert 'page.click("#btn-add-atoms-relax")' in capture
    assert 'page.select_option("#add-atoms-device", "cpu")' in capture
    assert 'page.select_option("#add-atoms-cpus"' in capture
    assert 'page.click("#btn-add-atoms-finish")' in capture
    assert "renderer.addAtomsRegionGroup.visible === true" in capture
    assert "renderer.addAtomsRegionGroup.visible === false" in capture
    assert "np.testing.assert_array_equal" in capture
    assert "relaxed_positions[: len(host)]" in capture
    assert 'page.click(f"#btn-add-atoms-{role}-region")' in source
    assert "#add-atoms-region-list .add-atoms-region-item" in source
    assert 'gif_name="readme_add_atoms_allowed.gif"' in capture
    assert 'gif_name="readme_add_atoms_prohibited.gif"' not in capture
    assert "_capture_add_molecules_media(browser)" in capture
    molecule_capture = source.split("def _capture_add_molecules_media", 1)[1].split(
        "def capture_measurement_media", 1
    )[0]
    assert 'page.click("#add-atoms-content-molecules")' in molecule_capture
    assert 'page.click("#add-molecules-quantity-density")' in molecule_capture
    assert 'metadata["regions"]' in molecule_capture
    assert 'metadata["accessible_volume_angstrom3"]' in molecule_capture
    assert 'metadata["expected_molecule_count"]' in molecule_capture
    assert '["reject", "reject"]' in molecule_capture
    assert "target density 1.00 g/cm³" in molecule_capture
    assert 'page.click("#add-atoms-placement-random")' in molecule_capture
    assert 'page.locator("#add-molecules-random-orientation").set_checked(True)' in molecule_capture
    assert 'page.locator("#add-molecules-rigid").set_checked(True)' in molecule_capture
    assert "reference_distances" in molecule_capture
    assert 'ASSET_DIR / "readme_add_molecules.gif"' in molecule_capture
    assert "6 Å periodic channels" in molecule_capture
    assert "GO plane · 2 Å" in molecule_capture
    assert 'metadata["expected_molecule_count"]' in molecule_capture


def test_readme_ferrocene_and_copper_bond_media_use_documented_visual_controls():
    source = (ROOT / "scripts" / "capture_readme_screenshots.py").read_text()
    _, ferrocene_groups = make_ferrocene_scene()

    assert ferrocene_groups["iron"] == [0]
    assert 'pivot_mode="active"' in source
    assert 'pivot_index=indices["iron"][0]' in source
    assert '"1/2 | active pivot: Fe #0 | R Z"' in source
    assert '"2/2 | active pivot: Fe #0 | R X ring fold"' in source
    assert '"bondThickness": 0.30' in source
    assert '"bondColorMode": "split"' in source
    assert '"Cu_substrate": "#744637"' in source
    assert '"Cu_oxide": "#efb34f"' in source
    assert '"O_oxide": "#df2935"' in source
    assert '"Cu_substrate": "metal"' in source
    assert '"Cu_oxide": "standard"' in source
    assert '"O_oxide": "rubber"' in source
    assert "1 · BOX-SELECT SUBSTRATE" in source
    assert 'page.mouse.down(button="left")' in source
    assert 'page.mouse.up(button="left")' in source
    assert 'page.fill("#selected-atom-label", "Cu_substrate")' in source
    assert 'page.select_option("#selected-atom-material", "metal")' in source
    assert '.label-radius-input[data-atom-label="Cu_substrate"]' in source
    assert '.label-color-input[data-atom-label="Cu_substrate"]' in source


def test_readme_volumetric_media_uses_refined_isosurface_controls():
    source = (ROOT / "scripts" / "capture_readme_screenshots.py").read_text()
    volumetric = source.split("def capture_volumetric_media", 1)[1].split(
        "def capture_atom_colorscale_media", 1
    )[0]
    assert '"smearingSigma": 0.45' in volumetric
    assert '"smoothingIterations": 7' in volumetric
    assert "run_external_ai_apply" in volumetric
    assert "document.getElementById('volume-smearing')?.value" in source
    assert "document.getElementById('volume-smoothing')?.value" in source
    assert "#176f8c" not in source

    image = np.asarray(
        Image.open(ROOT / "docs" / "assets" / "readme_bonds.png").convert("RGB")
    )[60:, :1360]
    oxide_red = (
        (image[:, :, 0] > 150)
        & (image[:, :, 1] < 100)
        & (image[:, :, 2] < 110)
    )
    warm_oxide_copper = (
        (image[:, :, 0] > 170)
        & (image[:, :, 1] > 95)
        & (image[:, :, 1] < 190)
        & (image[:, :, 2] < 100)
    )
    dark_metallic_copper = (
        (image[:, :, 0] > 55)
        & (image[:, :, 0] < 155)
        & (image[:, :, 1] > 25)
        & (image[:, :, 1] < 105)
        & (image[:, :, 2] < 90)
    )
    assert int(oxide_red.sum()) > 1_500
    assert int(warm_oxide_copper.sum()) > 7_500
    assert int(dark_metallic_copper.sum()) > 30_000
