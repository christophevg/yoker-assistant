# Security Policy

## Reporting a Vulnerability

Email christophe.vg with a description and repro. Expect an
acknowledgement within 72 hours and a fix or mitigation plan within
30 days for the current release line. Do not publish until the fix is
released unless we agree otherwise.

## `__YOKER_MANIFEST__` Change Review Process

yoker-assistant is a yoker plugin provider. Its `__YOKER_MANIFEST__`
(in `src/yoker_assistant/__init__.py`) declares the tools this package
exposes. When a user installs yoker-assistant and marks
`[plugins.trusted] yoker_assistant = true` in `~/.yoker.toml`, every tool
in the manifest runs with **no per-call gate** — the trust decision is
made once, at install time, and admits all tool code from the package.

This is the intended yoker trust model, but it means adding a new tool
to `__YOKER_MANIFEST__` — or making a capability-changing edit to an
existing tool — is a security-relevant change. Contributors MUST follow
this review process before merging a manifest addition **or a
capability-changing edit to an existing tool** (new args, new side
effects, new dependencies, or a change to the tool's reach). Pure
refactors that do not change the tool's inputs, outputs, reach, or
failure modes do not require this review.

### 1. Blast-radius assessment

For the proposed tool (or the proposed change to an existing tool),
document:
- **Inputs:** what arguments does it accept? Any string/path/URL input?
- **Outputs:** what does it return? Side effects beyond the return value?
- **Reach:** what can it touch? (filesystem read/write, network, shell,
  subprocess, env vars, other tools)
- **Failure modes:** what happens on bad input? On missing resources?
  Does it leak secrets in error messages?

### 2. Capability review

- Does the tool duplicate an existing yoker built-in? If so, justify why
  a second path to the same capability is warranted (it usually is not).
- Does the tool compose with `yoker:git`, `yoker:write`, or
  `yoker:webfetch` in a way that creates a new exfiltration or
  persistence path? If so, document the mitigation.
- Is the tool bounded (named, typed args, no `**kwargs` shell) or
  unbounded (accepts arbitrary commands/paths)? Unbounded tools are
  rejected by default.

### 3. Version pinning

- The tool's behavior must be deterministic for a pinned package
  version. No network-fetched code paths at call time.
- If the tool depends on a network resource, the dependency must be
  declared in `pyproject.toml` (so `uv pip install
  yoker-assistant==<version>` reproduces it), not loaded dynamically.

### 4. Review checklist (PR description)

- [ ] Blast-radius assessment recorded (for an addition or a capability-changing edit)
- [ ] Capability review recorded (duplicates check, composition check,
      bounded-args check)
- [ ] Version pinning confirmed (static deps, no dynamic fetch)
- [ ] Tests cover the happy path + at least one failure mode
- [ ] `make check` green
- [ ] `SECURITY.md` updated if the process itself changes

A manifest addition or capability-changing edit merged without this
checklist is a process violation: it is not automatically a security
incident, but it triggers (1) immediate revert of the change, and (2) a
retroactive security review of what the unreviewed code did while live,
covering the exposure window from merge to revert. CI does not enforce
this — it is a reviewer judgment gate.

## Publishing Guards

`make pre-publish` (see `Makefile`) rejects built sdist/wheel metadata
containing non-registry source URLs (`file://`, VCS schemes, direct
`@ <url>` references, `path =`). This prevents local-path development
wiring (which lives in `[tool.uv.sources]` and is structurally excluded
from PyPI metadata) from ever leaking into a published artifact if
discipline slips.

## Deliberate Non-Additions

A supported-versions table, a formal CVE-handling section, a PGP key,
and a `security.txt` are deliberately omitted. For a 0.1.0
single-tool plugin provider with no released security history, these
are ceremony — premature policy-writing that would go stale
immediately. If a real CVE lands or multiple release lines emerge,
revisit then; until then, GitHub Security Advisories is the
one-line-footnote fallback for CVE publication.