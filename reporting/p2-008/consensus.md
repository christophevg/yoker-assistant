# P2-008 Cross-Domain Consensus

**Date:** 2026-07-22
**Task:** P2-008 — Implement the markdown→HTML converter as a yoker tool
**Scope:** backend + security

## Domain Agents Invoked

| Agent | Role | Verdict |
|------|------|---------|
| api-architect | Backend design, reuse strategy, tool signature, manifest | APPROVED |
| security-engineer | Blast radius, XSS/injection, self-trust, S-01 prerequisite | APPROVED with one blocking fix |

## Consensus

Both domain agents approve the design. The security-engineer's blocking fix (HTML-escape input before interpolation) is incorporated as a mandatory part of the implementation.

## Design decisions

### Reuse strategy: VENDOR (both agents agree)

c3 is not importable (no package metadata, no pyproject.toml, no importable __init__.py). Importing c3 as a dependency would massively expand the attack surface for ~120 lines of regex. Vendoring `convert_markdown` + `convert_table` into `src/yoker_assistant/` (or a private `_md.py` helper) is the simplest path that satisfies the owner's instruction ("reuse c3/bin/md-to-html.py"). Add a provenance comment.

### Tool function signature (api-architect)

```python
def md_to_html(
  markdown: Annotated[str, Text("Markdown source to convert to HTML")],
) -> str:
  """Convert a markdown string to an HTML body fragment.

  Handles headers, bold, tables, lists, horizontal rules, and paragraphs.
  Returns the HTML body (no <html> wrapper).
  """
  return convert_markdown(markdown)
```

- Plain function, no class, no decorator
- Annotated[str, Text(...)] is the yoker tool guardrail
- First docstring line becomes the LLM-visible description
- Namespace is automatic: yoker_assistant:md_to_html

### Manifest setup (api-architect)

`src/yoker_assistant/__init__.py`:
```python
from yoker.plugins import PluginManifest
from yoker_assistant.tools import md_to_html

__version__ = "0.1.0"
__YOKER_MANIFEST__ = PluginManifest(tools=[md_to_html])
__all__ = ["__YOKER_MANIFEST__", "__version__"]
```

`__init__.py` discipline: only manifest + version + the import needed to populate the manifest. No Agent, no loop, no email logic.

### Plugin registration (api-architect)

No yoker.toml exists yet. P2-008 must create one with the minimum [plugins] block:
```toml
[plugins]
enabled = true
packages = ["yoker_assistant"]

[plugins.trusted]
yoker_assistant = true
```

### BLOCKING security fix (security-engineer)

The vendored converter MUST HTML-escape all input text before interpolating into HTML tags. The original c3/bin/md-to-html.py does not escape &, <, > — this is an XSS/injection vector because the HTML output is used as html_body= in reply_email(...).

Fix: escape (&, <, >) in each input line's raw text content before any HTML interpolation, then apply the bold regex on the escaped text. The ** marker is unaffected by HTML escaping, so bold still works.

```python
from html import escape

def _esc(s: str) -> str:
    return escape(s, quote=False)  # escapes &, <, >
```

Apply to all interpolation sites: headers, paragraphs, list items, table cells, bold substitution. Table separator-line detection runs on the raw cell before escaping.

Keep wrap_email's title hardcoded — do not expose it as an agent-controlled parameter without escaping.

### S-01 (security-engineer — related, not blocking)

S-01 (SECURITY.md describing the manifest review process) does NOT block P2-008. md_to_html is the FIRST tool added to the manifest — S-01's priority rationale is "land before Phase B so the review process exists before any second tool is added." The first tool is the exception because it IS the showcase example. S-01 must land before a second tool is added.

## Wrapper Check

**Passes trivially.** md_to_html is a plain Python function. The vendored helpers (convert_markdown, convert_table) are plain functions. No class wrapping another class. No indirection. The design is a pure in-memory CPU-bound string transform.

## Simplicity Principle

- Owner instruction: "reuse c3/bin/md-to-html.py" — the plan vendors the converter logic, not a new converter. Simpler path confirmed by both agents.
- Owner instruction: "don't reinvent the wheel" — the plan reuses the existing logic with the security fix applied. No new converter.
- Security-engineer's blocking fix is earned by the XSS finding — it adds real behavior (escaping) beyond simple forwarding. Not a useless wrapper.
- No new abstractions, no wrapper classes, no indirections. Plain functions only.

## Open items for the implementation plan

1. The api-architect flagged that no yoker.toml exists yet — P2-008 must create one with the minimum [plugins] block. (The agent needs more config to actually run, but the minimum [plugins] block satisfies P2-008's acceptance criterion. The fuller config is a separate concern.)
2. The converter handles a limited markdown subset (no code blocks, links, blockquotes, nested lists) — the tool docstring must reflect that, not over-promise.
3. Unit test fixture: one representative fixture covering headers/table/list/bold/hr is enough.