# Security Review: P2-008 (md_to_html tool)

**Reviewer:** security-engineer
**Round:** 0
**Files reviewed:**
- `src/yoker_assistant/tools.py` (vendored converter + `_esc` helper + `md_to_html` tool)
- `src/yoker_assistant/__init__.py` (plugin manifest)
- `yoker.toml.example` (self-trust documentation)

**Verdict:** approved

## Executive Summary

The blocking XSS/injection gap identified in Phase 3 review of `c3/bin/md-to-html.py`
is correctly fixed in the vendored copy. Every HTML interpolation site wraps user
input through `_esc()` (which calls `html.escape(s, quote=False)`) BEFORE the text
touches an HTML tag. The bold `**...**` substitution runs on already-escaped text,
so the `<strong>` tags are the only markup introduced by the converter. No
filesystem, network, or code-execution primitives are reachable from the tool.
Manifest registers exactly one tool. Self-trust blast radius is documented in
`yoker.toml.example`.

## 1. XSS fix verification (BLOCKING) — PASS

### `_esc` helper
`tools.py:18-20` defines `_esc(s)` returning `html.escape(s, quote=False)`, which
escapes `&`, `<`, `>`. `quote=False` is correct here: the output is interpolated
into element content, not into an attribute, so single/double-quote escaping is
not needed and would only corrupt prose.

### Interpolation site audit (every f-string wrapping user input)

| Site | Line | Escaped? |
|------|------|----------|
| `<th>{cell}</th>` | 47 | yes — `cell` from `re.sub(..., _esc(c))` on line 41 |
| `<td>{cell}</td>` | 54 | yes — same path as `<th>` |
| `<h3>{...}</h3>` | 83 | yes — `_esc(line[4:].strip())` inline |
| `<h2>{...}</h2>` | 87 | yes — `_esc(line[3:].strip())` inline |
| `<h1>{...}</h1>` | 91 | yes — `_esc(line[2:].strip())` inline |
| `<li>{...}</li>` | 107 | yes — `_esc(line[2:].strip())` inline |
| `<p>{escaped_line}</p>` | 123 | yes — `escaped_line = _esc(line)` then bold sub on escaped (line 119-120) |
| `<hr>` | 77 | n/a — no user input |
| `<ul>...{m.group(0)}...</ul>` | 130 | n/a — `m.group(0)` is a run of already-escaped `<li>...</li>` lines produced by the escaped path above |

No interpolation site is missed.

### Bold substitution runs on ESCAPED text

Both sites that apply the `**(.+?)**` → `<strong>\1</strong>` regex run it on
already-escaped text:

- Table cells: `_esc(c)` is the third argument to `re.sub` (line 41).
- Paragraphs: `escaped_line = _esc(line)` precedes the `re.sub` call (lines 119-120).

The `**` marker is not modified by `html.escape`, so bold still works. The
`<strong>`/`</strong>` tags come from the converter's own replacement string,
never from user input. The `\1` capture is a slice of already-escaped text, so an
input like `**<script>**` becomes `**&lt;script&gt;**` → `<strong>&lt;script&gt;</strong>` — safe.

### Separator-line detection on RAW cells (correct)

`convert_table` line 35 checks `set(c) <= {"-", ":", " "}` on the RAW cell before
escaping. The comment at lines 33-34 documents the rationale. This is correct:
escaping does not transform `-`, `:`, or space, so the check is equivalent either
way, but running it on raw input is cleaner and matches the original tool's
behavior. No security impact.

## 2. No code execution / FS / network — PASS

`grep -nE "open\(|pathlib|socket|urllib|requests|subprocess|os\.system|eval\(|exec\("`
on `tools.py` returned **NONE FOUND**.

Imports (`tools.py:11-15`):
- `re` — stdlib
- `html.escape` — stdlib
- `typing.Annotated` — stdlib
- `yoker.tools.annotations.Text` — yoker SDK annotation helper

No filesystem, network, or subprocess primitives. No `eval`/`exec`. No dynamic
import. The module is a pure string transformer.

## 3. Tool capability bounded — PASS

`md_to_html(markdown: str) -> str` (`tools.py:135-143`) is a pure `str -> str`
transform. It calls `convert_markdown` which builds an HTML fragment in memory
and returns it. No side effects: no I/O, no globals mutated, no callbacks
invoked. Even if an attacker controlled the entire input string, the worst
observable effect is an HTML fragment contained in the return value — which is
itself escaped. The tool cannot send email, touch the filesystem, or reach the
network.

## 4. Manifest safety — PASS

`__init__.py:20`: `__YOKER_MANIFEST__ = PluginManifest(tools=[md_to_html])`.

Exactly one tool registered. No other symbols from `tools.py` are exposed via
the manifest. `__all__` (line 22) only exports `__YOKER_MANIFEST__` and
`__version__`. `convert_markdown` and `convert_table` are module-private helpers
not re-exported.

`__init__.py` is import-safe per its docstring: no Agent construction, email
loop, or side effects at import time. Confirmed by reading the full file (22
lines, no executable side effects beyond defining the manifest).

## 5. Self-trust blast radius — PASS (documented)

`yoker.toml.example` lines 12-15 document the blast radius explicitly:

> Self-trust blast radius: marking [plugins.trusted] yoker_assistant = true
> (and pkgq = true) admits ALL tool code from those packages as trusted
> with no per-call gate. Pin the installed versions
> (`uv pip install yoker_assistant==<version>`) and verify the source.

This is the correct framing. Today the blast radius is one pure-function tool
(`md_to_html`); the trust admission is broader than the tool surface, but the
documentation calls this out and recommends version pinning. No remediation
needed for P2-008.

## 6. S-01 (SECURITY.md) status — not blocking P2-008

`SECURITY.md` is absent from the repo root. Per the task framing, S-01 is not
blocking P2-008 because `md_to_html` is the first tool — the self-trust
admission is bounded to a single pure `str -> str` transform with no FS/network/
exec surface.

**Flag for the owner:** if a second tool is added to `yoker_assistant` before
S-01 lands, the self-trust blast radius grows without a governing security
policy. Recommend tracking this as a precondition for the second tool, not for
this one.

## Wrapper Check — PASS

Trivially passes. `md_to_html` is a plain function; `convert_markdown` and
`convert_table` are plain helpers. No wrapper classes, no `__getattr__`, no
dynamic dispatch. The trust surface is exactly the functions named in the
manifest.

## Scope Classification

| Finding | Classification | Action |
|---------|---------------|--------|
| XSS fix applied at all interpolation sites | Blocking | Verified — no action |
| No FS/network/exec primitives | Blocking | Verified — no action |
| Manifest registers only md_to_html | Blocking | Verified — no action |
| Self-trust blast radius documented | Related | Already documented in yoker.toml.example |
| SECURITY.md (S-01) absent | New | Backlog — precondition for the SECOND tool, not P2-008 |

## Positive Observations

- Escape-then-substitute ordering is correct at both bold sites and clearly
  commented (`tools.py:38-40`, `117-118`).
- Separator-line check is explicitly run on raw input with a comment explaining
  why (`tools.py:33-35`).
- Module is import-safe by construction; no side effects in `__init__.py`.
- Self-trust documentation in `yoker.toml.example` is honest about the blast
  radius and recommends version pinning.
- Tool is a pure function — easiest possible capability boundary to reason
  about.

## Recommendations

1. (Backlog, not blocking) Land S-01 (`SECURITY.md`) before a second tool is
   added to `yoker_assistant`.
2. (Optional, not blocking) Consider a single regression test that feeds
   `**<script>alert(1)</script>**` and `<img src=x onerror=alert(1)>` through
   `md_to_html` and asserts no raw `<script>`/`onerror=` appears in the output.
   This locks the escape ordering against future refactors.