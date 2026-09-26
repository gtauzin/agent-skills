---
description: "QA spoke: source quality review (dead code, library idioms, error handling, contradictions, duplication, needless complexity, comment altitude)."
---

# /qa-source

> **Chassis required.** Read the hub `qa.md` FIRST (the project's `.claude/commands/qa.md` if it exists, else `~/.claude/commands/qa.md`) and follow its project discovery, ground rules, severity rubric, finding schema, orchestration, verification, and reporting. This file defines only the source dimension.

## Units and batching

```bash
python3 ~/.claude/commands/qa/scripts/qa_manifest.py units source [--path <dir>] [--changed -]
```

Units are the `UNIT` lines: modules of one subpackage under the source root, at most ~5 modules and ~1800 lines per reviewer. Each reviewer receives the module files, `PROJECT_CONTRACT`, the profile's Library idioms section, and this charter.

**Incremental-eligible.** This is a per-file dimension: on an incremental run, pipe the chassis `CHANGED_FILES` into `units --changed -` so units cover only changed modules, and carry prior-report findings on unchanged modules forward as KNOWN.

## Reviewer prompt

```text
You are a source-quality reviewer for the {package} package (chassis rules apply; return findings in the hub JSON schema).
UNIT: {unit} | FILES: {files}
PROJECT_CONTRACT: {data contract and conventions} | LIBRARY_IDIOMS: {profile section, or "none stated"}
UTILITY_MODULES: {subpackages the profile's Layering section names as shared primitives, else utils-like subpackages from the profile manifest}

Work through every file and produce findings per category:

### dead-code
- Unreachable branches, unused private helpers, parameters accepted but never used.
- Code kept "for later" with no caller and no test.

### library-idioms
- Only for the libraries LIBRARY_IDIOMS names, or, when it names none, the core dependencies the module imports:
  hand-written loops where the library provides a vectorized or built-in operation, needless materialization or
  conversion between libraries, repeated expensive calls inside loops, manual arithmetic the library already
  implements (dates, grouping, windows).

### error-handling
- Exceptions swallowed or converted to silent defaults.
- Error messages that mislabel the failure or omit the offending value.
- Validation that runs too late (after partial mutation).

### contradiction
- Code that contradicts its own comment or docstring (severity high: false claim).
- Behavior that contradicts PROJECT_CONTRACT (severity high).

### duplication
- Logic re-implemented locally that a UTILITY_MODULES function already provides (cite the function).

### needless-complexity (simplification category)
- Indirection with a single caller: a private helper wrapping one expression, a class where a function suffices.
- Parameters no caller ever varies from the default, or that only ever receive one value repo-wide; suggest inlining the default.
- Nested conditionals that flatten to a guard clause, and helper chains collapsible to a single library call (skip patterns the linter already enforces, such as ruff SIM).
- Clever constructs (metaprogramming, dynamic dispatch, nested comprehensions) where the plain form is shorter and reads directly.
Name the concrete replacement; the rewrite must be net deletion. Skip findings equivalent to an accepted entry you were given.

### comment-altitude (simplification category)
- Trigger: any block of 3+ consecutive inline `#` comment lines. Never flag 1-2 line comments.
- Classify each passage of a flagged block, in priority order:
  1. keep: a constraint the code cannot show, at most 2 surviving lines per block.
  2. delete: restatement of adjacent code (an assert message, the call on the next line, a literal below).
  3. relocate: caller-facing contract or usage instruction; destination is the enclosing function or class docstring, never the module docstring (/qa-docstrings reviews module docstrings under module-docstring).
  4. link: mechanism or domain exposition an existing docs page covers; replace with a one-line pointer to that page. Verify the page exists before citing it, never assert coverage from memory. If no page covers it, propose the new explanation page or section as the destination.
- One finding per FILE: evidence cites every flagged block by line range.
- The suggestion states the surviving comment text (possibly none), the destination of every relocated or linked passage, and the net comment-line reduction summed over the file's blocks; a suggestion missing any element is not a finding.
- Commented-out code is excluded: per the chassis exclusion rule it routes to at most one design finding proposing a lint rule (ruff ERA), never per-instance findings here.

{extra categories for this dimension from the profile, if any}

Rules: cite file:line for every finding; skip anything the project's gates already enforce; at most 8 findings per batch, highest value first.
```

## Aggregation

Dedup by `id`. Report counts derive from findings per category. No source-specific consistency prompts (cross-family consistency lives in `/qa-design`).

Cluster the `comment-altitude` no-destination proposals: when relocate or link passages across files carry the same theme and no existing docs page covers it, emit one finding per theme proposing the new explanation page or section, and make the per-file findings name that theme as their destination. This clustering lives here, not in `/qa-docs`: docs reviewers never read source files.
