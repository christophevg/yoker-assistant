"""Sphinx configuration for yoker-assistant documentation."""

import os
import sys

sys.path.insert(0, os.path.abspath("../src"))

project = "yoker-assistant"
copyright = "2026, Christophe VG"
author = "Christophe VG"

extensions = [
  "myst_parser",
  "sphinx.ext.autodoc",
  "sphinx.ext.napoleon",
  "sphinx.ext.viewcode",
  "sphinx.ext.intersphinx",
]

templates_path = ["_templates"]
exclude_patterns = ["_build", "Thumbs.db", ".DS_Store"]

html_theme = "sphinx_rtd_theme"
html_static_path = ["_static"]

# MyST configuration
myst_enable_extensions = ["colon_fence", "deflist"]

# Autodoc settings
autodoc_member_order = "bysource"

# Intersphinx mappings
intersphinx_mapping = {
  "python": ("https://docs.python.org/3", None),
}