# Code Review: P2-008 — md_to_html yoker tool

**Date:** 2026-07-22
**Reviewer:** Code Reviewer Agent
**Round:** 0
**Verdict:** APPROVED

## Simplicity Check (MANDATORY)

### Owner Instruction 1: "Reuse c3/bin/md-to-html.py"
SATISFIED. Provenance comment at tools.py:8-9. convert_table and convert_markdown logic matches c3/bin/md-to-html.py. wrap_email and main correctly NOT vendored.

### Owner Instruction 2: "Don't reinvent the wheel"
SATISFIED. The converter is reused, not rewritten. The only additions are the _esc() helper and its call sites — the security-engineer's blocking fix.

### Owner Instruction 3: Security-engineer blocking fix (HTML-escape before interpolation)
SATISFIED. _esc() at tools.py:18-20 uses html.escape(s, quote=False). Verified at every interpolation site: h3 (L83), h2 (L87), h1 (L91), table cells (L41), list items (L107), paragraphs (L119-120). Order is correct: escape first, then bold substitution on the escaped text.

**New abstractions added beyond owner's proposal:** none. _esc is the security fix itself, not a new abstraction.

## Wrapper Check

Passes trivially. md_to_html, convert_markdown, convert_table, _esc all plain functions. No class wrapping another class. No decorators. The Annotated[str, Text(...)] annotation is earned behavior (makes it a yoker tool), not pass-through config.

## Design Assessment

Strengths:
- Module docstring clearly bounds scope
- Comments follow WHY-not-WHAT pattern
- __init__.py discipline preserved: only manifest + version + import

## Quality Issues

Critical: None. High: None. Medium: None.

Low Priority (all vendored fidelity, none warrant changes):
- L1: md_to_html and convert_markdown docstrings are identical (intentional — different audiences)
- L2: convert_table thead-on-first-line behavior (vendored fidelity)
- L3: ul wrapping requires trailing newline (vendored fidelity)
- L4: test_convert_markdown_directly uses exact-string assertion (acceptable for deterministic converter)

## Maintainability Score

DRY: 5/5 | Dead Code: 5/5 | Consistency: 5/5 | Abstractions: 5/5 | Configurability: 5/5

Overall: 5/5 — Tight, focused, earned abstractions only.

## Test Coverage

15 tests — comprehensive for the supported subset. Feature coverage: h1/h2/h3, bold, table with separator, list in ul, hr, paragraph. Security regressions: XSS in body/header/list/table-cell, link injection, ampersand escaping, bold-survives-escaping. Each XSS test asserts BOTH "bad substring absent" AND "escaped form present."

## Conclusion

Status: approved. Simplicity Check passes, Wrapper Check passes, code quality is high. The 4 Low-priority nits are all vendored fidelity or acceptable brittleness — none warrant changes.