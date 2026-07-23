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
from v_ase.io import set_atom_type_labels
from v_ase.session import EditorSession


def cad_session():
    atoms = Atoms(
        "OH2",
        positions=[[0.0, 0.0, 0.0], [0.96, 0.0, 0.0], [-0.24, 0.93, 0.0]],
        cell=[[4.0, 0.0, 0.0], [0.5, 4.2, 0.0], [0.0, 0.0, 5.0]],
        pbc=True,
    )
    set_atom_type_labels(atoms, ["O_surface", "H_water", "H_water"])
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
            "atomRadiusScale": 1.1,
            "elementColors": {"O_surface": "#12ab34"},
            "elementRadii": {"O_surface": 0.72},
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
    assert any("bridge" in item["name"] for item in scene["bonds"])
    assert all(item["diameter"] == pytest.approx(0.12) for item in scene["bonds"])
    assert all(item["radius"] == pytest.approx(0.06) for item in scene["bonds"])
    assert len(scene["cell_edges"]) == 20
    assert scene["cell_color"] == "#d6bd67"
    assert scene["camera"]["projection"] == "orthographic"


def test_cad_scene_respects_hidden_atom_types():
    session = cad_session()
    payload = cad_payload()
    payload["display"]["elementVisible"] = {"H_water": False}
    scene = _cad_scene_data(session, payload)

    assert len(scene["atoms"]) == 2
    assert {item["label"] for item in scene["atoms"]} == {"O_surface"}
    assert scene["bonds"] == []


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
        assert "v_ase_12ab34" in mtl
        assert "Kd 0.070588 0.670588 0.203922" in mtl
        assert "usemtl v_ase_12ab34" in obj
        assert "newmtl v_ase_d6bd67" in mtl
        assert "o cell_edge_0\nusemtl v_ase_d6bd67\n" in obj
        assert metadata["bond_thickness_semantics"] == "diameter"
        assert metadata["camera"]["position"] == [5.0, -6.0, 4.0]
        assert metadata["include_cell"] is True
        assert all(item["diameter"] == pytest.approx(0.12) for item in metadata["bonds"])
        assert all(item["radius"] == pytest.approx(0.06) for item in metadata["bonds"])
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
        assert len(model.InstanceDefinitions) == 2
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
        assert len(atom_objects) == 6
        assert len(bond_objects) == 4
        assert all(type(item.Geometry).__name__ == "InstanceReference" for item in atom_objects)
        assert all(type(item.Geometry).__name__ == "InstanceReference" for item in bond_objects)
        assert atom_objects[0].Attributes.GetUserString("v_ase.units") == "angstrom"
        assert atom_objects[0].Attributes.Name.startswith("atom_")
        atom_xform = atom_objects[0].Geometry.Xform
        atom_scale = (atom_xform.M00 ** 2 + atom_xform.M10 ** 2 + atom_xform.M20 ** 2) ** 0.5
        assert atom_scale == pytest.approx(0.792)
        bond_xform = bond_objects[0].Geometry.Xform
        bond_diameter = (bond_xform.M00 ** 2 + bond_xform.M10 ** 2 + bond_xform.M20 ** 2) ** 0.5
        bond_length = (bond_xform.M02 ** 2 + bond_xform.M12 ** 2 + bond_xform.M22 ** 2) ** 0.5
        assert bond_diameter == pytest.approx(0.12)
        assert bond_length == pytest.approx(0.96)
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
