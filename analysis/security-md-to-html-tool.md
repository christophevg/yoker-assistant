# Security Review: P2-008 — md_to_html yoker tool

**Date:** 2026-07-22
**Reviewer:** security-engineer
**Verdict:** APPROVED with one blocking fix

## Executive Summary

The conversion logic in `c3/bin/md-to-html.py` is a pure-function, regex-based converter with no code execution, no filesystem access, and no network calls — its standalone blast radius is minimal. However, it performs no HTML escaping or output sanitization, so any raw HTML embedded in the markdown input passes straight through into the email body. Because the output is destined for `html_body=` in `reply_email(...)`, this is an injection/XSS vector against email recipients (medium severity, mitigated in part by email-client script stripping but not by CSS/link-based phishing). The self-trust blast radius for `md_to_html` alone is low; S-01 should not block this first tool but must land before any second tool is added.

## 1. Security posture of c3/bin/md-to-html.py

- Imports only `re` and `sys`.
- `convert_markdown(md: str) -> str`: hand-rolled line-by-line parser for headers, tables, lists, horizontal rules, bold, and paragraphs. No markdown library.
- `wrap_email(html, title="Activity Report")`: wraps output in a DOCTYPE + style template with hardcoded CSS.
- `main()`: reads stdin, converts, prints.

Threat surface:
- No arbitrary code execution (no eval, exec, subprocess, os.system, compile, pickle, importlib)
- No filesystem access beyond sys.stdin.read() in main()
- No network calls (no socket, urllib, requests, http, smtplib)
- No markdown library dependency (no supply-chain exposure)
- No template engine (plain f-string with hardcoded title/html interpolation)

Standalone blast radius: very small. Pure str -> str transform with no side effects.

## 2. XSS / injection risk — the real finding

**Medium severity (CVSS ~5.5). OWASP A03 (Injection — XSS in the email output channel).**

The converter never escapes HTML special characters (<, >, &, ", ') in the input before interpolating it into HTML tags. Every interpolation site is an injection sink:

- Headers: f"<h1>{line[2:].strip()}</h1>" — raw header text
- Table cells: f"<th>{cell}</th>", f"<td>{cell}</td>"
- List items: f"<li>{line[2:].strip()}</li>"
- Paragraphs: f"<p>{line}</p>"
- Bold substitution: re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', line) — captured group is unescaped input

Concrete exploit: markdown input `# <script>alert(document.cookie)</script>` produces `<h1><script>alert(document.cookie)</script></h1>`.

Data flow: inbound email content (untrusted) → agent composes markdown reply → md_to_html converts → HTML string passed as html_body= to reply_email → recipient's email client renders the HTML.

Realistic threats:
- Script tags — most modern email clients strip <script>, so direct JS execution is largely mitigated. This is why severity is Medium, not High.
- CSS injection — <style> blocks and inline style= attributes are NOT universally stripped; attackers can disguise phishing UI, hide content, or re-skin the email.
- Link-based phishing — <a href="https://evil.example">View invoice</a> passes through untouched. Highest-residual-risk vector.
- Image-based tracking/beaconing — <img src="https://evil.example/track.png"> passes through, enabling read-receipt tracking.

## 3. Self-trust blast radius

For md_to_html specifically:
- Capability granted: pure str -> str conversion. No FS, no network, no subprocess, no access to yoker internals, no access to email-sending primitives.
- Auto-trust safety of THIS tool: acceptable. Even if maliciously invoked, the worst it can do is return a malicious HTML string — harm only materializes if the caller feeds that string to reply_email.
- The systemic risk is not the tool, it's the auto-trust model: every future tool added to __YOKER_MANIFEST__ inherits trust with no review gate. That is exactly what S-01 is designed to address.

## 4. S-01 prerequisite assessment

No — not blocking for P2-008, but blocking for the next tool after it.

- md_to_html is the FIRST tool added to the manifest (P1-001 shipped an empty manifest). S-01's stated priority rationale is "land before Phase B so the review process exists before any second tool is added to the manifest." The first tool is the exception because it IS the showcase example.
- md_to_html's capability is bounded and easily reviewable inline. A full S-01 process doc would not change the outcome of this specific review.
- However, S-01 must land before a second tool is added.

## 5. Reuse strategy

- Importing c3 as a dependency: rejected. c3 is a large agent framework. Adding it as a runtime dependency massively expands the attack surface and supply-chain footprint for ~120 lines of regex. Fails the Simplicity Principle.
- Vendoring the converter: recommended. Self-contained (two functions, one stdlib import, no c3 coupling). Vendoring ~120 lines into src/yoker_assistant/ is the right-sized approach. The vendored code must be fixed for the XSS gap.

## 6. Recommended security guardrails

**Blocking fix for P2-008 — HTML-escape input before interpolation.**

Escape &, <, > (and optionally " ') in each input line's raw text content before any HTML interpolation, then apply the bold regex on the escaped text. The ** marker is unaffected by HTML escaping, so bold still works; the <strong>/</strong> tags are added by the converter, not from input, so they are safe.

```python
from html import escape

def _esc(s: str) -> str:
    return escape(s, quote=False)  # escapes &, <, >
```

Table cells: apply escaping after separator-line detection (which runs on the raw cell).

wrap_email's title parameter: currently hardcoded to "Activity Report". Keep it hardcoded — do not expose it as an agent-controlled parameter without escaping.

Optional defense-in-depth (not blocking):
- Run the final HTML through a sanitizer such as bleach with an allowlist. Adds a dependency; not strictly necessary if input escaping is correct. Per Simplicity Principle, prefer the simpler input-escaping fix.

## 7. Positive observations

- No eval/exec, no subprocess, no filesystem mutation, no network, no pickle, no template engine with auto-rendering
- No third-party markdown library — removes supply-chain CVE risk
- yoker.toml.example already documents the self-trust blast radius clearly
- The dual-mode / import-safe discipline in __init__.py prevents circular-import-driven side effects
- The tool capability is genuinely bounded

## Findings summary

| Finding | Classification | Action |
|---|---|---|
| XSS / HTML injection in converter output (no escaping) | Blocking | Fix in P2-008 before merge |
| S-01 (manifest review process) not yet landed | Related | Not blocking P2-008 (first tool), blocking for the next tool |
| Self-trust auto-trusts all future tools with no per-call gate | New | Tracked by S-01; no action in P2-008 beyond pinning versions |
| Vendoring vs importing c3 as a dependency | Blocking | Vendor the converter, do NOT add c3 as a dep |