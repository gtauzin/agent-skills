---
description: "QA spoke: public surface review (exports vs docs, private-by-intent names, overlapping exports, export completeness, deprecation hygiene)."
---

# /qa-surface

> **Chassis required.** Read the hub `qa.md` FIRST (the project's `.claude/commands/qa.md` if it exists, else `~/.claude/commands/qa.md`) and follow its project discovery, ground rules, severity rubric, finding schema, orchestration, verification, and reporting. This file defines only the surface dimension.

## Phase 0 manifest: inventory and exports (`SURFACE_MANIFEST`)

This manifest imports the package, so it runs in the project environment:

```bash
uv run python ~/.claude/commands/qa/scripts/qa_manifest.py surface
```

The output has these blocks:

- `EXPORTS`: each package's `__all__`.
- `SYMBOLS`: every exported name as `qualified name, kind, parameters, exported_from=<packages>, bases=<in-package bases>`. Kind `MISSING` means `__all__` names something the package does not define (always a finding, category `export-doc-mismatch`, severity high: importing it fails).
- `UNEXPORTED_PUBLIC`: public classes and functions defined in the package but in no `__all__`. This is a signal, often deliberate; judge it against the profile and docs, never report the list wholesale.
- `IMPORT_ERRORS`: modules that failed to import (usually optional dependencies). Their exports are missing from the manifest; say so in the report instead of reporting them as absent.
- `DEPRECATIONS`: static scan for deprecation warnings and decorators.

Also run `python3 ~/.claude/commands/qa/scripts/qa_manifest.py docs` for `API_PAGES`, the docs pages that document a package symbol.

## Units

One global unit; the path filter is ignored. **Always full, never incremental:** this is a cross-file dimension (exports compared across families, docs, and glossary), so a change in one file can surface a mismatch against an unchanged file; it ignores the chassis `CHANGED_FILES` manifest.

## Reviewer prompt

```text
You are a public-surface reviewer for the {package} package (chassis rules apply; return findings in the hub JSON schema).
INPUT: SURFACE_MANIFEST, API_PAGES, the API reference section of the docs nav, the glossary file if any.
PROJECT_CONTRACT: {data contract and conventions}

Findings per category:

### export-doc-mismatch
- Public names exported in an __all__ but absent from API_PAGES and the API reference; documented names not exported; MISSING exports.

### private-by-intent
- Exported names that look internal (defined in leading-underscore modules with helper-style names, test utilities) and are unused in docs and examples.

### overlapping-export (simplification category)
- Two public names whose capability is one function with a parameter; recommend the merged form.
- A wrapper exported alongside the thing it wraps.
Every public name carries documentation and deprecation cost; the suggestion names what to merge or unexport.

### export-completeness
- Subpackages whose __all__ omits classes their sibling families export (compare equivalent families by their bases).
- UNEXPORTED_PUBLIC names that docs, examples, or other packages' code already use as if public.

### deprecation-hygiene
- Deprecations without a version and removal target; removal targets already passed (compare with the current version); deprecated names still used internally.

{extra categories for this dimension from the profile, if any}

Rules: cite file:line or doc path for every finding; at most 10 findings, highest value first.
```

## Aggregation

Dedup by `id` (the same missing export reported from two directions is one finding).
