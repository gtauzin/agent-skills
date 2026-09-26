---
description: "QA spoke: docstring quality review (signature drift, false claims, section placement, module docstrings, misleading examples)."
---

# /qa-docstrings

> **Chassis required.** Read the hub `qa.md` FIRST (the project's `.claude/commands/qa.md` if it exists, else `~/.claude/commands/qa.md`) and follow its project discovery, ground rules, severity rubric, finding schema, orchestration, verification, and reporting. This file defines only the docstrings dimension.

## Phase 0 manifests

- `SURFACE_MANIFEST` from `/qa-surface` (`uv run python $QA surface`) for signature cross-checks.
- The docstring convention and docstring-existence gate from the `profile` manifest's `GATES` block (`docstring convention`, `interrogate`). When a coverage tool such as interrogate is configured, run it for context only, never as a finding.
- `DOCSTRING_RENDERING`: which docstrings reach the built docs. Take it from the profile's Docs section; otherwise determine it once from the docs config (mkdocstrings or autodoc options, the API page generator, and the `API_PAGES` block of `$QA docs`): whether module docstrings render, and whether a subpackage page shows the full `__init__` docstring or only its first line. State the result in one sentence and pass it to every reviewer.

## Units and batching

`$QA units source [--path <dir>] [--changed -]`, the same units as `/qa-source`.

**Incremental-eligible.** This is a per-file dimension: on an incremental run, pipe the chassis `CHANGED_FILES` into `units --changed -`, and carry prior-report findings on unchanged modules forward as KNOWN.

## Rubric

The docstring convention is the one the lint config sets (for example `[tool.ruff.lint.pydocstyle] convention = "numpy"`); the linter owns section ordering and formatting. This spoke reviews only what the linter cannot: truth, usefulness, and content placement. Section names below are numpydoc's; for Google style read `Parameters` as `Args` and `Notes` as `Note`. If no convention is configured, infer it from the majority of docstrings and say so in the report.

## Reviewer prompt

```text
You are a docstring-quality reviewer for the {package} package (chassis rules apply; return findings in the hub JSON schema).
UNIT: {unit} | FILES: {files} | SURFACE_MANIFEST: {manifest}
PROJECT_CONTRACT: {data contract and conventions} | CONVENTION: {docstring convention}
DOCSTRING_RENDERING: {one sentence} | REFERENCE_SHAPES: {profile's reference docstrings, or "none stated"}

Findings per category:

### signature-drift
- Parameters sections that omit, misname, or mistype actual parameters (cross-check SURFACE_MANIFEST); documented defaults that differ from the signature.

### false-claim
- Any docstring sentence the implementation contradicts (severity high). Verify behavioral claims (shapes, columns, types, side effects, state across method calls, raised exceptions) against the code.

### section-placement
Content in a section the convention assigns elsewhere. The rules, a closed list (no findings by analogy):
1. A Parameters entry states what the parameter is: type line, constraints, default semantics, how to choose a value. Anything beyond that (multi-paragraph entries, internal mechanics, allocation or lifecycle detail, subclass contracts, cross-parameter interactions, theory caveats) routes to Notes, with the entry ending in "See Notes." when it points there. REFERENCE_SHAPES, when given, show the intended shape.
2. The extended summary states the contract. Implementation detail, theory, and design rationale route to Notes.
3. Notes never duplicates a Parameters entry or restates the summary.
4. Examples demonstrate usage; explanatory prose inside Examples routes to Notes.
5. A See Also entry is a symbol plus at most one line of description; longer comparisons route to Notes.
Header validity, ordering, and completeness are the linter's job (chassis exclusion rule); wordiness stays in simpler-description. Content relocated from inline comments (qa-source comment-altitude) lands where these rules select: rationale in Notes, caller-set semantics in the relevant Parameters entry. Quote the misplaced passage in the evidence; the suggestion names the target section, or deletion when the passage duplicates another section. Severity low.

### module-docstring (simplification category)
- Trigger: a module-level docstring carrying content beyond a short summary of what the module contains (design rationale, cross-module topology, configuration guidance, usage instructions) where DOCSTRING_RENDERING says that content does not reach the built docs. If module docstrings render in full, skip this category.
- Classify each passage of a flagged docstring, in priority order:
  1. keep: a 1-3 line summary stating what the module contains. Never suggest deleting the module docstring outright when a docstring-coverage gate counts modules.
  2. relocate: contract or behavior of a specific symbol; destination is that symbol's docstring, where the rendered docs show it.
  3. link: rationale or domain exposition an existing docs page covers; replace with a one-line pointer. Verify the page exists before citing it, never assert coverage from memory. If no page covers it, propose the new explanation page or section as the destination.
- The suggestion states the surviving summary text, the destination of every relocated or linked passage, and the net docstring-line reduction; a suggestion missing any element is not a finding. Severity low.

### vacuous-section
- Sections that restate the name without information ("size : int, the size").

### simpler-description (simplification category)
- Mechanism narration where the reader needs the rule: "iterates over the rows accumulating those that..." for "returns rows where X".
- Restating implementation steps instead of stating the contract; jargon where a glossary term or plain phrase exists.
- Sentences whose full content survives in half the words.
Quote the original; put the rewrite in the suggestion. Skip findings equivalent to an accepted entry you were given.

### misleading-example
- Examples that execute (when doctests run, that is already guaranteed) but demonstrate anti-patterns, unrealistic parameter values, or a different feature than the prose claims.

### bidirectional
Docstring-vs-implementation review, both directions:
- Docstring -> code: every documented behavior, parameter interaction, and raised exception exists in the code.
- Code -> docstring: significant behavior visible in the code (special cases, dispatch on input kind, state handling, raised exceptions) that the docstring omits.

{extra categories for this dimension from the profile, if any}

Rules: cite file:line; skip anything the docstring linter or coverage gate enforces; at most 8 findings per batch, highest value first.
```

## Aggregation

Dedup by `id`. `false-claim` findings are never auto-downgraded below medium even when marked unconfirmed; flag them for human review instead.

Cluster the `module-docstring` no-destination proposals: when link passages across modules carry the same theme and no existing docs page covers it, emit one finding per theme proposing the new explanation page or section, and make the per-module findings name that theme as their destination. This clustering lives here, not in `/qa-docs`: docs reviewers never read source files.
