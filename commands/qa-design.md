---
description: "QA spoke: design review (dependency direction, shared-base leakage, composition violations, dead modules, needless abstraction, cross-family and naming consistency)."
---

# /qa-design

> **Chassis required.** Read the hub `qa.md` FIRST (the project's `.claude/commands/qa.md` if it exists, else `~/.claude/commands/qa.md`) and follow its project discovery, ground rules, severity rubric, finding schema, orchestration, verification, and reporting. This file defines only the design dimension.

## Phase 0 manifest: import graph (`IMPORT_GRAPH`)

```bash
python3 ~/.claude/commands/qa/scripts/qa_manifest.py imports
```

The output has three blocks: `EDGES` between subpackages and top-level modules of the source root (a subpackage appears by name, a top-level module as `name.py`, the package `__init__` as `(root)`; edges marked `[type-only]` exist only under `if TYPE_CHECKING:`), `CYCLES` among runtime edges, and `NEVER_IMPORTED` modules no in-package module imports.

Also run the `SURFACE_MANIFEST` from `/qa-surface` for cross-family consistency: its `bases=` column groups classes into families by in-package base class.

**Layering contract (`LAYERING`).** Take it from the profile's Layering section. Otherwise extract it from the convention files and explanation docs; if none states one, use this default and label every finding it produces as judged against the default: foundation subpackages and top-level modules (names like `base`, `core`, `utils`, `common`, `constants`, `_internal`) import no feature subpackage, and type-only edges are tolerated.

## Units and batching

Units come from `$QA units source [--path <dir>]` (subpackages under the source root, ~5 modules per reviewer), plus one global consistency unit that ignores the path filter.

**Always full, never incremental:** this is a cross-file dimension. Both the per-subpackage checks (dependency-direction and dead-module are defined against the whole `IMPORT_GRAPH`) and the cross-family consistency unit can surface findings against an unchanged file when another file changes, so the dimension ignores the chassis `CHANGED_FILES` manifest.

## Reviewer prompt (per unit)

```text
You are a design reviewer for the {package} package (chassis rules apply; return findings in the hub JSON schema).
UNIT: {unit} | FILES: {files} | IMPORT_GRAPH: {import graph}
LAYERING: {layering contract, with its source} | PROJECT_CONTRACT: {data contract and conventions}

Findings per category:

### dependency-direction
- Any IMPORT_GRAPH edge from this unit violating LAYERING (severity medium, high if it is part of a CYCLES entry).

### base-leakage
- Logic specific to one family or feature living in a shared base or foundation module that other families inherit or import.

### composition-violation
- Code re-implementing what the subpackages LAYERING names as shared primitives already provide (pipelines, unions, routing, validation helpers).

### dead-module
- NEVER_IMPORTED modules in this unit with no public export, no entry point (console scripts, plugin entry points, `__main__`), and no test-only role.

### needless-abstraction (simplification category)
- Abstractions with a single implementation and no plausible second one; flag with the simpler alternative.
- Speculative extension points: registries or dispatch tables with one entry (severity medium when presented as pluggable, per the chassis misleading-structure list).
- Parameters threaded through layers that every caller sets identically.

{extra categories for this dimension from the profile, if any}

Rules: cite file:line; at most 6 findings per unit, highest value first.
```

## Cross-family consistency prompts (global, one agent each)

Families are the groups the profile's Families section names; otherwise, classes sharing an in-package base in `SURFACE_MANIFEST`. When the package has fewer than two families of two or more classes, skip prompts 1 to 4 and say so in the report; prompt 5 always runs. Each prompt receives the family list, `SURFACE_MANIFEST`, and `IMPORT_GRAPH`; prompt 5 also receives `NAMING_CONVENTIONS`. Categories: `naming-consistency`, `state-attr-convention`, `error-style`, `metadata-consistency`, `verb-consistency`.

1. Parameter naming: the same concept must use the same name across families; list divergences with all class names.
2. Learned or cached state: follow the convention the project states (for example, scikit-learn's trailing underscore for attributes set in `fit`); flag exceptions. Skip when no convention is stated or evident from a majority.
3. Error style: the same failure mode (missing input, invalid configuration, use before initialization or fitting) must raise the same exception type with the same message shape across families.
4. Class metadata: tags, registries, class attributes, or decorators declaring capabilities are applied consistently for equivalent capabilities.
5. Verbs, prefixes and parameters across the package: using the functions in `SYMBOLS` and `UNEXPORTED_PUBLIC`, and reading bodies where the name alone cannot settle it, flag a verb or judgement prefix used with two meanings in different modules (a `get_` that raises in one module and returns `None` in another; a `check_` that reads configuration in one module and a remote service in another), and the same concept passed under two parameter names across functions. One finding per verb or concept, listing every divergent site; the suggestion names the one form to keep, per `NAMING_CONVENTIONS`. Per-name issues inside one module belong to `/qa-source` (`naming`), not here.

## Aggregation

Dedup by `id`. A style concern the linter could own becomes at most ONE finding proposing the lint rule (chassis exclusion rule).
