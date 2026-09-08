"""Compare bounded scientific workloads against a local release tag.

Run without concurrent test/render workloads. Results are timings on this
machine, not application-wide speedups. The baseline is read without checkout.
"""
from __future__ import annotations

import argparse
import base64
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import json
from pathlib import Path
import platform
import shutil
import statistics
import subprocess
import sys
import tempfile
import time
import types

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import numpy as np
from ase import Atoms
from ase.geometry import find_mic as ase_find_mic
from v_ase import analysis, commensurate, io, neighbors


def source_at(ref, relative):
    return subprocess.check_output(["git", "show", f"{ref}:{relative}"], cwd=ROOT).decode()


def baseline_module(ref, name):
    key = f"v_ase._audit_before_{name}"
    module = types.ModuleType(key)
    module.__file__ = str(ROOT / "v_ase" / f"{name}.py")
    sys.modules[key] = module
    exec(compile(source_at(ref, f"v_ase/{name}.py"), module.__file__, "exec"), module.__dict__)
    return module


def measure(operation, repeats):
    operation()
    values = []
    for _ in range(repeats):
        start = time.perf_counter()
        operation()
        values.append((time.perf_counter() - start) * 1000)
    return {"samples_ms": values, "median_ms": statistics.median(values)}


def compare(before, after, repeats, **metadata):
    result = {**metadata, "before": measure(before, repeats), "after": measure(after, repeats)}
    result["before_over_after"] = result["before"]["median_ms"] / result["after"]["median_ms"]
    return result


def trajectory_benchmark(ref, repeats):
    node = shutil.which("node")
    if not node:
        raise RuntimeError("Node.js is required; no benchmark is silently skipped.")
    old_url = "data:text/javascript;base64," + base64.b64encode(
        source_at(ref, "v_ase/static/trajectory.js").encode()).decode()
    urls = [old_url, (ROOT / "v_ase/static/trajectory.js").as_uri()]
    script = "const urls = " + json.dumps(urls) + "; const repeats = " + str(repeats) + ";" + r'''
const modules = await Promise.all(urls.map(url => import(url)));
const results = {};
let seed = 713;
const random = () => ((seed = (1664525 * seed + 1013904223) >>> 0) / 2**32);
const mul = (v, c) => [0,1,2].map(j => v.reduce((s,x,i) => s+x*c[i][j],0));
for (const [name, cell] of Object.entries({
    orthogonal: [[40,0,0],[0,45,0],[0,0,50]],
    skew: [[40,0,0],[27,45,0],[9,7,50]]
})) {
    const count = 10000;
    const a = new Float64Array(3*count), b = new Float64Array(3*count);
    for (let i=0; i<count; i++) {
        const f = [random(), random(), random()];
        const g = f.map(x => (x + (random()-.5)*1.1 + 1) % 1);
        a.set(mul(f,cell),3*i); b.set(mul(g,cell),3*i);
    }
    const first = {positions:a,cell,pbc:[true,true,true]};
    const second = {positions:b,cell,pbc:first.pbc};
    const outcomes = modules.map(m => m.interpolateTrajectoryFrames(first,second,.5,{useMic:true}));
    let differentAtoms = 0;
    for (let i=0; i<count; i++) {
        if ([0,1,2].some(k => Math.abs(outcomes[0].positions[3*i+k]-outcomes[1].positions[3*i+k])>1e-9)) differentAtoms++;
    }
    const timings = modules.map(m => {
        for(let i=0;i<5;i++) m.interpolateTrajectoryFrames(first,second,.5,{useMic:true});
        const samples=[];
        for(let i=0;i<repeats;i++) {
            const start=performance.now();
            m.interpolateTrajectoryFrames(first,second,.5,{useMic:true});
            samples.push(performance.now()-start);
        }
        const sorted=[...samples].sort((a,b)=>a-b), n=sorted.length;
        return {samples_ms:samples,median_ms:(sorted[Math.floor(n/2)]+sorted[Math.floor((n-1)/2)])/2};
    });
    if(name==='orthogonal' && differentAtoms) throw new Error('Orthogonal interpolation changed');
    results[name]={atoms:count,before:timings[0],after:timings[1],
        before_over_after:timings[0].median_ms/timings[1].median_ms,
        different_atoms:differentAtoms};
}
console.log(JSON.stringify({node:process.version,cases:results}));
'''
    return json.loads(subprocess.check_output([node, "--input-type=module", "-e", script], cwd=ROOT))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline", default="v0.3.3")
    parser.add_argument("--repeats", type=int, default=7)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.repeats < 3:
        parser.error("Use at least three timed repetitions.")
    baseline = {name: baseline_module(args.baseline, name) for name in ("analysis", "commensurate", "io")}
    result = {"schema": "v_ase.scientific-audit-timings.v1", "baseline": args.baseline,
              "baseline_commit": subprocess.check_output(["git", "rev-parse", args.baseline], cwd=ROOT).decode().strip(),
              "source": "unreleased working source", "repeats": args.repeats,
              "recorded_at": datetime.now(timezone.utc).isoformat(),
              "source_sha256": {name: hashlib.sha256((ROOT / "v_ase" / name).read_bytes()).hexdigest()
                                for name in ("neighbors.py", "analysis.py", "commensurate.py", "io.py", "static/trajectory.js")},
              "python": platform.python_version(), "platform": platform.platform(),
              "packages": {name: importlib.metadata.version(name) for name in ("numpy", "scipy", "ase", "matscipy")},
              "method": "One warmup, median of recorded repetitions; JS uses five warmups. No concurrent test/render workloads.",
              "cases": {}}
    cases = result["cases"]
    cell = np.array([[4., 0, 0], [2, 3, 0], [.4, .2, 4]])
    vectors = np.random.default_rng(3).uniform(-3, 3, (24, 3)) @ cell
    np.testing.assert_allclose(neighbors.find_mic(vectors, cell)[1], ase_find_mic(vectors, cell)[1], atol=1e-12)
    cases["cached_mic"] = compare(
        lambda: [ase_find_mic(vectors, cell) for _ in range(1024)],
        lambda: [neighbors.find_mic(vectors, cell) for _ in range(1024)], args.repeats,
        calls=1024, vectors_per_call=24, equality="lengths agree to 1e-12 Å for this workload")
    atoms = Atoms("H" * 2000, positions=np.random.default_rng(79).uniform(0, 40, (2000, 3)), cell=[40]*3, pbc=True)
    io.set_atom_labels(atoms, [f"H_site_{i}" for i in range(len(atoms))])
    rdf = lambda module: module.calculate_rdf(atoms, cutoff=2, bins=100, pair_mode="none")
    np.testing.assert_array_equal(rdf(baseline["analysis"]).total, rdf(analysis).total)
    cases["total_rdf"] = compare(lambda: rdf(baseline["analysis"]), lambda: rdf(analysis), args.repeats,
        atoms=2000, distinct_labels=2000, cutoff_angstrom=2, bins=100, equality="total curve exactly equal")
    host = np.array([[2.46, 0, 0], [-1.23, np.sqrt(3)*1.23, 0], [0, 0, 20.]])
    guest = host.copy(); guest[:2] *= 1.018
    match = lambda module: module.find_lattice_matches(host, [True,True,False], guest, [True,True,False], max_area_ratio=64, strain_tolerance=.025)
    cases["lattice_search_64"] = compare(lambda: match(baseline["commensurate"]), lambda: match(commensurate), args.repeats,
        max_area_ratio=64, strain_tolerance=.025, before_orientations=8, after_orientations=20,
        equality="Search correspondence set expanded; speed ratio is not equal-work algorithm isolation")
    with tempfile.TemporaryDirectory(prefix="vase-audit-io-") as temp:
        path = Path(temp) / "benchmark.lammpstrj"
        rows = [f"{i+1} 1 0 {i*.001:.12f} .1 .2 .3 .4 .5 .123456789123" for i in range(10000)]
        path.write_text("ITEM: TIMESTEP\n0\nITEM: NUMBER OF ATOMS\n10000\nITEM: BOX BOUNDS pp pp pp\n0 40\n0 40\n0 40\nITEM: ATOMS id type mol x y z fx fy fz q\n" + "\n".join(rows) + "\n")
        old = baseline["io"].read_fast_lammps_dump(path).trajectory
        new = io.read_fast_lammps_dump(path).trajectory
        np.testing.assert_array_equal(old.read_positions(0), new.read_positions(0))
        cases["lammps_display_read"] = compare(lambda: old.read_positions(0), lambda: new.read_positions(0), args.repeats,
            atoms=10000, equality="FP32 display positions exactly equal", cache="warm file cache, already indexed")
        cases["lammps_scientific_read"] = compare(lambda: old.read_atoms(0), lambda: new.read_atoms(0), args.repeats,
            atoms=10000, before_precision="FP32 values", after_precision="FP64 values and int64 identity", cache="warm file cache, already indexed")
    result["trajectory"] = trajectory_benchmark(args.baseline, args.repeats)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
