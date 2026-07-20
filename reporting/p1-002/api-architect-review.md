# API-Architect Review — Task P1-002 (Add Runtime Dependencies)

- **Date:** 2026-07-20
- **Reviewer:** api-architect agent
- **Task:** P1-002 Add runtime dependencies (backend dependency wiring + config)
- **Branch:** `feature/p1-002-runtime-deps`
- **Scope:** No new API surface. P1-002 wires runtime dependencies and ships
  reference config. The SDK/email seams (`Agent` + `agent_path` + `process`;
  async `IMAPClient`/`SMTPClient` + `EmailAccount`; `PluginManifest` /
  `__YOKER_MANIFEST__`) are *consumed* in later tasks (P1-003, P1-004, P2-008).
  This review checks that the dependency + config layer correctly targets the
  documented SDK surface and dual-mode plugin pattern from
  `analysis/functional.md` §2.3 / §2.3.1 / §2.4 / §5.

## Summary

**Verdict: approved.** The dependency declarations, version lower bounds,
and reference config are correct for the documented SDK surface and the
dual-mode plugin pattern. No RPC-style surface is introduced (none applies
here — no endpoints). Four non-blocking observations are recorded for follow-up
tasks; none block P1-002.

## Findings

### 1. Dependency lower bounds are defensible against the documented SDK surface

| Dep | Declared | Published latest | SDK surface the bound protects | Verdict |
|---|---|---|---|---|
| `yoker` | `>=0.8.0` | 0.8.0 (2026-07-15) | `Agent` + `agent_path` + async `process(message) -> str`; `PluginManifest` / `__YOKER_MANIFEST__` plugin loader; `yoker:read`/`write`/`update`/`list`/`search`/`websearch`/`webfetch`/`skill`/`agent`/`git` built-ins | OK. `process()` confirmed async returning str (yoker README + functional.md §2.3 against source). `agent_path` not in the README's public docs but functional.md §2.3 records it as confirmed against `yoker/src/yoker/core/__init__.py`; the lower bound is the version functional.md names as the SDK release. |
| `simple-email-gw` | `>=0.3.0` | 0.3.0 | async `IMAPClient`/`SMTPClient`, `EmailAccount` with `name`/`imap_host`/`smtp_host`/`username`/`password`; `search`/`fetch_message`/`mark_message`/`move_message`/`send_email`/`reply_email`; env contract `EMAIL_IMAP_HOST` etc. | OK. 0.3.0 is the current published line and exposes the full async surface functional.md §2.4 quotes verbatim. |
| `pkgq` | `>=0.3.2` | 0.3.2 | Loaded as a yoker plugin (not imported). 0.3.0 introduced yoker plugin support; 0.3.1/0.3.2 are package-structure fixes (skills directory, hatchling build). | OK. Pinning to 0.3.2 ensures the skills-directory fix is present, which matters because pkgq ships skills via the plugin loader. |

No path-dep leakage: `uv.lock` resolves all three from `https://pypi.org/simple`.
The only non-registry source in the lockfile is `editable = "."` for
`yoker-assistant` itself. `[project.dependencies]` contains PyPI names only.

### 2. Dependency set is complete for §2.3.1 (dual-mode plugin) and §3.3 (bounded tool set) at runtime

- `yoker` — required for the SDK consumer half (Agent + process + built-in
  curated tools `yoker:read|list|search|write|update|websearch|webfetch|skill|agent|git`).
- `simple-email-gw` — required for the email loop (§2.4 async IMAP/SMTP).
- `pkgq` — required for the `pkgq:find` plugin tool in §3.3's bounded tool set
  AND for the dual-mode showcase demonstration (§2.3.1 lists pkgq alongside
  yoker_assistant in `[plugins] packages`).

The transitive deps cover the implicit runtime needs:
- `aioimaplib` / `aiosmtplib` come via `simple-email-gw` (async IMAP/SMTP).
- `pydantic` comes via both `simple-email-gw` and `yoker` (for `EmailAccount`
  and yoker's config models).
- `python-dotenv` comes transitively via `simple-email-gw` and `yoker` (for
  `.env` loading). See observation 4 below.

No additional runtime deps are needed at the P1-002 layer. The seam modules
themselves (e.g., `src/yoker_assistant/__init__.py` manifest, `tools.py`,
`loop.py`, `agent.py`) are P1-003/P1-004/P2-008 — correctly out of scope here.

### 3. `pkgq` declaration: `[project.dependencies]` is the right call

`pkgq` is loaded as a yoker plugin and never imported directly by
`yoker_assistant`. Two placement options were considered:

- **`[project.dependencies]` (chosen)** — pulls pkgq on every install.
- **Optional extra, e.g. `yoker-assistant[pkgq]`** — only pulls pkgq when the
  consumer opts in.

The chosen placement is correct for the design intent:

1. functional.md §3.3 lists `pkgq:find` in the **bounded tool set** the
   assistant depends on at runtime. If pkgq is absent, the agent's declared
   tools frontmatter references a tool that won't load.
2. functional.md §2.3.1 lists `pkgq` in `[plugins] packages =
   ["yoker_assistant", "pkgq"]` in the user's `~/.yoker.toml`. The dual-mode
   showcase (§8.1) treats pkgq as part of the demonstration, not an optional
   add-on.
3. For unattended operation the trust gate requires pkgq to be present and
   trusted (§2.3.1, self-trust). Missing pkgq at runtime breaks the showcase.

A future owner call could split pkgq into an extra for users who only want
the `md_to_html` tool — but that is a design change to the showcase, not a
P1-002 packaging fix. Non-blocking; noted as observation 4 below.

### 4. `pyproject.toml` structure / conventions

- `hatchling` build backend, proper `classifiers` (3.10/3.11/3.12, typed),
  `requires-python = ">=3.10"` consistent across `[project]`, `[tool.mypy]`,
  `[tool.ruff]`, `[tool.tox]`.
- `dependencies` comments are tight and explain *why* each lower bound is
  pinned — good signal for future contributors.
- `[project.optional-dependencies]` cleanly separates `docs` and `dev`.
- `[tool.mypy.overrides]` sets `ignore_missing_imports = true` for
  `yoker.*`, `simple_email_gw.*`, `pkgq.*`. This is correct for P1-002
  (seam modules don't exist yet). When P1-003/P1-004 add direct imports,
  consider tightening per-package (e.g., remove the override for
  `yoker.*` once the package imports it directly and ships its own
  type stubs or vendor-stub module). Non-blocking.
- `[tool.uv.sources]` is **absent**. The consensus.md decision was that
  local-path dev wiring (`../yoker`, `../simple-email-gw`, editable) uses
  `[tool.uv.sources]` so it is *structurally excluded* from PyPI metadata.
  The safety property — no `file://`/`path =` entries in
  `[project.dependencies]` — is satisfied (verified in `uv.lock`). The
  `[tool.uv.sources]` block is optional for contributors who want to point
  at local sibling checkouts; its absence just means dev also resolves from
  PyPI. This is acceptable for P1-002. Contributors with local checkouts
  can add the block locally (it is not committed by design — though see
  observation 5 for the alternative). Non-blocking.
- `[project.scripts]` entry `yoker-assistant = "yoker_assistant.__main__:main"`
  matches functional.md §6.

### 5. `yoker.toml.example` correctly reflects the dual-mode plugin pattern

Checked against functional.md §2.3.1 / §5.2 line by line:

| Pattern from §2.3.1 / §5.2 | `yoker.toml.example` | OK |
|---|---|---|
| `[plugins] enabled = true` | present | yes |
| `[plugins] packages = ["yoker_assistant", "pkgq"]` | present, exact order and names | yes |
| `[plugins.trusted] yoker_assistant = true` (self-trust) | present | yes |
| `[plugins.trusted] pkgq = true` | present | yes |
| `[skills] directories = ["./skills"]` | present | yes |
| Backend/model block (provider, base_url, model) | present, Ollama placeholder shape, `api_key` commented out with REDACTED note | yes |
| Agents directory | Omitted (§5.2 says "optional; the agent is loaded by explicit path") | yes — correctly not in the example |
| REFERENCE ONLY banner explaining cwd-vs-`~` resolution and clobber risk | present at top, comprehensive | yes |
| Self-trust blast radius + version-pinning mitigation in banner | present | yes |
| No real `api_key` | `# api_key = "REDACTED"` comment only | yes |

The example is reference-only documentation and matches the agreed
consensus.md remediation text. Good.

### 6. `.env.example` matches §5.1 / §5.3

- `EMAIL_IMAP_HOST` / `EMAIL_SMTP_HOST` / `EMAIL_USERNAME` / `EMAIL_PASSWORD`
  match §5.1.
- `EMAIL_PASSWORD=your-app-password-here` matches the consensus.md optional
  hardening (`changeme` → `your-app-password-here`).
- `EMAIL_RECIPIENT_ADDRESSES=owner@example.com` present with a comment
  identifying it as the **primary reply-safety boundary** (§5.3), correctly
  attributed to `simple-email-gw` config, not package code.
- Header notes that backend API keys belong in `~/.yoker.toml`, not `.env`.
  Good separation.

### 7. README.md configuration section

The README config section accurately restates the dual-mode plugin pattern
from §2.3.1: `[plugins]` / `[plugins.trusted]` / `[skills]` blocks, the
self-trust rationale (no TTY → trust gate rejects untrusted), blast-radius +
version-pinning note, and the `~/.yoker.toml`-vs-`./yoker.toml` resolution
warning. The `.env` section correctly attributes `EMAIL_RECIPIENT_ADDRESSES`
as a `simple-email-gw` concern. No drift from functional.md.

## Non-Blocking Observations (for follow-up tasks, not P1-002)

1. **`pkgq:find` vs `pkgq:find_package` naming discrepancy.**
   functional.md §3.2 and §3.3 call the tool `pkgq:find_package`, but the
   published pkgq yoker plugin exposes `pkgq:find` (per pkgq's PACKAGE.md;
   `find_package` is the MCP-server tool name, which is a different surface).
   This is a documentation/agent-definition issue, not a dependency issue —
   P1-002 is unaffected. Flag for P1-004 (agent definition `tools:`
   frontmatter) so the agent definition declares `pkgq:find`, not
   `pkgq:find_package`, and for a corresponding functional.md errata.

2. **`python-dotenv` direct import.** `python-dotenv` is currently only
   transitive (via `simple-email-gw` and `yoker`). If P1-003/P1-004 ends up
   calling `dotenv.load_dotenv()` directly in the package's own config
   loader, declare `python-dotenv` as a direct runtime dep then. Don't
   pre-declare it on speculation; declare when the import lands.

3. **`[tool.uv.sources]` for sibling-repo dev wiring.** Consensus.md
   recommended `[tool.uv.sources]` as the structural-exclusion mechanism for
   contributors pointing at `../yoker` / `../simple-email-gw` editable.
   P1-002 ships without it (PyPI-only resolution for dev too). That is
   acceptable, but if the project wants to make sibling-repo dev ergonomic
   without each contributor hand-editing `pyproject.toml`, consider
   committing a `[tool.uv.sources]` block (it does not leak to PyPI sdist/wheel
   metadata — that is the whole point of using it). Optional; no action
   required for P1-002.

4. **`pkgq` as an extras group (future).** If a future owner wants to let
   consumers install `yoker-assistant` for the `md_to_html` tool alone
   without pulling pkgq, `pkgq` could move to an optional extra. That is a
   design change to the §8.1 dual-mode showcase (which treats pkgq as part
   of the demo), not a P1-002 packaging fix. Not recommended now; noted for
   the backlog if the showcase scope ever narrows.

5. **`[tool.mypy.overrides]` tightening.** The `ignore_missing_imports =
   true` override for `yoker.*`, `simple_email_gw.*`, `pkgq.*` is right for
   P1-002 (no direct imports yet). Re-evaluate per-package once P1-003/P1-004
   introduce direct imports — yoker is typed (`Typing :: Typed` classifier
   on its PyPI metadata) and may ship inline type info that mypy can use
   without the override.

## Compliance Check

- RESTful design: N/A — P1-002 introduces no endpoints.
- Security: matches `analysis/security-p1-002.md` and consensus.md —
  self-trust blast radius documented in README and `yoker.toml.example`
  banner; `EMAIL_RECIPIENT_ADDRESSES` documented as the reply-safety
  boundary; no path-dep leakage to built metadata (verified in `uv.lock`:
  all three runtime deps resolve from `https://pypi.org/simple`; only
  `editable = "."` for the project itself).
- Documentation: README + `yoker.toml.example` + `.env.example` consistent
  with functional.md §2.3.1 / §5 / §8.1.

## Conclusion

**Approved.** P1-002's dependency declarations and reference config are
correct for the documented SDK surface and the dual-mode plugin pattern.
The five non-blocking observations above belong to follow-up tasks
(P1-003, P1-004, P2-008) and the backlog, not to P1-002.

## Next Steps

- P1-002 proceeds to merge.
- Open a backlog note for observation 1 (`pkgq:find` naming) so P1-004
  declares the correct tool name in the agent definition `tools:` frontmatter
  and an errata is filed against `analysis/functional.md` §3.2/§3.3.
- Re-evaluate observations 2, 3, 5 when the relevant later tasks land.