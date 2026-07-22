# P2-008 Testing Review

**Date:** 2026-07-22
**Task:** P2-008 — Implement the markdown→HTML converter as a yoker tool
**Round:** 0
**Files reviewed:**
- `tests/test_md_to_html.py` (15 tests)
- `tests/test_import_safety.py` (1 test, updated assertion)
- `src/yoker_assistant/tools.py` (tool under test)

## Verdict: approved

Test coverage is adequate and the tests are meaningful. The suite is
behavior-based (asserts on HTML output, not internals), well-named, and
covers every markdown feature supported by the converter plus the XSS
regressions from the security-engineer review. A few minor edge cases are
noted below as optional improvements — none block merge.

## 1. Coverage assessment

### Markdown features — all covered

| Feature | Test | Status |
|---------|------|--------|
| Headers (h1/h2/h3) | `test_headers_h1_h2_h3` | Covered |
| Bold (`**...**`) | `test_bold_text` | Covered |
| Table + separator | `test_table_with_separator` | Covered (also asserts separator line does not leak as a row) |
| List (`<ul><li>`) | `test_list_items_wrapped_in_ul` | Covered |
| Horizontal rule | `test_horizontal_rule` | Covered |
| Paragraph | `test_paragraph` | Covered |

### XSS / injection regressions — robust

- `test_xss_script_tag_is_escaped` — body script tag
- `test_xss_script_in_header_is_escaped` — header context
- `test_xss_script_in_list_item_is_escaped` — list context
- `test_xss_script_in_table_cell_is_escaped` — table cell context
- `test_link_injection_is_escaped` — `<a href=...>` injection
- `test_ampersand_is_escaped` — bare `&` becomes `&amp;`
- `test_bold_survives_escaping` — `**` markers survive escaping, `<tag>` is escaped

Each XSS test asserts both the negative (raw tag absent) and the positive
(escaped form present), which is the right pattern — a test that only
asserts `"<script>" not in html` could pass by simply dropping the text.

### Integration — covered

`test_import_safety.py::test_package_imports` asserts
`"md_to_html" in tool_names` against `__YOKER_MANIFEST__.tools`, so the
tool is verified as registered and callable through the plugin manifest.
No side-effect import check is also performed (manifest presence is the
proxy). This is the correct integration seam for a yoker tool.

### Behavior vs. implementation — behavior-based

Every test asserts on the HTML string returned by `md_to_html` /
`convert_markdown`. No test peeks at private helpers (`_esc`,
`convert_table` internals, regex shapes). The suite would survive a
rewrite of the converter as long as the HTML contract held.

## 2. Missing test scenarios (non-blocking)

These are edge cases that could regress in a future refactor. Adding them
would be nice-to-have, not required for this round.

| Scenario | Risk | Notes |
|----------|------|-------|
| Empty input `md_to_html("")` | Low | Returns empty string; not asserted. One-liner would lock the contract. |
| Whitespace-only input | Low | `"   \n  \n"` — current impl emits empty lines; not asserted. |
| Header with bold `# **Bold Header**` | Low-medium | The header path escapes the whole line *before* bold substitution (see `tools.py` lines 82-91), so `**` in a header is NOT converted to `<strong>`. This is a real behavioral quirk worth a regression test to pin down — either it should work (and the impl is buggy) or it should be documented as not supported. |
| Table with empty cells | Low | `convert_table` drops empty cells via `if c.strip()`; a `| | |` row would produce `<tr></tr>`. Not asserted. |
| Nested bold `**bold **text**` | Low | Non-greedy `.+?` makes this produce `<strong>bold </strong>text**`. Edge case, unlikely in real markdown. |
| Very long input | Low | No perf concern at expected scale. |
| Mixed content in one input | Covered | `MARKDOWN_FIXTURE` already exercises headers + table + list + hr + paragraph in a single call. |

Of the above, **header with bold** is the one I'd most recommend adding,
because the current behavior is subtly inconsistent: bold works in
paragraphs and table cells (those paths escape-then-substitute) but not
in headers or list items (those paths escape-only). A test pinning the
current behavior — whatever the owner decides it should be — would
prevent a future refactor from silently changing it.

## 3. Test quality

- No `assert True`, no `pass`, no empty bodies.
- No over-mocking — no mocks at all; tests call the real function.
- No framework-internals tests.
- No duplicate assertions across tests.
- One fixture (`MARKDOWN_FIXTURE`) is reused across 7 tests — justified,
  single shared input with diverse assertions.
- `test_convert_markdown_directly` uses an exact-string assertion
  (`html == "<h1>Hello</h1>"`); acceptable here because the HTML contract
  for a single header is the public behavior, not a presentation detail.

## 4. Test naming and organization

Names follow `test_{feature}_{scenario}` consistently. File is organized
as: shared fixture → happy-path feature tests → XSS regression tests →
converter-direct test. Logical and readable.

## 5. Recommendation

Approve as-is. Optionally add one test for header-with-bold behavior to
pin the current escape-only semantics (or expose the inconsistency for
owner decision). The empty-input and table-empty-cell cases are
low-value and can be skipped without risk.