# P2-008 Functional Review

**Task:** Implement the markdown→HTML converter as a yoker tool
**Round:** 0
**Verdict:** approved

## Acceptance Criteria (TODO.md L271-275)

| # | Criterion | Status | Evidence |
|---|-----------|--------|----------|
| 1 | Loadable as `yoker_assistant:md_to_html` by the package's own agent | PASS | `__init__.py:20` declares `PluginManifest(tools=[md_to_html])`; `yoker.toml` registers the package as trusted plugin |
| 2 | Loadable by an external yoker consumer | N/A (P2-009 scope) | Explicitly out of scope per task brief |
| 3 | Agent can call it during `process()` | PASS | `md_to_html` is a plain function in the manifest; `Annotated[str, Text(...)]` signature matches yoker tool convention |
| 4 | Given a markdown string it returns an HTML string | PASS | `md_to_html` returns `convert_markdown(markdown)` which returns `str`; `test_md_to_html_is_callable_and_returns_str` verifies |
| 5 | Unit-tested with a representative markdown fixture | PASS | `MARKDOWN_FIXTURE` exercises h1/h2/h3, bold, table with separator, list, hr, paragraph; 15 tests total |

## Owner-Stated Instructions

### 1. "Reuse c3/bin/md-to-html.py" — SATISFIED

Provenance comment present at `tools.py:8-9`:
```
# Vendored from c3/bin/md-to-html.py — reuses the existing conversion logic
# per owner instruction. HTML-escaping fix applied for XSS prevention.
```

Logic comparison:
- `convert_table` (c3/bin L18-51 vs tools.py L23-59): identical structure — cell split, separator skip on raw cells, header/body branching, `<th>`/`<td>` emission. Only diff: escaping added at interpolation.
- `convert_markdown` (c3/bin L54-119 vs tools.py L62-132): identical control flow — hr, h3/h2/h1, table detection, list items, empty line, paragraph, `<ul>` wrapping post-process. Only diff: escaping added at interpolation.
- `wrap_email` and `main` correctly NOT vendored (out of scope: email wrapping is P2-005's job). Stated in module docstring.

### 2. "Don't reinvent the wheel" — SATISFIED

The converter is reused, not rewritten. The only additions are the `_esc()` helper and its call sites — the security-engineer fix. No new abstractions, no wrapper classes, no indirections.

### 3. Security-engineer blocking fix: `_esc()` at EVERY interpolation site — SATISFIED

`_esc()` helper at `tools.py:18-20` uses `html.escape(s, quote=False)` (escapes `&`, `<`, `>`; leaves quotes alone — appropriate since attributes are not interpolated, only tag bodies).

Verified call sites:

| Site | Line | Escaped? |
|------|------|----------|
| h3 header | 83 | `_esc(line[4:].strip())` |
| h2 header | 87 | `_esc(line[3:].strip())` |
| h1 header | 91 | `_esc(line[2:].strip())` |
| Table cell (before bold sub) | 41 | `re.sub(..., _esc(c))` |
| List item | 107 | `_esc(line[2:].strip())` |
| Paragraph (before bold sub) | 119-120 | `_esc(line)` then `re.sub` on escaped text |
| Bold substitution | 41, 120 | Applied to ALREADY-escaped text — `**` survives escaping, `<strong>` tags are ours, not from input |

Separator-line detection (line 35) correctly runs on RAW cells (`raw_cells`) before escaping, so the `{"-", ":", " "}` set check is not confused by `&` → `&amp;` transformation. Comment at L33-34 documents this ordering rationale.

No interpolation site is missed. The bold-substitution-after-escaping pattern is the correct order: it prevents an attacker from injecting `<strong>` via input (input `<` becomes `&lt;` before the regex runs), while preserving the `**` marker which is ASCII-safe under `html.escape(quote=False)`.

## Wrapper Check — PASS

- `md_to_html` — plain function
- `convert_markdown` — plain function
- `convert_table` — plain function
- `_esc` — plain function

No class wrapping another class. No decorator on `md_to_html`. No `Tool` subclass. The function is registered directly in `PluginManifest(tools=[...])`.

## `__init__.py` Discipline — PASS

`__init__.py` contains ONLY:
- Module docstring (L1-12)
- `from yoker.plugins import PluginManifest` (L14)
- `from yoker_assistant.tools import md_to_html` (L16)
- `__version__ = "0.1.0"` (L18)
- `__YOKER_MANIFEST__ = PluginManifest(tools=[md_to_html])` (L20)
- `__all__` (L22)

No `Agent` construction, no loop logic, no email logic, no side effects at import time. Import-safety preserved.

## Test Coverage — PASS

`tests/test_md_to_html.py` (15 tests):

Feature coverage:
- Headers h1/h2/h3: `test_headers_h1_h2_h3`
- Bold: `test_bold_text`, `test_bold_survives_escaping`
- Table with separator: `test_table_with_separator` (verifies separator line does NOT leak as `<td>---</td>`)
- List wrapped in `<ul>`: `test_list_items_wrapped_in_ul`
- Horizontal rule: `test_horizontal_rule`
- Paragraph: `test_paragraph`
- Direct `convert_markdown`: `test_convert_markdown_directly`

Security regressions:
- XSS in body: `test_xss_script_tag_is_escaped`
- XSS in header: `test_xss_script_in_header_is_escaped`
- XSS in list item: `test_xss_script_in_list_item_is_escaped`
- XSS in table cell: `test_xss_script_in_table_cell_is_escaped`
- Link injection: `test_link_injection_is_escaped`
- Ampersand escaping: `test_ampersand_is_escaped`

## `test_import_safety.py` — PASS

Updated assertion (L13-17) verifies `md_to_html` appears in `__YOKER_MANIFEST__.tools` by `__name__`. Correctly handles both function and Tool-wrapper cases via `getattr(t, "__name__", t.__class__.__name__)`.

## yoker.toml / yoker.toml.example — PASS

- `yoker.toml.example` (committed) documents the `[plugins]` block, `[plugins.trusted]` self-trust blast radius, and references P2-008's plugin registration. Clear warning against copying to `./yoker.toml`.
- `yoker.toml` (gitignored per `.gitignore:28`) exists for local dev with minimal `[plugins]` block registering `yoker_assistant` as trusted.
- `.gitignore:29` explicitly `!yoker.toml.example` — example stays tracked.

## Simplicity Principle — PASS

- Owner's "reuse c3/bin/md-to-html.py" honored: vendored, not rewritten.
- Owner's "don't reinvent the wheel" honored: only the security fix was added.
- `_esc()` earns its place: adds real escaping at 6 interpolation sites, not just forwarding.
- No new abstractions beyond what the plan specified.
- No wrapper classes, no decorators, no indirections.

## Notes (non-blocking)

- The `<ul>` wrapping regex (`tools.py:130`) operates on already-escaped `<li>` content, so it cannot be confused by attacker-injected `</li>` — escaping runs first at L107, regex runs after the join at L127. Order is correct.
- `convert_table` emits `<thead>` on the first non-separator line regardless of position; this matches c3/bin behavior (vendored fidelity) and is not a regression.

## Verdict

**approved** — all 5 acceptance criteria met (criterion 2 correctly deferred to P2-009), all 3 owner instructions satisfied, security-engineer fix verified at every interpolation site, no wrappers introduced, `__init__.py` discipline preserved, test coverage comprehensive including XSS regressions.