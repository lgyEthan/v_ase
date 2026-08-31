import builtins
import json
from pathlib import Path
import zipfile

from ase import Atoms
import pytest

from v_ase.export import (
    OptionalExportDependencyError,
    _cad_scene_data,
    export_3dm_response,
    export_obj_response,
)
from v_ase.io import set_atom_labels
from v_ase.session import EditorSession


def cad_session():
    atoms = Atoms(
        "OH2",
        positions=[[0.0, 0.0, 0.0], [0.96, 0.0, 0.0], [-0.24, 0.93, 0.0]],
        cell=[[4.0, 0.0, 0.0], [0.5, 4.2, 0.0], [0.0, 0.0, 5.0]],
        pbc=True,
    )
    set_atom_labels(atoms, ["O_surface", "H_water", "H_water"])
    return EditorSession("cad-export-test", atoms.copy(), atoms.copy())


def cad_payload():
    return {
        "display": {
            "showBonds": True,
            "showCell": True,
            "supercell": [2, 1, 1],
            "bondColorMode": "split",
            "bondStyle": "cylinder",
            "bondThickness": 0.12,
            "pairwiseBondStyles": {
                "H_water-O_surface": {
                    "style": "cylinder",
                    "material": "metal",
                    "thickness": 0.18,
                    "colorMode": "split",
                    "color": "#c8ccd0",
                    "opacity": 0.8,
                }
            },
            "atomRadiusScale": 1.1,
            "labelColors": {"O_surface": "#12ab34"},
            "labelRadii": {"O_surface": 0.72},
            "labelOpacities": {"O_surface": 0.35},
            "labelMaterials": {"O_surface": "metal", "H_water": "standard"},
            "atomRadiusScales": {"1": 1.5},
            "atomColors": {"1": "#4455aa"},
            "atomOpacities": {"1": 0.6},
            "atomMaterials": {"1": "rubber"},
            "atomBondStyles": {"1": {"material": "rubber", "opacity": 0.4}},
        },
        "bond_pairs": [[0, 1], [0, 2]],
        "camera": {
            "position": [5.0, -6.0, 4.0],
            "target": [1.0, 0.5, 0.25],
            "up": [0.0, 0.0, 1.0],
            "projection": "orthographic",
            "ortho_scale": 8.0,
            "aspect": 1.5,
            "near": 0.1,
            "far": 100.0,
        },
        "include_cell": True,
    }


def test_cad_scene_preserves_display_overrides_supercell_and_bridge_bonds():
    session = cad_session()
    payload = cad_payload()
    payload["bond_bridges"] = [{"i": 0, "j": 1, "imageOffset": [1, 0, 0]}]
    scene = _cad_scene_data(session, payload)

    assert scene["units"] == "angstrom"
    assert scene["repetitions"] == [2, 1, 1]
    assert len(scene["atoms"]) == 6
    oxygen = [item for item in scene["atoms"] if item["label"] == "O_surface"]
    assert len(oxygen) == 2
    assert oxygen[0]["color"] == "#12ab34"
    assert oxygen[0]["radius"] == pytest.approx(0.792)
    assert oxygen[0]["material"] == "metal"
    assert oxygen[0]["opacity"] == pytest.approx(0.35)
    hydrogen = [item for item in scene["atoms"] if item["index"] == 1]
    assert {item["material"] for item in hydrogen} == {"rubber"}
    assert {item["color"] for item in hydrogen} == {"#4455aa"}
    assert all(item["opacity"] == pytest.approx(0.6) for item in hydrogen)
    reference_hydrogen = [item for item in scene["atoms"] if item["index"] == 2]
    assert hydrogen[0]["radius"] / reference_hydrogen[0]["radius"] == pytest.approx(1.5)
    assert any("bridge" in item["name"] for item in scene["bonds"])
    assert all(item["diameter"] == pytest.approx(0.18) for item in scene["bonds"])
    assert all(item["radius"] == pytest.approx(0.09) for item in scene["bonds"])
    selected_bond = [item for item in scene["bonds"] if item["i"] == 0 and item["j"] == 1]
    assert {item["material"] for item in selected_bond} == {"metal", "rubber"}
    assert {round(item["opacity"], 6) for item in selected_bond} == {0.4, 0.8}
    assert len(scene["cell_edges"]) == 20
    assert scene["cell_color"] == "#d6bd67"
    assert scene["camera"]["projection"] == "orthographic"


def test_cad_scene_respects_hidden_atom_types():
    session = cad_session()
    payload = cad_payload()
    payload["display"]["labelVisible"] = {"H_water": False}
    scene = _cad_scene_data(session, payload)

    assert len(scene["atoms"]) == 2
    assert {item["label"] for item in scene["atoms"]} == {"O_surface"}
    assert scene["bonds"] == []


def test_cad_scene_preserves_unit_cell_style():
    payload = cad_payload()
    payload["display"].update({
        "cellColor": "#38bda8",
        "cellThickness": 0.18,
        "cellMaterial": "metal",
    })
    scene = _cad_scene_data(cad_session(), payload)

    assert scene["cell_color"] == "#38bda8"
    assert scene["cell_thickness"] == pytest.approx(0.18)
    assert scene["cell_material"] == "metal"


def test_cad_scene_applies_visual_translation_after_supercell_without_moving_cell():
    payload = cad_payload()
    payload["display"].update({
        "translation": [0.25, 0.5, -0.1],
        "translationMode": "fractional",
    })
    scene = _cad_scene_data(cad_session(), payload)

    assert scene["translation"] == pytest.approx([1.25, 2.1, -0.5])
    base_oxygen = next(
        atom for atom in scene["atoms"]
        if atom["index"] == 0 and atom["cell_offset"] == [0, 0, 0]
    )
    repeated_oxygen = next(
        atom for atom in scene["atoms"]
        if atom["index"] == 0 and atom["cell_offset"] == [1, 0, 0]
    )
    assert base_oxygen["position"] == pytest.approx([1.25, 2.1, -0.5])
    assert repeated_oxygen["position"] == pytest.approx([5.25, 2.1, -0.5])
    assert scene["cell_edges"][0]["start"] == pytest.approx([0.0, 0.0, 0.0])


def test_obj_export_is_dependency_free_and_bundles_materials():
    response = export_obj_response(cad_session(), cad_payload())
    archive_path = Path(response.path)
    try:
        assert response.filename == "v_ase_obj_scene.zip"
        with zipfile.ZipFile(archive_path) as bundle:
            assert set(bundle.namelist()) == {
                "v_ase_scene.obj", "v_ase_scene.mtl", "v_ase_scene.json"
            }
            obj = bundle.read("v_ase_scene.obj").decode("ascii")
            mtl = bundle.read("v_ase_scene.mtl").decode("ascii")
            metadata = json.loads(bundle.read("v_ase_scene.json"))

        assert "mtllib v_ase_scene.mtl" in obj
        assert obj.count("o atom_") == 6
        assert obj.count("o bond_") == 8
        assert obj.count("o cell_edge_") == 20
        assert "v_ase_metal_12ab34" in mtl
        assert "Kd 0.070588 0.670588 0.203922" in mtl
        assert "usemtl v_ase_metal_12ab34" in obj
        assert "newmtl v_ase_metal_12ab34_a3500" in mtl
        assert "d 0.350000" in mtl
        assert "newmtl v_ase_rubber_" in mtl
        assert "newmtl v_ase_standard_d6bd67" in mtl
        assert "o cell_edge_0\nusemtl v_ase_standard_d6bd67\n" in obj
        assert metadata["bond_thickness_semantics"] == "diameter"
        assert metadata["camera"]["position"] == [5.0, -6.0, 4.0]
        assert metadata["include_cell"] is True
        assert {item["material"] for item in metadata["atoms"]} == {
            "standard", "metal", "rubber"
        }
        oxygen_opacities = [
            item["opacity"] for item in metadata["atoms"]
            if item["label"] == "O_surface"
        ]
        assert oxygen_opacities == pytest.approx([0.35, 0.35])
        assert all(item["diameter"] == pytest.approx(0.18) for item in metadata["bonds"])
        assert all(item["radius"] == pytest.approx(0.09) for item in metadata["bonds"])
        assert {item["material"] for item in metadata["bonds"]} == {"metal", "rubber"}
        assert {round(item["opacity"], 6) for item in metadata["bonds"]} == {0.4, 0.8}
    finally:
        archive_path.unlink(missing_ok=True)


def test_3dm_export_reports_optional_dependency_install_command(monkeypatch):
    original_import = builtins.__import__

    def missing_rhino(name, *args, **kwargs):
        if name == "rhino3dm":
            raise ImportError("rhino3dm intentionally unavailable")
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", missing_rhino)
    with pytest.raises(OptionalExportDependencyError) as excinfo:
        export_3dm_response(cad_session(), cad_payload())

    message = str(excinfo.value)
    assert "rhino3dm" in message
    assert 'v_ase-gui[rhino]' in message


def test_3dm_export_round_trips_as_editable_angstrom_scene():
    rhino3dm = pytest.importorskip("rhino3dm")
    response = export_3dm_response(cad_session(), cad_payload())
    model_path = Path(response.path)
    try:
        model = rhino3dm.File3dm.Read(str(model_path))
        assert model is not None
        assert response.filename == "v_ase_scene.3dm"
        assert model.Settings.ModelUnitSystem == rhino3dm.UnitSystem.Angstroms
        assert [layer.Name for layer in model.Layers] == ["Atoms", "Bonds", "Unit Cell"]
        assert len(model.InstanceDefinitions) == 3
        assert len(model.Views) == 1
        assert len(model.NamedViews) == 1
        assert model.Views[0].Name == "v_ase View"
        assert model.NamedViews[0].Name == "v_ase Saved View"
        assert model.Views[0].Viewport.CameraLocation == rhino3dm.Point3d(5.0, -6.0, 4.0)
        assert model.Views[0].Viewport.TargetPoint == rhino3dm.Point3d(1.0, 0.5, 0.25)
        assert model.Views[0].Viewport.IsParallelProjection
        frustum = model.Views[0].Viewport.GetFrustum()
        assert frustum["left"] == pytest.approx(-6.0)
        assert frustum["right"] == pytest.approx(6.0)
        assert frustum["bottom"] == pytest.approx(-4.0)
        assert frustum["top"] == pytest.approx(4.0)
        live_objects = [item for item in model.Objects if not item.Attributes.IsInstanceDefinitionObject]
        assert len(live_objects) == 6 + 4 + 20
        atom_objects = [
            item for item in model.Objects
            if item.Attributes.GetUserString("v_ase.kind") == "atom"
        ]
        bond_objects = [
            item for item in model.Objects
            if item.Attributes.GetUserString("v_ase.kind") == "bond"
        ]
        cell_objects = [
            item for item in model.Objects
            if item.Attributes.GetUserString("v_ase.kind") == "unit_cell"
        ]
        assert len(atom_objects) == 6
        assert len(bond_objects) == 4
        assert len(cell_objects) == 20
        assert all(type(item.Geometry).__name__ == "InstanceReference" for item in atom_objects)
        assert all(type(item.Geometry).__name__ == "InstanceReference" for item in bond_objects)
        assert all(type(item.Geometry).__name__ == "InstanceReference" for item in cell_objects)
        assert atom_objects[0].Attributes.GetUserString("v_ase.units") == "angstrom"
        assert atom_objects[0].Attributes.Name.startswith("atom_")
        assert {
            item.Attributes.GetUserString("v_ase.material")
            for item in atom_objects
        } == {"standard", "metal", "rubber"}
        oxygen_atoms = [
            item for item in atom_objects
            if item.Attributes.GetUserString("v_ase.label") == "O_surface"
        ]
        assert len(oxygen_atoms) == 2
        assert {
            item.Attributes.GetUserString("v_ase.opacity")
            for item in oxygen_atoms
        } == {"0.35"}
        assert all(
            model.Materials[item.Attributes.MaterialIndex].Transparency
            == pytest.approx(0.65)
            for item in oxygen_atoms
        )
        atom_xform = atom_objects[0].Geometry.Xform
        atom_scale = (atom_xform.M00 ** 2 + atom_xform.M10 ** 2 + atom_xform.M20 ** 2) ** 0.5
        assert atom_scale == pytest.approx(0.792)
        bond_xform = bond_objects[0].Geometry.Xform
        bond_diameter = (bond_xform.M00 ** 2 + bond_xform.M10 ** 2 + bond_xform.M20 ** 2) ** 0.5
        bond_length = (bond_xform.M02 ** 2 + bond_xform.M12 ** 2 + bond_xform.M22 ** 2) ** 0.5
        assert bond_diameter == pytest.approx(0.12)
        assert bond_length == pytest.approx(0.96)
        assert cell_objects[0].Attributes.GetUserString("v_ase.thickness") == "0.04"
        assert cell_objects[0].Attributes.GetUserString("v_ase.material") == "unlit"
    finally:
        model_path.unlink(missing_ok=True)


def test_cad_exports_can_exclude_unit_cell():
    payload = cad_payload()
    payload["include_cell"] = False
    scene = _cad_scene_data(cad_session(), payload)
    assert scene["cell_edges"] == []

    response = export_obj_response(cad_session(), payload)
    archive_path = Path(response.path)
    try:
        with zipfile.ZipFile(archive_path) as bundle:
            obj = bundle.read("v_ase_scene.obj").decode("ascii")
            metadata = json.loads(bundle.read("v_ase_scene.json"))
        assert "o cell_edge_" not in obj
        assert metadata["include_cell"] is False
        assert metadata["cell_edges"] == []
    finally:
        archive_path.unlink(missing_ok=True)

    rhino3dm = pytest.importorskip("rhino3dm")
    response = export_3dm_response(cad_session(), payload)
    model_path = Path(response.path)
    try:
        model = rhino3dm.File3dm.Read(str(model_path))
        assert model is not None
        assert not any(
            item.Attributes.GetUserString("v_ase.kind") == "unit_cell"
            for item in model.Objects
        )
        assert len(model.Views) == 1
        assert len(model.NamedViews) == 1
    finally:
        model_path.unlink(missing_ok=True)
