# API Design Review: S-02 `make pre-publish` guard

**Date:** 2026-07-23
**Reviewer:** api-architect agent
**Task:** Phase 3 design review for Bucket A hardening bundle, Q3 only
**Scope:** S-02 — `make pre-publish` guard against non-registry source URLs in built sdist/wheel METADATA
**Input reviewed:** `Makefile` (lines 59-80), `pyproject.toml`, `reporting/bucket-a-hardening/plan.md` (S-02 section, lines 94-154)

## Verdict: APPROVE WITH CHANGES

The design intent is correct and the overall shape (depend on `build`, run `twine check`, then grep built metadata) is right. However the proposed recipe has one **critical bug** that makes the guard a no-op, plus one **wrong sub-pattern** and one **incomplete coverage** class. The fixes below keep the recipe a tight Makefile snippet — no Python script, no temp dirs.

## (a) The real gap — `find dist -name METADATA` catches NOTHING

The functional-analyst flagged that `find dist -name METADATA` "only catches the wheel's METADATA." That understates the problem. Both artifacts are **archives**:

- **Wheel (`.whl`):** a ZIP file. `METADATA` lives at `<name>-<ver>.dist-info/METADATA` **inside the zip**. `find` sees the `.whl` as a single file, not its contents. `find dist -name METADATA` returns **nothing**.
- **Sdist (`.tar.gz`):** a gzipped tar. The metadata file is `PKG-INFO` (not `METADATA`) at `<name>-<ver>/PKG-INFO` **inside the tarball**. `find dist -name METADATA` returns **nothing** here too — and even `find -name PKG-INFO` would not penetrate the archive.

So the proposed guard, as written, always emits "OK: No path/file source URLs in built metadata" regardless of what's in the dependencies. That is a silent failure of the security control — worse than no guard, because it looks like it works.

Confirmed against the wheel spec (PEP 427) and sdist spec: METADATA and PKG-INFO are format-equivalent (core metadata, email-header style, same `Requires-Dist:` lines), just at different paths inside different archive types. Sources: [PEP 427](https://github.com/python/peps/blob/main/peps/pep-0427.rst), [binary-distribution-format](https://github.com/pypa/packaging.python.org/blob/main/source/specifications/binary-distribution-format.rst), [source-distribution-format](https://github.com/pypa/packaging.python.org/blob/main/source/specifications/source-distribution-format.rst).

### Evaluation of the proposed options

| Option | Catches path deps? | Verdict |
|---|---|---|
| (i) Guard wheel only by extracting | Wheel yes, sdist no | Acceptable but owner's acceptance says "sdist/wheel" — both. Reject. |
| (ii) Extract both sdist and wheel to temp dirs | Yes | Works, but temp dirs are unnecessary complexity. |
| (iii) `twine check` output parsing only | **No** — `twine check` validates long_description rendering and required metadata fields; it does **not** reject `Requires-Dist: yoker @ file://...` | Insufficient. Reject as sole mechanism. Keep `twine check` as a complementary rendering check, not the path-dep guard. |
| (iv) `uv build --preview` metadata inspection | Not a built-artifact inspection | Wrong tool. Reject. |
| **(v) Stream archive contents to stdout, grep the stream** | Yes, both formats | **Recommended.** No temp dir, no Python, one pipeline. |

### Recommended approach (v): stream, don't extract

- Wheel: `unzip -p dist/*.whl '*.dist-info/METADATA'` streams METADATA to stdout without writing to disk.
- Sdist: `tar -xzOf dist/*.tar.gz '*/PKG-INFO'` streams PKG-INFO to stdout without writing to disk.

Both ship with macOS and most Linux distros. Both produce text in the same core-metadata format, so a single `grep` over the concatenated stream catches `Requires-Dist:` lines in either. `grep -n` line numbers will be relative to the concatenated stream — that's acceptable for a guard (the error tells you a leak was found; you then inspect the artifacts directly). Keeping per-file labels would add a wrapper; per the Simplicity Principle, skip it.

## (b) Grep pattern — complete coverage of PEP 440 direct-reference forms

### What's wrong with the proposed pattern

The proposed pattern is `(file://|@ file://|^ \.\./|path = )`:

- `^ \.\./` is **wrong**. The rationale ("a METADATA continuation line starting with a relative path") misreads the core-metadata format. `Requires-Dist:` is a single-line field; it does not wrap. A relative-path direct reference renders as `Requires-Dist: yoker @ ../yoker` — `../` appears mid-line after `@ `, not at line start. `^ \.\./` will never match. Drop it.
- `@ file://` is redundant with `file://` (the bare `file://` substring already catches it). Harmless but noise.
- `path =` is kept per owner's acceptance wording. It is defensive: `[tool.uv.sources]` is a uv-specific tool section that is **structurally excluded** from built PyPI metadata, so `path =` will never appear in a real `Requires-Dist:` line. Keep it as defense-in-depth to satisfy acceptance, but document that it's paranoid.
- `file://` as a global substring is fine — no legitimate metadata field contains `file://`.

### What's missing — PEP 440 / PEP 508 direct-reference forms

Registry dependencies in `Requires-Dist` use the form `name<version-spec>` (e.g. `yoker>=0.8.0`). A direct reference uses `name @ <url-or-path>`. The `@` separator is **unambiguous** in `Requires-Dist:` — PEP 508 markers use `;`, `and`, `or`, comparison operators; `@` is not a marker operator. So **any `Requires-Dist:` line containing `@` is a direct reference** — that is the clean catch-all.

Direct-reference URL forms that the current pattern misses:
- `git+https://`, `git+ssh://`, `git+file://` — VCS URLs (git)
- `hg+`, `svn+`, `bzr+` — other VCS schemes
- `@ https://...`, `@ http://...` — plain HTTP/HTTPS direct URLs (non-registry)
- `@ ssh://...` — SSH URLs
- `@ /abs/path`, `@ ./rel/path` — bare path references without `file://` scheme
- `name @ ../rel` — relative path (the case the `^ \.\./` pattern tried and failed to catch)

Note: `git+`, `hg+`, `svn+`, `bzz+`, `file://` as global substrings are safe to flag anywhere in metadata — no legitimate metadata field contains them. But `https://`, `http://`, `ssh://`, `../`, `/` must NOT be flagged globally because `Project-URL:` lines legitimately contain HTTPS URLs (Homepage, Repository, Issues). Scope those to `Requires-Dist:`.

### Recommended pattern

```
(^Requires-Dist:.*@|file://|git\+|hg\+|svn\+|bzr\+|path = )
```

Rationale:
- `^Requires-Dist:.*@` — catches **every** direct reference in one shot (file, path, URL, VCS, relative). This is the primary guard and replaces `@ file://`, `^ \.\./`, and the missing `@ https://` / `@ git+` / `@ /path` cases.
- `file://` — global substring, catches `Download-URL` or `Project-URL` typos too.
- `git\+|hg\+|svn\+|bzr\+` — global substrings, catches VCS URLs in any field.
- `path =` — kept per owner's acceptance wording (paranoid defense-in-depth; harmless).

This is tighter and more complete than the original, and it's shorter.

## Specific recipe adjustments

Replace the proposed block (plan.md lines 124-133):

```make
@echo "Checking built distribution metadata for non-registry source URLs..."
@uv run twine check dist/* >/dev/null
@METADATA_HITS=$$(find dist -name METADATA -exec grep -lE '(file://|@ file://|^ \.\./|path = )' {} + 2>/dev/null || true); \
if [ -n "$$METADATA_HITS" ]; then \
	echo "ERROR: non-registry source URLs found in built METADATA:"; \
	echo "$$METADATA_HITS"; \
	find dist -name METADATA -exec grep -nE '(file://|@ file://|^ \.\./|path = )' {} +; \
	exit 1; \
fi; \
echo "OK: No path/file source URLs in built metadata"
```

with:

```make
@echo "Checking built distribution metadata for non-registry source URLs..."
@uv run twine check dist/* >/dev/null
@hits=$$( { for whl in dist/*.whl; do [ -e "$$whl" ] && unzip -p "$$whl" '*.dist-info/METADATA' 2>/dev/null; done; \
	for sdist in dist/*.tar.gz; do [ -e "$$sdist" ] && tar -xzOf "$$sdist" '*/PKG-INFO' 2>/dev/null; done; } \
	| grep -nE '(^Requires-Dist:.*@|file://|git\+|hg\+|svn\+|bzr\+|path = )' ); \
if [ -n "$$hits" ]; then \
	echo "ERROR: non-registry source URLs found in built metadata:"; \
	echo "$$hits"; \
	exit 1; \
fi; \
echo "OK: No non-registry source URLs in built metadata"
```

Key changes:
1. **Stream wheel METADATA via `unzip -p`** (penetrates the .whl zip without extraction).
2. **Stream sdist PKG-INFO via `tar -xzOf`** (penetrates the .tar.gz without extraction; note the file is `PKG-INFO`, not `METADATA`).
3. **Single `grep` over the concatenated stream** — no `find`, no temp dir, no `-exec`.
4. **Pattern corrected** to `(^Requires-Dist:.*@|file://|git\+|hg\+|svn\+|bzr\+|path = )` — catches all PEP 440 direct-reference forms, drops the broken `^ \.\./` sub-pattern.
5. **`[ -e "$$whl" ]` / `[ -e "$$sdist" ]` guards** so the recipe doesn't error on empty glob (e.g. only a wheel exists, no sdist yet) — the grep simply sees less input.

The `pre-publish: check build` dependency change (plan.md line 113) is correct — keep it. Without `build` as a dep, `dist/` is empty on standalone `make pre-publish` and the guard silently passes.

## Simplicity check

- No Python wrapper introduced. ✓
- No temp dir, no extraction to disk. ✓
- No `pkginfo` dependency added (would be the "clean" object-oriented approach but adds a runtime dep and a script — over-engineering for a grep guard). ✓
- Recipe stays a single Makefile block, ~9 lines. ✓
- `twine check` retained as complementary rendering check (already a dev dep in `pyproject.toml` line 55). ✓
- `path =` retained despite being structurally excluded from built metadata — kept only because owner's acceptance names it; flagged as paranoid in the doc but not removed. ✓

## Verification (for the implementer, not for this review)

1. **Positive path:** `make clean && make build && make pre-publish` passes with current `pyproject.toml` (deps are `yoker>=0.8.0`, `simple-email-gw>=0.3.0`, `pkgq>=0.3.2` — all registry names, no `@`).
2. **Negative path (wheel):** temporarily inject `yoker @ file://../yoker` into `[project.dependencies]`, `make clean && make build && make pre-publish` → fails with ERROR and non-zero exit. Revert.
3. **Negative path (VCS):** temporarily inject `yoker @ git+https://github.com/x/yoker.git`, confirm failure. Revert.
4. **Negative path (sdist-only leakage):** if a path dep somehow lands only in the sdist's `PKG-INFO`, confirm the `tar -xzOf` arm catches it. (In practice hatchling writes the same `Requires-Dist` to both, so this is belt-and-suspenders.)
5. **`make publish` end-to-end:** `publish: clean build` then `@$(MAKE) pre-publish` — `build` dedups under make, no double build.

## Action items

- **S-02 implementer:** apply the recipe replacement above before implementation. Do not merge the proposed `find dist -name METADATA` recipe as-is — it is a silent no-op.
- **Plan.md author:** update the S-02 section's "Notes on the grep pattern" block to reflect the corrected pattern and the archive-penetration mechanism (`unzip -p` / `tar -xzOf`). The current note's claim that "sdist tarball and wheel both contain a METADATA file" is wrong for sdist (it contains `PKG-INFO`).
- **Backlog:** no change to S-02 acceptance — the owner's wording ("rejecting `file://`/`path =`/non-registry source URLs in built sdist/wheel METADATA") is satisfied by the corrected recipe.