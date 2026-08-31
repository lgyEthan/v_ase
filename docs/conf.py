"""Sphinx configuration for the v_ase user and developer manual."""

from __future__ import annotations

import os
import runpy
import sys
from pathlib import Path


DOCS_DIR = Path(__file__).resolve().parent
REPOSITORY_ROOT = DOCS_DIR.parent
sys.path.insert(0, str(DOCS_DIR / "_ext"))
release = runpy.run_path(REPOSITORY_ROOT / "v_ase" / "_version.py")["__version__"]

project = "v_ase"
author = "v_ase contributors"
copyright = "2026, v_ase contributors"
version = release

extensions = [
    "myst_parser",
    "sphinx_rtd_theme",
    "vase_demo",
]

source_suffix = {
    ".rst": "restructuredtext",
    ".md": "markdown",
}
root_doc = "index"
exclude_patterns = [
    "_build",
    "_interactive",
    "design",
    "Thumbs.db",
    ".DS_Store",
]

myst_enable_extensions = [
    "colon_fence",
    "deflist",
    "fieldlist",
    "tasklist",
]
myst_heading_anchors = 4

language = "en"
nitpicky = True

html_theme = "sphinx_rtd_theme"
html_title = f"v_ase {release} documentation"
html_logo = "assets/v_ase-logo.png"
html_favicon = "assets/v_ase-logo.png"
html_static_path = ["_static"]
html_css_files = ["custom.css"]
html_theme_options = {
    "collapse_navigation": True,
    "navigation_depth": 3,
    "prev_next_buttons_location": "both",
    "sticky_navigation": True,
    "titles_only": True,
}
html_context = {
    "display_github": True,
    "github_user": "lgyEthan",
    "github_repo": "v_ase",
    "github_version": os.environ.get("READTHEDOCS_GIT_IDENTIFIER", "main"),
    "conf_py_path": "/docs/",
}

pygments_style = "sphinx"
pygments_dark_style = "monokai"

latex_documents = [
    ("index", "v_ase.tex", r"v\_ase Documentation", r"v\_ase contributors", "manual"),
]
latex_engine = "xelatex"
epub_title = "v_ase Documentation"
epub_author = author
epub_exclude_files = ["search.html"]

linkcheck_ignore = [
    r"http://127\.0\.0\.1(:\d+)?/.*",
    r"http://localhost(:\d+)?/.*",
    r"https://ase-lib\.org/.*",
    # These DOI resolvers redirect automated HEAD/GET checks to publisher
    # bot-protection pages even though the DOI records are valid.
    r"https://doi\.org/10\.1073/pnas\.1108174108",
    r"https://doi\.org/10\.1103/PhysRevB\.86\.155449",
]
