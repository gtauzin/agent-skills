---
description: "QA spoke: agent-asset freshness audit (project commands and skills, CLAUDE.md and other agent instructions, the QA profile, hub-spoke integrity)."
---

# /qa-assets

> **Chassis required.** Read the hub `qa.md` FIRST (the project's `.claude/commands/qa.md` if it exists, else `~/.claude/commands/qa.md`) and follow its project discovery, ground rules, severity rubric, finding schema, orchestration, verification, and reporting. This file defines only the assets dimension.

## Units

One global unit; the path filter is ignored. Inputs: every tracked or untracked file under `.claude/commands/`, `.claude/skills/`, and `.github/skills/`, plus `CLAUDE.md`, `AGENTS.md`, `.github/copilot-instructions.md`, and `.claude/qa-profile.md` where they exist (the `profile` manifest's `CONVENTIONS`, `SKILLS`, and `COMMANDS` lines list them). Global assets under `~/.claude/` are out of scope: they are shared across projects and reviewed where they are maintained. **Always full, never incremental:** this is a cross-file dimension (hub-spoke integrity, cross-asset stale references), so it ignores the chassis `CHANGED_FILES` manifest.

## Reviewer prompt

```text
You are an agent-asset freshness auditor for the {package} project (chassis rules apply; return findings in the hub JSON schema).
INPUT: the asset files, the profile manifest output, plus live repo state for verification.

Findings per category:

### stale-reference
- Referenced files, modules, classes, functions, task-runner recipes, workflow names, and doc paths that no
  longer exist or have moved. Verify each by checking the repo, the task runner file (justfile, noxfile,
  Makefile), and .github/workflows/.

### stale-count
- Hard-coded counts (e.g. "27 checks", file totals) that no longer match reality. Recompute and cite
  both numbers. Severity high if following the asset would produce wrong results, else medium.

### broken-scripts
- Embedded scripts that no longer execute: run each asset's bash/python snippets in a safe read-only
  way and flag failures with the error.

### non-portable
- Machine-specific absolute paths (anything under a home directory), user-specific config assumptions, or
  references that break for other collaborators.

### hub-spoke-integrity
- Any command or skill family built as a hub plus spokes: the hub must list every spoke that exists; every
  spoke must begin with the read-the-hub instruction; flag spokes defining hub content locally (severity
  medium: drift seed). Deprecation pointer files are valid assets when their replacement exists; flag
  pointers whose target is gone.
- Project copies of the global QA family (`.claude/commands/qa.md` or `qa-*.md`) shadow the global commands.
  Flag each as medium when it has no stated reason (a comment or profile note saying why the project
  diverges); project-specific QA facts belong in `.claude/qa-profile.md`.
- `.claude/qa-profile.md`: every path, skill, script, recipe, and module it names must exist.

### mirror-drift
- Asset trees the project keeps as mirrors (for example `.claude/skills/` and `.github/skills/`) that
  differ in file set or content, when a convention file states they must match.

### convention-drift
- Asset statements contradicting current conventions in the convention files or pyproject (e.g. an asset
  telling agents to write ad-hoc tests when the convention requires the systematic check suite).

Rules: cite asset-file:line plus the verifying repo evidence; at most 12 findings, highest value first.
```

## Aggregation

Dedup by `id`. When the same stale fact appears in several assets (e.g. an old recipe name repeated in three skills), emit one finding per asset file so each fix is independently actionable, but cross-link them in the evidence field.
