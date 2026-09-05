# Workflows

Task-focused guides for inspecting, editing, analyzing, styling, and exporting
atomistic data. Each page states the scientific assumptions and the state that
should be verified before saving a result.

```{toctree}
:maxdepth: 1

data-input
visualization
editing
atomic-distributions
constraints-relaxation
trajectories-analysis
rdf
volumetric-guide
periodic-interfaces
projects-export
worked-examples
```

## Find a feature

| Task | Guide | What to verify |
| --- | --- | --- |
| Move, rotate, or constrain coordinates | [Editing](editing.md), [constraints](constraints-relaxation.md) | Selected atoms and final ASE positions |
| Generate atoms or solvent | [Distributions](atomic-distributions.md) | Density, composition, periodic contacts, host preservation |
| Match two lattices | [Periodic interfaces](periodic-interfaces.md) | Integer matrices, strain target, area, atom count |
| Inspect pair statistics | [RDF](rdf.md) | PBC, normalization, frame, cutoff |
| Process a scalar grid | [Volumetric fields](volumetric-guide.md) | Units, precision, integral, sampling geometry |
| Color atoms or inspect a trajectory | [Visualization](visualization.md), [trajectories](trajectories-analysis.md) | Property source and frame/range |
| Save, render, or share | [Projects and exports](projects-export.md) | Physical structure versus saved view |

Each guide separates GUI steps, scientific interpretation, and automation
examples. JSON examples are API request bodies, not Python code; replace example
IDs and revisions with current values from `describe` before submitting them.
