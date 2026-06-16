"""Optional-torch repulsion calculator used as v_ase's fallback calculator."""

from __future__ import annotations

import os
from functools import lru_cache
from typing import Any

import numpy as np
from ase import Atoms
from ase.calculators.calculator import Calculator, all_changes
from ase.data import atomic_numbers, covalent_radii, vdw_radii
from ase.neighborlist import primitive_neighbor_list

_EPS = 1e-12


@lru_cache(maxsize=1)
def optional_torch():
    try:
        import torch
    except Exception:
        return None
    return torch


def torch_available() -> bool:
    return optional_torch() is not None


def cuda_available() -> bool:
    torch = optional_torch()
    if torch is None:
        return False
    try:
        return bool(torch.cuda.is_available())
    except Exception:
        return False


def cpu_thread_options() -> list[int]:
    count = os.cpu_count() or 1
    return list(range(1, max(1, count) + 1))


def default_cpu_threads() -> int:
    return min(4, max(1, os.cpu_count() or 1))


def _normalized_device(device: str | None) -> str:
    value = str(device or "cpu").strip().lower()
    return "cuda" if value.startswith("cuda") else "cpu"


def _valid_cpu_threads(value: Any | None) -> int:
    try:
        threads = int(value)
    except (TypeError, ValueError):
        threads = default_cpu_threads()
    max_threads = max(cpu_thread_options())
    return min(max(1, threads), max_threads)


def _copy_calc_config(source: "VAseRepulsionCalculator") -> dict[str, Any]:
    return {
        "min_bondinfo": source.min_bondinfo,
        "region": list(source.region),
        "set_region_as_prohibited": source.set_region_as_prohibited,
        "k_boundary": source.k_boundary,
        "k_repulsion": source.k_repulsion,
        "max_force_norm": source.max_force_norm,
        "mic": source.mic,
        "work_on_relax_atoms_too": source.work_on_relax_atoms_too,
        "device": source.device_requested,
        "cpu_threads": source.cpu_threads,
        "backend": source.backend,
    }


def copy_calculator(calc):
    if isinstance(calc, VAseRepulsionCalculator):
        return VAseRepulsionCalculator(**_copy_calc_config(calc))
    return calc


def is_vase_repulsion_calculator(calc) -> bool:
    return isinstance(calc, VAseRepulsionCalculator)


class VAseRepulsionCalculator(Calculator):
    """ASE calculator for soft pair repulsion and optional region penalties.

    The default model follows the semantics of the reference Conditioner:
    atoms closer than a covalent-radius threshold receive a harmonic repulsive
    force. Torch is used when available, including CUDA if requested; otherwise
    the same force expression is evaluated with NumPy.
    """

    implemented_properties = ["energy", "forces"]

    def __init__(
        self,
        min_bondinfo: dict[str, float] | float | str = "cov",
        region: list[float | None] | None = None,
        set_region_as_prohibited: bool = False,
        k_boundary: float = 1.0,
        k_repulsion: float = 1.0,
        max_force_norm: float | None = 10.0,
        mic: bool = True,
        work_on_relax_atoms_too: bool = True,
        device: str = "cpu",
        cpu_threads: int | None = None,
        backend: str = "auto",
        **kwargs,
    ):
        super().__init__(**kwargs)
        self.min_bondinfo = min_bondinfo.lower() if isinstance(min_bondinfo, str) else min_bondinfo
        self.region = [None] * 6 if region is None else list(region)
        if len(self.region) != 6:
            raise ValueError("region must be a list of length 6")
        self.set_region_as_prohibited = bool(set_region_as_prohibited)
        self.k_boundary = float(k_boundary)
        self.k_repulsion = float(k_repulsion)
        self.max_force_norm = None if max_force_norm is None else float(max_force_norm)
        self.mic = bool(mic)
        self.work_on_relax_atoms_too = bool(work_on_relax_atoms_too)
        self.device_requested = _normalized_device(device)
        self.cpu_threads = _valid_cpu_threads(cpu_threads)
        self.backend = str(backend or "auto").lower()
        self.backend_used = "numpy"
        self.device_used = "cpu"

    def configure(self, *, device: str | None = None, cpu_threads: int | None = None):
        if device is not None:
            self.device_requested = _normalized_device(device)
        if cpu_threads is not None:
            self.cpu_threads = _valid_cpu_threads(cpu_threads)
        self.reset()

    def status(self) -> dict[str, Any]:
        return {
            "is_default_repulsion": True,
            "calculator": self.__class__.__name__,
            "backend": self.backend_used,
            "requested_device": self.device_requested,
            "effective_device": self.device_used,
            "cpu_threads": self.cpu_threads,
            "cpu_thread_options": cpu_thread_options(),
            "torch_available": torch_available(),
            "cuda_available": cuda_available(),
            "min_bondinfo": self.min_bondinfo,
        }

    def _min_bondinfo_for_atoms(self, atoms: Atoms):
        if isinstance(self.min_bondinfo, str):
            mode = self.min_bondinfo.lower()
            syms = np.unique(atoms.get_chemical_symbols())
            values = {}
            for i, sym_i in enumerate(syms):
                for sym_j in syms[i:]:
                    if mode.startswith("vdw"):
                        threshold = vdw_radii[atomic_numbers[sym_i]] + vdw_radii[atomic_numbers[sym_j]]
                    elif mode.startswith("cov"):
                        threshold = covalent_radii[atomic_numbers[sym_i]] + covalent_radii[atomic_numbers[sym_j]]
                    else:
                        raise ValueError("min_bondinfo must be 'vdw', 'cov', a number, or a pair dictionary")
                    if np.isfinite(threshold):
                        values[f"{sym_i}-{sym_j}"] = float(threshold)
            return values
        return self.min_bondinfo

    def _threshold_for_pair(self, min_bondinfo, sym_i: str, sym_j: str) -> float | None:
        if isinstance(min_bondinfo, dict):
            key_ij = f"{sym_i}-{sym_j}"
            key_ji = f"{sym_j}-{sym_i}"
            value = min_bondinfo.get(key_ij, min_bondinfo.get(key_ji))
            return None if value is None else float(value)
        return float(min_bondinfo)

    def _manual_pairs(self, atoms: Atoms, min_bondinfo):
        positions = atoms.get_positions()
        symbols = atoms.get_chemical_symbols()
        pairs = []
        for i in range(len(atoms) - 1):
            for j in range(i + 1, len(atoms)):
                threshold = self._threshold_for_pair(min_bondinfo, symbols[i], symbols[j])
                if threshold is None or threshold <= 0:
                    continue
                vec = positions[j] - positions[i]
                dist = float(np.linalg.norm(vec))
                if _EPS < dist < threshold:
                    pairs.append((i, j, vec, dist, threshold))
        return pairs

    def _neighbor_pairs(self, atoms: Atoms, min_bondinfo):
        if len(atoms) < 2:
            return []
        if isinstance(min_bondinfo, dict):
            max_cutoff = max(float(value) for value in min_bondinfo.values()) if min_bondinfo else 0.0
            cutoff = max_cutoff
        else:
            cutoff = float(min_bondinfo)
            max_cutoff = cutoff
        if max_cutoff <= 0:
            return []
        pbc = np.asarray(atoms.pbc, dtype=bool) if self.mic else np.asarray([False, False, False])
        use_neighborlist = atoms.cell.rank > 0 or bool(np.any(pbc))
        if not use_neighborlist:
            return self._manual_pairs(atoms, min_bondinfo)
        try:
            is_, js, vecs, dists = primitive_neighbor_list(
                "ijDd",
                pbc=pbc,
                cell=atoms.cell,
                positions=atoms.get_positions(),
                cutoff=cutoff,
                numbers=atoms.get_atomic_numbers(),
                self_interaction=False,
                use_scaled_positions=False,
            )
        except Exception:
            return self._manual_pairs(atoms, min_bondinfo)

        symbols = atoms.get_chemical_symbols()
        pairs = []
        for i, j, vec, dist in zip(is_, js, vecs, dists):
            i = int(i)
            j = int(j)
            if i >= j or dist <= _EPS:
                continue
            threshold = self._threshold_for_pair(min_bondinfo, symbols[i], symbols[j])
            if threshold is None or dist >= threshold:
                continue
            pairs.append((i, j, np.asarray(vec, dtype=float), float(dist), float(threshold)))
        return pairs

    def _boundary_energy_forces(self, atoms: Atoms):
        positions = atoms.get_positions()
        tags = atoms.get_tags()
        forces = np.zeros((len(atoms), 3), dtype=float)
        energy = 0.0
        for i, position in enumerate(positions):
            if tags[i] != 3 and not self.work_on_relax_atoms_too:
                continue
            for axis in range(3):
                coord = float(position[axis])
                lower = self.region[axis * 2]
                upper = self.region[axis * 2 + 1]
                if lower is None and upper is None:
                    continue
                if not self.set_region_as_prohibited:
                    if lower is not None and coord < lower:
                        disp = float(lower) - coord
                        forces[i, axis] += self.k_boundary * disp
                        energy += 0.5 * self.k_boundary * disp**2
                    if upper is not None and coord > upper:
                        disp = coord - float(upper)
                        forces[i, axis] -= self.k_boundary * disp
                        energy += 0.5 * self.k_boundary * disp**2
                elif lower is not None and upper is not None and float(lower) < coord < float(upper):
                    d_lower = coord - float(lower)
                    d_upper = float(upper) - coord
                    disp = -d_lower if d_lower < d_upper else d_upper
                    forces[i, axis] += self.k_boundary * disp
                    energy += 0.5 * self.k_boundary * abs(disp) ** 2
        return energy, forces

    def _should_use_torch(self):
        torch = optional_torch()
        if torch is None or self.backend == "numpy":
            self.backend_used = "numpy"
            self.device_used = "cpu"
            return None, None
        device = "cuda" if self.device_requested == "cuda" and cuda_available() else "cpu"
        if device == "cpu":
            try:
                torch.set_num_threads(self.cpu_threads)
            except Exception:
                pass
        self.backend_used = "torch"
        self.device_used = device
        return torch, device

    def _pair_energy_forces_numpy(self, atoms: Atoms, pairs):
        tags = atoms.get_tags()
        forces = np.zeros((len(atoms), 3), dtype=float)
        energy = 0.0
        for i, j, vec, dist, threshold in pairs:
            delta = threshold - dist
            energy += 0.5 * self.k_repulsion * delta**2
            f_vec = (self.k_repulsion * delta / max(dist, _EPS)) * vec
            if tags[i] == 3 or self.work_on_relax_atoms_too:
                forces[i] -= f_vec
            if tags[j] == 3 or self.work_on_relax_atoms_too:
                forces[j] += f_vec
        return energy, forces

    def _pair_energy_forces_torch(self, atoms: Atoms, pairs, torch, device: str):
        tags_np = atoms.get_tags()
        is_np = np.asarray([p[0] for p in pairs], dtype=np.int64)
        js_np = np.asarray([p[1] for p in pairs], dtype=np.int64)
        vecs_np = np.asarray([p[2] for p in pairs], dtype=float)
        dists_np = np.asarray([p[3] for p in pairs], dtype=float)
        thresholds_np = np.asarray([p[4] for p in pairs], dtype=float)

        dt = torch.float64
        is_ = torch.as_tensor(is_np, dtype=torch.long, device=device)
        js = torch.as_tensor(js_np, dtype=torch.long, device=device)
        vecs = torch.as_tensor(vecs_np, dtype=dt, device=device)
        dists = torch.as_tensor(dists_np, dtype=dt, device=device).clamp_min(_EPS)
        thresholds = torch.as_tensor(thresholds_np, dtype=dt, device=device)
        deltas = thresholds - dists
        energy = 0.5 * self.k_repulsion * torch.sum(deltas**2)
        fvec = (self.k_repulsion * deltas / dists).unsqueeze(1) * vecs

        forces = torch.zeros((len(atoms), 3), dtype=dt, device=device)
        tags = torch.as_tensor(tags_np, dtype=torch.long, device=device)
        apply_i = (tags[is_] == 3) | bool(self.work_on_relax_atoms_too)
        apply_j = (tags[js] == 3) | bool(self.work_on_relax_atoms_too)
        if bool(torch.any(apply_i)):
            forces.index_add_(0, is_[apply_i], -fvec[apply_i])
        if bool(torch.any(apply_j)):
            forces.index_add_(0, js[apply_j], fvec[apply_j])
        return float(energy.detach().cpu().item()), forces.detach().cpu().numpy()

    def _limit_forces(self, atoms: Atoms, forces: np.ndarray) -> np.ndarray:
        if self.max_force_norm is None:
            return forces
        tags = atoms.get_tags()
        limited = np.array(forces, dtype=float, copy=True)
        for i, force in enumerate(limited):
            if tags[i] != 3 and not self.work_on_relax_atoms_too:
                continue
            norm = float(np.linalg.norm(force))
            if norm > _EPS:
                limited[i] = self.max_force_norm * np.tanh(norm / self.max_force_norm) * (force / norm)
        return limited

    def calculate(self, atoms=None, properties=("energy", "forces"), system_changes=all_changes):
        Calculator.calculate(self, atoms, properties, system_changes)
        atoms = self.atoms
        energy, forces = self._boundary_energy_forces(atoms)
        min_bondinfo = self._min_bondinfo_for_atoms(atoms)
        pairs = self._neighbor_pairs(atoms, min_bondinfo)
        if pairs:
            torch, device = self._should_use_torch()
            if torch is None:
                pair_energy, pair_forces = self._pair_energy_forces_numpy(atoms, pairs)
            else:
                with torch.no_grad():
                    pair_energy, pair_forces = self._pair_energy_forces_torch(atoms, pairs, torch, device)
            energy += pair_energy
            forces += pair_forces
        else:
            self._should_use_torch()
        forces = self._limit_forces(atoms, forces)
        self.results = {"energy": float(energy), "forces": forces}


def ensure_default_calculator(atoms: Atoms) -> Atoms:
    if atoms.calc is None:
        atoms.calc = VAseRepulsionCalculator()
    return atoms


def repulsion_metadata(calc) -> dict[str, Any]:
    if isinstance(calc, VAseRepulsionCalculator):
        return calc.status()
    return {
        "is_default_repulsion": False,
        "cpu_thread_options": cpu_thread_options(),
        "torch_available": torch_available(),
        "cuda_available": cuda_available(),
    }
