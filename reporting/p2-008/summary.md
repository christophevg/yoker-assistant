# P2-008 Task Summary

**PR:** https://github.com/christophevg/yoker-assistant/pull/6
**Branch:** feature/p2-008-md-to-html-tool
**Type:** Backend implementation (yoker plugin tool)

## What was implemented

The `md_to_html` yoker tool: a markdown-to-HTML body-fragment converter vendored from `c3/bin/md-to-html.py`, with the security-engineer's XSS fix (HTML-escaping) applied at every interpolation site, exposed via the package's `__YOKER_MANIFEST__` and loadable through `yoker.toml [plugins]`.

### Owner instructions satisfied

1. **"Reuse c3/bin/md-to-html.py"** — vendored convert_markdown + convert_table from c3/bin/md-to-html.py into src/yoker_assistant/tools.py. Provenance comment at tools.py:8-9.
2. **"Don't reinvent the wheel"** — the converter logic is reused, not rewritten. Only the security fix was added.
3. **Security-engineer blocking fix** — _esc() using html.escape(quote=False) applied at all 6 interpolation sites: h1/h2/h3 headers, table cells, list items, paragraphs. Bold substitution runs on escaped text.

### Files created/modified

- `src/yoker_assistant/tools.py` (modified) — vendored converter + _esc helper + md_to_html tool function (143 lines)
- `src/yoker_assistant/__init__.py` (modified) — manifest now registers md_to_html
- `tests/test_md_to_html.py` (new) — 15 unit tests covering all features + XSS/link injection regressions
- `tests/test_import_safety.py` (modified) — updated assertion to verify md_to_html in manifest
- `yoker.toml` (created locally, gitignored) — minimum [plugins] block; yoker.toml.example already documents the config per P1-002

### Key design decisions

- **Vendoring (not importing c3):** c3 is not importable (no package metadata). Vendoring ~120 lines into tools.py is the simplest path that satisfies "reuse c3/bin/md-to-html.py."
- **Plain function (no class):** md_to_html is a plain Python function with Annotated[str, Text(...)] annotation. No wrapper class. The Wrapper Check passes trivially.
- **Body fragment (not full HTML doc):** wrap_email() and main() were NOT vendored. The tool returns an HTML body fragment; email wrapping is the loop's job (P2-005).
- **Security fix is earned behavior:** _esc() adds real escaping, not just forwarding. It is called at 6 sites, avoiding repetition. Not a useless wrapper.

### Non-blocking notes from reviews

- **Security:** S-01 (SECURITY.md) should land before a second tool is added to the manifest. Not blocking P2-008 (first tool exception).
- **Testing:** headers and list items are escape-only (no bold substitution), while paragraphs and table cells escape-then-substitute. This is inherited from c3/bin/md-to-html.py. `# **Bold Header**` won't render bold in headers. Optional regression test recommended.
- **Code review:** 4 low-priority nits, all vendored fidelity or acceptable brittleness — none warrant changes.

## Review cycle

- Stage a (functional): approved — all 5 acceptance criteria met, all 3 owner instructions satisfied, XSS fix verified at all 6 interpolation sites
- Stage b (security): approved — XSS fix correctly applied, no security regressions, no code execution/FS/network
- Stage c (code review): approved — Simplicity Check passes, Wrapper Check passes, code quality 5/5
- Stage c (testing): approved — 15 tests meaningful, behavior-based, comprehensive XSS regressions
- Stage e (make check): PASS — 16 tests, ruff/mypy clean

## Wrapper Check

Passes trivially — plain functions only, no wrapper classes.
