# API Design Analysis — Task P2-008 (md_to_html yoker tool)

**Date:** 2026-07-22
**Task:** P2-008 — Implement the markdown→HTML converter as a yoker tool
**Reviewer:** API Architect Agent
**Related documents:**
- `TODO.md` lines 245-276 (P2-008 entry)
- `analysis/functional.md` (custom bounded tool requirement)
- `c3/bin/md-to-html.py` (existing conversion logic to reuse)
- `pyproject.toml`, `src/yoker_assistant/__init__.py`, `src/yoker_assistant/tools.py`

## Summary

P2-008 adds one custom yoker tool, `md_to_html`, defined in this package
(`yoker_assistant`) and registered via `yoker.toml [plugins]`. The tool
wraps the existing `c3/bin/md-to-html.py` conversion logic so the agent can
convert markdown to HTML at runtime. This analysis confirms the reuse
strategy, the function signature, the manifest exposure, the plugin
registration, and the `__init__.py` discipline. The design is minimal: one
plain function in `tools.py`, one line in `__init__.py`'s manifest, and one
`yoker.toml` block.

## Findings on `c3/bin/md-to-html.py`

The file at `/Users/xtof/Workspace/agentic/c3/bin/md-to-html.py` is a
standalone CLI script (201 lines, `#!/usr/bin/env python3` shebang). It is
NOT a Python package module.

**What it does:** a line-based markdown→HTML converter for a specific
subset of markdown used by the git-activity-report. No third-party
markdown library — only `re` and `sys`.

**Public functions:**
- `convert_table(lines: list[str]) -> list[str]` — converts a table block
  (pipe-delimited rows, separator row skipped, bold-in-cells handled) to
  HTML `<table>` lines.
- `convert_markdown(md: str) -> str` — the core converter. Handles `#`/
  `##`/`###` headers, `---` horizontal rules, tables (detected by `|` in
  current + next line), `- ` list items (wrapped in `<ul>` post-hoc via
  regex), `**bold**`, empty lines, and paragraphs. Returns HTML body
  fragment (no `<html>` wrapper).
- `wrap_email(html: str, title: str = "Activity Report") -> str` — wraps a
  body fragment in a full HTML document with embedded CSS styling.
- `main()` — reads stdin, converts, wraps, prints. CLI entry point only.

**Output format:** `convert_markdown` returns a body fragment
(`<h1>...</h1><p>...</p><ul>...</ul><table>...</table>`). `wrap_email`
returns a full `<!DOCTYPE html>` document. The script's `main()` always
calls `wrap_email` before printing.

**Reuse scope:** P2-008's tool needs the body-fragment conversion for agent
use (the agent produces markdown, the consumer decides whether to wrap).
The agent does not need the email CSS wrapper baked in; if a caller wants
the full email document, that's a presentation concern. I recommend the
tool expose `convert_markdown` only and keep `wrap_email` out of scope. If
the owner wants the wrapper exposed too, it can be added as a second
parameter (`wrap: bool = False`) or a second tool — but that's not required
by P2-008 and is out of scope unless the owner says otherwise.

## Reuse strategy: vendor (recommended)

**Owner instruction (PR #5 review):** reuse `c3/bin/md-to-html.py`. The
three options:

| Option | Viable? | Notes |
|--------|---------|-------|
| (a) Import `c3` as a dependency | **No** | `c3/` has no `pyproject.toml`, no `setup.py`, no `__init__.py` at the repo root. It is not a Python package — it's a skills/agents repo with `bin/` scripts. Not installable, not importable. |
| (b) Vendor the conversion logic into `src/yoker_assistant/tools.py` | **Yes (recommended)** | Copy the core logic. Keeps the package self-contained, no new dependency, no cross-repo coupling. Matches the simplicity principle. |
| (c) Extract into a shared library | **No** | Premature. Adds a package for ~120 lines of regex-based conversion that the owner explicitly wants to reuse as-is. |

**Recommendation: vendor.** Copy `convert_markdown` and `convert_table`
into `src/yoker_assistant/tools.py` (or a private helper module
`_md.py` imported by `tools.py`). Add a one-line attribution comment
(`# Adapted from c3/bin/md-to-html.py`) so provenance is preserved.

**Deviation note:** The owner's instruction is "reuse." Vendoring IS
reuse — it reuses the exact conversion logic, not a reimplementation. The
only deviation from a strict "import" reading is that `c3` is not
importable, so we copy. This is the simplest path that satisfies the
instruction and keeps the package self-contained.

## Tool function signature

`src/yoker_assistant/tools.py`:

```python
"""Custom yoker tools defined by this package."""

from typing import Annotated

from yoker.tools.annotations import Text

from yoker_assistant._md import convert_markdown


def md_to_html(
  markdown: Annotated[str, Text("Markdown source to convert to HTML")],
) -> str:
  """Convert a markdown string to an HTML body fragment.

  Handles headers, bold, tables, lists, horizontal rules, and paragraphs.
  Returns the HTML body (no <html> wrapper).
  """
  return convert_markdown(markdown)
```

Notes:
- `Annotated[str, Text(...)]` is the exact guardrail pattern yoker's
  `build_tool_spec` introspects (see
  `/Users/xtof/Workspace/agentic/yoker/src/yoker/tools/annotations.py` and
  `schema.py`). `Text` is the right marker for plain-text input (no path/
  url/query guardrail).
- The first docstring line becomes the tool description shown to the LLM
  (`_resolve_description` in `schema.py`).
- Plain function — no class, no decorator needed. The `tool()` decorator
  is optional and only for name/description overrides; we don't need it.
- If vendoring inline (no `_md.py` helper), put `convert_markdown` and
  `convert_table` directly in `tools.py` and call locally. Either layout
  is fine; the `_md.py` split keeps `tools.py` focused on the tool surface.

The yoker loader namespaces the tool as `yoker_assistant:md_to_html`
automatically: `load_plugin("yoker_assistant")` calls
`build_tool_spec(tool, namespace="yoker_assistant")`, producing a tool
named `yoker_assistant__md_to_html` in the LLM schema (`__` replaces `:`).
The acceptance criterion "loadable as `yoker_assistant:md_to_html`" is
satisfied by this mechanism — no manual namespacing in the function.

## Manifest exposure

`src/yoker_assistant/__init__.py` (current state already correct except
the empty `tools=[]`):

```python
from yoker.plugins import PluginManifest
from yoker_assistant.tools import md_to_html

__version__ = "0.1.0"

__YOKER_MANIFEST__ = PluginManifest(tools=[md_to_html])

__all__ = ["__YOKER_MANIFEST__", "__version__"]
```

## `__init__.py` discipline

Confirmed: `__init__.py` contains ONLY the manifest, the `__version__`
constant, and the imports needed to populate the manifest. No `Agent`
construction, no loop, no email logic, no `process()`. Those live in
`__main__.py`, `loop.py`, `agent.py` (already the case — see
`src/yoker_assistant/agent.py` and `loop.py` placeholders). The manifest
import (`from yoker_assistant.tools import md_to_html`) is a pure import
with no side effects beyond defining the function object. **Passes.**

## Plugin registration via `yoker.toml [plugins]`

The project has no `yoker.toml` yet. P2-008 requires one (or updates to
an existing one) so the package's own agent loads itself as a plugin.
Required block (at the project root, next to `pyproject.toml`):

```toml
[plugins]
enabled = true
packages = ["yoker_assistant"]

[plugins.trusted]
yoker_assistant = true
```

Rationale (verified against
`/Users/xtof/Workspace/agentic/yoker/src/yoker/config/__init__.py` and
`plugins/security.py`):
- `[plugins] enabled = true` is the global opt-in (default false).
- `packages = ["yoker_assistant"]` adds the package to the load list.
- `[plugins.trusted] yoker_assistant = true` skips the interactive trust
  prompt for this package (the two-level security model in
  `check_plugin_allowed`).
- No `plugins=()` arg to `Agent` — registration is config-driven, per the
  task spec. The agent's own startup (in `__main__.py`/`loop.py`) must not
  pass `plugins=` programmatically.

## Concerns

1. **No yoker.toml exists yet.** P2-008 implicitly requires creating one.
   Confirm with the owner whether a broader `yoker.toml` (backend,
   context, permissions, etc.) is in scope for P2-008 or a separate task.
   The minimum block above is sufficient to satisfy the acceptance
   criterion ("loadable by the package's own agent"), but the agent will
   also need a backend and context manager configured to actually run.
   Flag this as a cross-task dependency, not a P2-008 blocker.

2. **Vendored code drift.** `c3/bin/md-to-html.py` may evolve; the
   vendored copy will not track it. Acceptable for a ~120-line
   regex converter, but add the provenance comment so a future maintainer
   can sync if needed.

3. **Converter scope.** `convert_markdown` handles a limited markdown
   subset (no code blocks, no inline code, no links, no blockquotes, no
   nested lists). This is fine for the agent's email-report use case but
   not a general markdown converter. The tool description should say
   "handles headers, bold, tables, lists, horizontal rules, paragraphs"
   so the LLM doesn't over-promise. (Already reflected in the proposed
   docstring.)

4. **List-wrapping regex.** `convert_markdown` wraps consecutive `<li>` in
   `<ul>` via a post-hoc regex (`re.sub(r'(<li>.*?</li>\n)+', ...)`). This
   is single-line-greedy and will mis-wrap if `<li>` appears in a
   non-list context (it won't, given the converter's own output). Acceptable
   for the vendored scope; no change needed.

5. **Unit test fixture.** Acceptance requires "unit-tested with a
   representative markdown fixture." The fixture should exercise headers,
   a table, a list, bold, and an `<hr>` at minimum — covering every branch
   in `convert_markdown`. A single representative fixture is enough; do
   not test each element in isolation (the converter is small and the
   branches are simple).

## Wrapper Check

**Passes trivially.** The design introduces no class that wraps another
class. `md_to_html` is a plain Python function. The vendored
`convert_markdown`/`convert_table` are plain functions. No
`Client`/`AsyncClient` pattern, no wrapper layer, no I/O class. The tool
is a pure in-memory CPU-bound string transform — async-first is not
required (per the async-first rule's "CPU-bound computations: pure sync
OK" exception).

## RESTful check

Not applicable — this is a yoker tool (in-process function), not an HTTP
endpoint. No REST/RPC concern.

## Action items

- [ ] Create `src/yoker_assistant/tools.py` with `md_to_html` and the
      vendored `convert_markdown`/`convert_table` (or split into
      `_md.py`). Add provenance comment.
- [ ] Update `src/yoker_assistant/__init__.py` manifest to
      `PluginManifest(tools=[md_to_html])` with the import.
- [ ] Create `yoker.toml` at project root with the `[plugins]` block above
      (confirm with owner whether a fuller config is in scope here).
- [ ] Add `tests/test_tools_md_to_html.py` with one representative
      markdown fixture covering headers/table/list/bold/hr.
- [ ] Confirm `make check` passes (mypy strict + ruff + pytest).

## Verdict

**Approved.** The design is minimal, satisfies the owner's "reuse
c3/bin/md-to-html.py" instruction via vendoring (the only viable path
since `c3` is not an importable package), keeps `__init__.py` disciplined,
registers via `yoker.toml [plugins]` (not programmatic), and passes the
Wrapper Check trivially. Implement per the signatures above.