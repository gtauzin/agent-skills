---
description: "QA hub: run verified quality reviews of a Python package across any combination of dimensions (source, docstrings, tests, design, surface, docs, assets)."
---

# QA Hub

The shared chassis for every quality review in this family. Every QA run, whether started here or from a dimension spoke (`/qa-source`, `/qa-docstrings`, `/qa-tests`, `/qa-design`, `/qa-surface`, `/qa-docs`, `/qa-assets`), follows this file's rules for project discovery, severity, finding format, orchestration, verification, and reporting. Spokes contain only what is dimension-specific: manifests, reviewer charters, and rubric references.

The family is package-independent. Everything project-specific comes from two places: the deterministic manifests (`qa/scripts/qa_manifest.py`, next to this file) and the optional project profile `.claude/qa-profile.md` (see Project profile). Never assume a package name, layout, docs engine, or convention that neither source states.

**Where the files live.** The family is installed globally under `~/.claude/commands/`. A project may override the hub or a spoke with its own copy under `.claude/commands/`; when a spoke says "read the hub", read the project copy if it exists, else `~/.claude/commands/qa.md`. The manifest script is always `~/.claude/commands/qa/scripts/qa_manifest.py`; below it is written `$QA`.

Relationship to other tooling:

- `/pr-review`, `/code-review`, `code-review-expert`, and `/simplify` are diff-scoped and can apply fixes; this family reviews the repo as it stands and only reports, including its simplification findings. A simplification opportunity in code the current branch touches belongs to the diff-scoped tools. A diff-scoped review may reuse this chassis (ground rules, schema, verification) restricted to the branch diff.
- The project's linters, type checker, docs linters, doctests, link checker, and CI are deterministic gates; QA never re-reports what they enforce (see Ground rules).

## Arguments

`/qa [dimensions] [path] [--full] [--init-profile]`

- `dimensions`: comma-separated subset of `source,docstrings,tests,design,surface,docs,assets`, or omitted for all.
- `path`: optional filter (a subpackage directory under the source root for code dimensions, a quadrant or page for docs). `surface` and `assets` are global and ignore it.
- `--full`: force a full review even when an incremental run would otherwise apply (see Incremental scope). The no-args run is full by default.
- `--init-profile`: draft `.claude/qa-profile.md` (see Project profile), show it to the user, and stop. No review runs.

**Incremental scope (default for routine runs).** The per-file dimensions (`source`, `docstrings`, `tests`) run incrementally whenever a prior report covering that dimension with a recorded commit SHA exists (see the Phase 0 changed-files manifest): only review units touching a file changed since that SHA spawn reviewers, and prior-report findings on unchanged files are carried forward as KNOWN without re-review. The cross-file dimensions (`surface`, `design`, `docs` consistency, `assets`) always run full and are never incremental, because a change in one file can create an inconsistency reported against an unchanged file. `--full`, or the absence of any qualifying prior report, makes every dimension run full; the full run is the source of truth and the only mode that establishes a fresh KNOWN baseline. `path`-scoped runs are already narrow and may run full within that path; incremental and `path` compose by intersecting the changed-file set with the path.

Spoke files (read each selected dimension's spoke for its manifests and charter):

| Dimension | Spoke |
| --- | --- |
| source | `qa-source.md` |
| docstrings | `qa-docstrings.md` |
| tests | `qa-tests.md` |
| design | `qa-design.md` |
| surface | `qa-surface.md` |
| docs | `qa-docs.md` |
| assets | `qa-assets.md` |

Cost guidance, state it to the user before launching. A full no-args run fans out one reviewer per unit per dimension plus the verifiers. On a package of ~90k lines that is 80+ review agents across the seven dimensions; state the unit count the `units` manifest reports for this project. Left unbatched, verification alone spawns one agent per finding, which on a whole-repo sweep is hundreds of agents and exhausts the token budget before the report is written. So:

- **Scope by default.** Routine usage should be narrow: `/qa-tests`, `/qa-docs how-to`, `/qa source,design <source-root>/<subpackage>`.
- **Prefer incremental for routine runs.** When a qualifying prior report exists, the per-file dimensions review only changed files and carry the rest forward as KNOWN. This is the cheapest routine path and removes the whole-repo read.
- **Confirm full runs.** Reserve the `--full` no-args run for after large merges or once per release cycle, and confirm with the user before launching.
- **One workflow per dimension.** For multi-dimension runs, launch a separate Workflow per dimension and read each result before starting the next, rather than one combined script. A single workflow covering every dimension at once tends to hit the concurrency and token ceilings mid-run and lose unwritten findings; per-dimension workflows each complete independently and are individually re-runnable.
- **Tier the models.** The bulk `Review` and `Consistency` phases run on a cheaper model (`sonnet`); the `Verify` phase inherits the main-loop model, and any finding a verifier rates `high` is adjudicated there. This cuts cost on the read-and-flag pass without weakening verification or high-severity judgment. Raise the reviewer tier for a deeper sweep.

## Project profile

`.claude/qa-profile.md` records what the manifests cannot detect. It is optional: without it, the run uses the manifests plus the convention files the `profile` manifest lists (`CLAUDE.md`, `AGENTS.md`, `CONTRIBUTING.md`, `.github/copilot-instructions.md`), and every category whose inputs are missing is reported as not applicable rather than guessed. With it, the profile wins over inference. It is committed to the repo and reviewed like code.

`--init-profile` drafts it: run the `profile` manifest, read the convention files and the docs' explanation index, fill in the sections below with what they state (cite the source file for each rule), write `.claude/qa-profile.md`, and show it to the user. Leave a section as `(none)` rather than invent content. The template:

```markdown
# QA profile

## Package
Only when detection picks the wrong package: `import name`, `source root`.

## Scope
Paths excluded from review (vendored code, generated code, sibling packages). Changed files under them
are listed in reports as not reviewed, never given findings.

## Data contract
Rules whose violation breaks callers (input/output schemas, required columns, naming schemes, invariants
between methods). Violations and false statements about them are severity high.

## Conventions
Where the project states conventions beyond the convention files (explanation pages, skills).

## Naming
Deviations from the hub's default Naming conventions, and where the project states its own (for
example a table of judgement kinds and their prefixes). `(none)` means the defaults apply as written.

## Deterministic gates
Gates the `profile` manifest cannot see (custom scripts, framework checks). Their rules are excluded.

## Layering
Allowed dependency direction between subpackages, and the subpackages that provide shared primitives
(composition, utilities) other code must not re-implement.

## Families
Groups of sibling classes sharing a base class, the parameters and fitted-state conventions they must
share, and the inventory function if the package has one.

## Test suite
The systematic check suite (where it runs, how exclusions are declared, what counts as dedicated
coverage), plus scaffolding skills whose test templates define a dedicated test file's shape.

## Library idioms
Core libraries whose idioms `source` reviewers check, one line each on what "idiomatic" means here.

## Docs
Glossary file, companion-notebook conventions, how API pages are addressed, which module docstrings
reach the built site, and reference docstrings that show correct section placement.

## Extra categories
Per dimension: project-specific categories with a one-line charter and a severity.
```

## Ground rules (every agent, every phase)

**Exclusion rule.** Never report findings that the project's deterministic gates already enforce or could enforce as a rule. The gates are what the `profile` manifest lists under `GATES` (pyproject tool sections, pre-commit hooks, just recipes, CI workflows) plus the profile's Deterministic gates section: typically formatting, import order, line length, naming case (for example ruff `N`, when it is enabled), type errors, markdown style, docstring existence (when interrogate or an equivalent runs), built-site link breakage, doctest and notebook execution. What a name means is not a gate: whether a name is clear on its own, and whether its verb or prefix matches what the code does, is reviewed under the `naming` categories (see Naming conventions). If a recurring style concern genuinely matters, file ONE `design` finding proposing the corresponding lint rule, and nothing else. The same routing applies to complexity patterns a currently unselected lint rule could own (e.g. ruff C901): one `design` finding proposing the rule, never per-instance findings. A pattern covered by a rule the lint config deliberately ignores is a settled decision; a `design` finding may propose revisiting it only by arguing against the recorded ignore reason.

**Simplicity rule.** Every finding's `suggestion`, in every category, proposes the simplest remedy that resolves the claim, preferring deletion over addition. Simplification categories (each spoke marks its own with "simplification category" in its charter) additionally require a named concrete replacement and a countable reduction (parameters, branches, layers, indirections, exported names, or net lines); "this could be simpler" with nothing named is not a finding.

Spokes running simplification categories pass the accepted entries (file, slug, justification) from `reviews/accepted.md` for the files under review into the reviewer prompt; a reviewer skips only findings equivalent to an accepted entry, never a whole file. Phase 4's ACCEPTED match is the backstop.

**Severity rubric.** Every reviewer receives the project's data contract (profile, else the convention files) as part of its prompt.

- `high`: violates the project's data contract, is a correctness bug, or is a docstring/doc/comment asserting something false.
- `medium`: inconsistency between sibling components (class families, parallel modules), or between code and stated conventions (convention files, profile, explanation docs, project skills). Also misleading structure, a closed list: an extension point with no second implementation presented as pluggable (a registry with one entry, a base class with one subclass named as a family); a parameter that nothing reads; test machinery implying coverage that does not exist (parametrized cases that collapse to one code path). This list is amended only by editing this file, never by reviewer analogy.
- `low`: judgment-call improvements (clarity, better tests or docs); every simplification finding not matching the misleading-structure list above.

**Finding format.** Every finding is a JSON object:

```json
{
  "id": "<dimension>:<file-path>:<kebab-slug-of-claim>",
  "dimension": "tests",
  "severity": "medium",
  "category": "<dimension-specific category from the spoke charter>",
  "file": "tests/compose/test_pipeline.py",
  "claim": "one-sentence factual claim",
  "evidence": "file:line citation plus a short quote",
  "suggestion": "one-sentence remedy"
}
```

The `id` derives from the file path and a 3-6 word normalized slug of the claim, never from prose wording, so it stays stable across runs. `category` comes from the spoke's charter or the profile's Extra categories and drives report counts.

## Naming conventions

The default style is modelled on scikit-learn: a name says what the code does, clearly enough to read on its own, even when that makes it longer. `train_test_split`, `check_is_fitted`, `make_pipeline`, `is_classifier` and `load_iris` are the reference. The profile's Naming section overrides any rule below; a rule the project explicitly rejects is never reported.

**Every name is clear on its own.** Read the name as if it were imported alone (`from module import name`), and as it appears inside its own module. A name that only makes sense with the module in front (`registry.entry`, `store.root`, `store.labels`) is unclear. Private helpers follow the same rules as public names.

**Functions start with a verb, then the object.** `get_registry_entry`, not `entry` or `registry_entry`. A function that returns a boolean may instead be a question: `is_<condition>`, `has_<object>`, or `<object>_exists`. Classes and constants are nouns.

**One verb per meaning, used the same way across the package:**

| Verb | Meaning |
| --- | --- |
| `load_` | Read configuration or a file and return a validated object |
| `get_` | Look up and return one item; raise when it is missing |
| `get_<object>_or_none` | The same lookup, returning `None` when the item is missing |
| `list_` | Return several items |
| `make_` | Build a small value (a name, a payload) |
| `derive_`, `compute_` | Work a value out from other data |
| `read_`, `write_`, `update_`, `delete_` | File or storage operations |
| `run_<command>_command` | The function behind one CLI command; it prints and returns an exit code |

**A judgement's prefix names its kind.** A judgement is a function whose job is to decide whether something is acceptable, and to refuse when it is not. What it reads decides when it can run and what its failure means, so each kind has one prefix:

| Kind | Reads | Runs | Prefix |
| --- | --- | --- | --- |
| Validation | One object's own fields, or one raw value before it is used | When the object is built or the value first used | `validate_` (or a validator of the modelling library, such as pydantic) |
| Check | Several already-valid configuration objects together | When configuration is loaded | `check_` |
| Verification | State outside the configuration: the clock, the local disk, a database, a remote service | Just before a command acts | `verify_` |
| Gate | Data in flight inside a running pipeline | Inside the pipeline step | `require_` (precondition) or `refuse_` (outcome) |
| Guard | The repository itself | In CI | A test |

A function that observes and carries on is not a judgement: `warn_`. When the project documents its own table of judgement kinds (the profile's Naming section says where), that table replaces this one.

**A lookup is not a judgement.** A function whose purpose is to return an item, and which raises only because the item is missing, uses `get_`, never a judgement prefix (`get_registry_entry`, not `require_entry`).

**A judgement that returns what it judged keeps its prefix.** scikit-learn's `check_array` checks an array and returns it; in the same way, `verify_registry_entry` may return the entry it verified. A function that runs judgements but returns new data (not the thing it judged) is named for what it returns.

**The same concept uses the same parameter name everywhere**, across functions as well as classes, as scikit-learn uses `X`, `y` and `random_state`.

**Module names say what the module holds**, in literal words: `freeze_history`, not `ledger`; `local_store`, not `store`. A generic name alone (`plan`, `local`, `helpers`) is unclear unless the package holds one thing of that kind.

**Severity of naming findings.** A name that states something false (a `get_` that returns nothing, a `delete_` that does not delete) is `high`. A judgement prefix that names the wrong kind, a verb used against its meaning above, or the same concept under two parameter names is `medium` (inconsistency with a stated convention). A name that is unclear on its own or not verb-first is `low`. Every naming suggestion states the new name; for an exported name it also says the rename breaks callers outside the package.

## Phase 0: Shared baseline (before any review)

Run from the project root:

```bash
QA=~/.claude/commands/qa/scripts/qa_manifest.py
python3 $QA profile
cat .claude/qa-profile.md 2>/dev/null || echo "(no .claude/qa-profile.md; using manifests and convention files)"
cat reviews/accepted.md 2>/dev/null || echo "(no reviews/accepted.md yet)"
```

`profile` prints `PACKAGE` (import name and source root), `SUBPACKAGES` with line counts, `GATES`, `DOCS`, `CONVENTIONS`, `SKILLS`, and `REVIEWS` (accepted count, latest reports with their dimensions and SHAs). If it picks the wrong package, or the profile names one, pass `--package NAME` or `--source-root PATH` to every later manifest call. Read the convention files it lists and extract the data contract, conventions, and layering rules the profile does not already state; every reviewer prompt receives them as `PROJECT_CONTRACT`. The source and design reviewers also receive the Naming conventions section of this hub, with the profile's Naming section applied on top, as `NAMING_CONVENTIONS`. Keep the accepted-finding IDs and justifications for Phase 4 and for simplification-category reviewer inputs, along with the most recent prior report. Then run each selected spoke's manifests (Phase 0 sections in the spokes). If a manifest command fails, stop and report; never substitute agent guesses for manifest data.

**Changed-files manifest (`CHANGED_FILES`), for incremental per-file dimensions.** Per dimension, the base is the latest `reviews/*-qa.md` whose `Scope:` line covers that dimension over a path containing the requested one, and whose `Commit:` SHA resolves:

```bash
python3 $QA changed --dimension source [--path <path>]
```

If it prints `FULL`, the dimension runs full and the report header states the fallback. Otherwise the first line is `INCREMENTAL base=<sha> report=<file>` and the remaining lines are `CHANGED_FILES`. Feed them to `units` (`--changed -`) so review units cover only changed files, and carry every finding of that base report on a path NOT in `CHANGED_FILES` forward as KNOWN (Phase 4). Different dimensions can have different bases; each carries forward from its own base report. `--full` skips this manifest entirely.

**Review units (`units`).** Per-file spokes build units with the manifest instead of by hand:

```bash
python3 $QA units source [--path <dir>] [--changed <file>|-] [--max-lines 1800] [--max-files 5]
python3 $QA units tests  [--path <dir>] [--changed <file>|-]
```

Each `UNIT` line names a subpackage batch, its line total, and its files; `tests` units also name the paired source directory. Regroup topically within a subpackage when that keeps the line budget (for example, all modules of one algorithm family together), never across it.

## Orchestration

Invoking any command in this family is the user's explicit opt-in to multi-agent orchestration. Use the Workflow tool. Each spoke defines its UNITS and its reviewer prompt; the hub supplies the schemas and flow. Pass today's date via `args`. For a multi-dimension run, prefer one workflow per dimension (see Cost guidance) over a single combined script.

Three rules keep a run inside the agent and token ceilings; all are load-bearing, not optional:

1. **Batch the verifiers.** Never spawn one verifier agent per finding. Group findings into batches of ~8 and hand each batch to a single verifier that returns one verdict per `id`. On a large sweep this is the difference between dozens of verifier agents and hundreds, and it is what lets the run reach the report.
2. **Checkpoint after Review.** Findings are the expensive output; persist them as soon as the review sweep finishes, before verification, so a halt (credits, concurrency cap, timeout) still leaves a usable artifact. Workflow scripts cannot write files directly, so dump the raw findings through one cheap agent. (They also remain recoverable post-hoc from each subagent's `StructuredOutput` block in `agent-*.jsonl`, but a checkpoint file is cleaner.)
3. **Size review units by lines, not module count.** A reviewer handed several large modules exhausts its context reading them and returns nothing. The `units` manifest enforces ~1800 lines and 5 files per unit; a single module above the budget is its own unit.

Build every prompt string in the main loop and pass it through `args`, or build it in the script with `[...].join('\n')`. Never paste prompt text containing markdown backticks into a JavaScript template literal: an unescaped backtick ends the literal and the script fails to parse before any agent starts. Syntax-check the script before launching.

Workflow script shape (adapt; spokes supply the unit prompts and consistency prompts, the main loop supplies `verifyRules`):

```javascript
export const meta = {
  name: 'qa',
  description: 'Manifest-driven quality review with batched adversarial verification',
  phases: [{ title: 'Review' }, { title: 'Consistency' }, { title: 'Verify' }],
}
const FINDINGS = { type: 'object', properties: { findings: { type: 'array', items: { type: 'object',
  properties: { id: {type:'string'}, dimension: {type:'string'}, severity: {enum:['high','medium','low']},
  category: {type:'string'}, file: {type:'string'}, claim: {type:'string'}, evidence: {type:'string'},
  suggestion: {type:'string'} },
  required: ['id','dimension','severity','category','file','claim','evidence','suggestion'] } } }, required: ['findings'] }
// One verifier judges a BATCH and returns one verdict per id (NOT one agent per finding).
const VERDICTS = { type: 'object', properties: { verdicts: { type: 'array', items: { type: 'object',
  properties: { id: {type:'string'}, refuted: {type:'boolean'}, citation: {type:'string'},
  severity_recommendation: {enum:['high','medium','low']} },
  required: ['id','refuted','citation','severity_recommendation'] } } }, required: ['verdicts'] }

// Model tiering: bulk read-and-flag runs on the cheaper tier; Verify omits `model`
// so it inherits the main-loop model, which keeps high-severity adjudication there.
const REVIEW_MODEL = 'sonnet'

// args.verifyRules: the Verification rules section below plus PROJECT_CONTRACT, as one string.
const verifyBatchPrompt = batch => [args.verifyRules, 'FINDINGS (JSON array):', JSON.stringify(batch)].join('\n')

// Phase 1: review every unit and run the consistency prompts, then dedupe by id.
// args.unitJobs = [{unit, dim, prompt}] from the spokes; on an incremental run it
// already excludes units with no file in CHANGED_FILES.
const reviewed = (await parallel(args.unitJobs.map(job => () =>
  agent(job.prompt, { label: `${job.dim}:${job.unit}`, phase: 'Review', model: REVIEW_MODEL, schema: FINDINGS }))))
  .filter(Boolean).flatMap(r => r.findings)
const cross = (await parallel(args.consistencyPrompts.map(p => () =>
  agent(p, { phase: 'Consistency', model: REVIEW_MODEL, schema: FINDINGS })))).filter(Boolean).flatMap(r => r.findings)
const seen = new Set()
const rawFindings = [...reviewed, ...cross].filter(f => f && !seen.has(f.id) && seen.add(f.id))

// Checkpoint before verification so a halt still yields findings.
await agent('Write this JSON array verbatim to reviews/.qa-checkpoint.json: ' + JSON.stringify(rawFindings),
  { label: 'checkpoint', phase: 'Review' })

// Phase 2: BATCHED verification (~8 findings per verifier). No `model:` override:
// verifiers inherit the main-loop model. Do not tier this down.
const B = 8, batches = []
for (let i = 0; i < rawFindings.length; i += B) batches.push(rawFindings.slice(i, i + B))
const verdicts = {}
for (const r of (await parallel(batches.map((b, i) => () =>
  agent(verifyBatchPrompt(b), { label: `verify:batch-${i + 1}`, phase: 'Verify', schema: VERDICTS }))))
  .filter(Boolean)) for (const v of r.verdicts) verdicts[v.id] = v

// Keep unrefuted or uncited (unconfirmed) findings; apply the verifier's severity.
return rawFindings.map(f => ({ ...f, verdict: verdicts[f.id] ?? null }))
  .filter(f => !f.verdict || !f.verdict.refuted || !f.verdict.citation)
  .map(f => ({ ...f, severity: f.verdict?.severity_recommendation ?? f.severity }))
```

**Fallback without the Workflow tool**: run the same structure with sequential Agent (subagent) calls, same prompts, same schemas (agents return raw JSON), same rules, still batching the verifiers. Slower; consider narrowing scope.

## Verification rules (bake into `verifyRules`)

Each verifier receives a BATCH of findings (~8) and returns one verdict per finding `id`. For every finding in its batch it tries to REFUTE the claim, working **excerpt-first**: read the cited `file:line` window first (roughly 40 lines either side of the citation in `evidence`, with the relevant manifest in context) and judge from it. Open the FULL file only when the window cannot settle the claim, for example when refuting it depends on compensating behavior elsewhere in the file. Most findings are local and settle on the window; escalation is always available, so this never weakens a verdict.

- Refuted with citation: drop the finding.
- Confirmed with citation: keep, record the confirmation.
- Cannot confirm or refute with a citation: keep, downgrade severity one level, mark `unconfirmed`.
- Verifiers always return `severity_recommendation` judged against the rubric and `PROJECT_CONTRACT` with the full context they gathered; when it differs from the reviewer's severity, synthesis uses the verifier's (reviewers over-rate findings whose subject has compensating coverage elsewhere).

**Simplification findings verify differently.** For a finding in a simplification category (marked as such in the spoke charter), the verdict is pass or refute; the `unconfirmed` outcome does not apply, and a verifier that cannot confirm such a finding returns `refuted: true`. The test has three parts, all required: the suggestion names the concrete replacement; the replacement preserves every behavior of the cited code, judged excerpt-first with escalation to the full file when the window cannot settle it (for prose findings, every fact of the original passage); and the replacement reduces a countable quantity (parameters, branches, layers, indirections, exported names, or net lines). Any part failing refutes the finding. Synthesis treats an `unconfirmed` verdict on a simplification finding as refuted.

## Phase 4: Report synthesis

Classify every surviving finding:

- `ACCEPTED`: its `id` is in `reviews/accepted.md` (exact match, the primary path), or its file plus normalized claim slug matches an accepted entry whose id differs only in the dimension or category segments (the same fuzzy match KNOWN uses). Suppress from the main list; count it and list id + justification in the appendix.
- `KNOWN`: it appeared in the dimension's base report or the most recent prior report (match by `id`; fuzzy-match file + slug if ids drifted).
- `NEW`: everything else.

**Incremental carry-forward.** On an incremental run, every base-report finding of that dimension whose `file` was NOT in `CHANGED_FILES` is carried into this report as `KNOWN` with its original `id` and severity, without being re-reviewed; it was already adjudicated against unchanged code. Only files in `CHANGED_FILES` are freshly reviewed and can yield `NEW` findings for the per-file dimensions. A carried finding whose `id` is in `reviews/accepted.md` stays `ACCEPTED` as usual. Record in the header which mode ran, per dimension.

Write the report to `reviews/<YYYY-MM-DD>-qa.md` (today's date), committed to the repo. The `Scope:` and `Commit:` lines are machine-read by the `changed` manifest: keep their format exactly (dimensions comma-separated, then ` / `, then the path or `all`).

```markdown
# QA report: <date>
Scope: <dimensions> / <path or all> | Mode: <full | incremental base=<sha> per dimension | full (no prior SHA)>
Commit: <HEAD sha this run was generated against>
Findings: N new, K known, A accepted-suppressed | Refuted in verification: R
Simplification: S findings, net reduction ~N
Profile: <.claude/qa-profile.md | none (inferred from <convention files>)> | Not applicable: <categories skipped for missing inputs>

## High / ## Medium / ## Low
| ID | Status | Category | File | Claim | Evidence | Suggestion |

## Per-dimension summaries
<each spoke defines its summary block, with all counts derived from findings by category>

## Appendix: accepted findings (suppressed)
| ID | Justification (from reviews/accepted.md) |

## Follow-up
Cluster related unaddressed findings into change proposals (for example /opsx:propose); a manual step, never automatic.
Cluster simplification findings into their own deletion-oriented changes per subsystem, never mixed into defect-fix changes.
To accept a finding as a deliberate tradeoff, add its ID and a one-line justification to reviews/accepted.md.
```

`reviews/accepted.md` holds one entry per line: `` - `<id>` - <one-line justification> ``, optionally grouped under headings.

Derive the `Simplification:` line from the surviving findings in simplification categories: S is their count and N sums the countable reductions their suggestions state; never hand-write either number.

Tell the user the headline counts and the report path. Do not create change proposals, do not fix findings, do not edit `reviews/accepted.md` yourself.

**If a run halts before synthesis** (credits, concurrency cap, timeout): recover the findings from `reviews/.qa-checkpoint.json`, or, failing that, from each subagent's `StructuredOutput` block in the workflow's `agent-*.jsonl` transcripts. Synthesize the report from whatever was collected, but mark every finding `UNVERIFIED` and state in the header which phases (verification, which dimensions) did not complete; raw reviewer output carries a real false-positive rate, so never present it as confirmed. Delete `reviews/.qa-checkpoint.json` once the report is written.
