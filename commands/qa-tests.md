---
description: "QA spoke: test-setup review (systematic-check coverage gaps, stale xfails, duplicate and vacuous tests, fixture sprawl, over-built tests)."
---

# /qa-tests

> **Chassis required.** Read the hub `qa.md` FIRST (the project's `.claude/commands/qa.md` if it exists, else `~/.claude/commands/qa.md`) and follow its project discovery, ground rules, severity rubric, finding schema, orchestration, verification, and reporting. This file defines only the tests dimension.

## Phase 0 manifest: test inventory and check-suite coverage (`TEST_INVENTORY`, `CHECK_COVERAGE`)

```bash
python3 ~/.claude/commands/qa/scripts/qa_manifest.py tests
```

The output has these blocks:

- `INVENTORY`, `MARKERS`, `UNMATCHED`: counts, marker usage, and public source modules with no name-matched test file. `UNMATCHED` is a signal for reviewers (coverage may live in a common-test file or a sibling file), never a finding by itself.
- `SYSTEMATIC_SUITE` and `GENERATORS`: files that run a systematic check suite (`parametrize_with_checks`, `check_estimator`, `_yield_*_checks` generators) or sweep an inventory (`all_estimators()` and similar). `none` means the project has no systematic suite: the `coverage-gap` and `stale-xfail` categories are not applicable, and the report says so.
- `EXCLUSION_LISTS`: module-level skip, xfail, and exclude containers in suite test files, with their entries.
- `EXCLUDED_ENTRY_COVERAGE`: each excluded entry marked `COVERED` (another test file names it and runs a check suite) or `GAP`.

If the profile's Test suite section defines a stricter coverage rule or its own manifest script, run that instead of, or in addition to, `EXCLUDED_ENTRY_COVERAGE`, and say which one the report used.

Every `GAP` line is automatically a finding (category `coverage-gap`, severity medium).

## Units and batching

```bash
python3 ~/.claude/commands/qa/scripts/qa_manifest.py units tests [--path <dir>] [--changed -]
```

Each `UNIT` line pairs test files from `tests/<subpackage>/` with the source directory named in `paired=`, at most ~5 test files per reviewer.

**Incremental-eligible.** This is a per-file dimension: on an incremental run, pipe the chassis `CHANGED_FILES` into `units --changed -`; a unit is built when one of its test files OR its paired source modules changed. Carry prior-report findings on unchanged pairs forward as KNOWN. Coverage-gap findings from `CHECK_COVERAGE` are computed fresh every run regardless of mode (they are cheap and not file-read-bound).

## Rubric

When the profile's Test suite section names scaffolding skills (for example `create-<package>-<family>` skills with a test-template section), read the matching skill's test template for the families in the unit before reviewing. That template defines what a dedicated test file should look like; deviations from it are the baseline for `ad-hoc-duplication` findings. Without such skills, the baseline is the systematic suite itself.

## Reviewer prompt

```text
You are a test-setup reviewer for the {package} package (chassis rules apply; return findings in the hub JSON schema).
UNIT: {unit} | TEST FILES: {files} | PAIRED SOURCE: {paired dir}
CHECK_COVERAGE: {suite, exclusion lists, coverage lines} | TEST_INVENTORY: {inventory}
PROJECT_CONTRACT: {data contract and conventions} | TEMPLATE: {scaffolding-skill test template, or "none"}

Findings per category:

### coverage-gap
- Every GAP from CHECK_COVERAGE in your unit (mandatory when a systematic suite exists; verify the detail and cite the exclusion-list line).

### stale-xfail
- Exclusion or xfail entries whose excluded check would pass against current code (read the check and the class it excludes).

### ad-hoc-duplication
- Tests re-asserting what a systematic check already covers; name the specific check function.

### vacuous-assertion
- Assertions that cannot fail (isinstance unions covering all reachable returns, `is None or isinstance(...)`), or test docstrings claiming behavior the body never exercises.
- Comment blocks that hand-derive expected values the assertions then decline to check (the derivation states exact numbers, the asserts check only shape or sign).

### near-duplicate
- Test functions duplicating each other within or across files; recommend which to keep (the stronger assertions win).

### fixture-sprawl
- conftest.py fixtures duplicating each other or unused; fixtures that build what a sibling fixture already provides.

### over-built-test (simplification category)
- Parametrization machinery for two cases where two plain tests read directly.
- Mocks or patching for objects cheap to construct for real (small data structures, instances of the package's own classes).
- Assertion helpers or fixture layers that hide what is asserted; suggest inlining.
- Parametrized cases that collapse to the same code path (severity medium: implies coverage that does not exist, per the chassis misleading-structure list).

### bidirectional
Test-vs-implementation review, both directions:
- Test -> code: tests asserting behavior the implementation does not have (passing for the wrong reason).
- Code -> test: significant branches in the unit's source modules (error paths, dispatch on input kind, inverse or round-trip operations) with no test exercising them.

{extra categories for this dimension from the profile, if any}

Rules: cite file:line; at most 8 findings per batch plus all mandatory coverage-gaps; highest value first.
```

## Aggregation

Dedup by `id`. Coverage-gap findings are never dropped by verifiers on "compensating ad-hoc coverage" grounds; compensating coverage may justify severity `low`, not removal, because the convention requires the systematic suite.
