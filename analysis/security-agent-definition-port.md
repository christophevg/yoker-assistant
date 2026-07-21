# Security Review — P2-001: Port the assistant agent definition

**Scope:** the `tools:` frontmatter and guardrails sections of the ported
`agents/assistant.md` (a markdown file). No code is written by P2-001; the
security boundary under review is the **bounded tool set** the agent
advertises to yoker.

**Owner's proposal (TODO.md P2-001, lines 168–188):** the ported frontmatter
admits exactly `read`, `list`, `search`, `write`, `update`, `websearch`,
`webfetch`, `skill`, `agent`, `git` (full git: read + commit + push),
`pkgq:find`, and `yoker_assistant:md_to_html`. No `Bash`, no `mcp__`
references. `PERSONAL.md` read/write behaviour kept AS-IS from c3. The
`pkgq:find` name is an errata correction of `functional.md` §3.2/§3.3 which
currently say `pkgq:find_package`.

**Wrapper Check:** P2-001 proposes no wrapper classes — it is a markdown file
port. The check passes trivially.

**Simplicity Principle:** the owner's spec is the simple default. I flag no
deviation. The analysis below confirms the spec is sound; it recommends no
added abstraction.

---

## 1. Verified bounded tool set (against yoker's actual registry)

Cross-checked against `yoker/src/yoker/tools/registry.py`
(`_TOOL_CONFIG_MAP`, lines 22–35), `yoker/src/yoker/builtin/*.py`, and the
pkgq plugin source.

| Declared tool | yoker registry name | Implementation | Verdict |
|---|---|---|---|
| `read` | `read` | `yoker/builtin/read.py` | **Resolves** — built-in, PathGuardrail-gated. |
| `list` | `list` | `yoker/builtin/list.py` | **Resolves** — built-in, PathGuardrail-gated. Replaces c3 `Glob`. |
| `search` | `search` | `yoker/builtin/search.py` | **Resolves** — built-in, PathGuardrail-gated (filesystem tool). Replaces c3 `Grep`. |
| `write` | `write` | `yoker/builtin/write.py` | **Resolves** — built-in, PathGuardrail-gated, overwrite protection, content-size limit, blocked-extensions list. |
| `update` | `update` | `yoker/builtin/update.py` | **Resolves** — built-in, PathGuardrail-gated, diff-size limit. Replaces c3 `Edit`. |
| `websearch` | `websearch` | `yoker/builtin/websearch.py` + `yoker/tools/web/guardrail.py` (`WebGuardrail`) | **Resolves** — built-in. SSRF guard, domain allow/blocklist, rate limit, query-length cap, sensitive-pattern block, invisible-Unicode strip. Requires backend API key. |
| `webfetch` | `webfetch` | `yoker/builtin/webfetch.py` + `UrlWebGuardrail` | **Resolves** — built-in. URL-format validation, SSRF (private CIDRs, cloud metadata `169.254.169.254`, localhost, DNS-resolves-to-private check), HTTPS-required default, domain allow/blocklist. |
| `skill` | `skill` | `yoker/builtin/skill.py` | **Resolves** — built-in. Invokes ported `pa-inbox` / `pa-outbox` skills. |
| `agent` | `agent` | (subagent spawning, 1-level recursion) | **Resolves** — built-in. Reviewed in P1-004 `security-agent-seam.md`. |
| `git` | `git` | `yoker/builtin/git.py` | **Resolves** — built-in. Supports read (`status`/`log`/`diff`/`branch`/`show`) + `commit` + `push`. PathGuardrail-gated (must be a `.git` repo). Arg sanitization (see §3). |
| `pkgq:find` | plugin namespace `pkgq` + tool name `find` | `pkgq/src/pkgq/plugin.py` (sets `yoker_tool_find.__yoker_name__ = "find"`) | **Resolves** — plugin tool. **Errata confirmed (see §2).** |
| `yoker_assistant:md_to_html` | plugin namespace `yoker_assistant` + tool name `md_to_html` | **NOT YET IMPLEMENTED** — `src/yoker_assistant/tools.py` is a P1-001 placeholder; the tool lands in P2-008. `__YOKER_MANIFEST__ = PluginManifest(tools=[])` today. | **Will NOT resolve at P2-001 implementation time.** Sequencing concern (see §5), not a security vulnerability. |

**Built-in tool set conclusion:** the 10 yoker built-ins declared in the
spec all match yoker's `_TOOL_CONFIG_MAP` and have real implementations.
`pkgq:find` resolves via the plugin loader. `yoker_assistant:md_to_html`
will not resolve until P2-008 lands.

---

## 2. `pkgq:find` errata — confirmed

Evidence (`pkgq/src/pkgq/plugin.py`, lines 13–39):

```python
yoker_tool_find.__yoker_name__ = "find"  # type: ignore[attr-defined]

__YOKER_MANIFEST__ = PluginManifest(
  tools=[yoker_tool_find],
  skills_dir="skills",
)
```

The yoker plugin loader namespaces plugin tools as `<source>:<name>`. The
pkgq package source is `pkgq`; the tool's `__yoker_name__` is `find`. So
the registered tool name is **`pkgq:find`**, NOT `pkgq:find_package`.

`find_package` is the MCP-server tool surface
(`pkgq/src/pkgq/mcp.py` — a separate integration that exposes the same
underlying `find()` function over MCP). The two integrations are distinct:
yoker-plugin consumers use `pkgq:find`; MCP clients use `find_package`.

**Errata confirmation:** `functional.md` §3.2 and §3.3 currently say
`pkgq:find_package`. This is incorrect for the yoker-plugin context. The
P2-001 TODO spec correctly uses `pkgq:find`. The same P2-001 edit that
ports the agent definition must update §3.2/§3.3 to `pkgq:find` (the TODO
explicitly calls this out, lines 172–180). No security impact — the
errata is a naming correction; the underlying tool is the same `find()`
function with the same behaviour.

**Acceptance criterion implication:** the P2-001 acceptance requires "yoker
logs no missing-tool warnings — in particular `pkgq:find` resolves;
`pkgq:find_package` would NOT resolve and must not appear." This is
correct and verifiable. If the ported frontmatter mistakenly used
`pkgq:find_package`, yoker would emit a missing-tool warning at agent
load and the tool would be unavailable to the agent.

---

## 3. `git` (full git: read + commit + push) — blast radius assessment

Confirmed against `yoker/src/yoker/builtin/git.py`:

**Operations supported (OPERATION_ARGS, lines 21–63):**
- Read: `status`, `log`, `diff`, `branch`, `show`
- Write: `commit` (args: `message`, `all`, `amend`)
- Push: `push` (args: `all`, `tags`, `force`)

**Security controls:**
- **No shell.** `_execute_command` uses `subprocess.run(cmd, ...)` with a
  list argv (line 344) — no `shell=True`. No shell injection vector.
- **Arg sanitization** (`_sanitize_arg`, lines 297–335): string args
  blocked if they contain any of `FORBIDDEN_CHARS` = `\n \r \x00 ` $ | ; &`,
  if they match `DANGEROUS_OPTIONS` = `--upload-pack --receive-pack --exec
  --git-dir --work-tree -c --config`, if they start with `-` (flag
  injection), or if they exceed 1000 chars. Integers bounded by
  `minimum`/`maximum` in the schema.
- **Path validation** (`_validate_repository_path`, lines 215–230): path
  must exist and the resolved directory (or parent for file args) must
  contain a `.git` entry. PathGuardrail also applies (git is in
  `_FILESYSTEM_TOOLS`), so the path must be inside a configured
  `filesystem_paths` root.
- **Output sanitization** (`_sanitize_output`, lines 354–356): redacts
  `https://user:pass@host` credential strings in git output.
- **Operation allowlist** (`allowed_commands` from `GitToolConfig`):
  operations not in the configured allowlist are rejected (line 119).
- **Permission gate** (`_check_permission`, lines 233–256): operations
  listed in `requires_permission` (typically `commit`, `push`) require a
  permission handler in `allow` mode; `block` mode rejects; `ask_user`
  mode rejects in unattended operation.
- **`--force` push** is in the schema (line 61). It is gated by the same
  `requires_permission` path as `push` itself. **Deployment-config
  concern:** if the deployment's `~/.yoker.toml` sets the `push`
  permission handler to `allow` mode, `force` becomes callable. Recommend
  the deployment config leave `push` requiring explicit permission, or
  block `force` at the config level if yoker exposes a per-arg gate (it
  does not today — this is a future hardening item, not a P2-001
  blocker).

**Blast radius conclusion:** the agent can commit and push to the
configured repository. This is the intentional demo beat (functional.md
§4.3) and was already accepted in P1-004's `security-agent-seam.md`
finding F3 (Low, Accept — demo beat). The P2-001 port does not change
this boundary: the same `yoker:git` tool, same guardrails, same
configuration. **No new risk.**

---

## 4. No `Bash`, no `mcp__` references — confirmed in spec

The TODO spec (lines 168–188) explicitly lists the bounded set and the
acceptance criterion (line 188) requires "the definition contains no
`mcp__` references and no `Bash`." This removes:

- **Shell access** — the single largest blast-radius reducer. c3's
  assistant declared `Bash` (c3/agents/assistant.md line 19); the port
  removes it. yoker's safety model substitutes named, guardrailed tools
  for an open shell. This is the showcase's central safety point.
- **MCP email-tool access** — all 10 `mcp__plugin_c3_email__*` tools
  (c3 lines 27–37) are removed. The agent cannot directly access the
  mailbox; Python owns the email loop. This eliminates the agent-as-IMAP
  attack surface.
- **MCP package-tool access** — `mcp__plugin_c3_pkgq__find_package` is
  replaced by the yoker-plugin `pkgq:find` (same capability, yoker-native
  mechanics, guardrailed path).

**Verification:** when the ported `agents/assistant.md` is written, a
grep for `Bash` and `mcp__` in the file should return zero hits. This is
a P2-001 acceptance criterion and a security control. The port
instructions (TODO lines 165–167) explicitly remove the "Email
Operations" section, the "Use MCP tools for email" guardrail (c3 line
236), and the c3-specific skill-priority table (c3 lines 239–247) —
these are the only places `mcp__` and `Bash`-adjacent phrasing appear in
the c3 source. Confirm during implementation that the `Bash(pwd)` step
in c3's Phase 1 (c3 line 102) is also removed (it references the Bash
tool).

---

## 5. `PERSONAL.md` writes — no new risk

The ported definition keeps the c3 behaviour: read `PERSONAL.md` at
session start via `yoker:read`, write learned behaviours via
`yoker:update`/`yoker:write`, commit/push via `yoker:git`. This is the
demo beat (functional.md §4.3) and was accepted in P1-004's
`security-agent-seam.md` finding F4 (Low, Accept — owner's P2-001
decision).

**P2-001 does not change this boundary.** The same PathGuardrail
(`PERSONAL.md` must be inside a configured `filesystem_paths` root), the
same git arg sanitization, and the same write/update content-size limits
apply. No new risk.

**Residual risk (already accepted, restated for completeness):** a
prompt-injected email could attempt to inject a "learned behaviour" into
`PERSONAL.md` that biases future responses. The agent definition's
guardrails section owns the "what is a legitimate learned behaviour"
policy. This is an agent-prompt-level control, not a tool-level control,
and is the owner's accepted design for the showcase.

---

## 6. `websearch` / `webfetch` on untrusted email content — SSRF-ish assessment

**Threat:** a prompt-injected email could instruct the agent to fetch
attacker-controlled URLs or search for attacker-chosen queries. This is
an SSRF-ish / prompt-injection-driven exfiltration vector.

**Controls confirmed in `yoker/src/yoker/tools/web/guardrail.py`:**

- **SSRF protection** (`_check_ssrf`, `_check_ssrf_for_host`):
  - Private CIDRs blocked: `10.0.0.0/8`, `172.16.0.0/12`,
    `192.168.0.0/16`, `127.0.0.0/8`, `169.254.0.0/16` (link-local /
    cloud metadata), IPv6 `::1/128`, `fe80::/10`, `fc00::/7`.
  - Cloud metadata IP `169.254.169.254` explicitly blocked.
  - `localhost` string blocked.
  - DNS resolution check: domains that resolve to private IPs are
    blocked (`_is_safe_domain`).
  - URL-encoded, hex-encoded, decimal-encoded IP variants decoded and
    checked.
- **HTTPS required** (default `require_https=True`): `UrlWebGuardrail`
  rejects non-`https` URLs (line 620). `WebGuardrail` (search) does not
  require HTTPS for queries, but the backend (Ollama) handles the
  actual search request.
- **Domain allowlist / blocklist** (config-driven): if the deployment
  sets `domain_allowlist`, only listed domains are fetchable.
- **Rate limiting**: per-minute, per-hour, concurrent caps
  (config-driven defaults: 60/min, 1000/hour).
- **Query length cap**: default 500 chars.
- **Sensitive-pattern block** in search queries: blocks
  `password=...`, `api_key=...`, `token=...`, `bearer ...`, etc. This
  prevents the agent from being prompt-injected into searching for
  secret literals (a minor exfiltration-shape reduction).
- **Invisible-Unicode strip** (including Unicode Tag characters
  `U+E0000–U+E007F`): reduces prompt-injection via invisible
  characters in queries.

**Residual risk (bounded, acceptable for the showcase):** a
prompt-injected email can still cause the agent to fetch arbitrary
**public HTTPS** URLs. The agent has no secrets to leak beyond its own
system prompt and the `PERSONAL.md` content it has read — both of which
are owner-controlled, not secret. The fetched content returns to the
agent's context, not to the email sender directly (the sender only sees
the agent's reply text). The risk is that a malicious email causes the
agent to spend tokens fetching attacker URLs or to be influenced by
attacker-controlled fetched content (a second-order prompt-injection
vector). This is bounded by yoker's web guardrails to public HTTPS
endpoints and is the same shape as any web-enabled agent. **Accept for
showcase.** If the owner wants tighter control post-showcase, setting a
`domain_allowlist` in `~/.yoker.toml` is the clean mitigation (no code
change).

---

## 7. Tool surface assessment — each tool's admission rationale

| Tool | Why admitted | What guardrail bounds it |
|---|---|---|
| `read` | Read `PERSONAL.md`, memory files, project files for reasoning. | `PathGuardrail`: path must be inside configured `filesystem_paths` root; blocked-pattern regex (e.g. `.env`); extension allowlist; file-size cap. |
| `list` | Discover files (replaces c3 `Glob`). | `PathGuardrail` (filesystem tool). |
| `search` | Content search (replaces c3 `Grep`). | `PathGuardrail` (filesystem tool); complexity limits in `yoker/builtin/search.py`. |
| `write` | Create memory files, write `PERSONAL.md` learned behaviours. | `PathGuardrail`; overwrite protection; content-size limit; blocked-extensions. |
| `update` | Update `PERSONAL.md`, memory files (replaces c3 `Edit`). | `PathGuardrail`; diff-size limit; file must exist. |
| `websearch` | Look up package docs, context for reasoning. | `WebGuardrail`: SSRF, rate limit, query-length, sensitive-pattern, invisible-Unicode. Requires API key. |
| `webfetch` | Fetch specific URLs (e.g. package docs). | `UrlWebGuardrail`: URL format, SSRF (private CIDRs, metadata, localhost, DNS-resolves-to-private), HTTPS-required, domain allow/blocklist. |
| `skill` | Invoke ported `pa-inbox` / `pa-outbox` reasoning skills. | Skills are loaded from configured `skills/` directories; skill content is trusted (author-controlled, not email-controlled). |
| `agent` | Spawn 1-level subagents for isolated reasoning. | Reviewed in P1-004 `security-agent-seam.md` — recursion limit, isolated context. |
| `git` | Demo beat: commit/push `PERSONAL.md` learned behaviours. | `PathGuardrail` (must be a `.git` repo inside allowed root); arg sanitization (no shell, no forbidden chars, no dangerous options); operation allowlist; permission gate for `commit`/`push`; output credential redaction. |
| `pkgq:find` | Look up Python package documentation (showcase plugin loading). | Plugin tool; args are package name + version strings; bounded by pkgq's own input handling. |
| `yoker_assistant:md_to_html` | Convert the agent's markdown reply to HTML for email rendering. | Plugin tool defined in this package; input is a markdown string (`Annotated[str, Text(...)]`); no filesystem, no network. Smallest possible blast radius. **Not yet implemented (P2-008).** |

**Missing tools (deliberately excluded):**
- `Bash` — removed (no shell). c3 had it; the port drops it.
- `AskUserQuestion`, `PushNotification` — removed (no interactive UI;
  email is the only channel).
- `ListMcpResourcesTool`, `ReadMcpResourceTool` — removed (MCP-specific).
- All 10 `mcp__plugin_c3_email__*` — removed (email loop is in Python).
- `mkdir`, `existence`, `make` — yoker built-ins NOT admitted. The agent
  does not need to create directories or check existence for the
  showcase workflow. **Recommendation: keep excluded.** Admitting `mkdir`
  would expand the write surface with no showcase benefit. This is the
  correct default per the Simplicity Principle.

**Excessive tools:** none identified. The set is the minimum that
supports the workflow (reason, read, write memory, reply in HTML,
showcase git + plugin loading).

---

## 8. Findings summary

| ID | Finding | Severity | Classification | Action |
|---|---|---|---|---|
| S1 | `yoker_assistant:md_to_html` declared in frontmatter but tool not yet implemented (P2-008 pending). yoker will log a missing-tool warning at agent load. | Low (functional/sequencing, not security) | **Related** | Either (a) land P2-008 before P2-001 acceptance, (b) relax P2-001 acceptance to allow the warning until P2-008, or (c) add the `yoker_assistant:md_to_html` entry to the frontmatter in P2-008 instead of P2-001. Owner decision. No security impact — the tool, when it lands, has the smallest possible blast radius (string in, string out, no FS, no network). |
| S2 | `git push --force` is in the git tool schema. Gated by `requires_permission`, but if deployment config sets `push` permission to `allow`, force-push becomes callable. | Low (deployment-config concern, not frontmatter concern) | **New** (post-showcase hardening) | Recommend the deployment's `~/.yoker.toml` leave `push` requiring explicit permission, or document that force-push is callable if `push` is allow-listed. Per-arg force-push blocking is a future yoker hardening item, not a P2-001 blocker. |
| S3 | `websearch`/`webfetch` on untrusted email content: a prompt-injected email can cause the agent to fetch arbitrary public HTTPS URLs (second-order prompt-injection vector). | Low (bounded by yoker web guardrails to public HTTPS) | **Related** (same as P1-004 finding F1/F3 shape) | Accept for showcase. Post-showcase mitigation: set `domain_allowlist` in `~/.yoker.toml`. No P2-001 action. |
| S4 | `PERSONAL.md` write + commit + push on untrusted email content: prompt-injection could inject a "learned behaviour" that biases future responses. | Low (accepted demo beat, P1-004 F4) | **Related** (already accepted) | No P2-001 action. The agent definition's guardrails section owns the "what is a legitimate learned behaviour" policy. |
| S5 | `pkgq:find` errata: `functional.md` §3.2/§3.3 say `pkgq:find_package`; the correct yoker-plugin name is `pkgq:find`. | Informational (naming correction) | **Related** | P2-001 already corrects this in the same edit that ports the agent definition (TODO lines 172–180). Confirm the §3.2/§3.3 edit happens in the same PR. |

---

## 9. Positive observations

- **No shell.** The single most impactful security property of the port:
  c3's `Bash` tool is removed. yoker substitutes named, guardrailed
  tools. This is the showcase's central safety thesis and P2-001
  preserves it.
- **No MCP email tools.** The agent cannot touch the mailbox directly;
  Python owns the email loop. This eliminates the agent-as-IMAP attack
  surface.
- **PathGuardrail is defense-in-depth.** Every filesystem tool (`read`,
  `list`, `search`, `write`, `update`, `git`) passes through the same
  path-containment guardrail — root containment via
  `os.path.realpath`, blocked-pattern regex, extension/size limits. The
  agent cannot read `/etc/passwd` or write outside the configured root.
- **Git tool has layered controls.** No shell, arg sanitization,
  operation allowlist, permission gate, credential redaction in output.
  The `force` flag is the one residual edge (S2).
- **Web tools have SSRF protection.** Private CIDRs, cloud metadata,
  localhost, DNS-resolves-to-private all blocked. HTTPS required.
  Rate-limited. Query-length-capped. Sensitive-pattern-blocked.
  Invisible-Unicode-stripped. This is a thorough web guardrail.
- **`pkgq:find` errata is correctly identified in the TODO.** The owner
  caught the naming mismatch between the MCP surface (`find_package`)
  and the yoker-plugin surface (`find`) during the api-architect review
  of P1-002. P2-001 corrects it.
- **Bounded set is minimal.** `mkdir`, `existence`, `make` are yoker
  built-ins that are NOT admitted — the set is the minimum that supports
  the workflow. This is the correct application of the Simplicity
  Principle.

---

## 10. Verdict — is the ported `tools:` frontmatter sound?

**Yes, with one sequencing caveat (S1).**

The 10 yoker built-ins declared in the spec all resolve in yoker's tool
registry. `pkgq:find` is the correct yoker-plugin name (errata
confirmed against `pkgq/src/pkgq/plugin.py`). `git` supports read +
commit + push as claimed, with layered guardrails. No `Bash`, no
`mcp__` references — the spec explicitly excludes them and the
acceptance criterion verifies their absence. `PERSONAL.md` read/write
and the git demo beat are the same boundary P1-004 already accepted.
Web tools are bounded by yoker's SSRF/rate-limit/domain guardrails.

**The one caveat:** `yoker_assistant:md_to_html` is declared in the
frontmatter but the tool does not yet exist (P2-008). At P2-001
implementation time, yoker will log a missing-tool warning. The P2-001
acceptance criterion ("declared tools all resolve — yoker logs no
missing-tool warnings") cannot be met until P2-008 lands. This is a
task-sequencing decision for the owner, not a security vulnerability —
the tool, when implemented, has the smallest possible blast radius
(markdown string in, HTML string out, no filesystem, no network).

**No deviation from the owner's spec is recommended.** The spec is the
simple default and it is sound. The frontmatter, when written exactly
as specified (plus the §3.2/§3.3 errata correction in `functional.md`),
is the correct security boundary for an email-driven assistant
showcase.