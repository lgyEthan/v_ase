"""Sphinx directive and build hook for embedded v_ase demonstrations."""

from __future__ import annotations

import html
import json
import os
import re
import shutil
from pathlib import Path
from urllib.parse import quote

from docutils import nodes
from docutils.parsers.rst import Directive, directives
from sphinx.errors import ExtensionError
from sphinx.util.osutil import relative_uri


SCENE_ID = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*")
HTML_BUILDERS = {"html", "dirhtml", "singlehtml"}
RUNTIME_FILES = (
    "renderer.js",
    "standalone.js",
    "standalone.css",
)


class VaseDemoDirective(Directive):
    """Render a live v_ase iframe in HTML and an image in offline formats."""

    required_arguments = 1
    has_content = False
    option_spec = {
        "alt": directives.unchanged_required,
        "fallback": directives.path,
        "height": directives.positive_int,
        "caption": directives.unchanged,
    }

    def run(self):
        scene_id = self.arguments[0].strip()
        if not SCENE_ID.fullmatch(scene_id):
            raise self.error(f"Invalid v_ase demo scene id: {scene_id!r}")

        env = self.state.document.settings.env
        source_root = Path(env.srcdir)
        scene_path = source_root / "_interactive" / "scenes" / f"{scene_id}.json"
        if not scene_path.is_file():
            raise self.error(f"Missing interactive v_ase scene: {scene_path}")

        fallback = self.options.get("fallback")
        if not fallback:
            raise self.error("The vase-demo directive requires :fallback: for PDF/ePub output.")
        fallback_path = source_root / fallback
        if not fallback_path.is_file():
            raise self.error(f"Missing v_ase demo fallback image: {fallback_path}")

        alt = self.options.get("alt", scene_id.replace("-", " "))
        caption = self.options.get(
            "caption",
            "Drag to rotate, Shift-drag to pan, and use the wheel to zoom.",
        )
        height = self.options.get("height", 520)
        builder_name = env.app.builder.name

        if builder_name in HTML_BUILDERS:
            current_uri = env.app.builder.get_target_uri(env.docname)
            viewer_path = relative_uri(current_uri, "_static/interactive/viewer.html")
            viewer = f"{viewer_path}?scene={quote(scene_id)}"
            markup = f"""
<figure class="vase-demo" data-vase-scene="{html.escape(scene_id, quote=True)}">
  <div class="vase-demo-frame" style="--vase-demo-height:{height}px">
    <iframe
      src="{viewer}"
      title="{html.escape(alt, quote=True)}"
      loading="lazy"
      allow="fullscreen"
      sandbox="allow-scripts allow-same-origin"
    ></iframe>
  </div>
  <figcaption>
    {html.escape(caption)}
    <a href="{viewer}" target="_blank" rel="noopener">Open full screen</a>
  </figcaption>
</figure>
"""
            return [nodes.raw("", markup, format="html")]

        return [nodes.image(uri=fallback, alt=alt)]


def _copy_interactive_runtime(app, exception) -> None:
    """Copy the tested package renderer once, avoiding one copy per scene."""

    if exception is not None or app.builder.name not in HTML_BUILDERS:
        return
    repository_root = Path(app.confdir).parent
    runtime_root = Path(os.environ.get("V_ASE_DOCS_RUNTIME_ROOT", repository_root))
    package_static = runtime_root / "v_ase" / "static"
    interactive_source = Path(app.confdir) / "_interactive"
    target_root = Path(app.outdir) / "_static" / "interactive"
    runtime_target = target_root / "runtime"
    poster_target = target_root / "posters"
    scene_target = target_root / "scenes"
    runtime_target.mkdir(parents=True, exist_ok=True)
    poster_target.mkdir(parents=True, exist_ok=True)
    scene_target.mkdir(parents=True, exist_ok=True)

    viewer_source = interactive_source / "viewer.html"
    if not viewer_source.is_file():
        raise ExtensionError(f"Missing v_ase interactive viewer: {viewer_source}")
    shutil.copy2(viewer_source, target_root / "viewer.html")

    for filename in RUNTIME_FILES:
        source = package_static / filename
        if not source.is_file():
            raise ExtensionError(f"Missing v_ase interactive runtime file: {source}")
        shutil.copy2(source, runtime_target / filename)

    three_source = package_static / "vendor" / "three.module.js"
    three_target = runtime_target / "vendor" / "three.module.js"
    three_target.parent.mkdir(parents=True, exist_ok=True)
    if not three_source.is_file():
        raise ExtensionError(f"Missing bundled Three.js module: {three_source}")
    shutil.copy2(three_source, three_target)

    scene_dir = interactive_source / "scenes"
    for scene_path in sorted(scene_dir.glob("*.json")):
        shutil.copy2(scene_path, scene_target / scene_path.name)
        scene = json.loads(scene_path.read_text(encoding="utf-8"))
        poster_name = str(scene.get("referenceImage") or "").strip()
        if not poster_name:
            continue
        poster_source = Path(app.confdir) / "assets" / poster_name
        if not poster_source.is_file():
            raise ExtensionError(
                f"Interactive scene {scene_path.name} references missing poster {poster_source}"
            )
        shutil.copy2(poster_source, poster_target / poster_source.name)


def setup(app):
    app.add_directive("vase-demo", VaseDemoDirective)
    app.connect("build-finished", _copy_interactive_runtime)
    return {
        "version": "1.0",
        "parallel_read_safe": True,
        "parallel_write_safe": True,
    }
