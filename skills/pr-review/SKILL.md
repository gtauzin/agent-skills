---
name: pr-review
description: "Advanced multi-agent review of the current PR changes: lens reviewers (correctness, design, security, tests, docs, simplification) over the branch diff against main, with batched adversarial verification and the EvoltaForecast severity rubric. Use whenever the user asks to review the PR, review the branch, review the current changes or diff in depth, do an advanced or thorough code review, or check the branch before pushing or merging, even if they do not name this skill."
---

# PR Review

Verified quality review of the current PR changes. This skill is the diff-scoped counterpart of the `/qa` family: it reviews only what the branch changes relative to `main`, but with the same machinery (fan-out reviewers, batched adversarial verification, the EvoltaForecast severity rubric) instead of a single-pass read.

Relationship to other tooling:

- The `/qa` family reviews the repo as it stands and only reports. This skill reviews the PR diff and can apply fixes after the report, on explicit instruction.
- `/code-review`, `code-review-expert`, and `/simplify` are lighter single-pass diff reviews. Use this skill when the user wants depth or verification.
- ruff, ty, rumdl, interrogate, linkchecker, `kedro check-pipelines`, and the CI workflows are deterministic gates. Never report what they enforce (chassis exclusion rule).

## Chassis required

Read `.claude/commands/qa.md` FIRST. The following sections apply verbatim to this skill:

- **Ground rules**: the exclusion rule, the simplicity rule, the severity rubric (high = data contract, topology contract, correctness bug, false claim; medium = cross-pipeline or code-vs-convention inconsistency, the misleading-structure list; low = judgment calls and all other simplification findings), and the finding JSON format.
- **Scope**: `packages/` is out of scope. Changed files under `packages/` are listed in the report as not reviewed, never given findings.
- **Orchestration** rules 1 to 3: batch the verifiers, checkpoint after Review, size review units by lines.
- **Verification rules**, including the stricter pass-or-refute test for simplification categories.

This file defines only what is diff-specific: the manifest, the scoping rules, the lenses, the workflow, and the report. The `/qa` incremental and KNOWN machinery does not apply here; every run reviews the full diff fresh.

## Arguments

`/pr-review [base] [--report] [--fix]`

- `base`: base ref to diff against. Default `main`, falling back to `origin/main` if `main` does not resolve.
- `--report`: also write the report to `reviews/<YYYY-MM-DD>-pr-review-<branch-slug>.md`. Default is chat output only.
- `--fix`: after presenting the report, apply the surviving high and medium findings to the working tree. Without this flag, never edit anything; present the report and the next-steps options instead.

## Phase 0: diff manifest (`DIFF_MANIFEST`)

```bash
base=main
git rev-parse --verify --quiet "$base" >/dev/null || base=origin/main
mb=$(git merge-base "$base" HEAD)
echo "BRANCH $(git rev-parse --abbrev-ref HEAD) | BASE $base | MERGE_BASE $mb | HEAD $(git rev-parse --short HEAD)"
git diff --stat "$mb"
git diff --name-status "$mb"
git status --porcelain=v1 | sed -n 's/^?? /UNTRACKED /p'
cat reviews/accepted.md 2>/dev/null || echo "(no reviews/accepted.md yet)"
```

The diff runs against the working tree (`git diff "$mb"`, not `"$mb"..HEAD`), so uncommitted edits are in scope; untracked files count as added. Keep the accepted-finding IDs for report synthesis.

Edge cases:

- **Empty diff**: no changed files against the merge-base. Say so, suggest `/qa` for a repo-state review, and stop.
- **On main**: HEAD is `main` and there is no branch diff. Ask the user for a base ref or a commit range, and stop.
- **Large diff**: if the diff exceeds roughly 2000 lines, split each lens into per-file-group jobs so no reviewer reads more than ~2000 lines (chassis orchestration rule 3). Label the jobs `<lens>:<group>`.

## Diff-scoping rules (every reviewer)

1. A finding must cite at least one changed line, or be a direct consequence of the change. An unchanged caller broken by a changed signature qualifies; cite both sides.
2. Read context freely (surrounding code, callers of changed symbols, sibling pipelines, the paired tests), but report only on the diff. Callers of every changed public function or class must actually be read, not assumed.
3. Pre-existing defects in unchanged code are not findings. If reviewers notice a cluster of them, the report carries at most one line suggesting a `/qa` run for that area.
4. `dimension` in the finding JSON is the lens name below.

## Lenses

One reviewer per lens. Each reviewer prompt starts with:

```text
You are the {lens} reviewer for an EvoltaForecast PR review.
Read .claude/commands/qa.md "Ground rules" first and return findings in its JSON schema.
Apply the diff-scoping rules: findings must anchor on a changed line or a direct consequence of one.
MERGE_BASE: {mb} | CHANGED FILES: {relevant subset of DIFF_MANIFEST}
Run `git diff {mb} -- <files>` yourself to read the hunks. Cite file:line.
At most 8 findings, highest value first.
```

Then the lens charter:

### correctness

Read `.claude/commands/qa-source.md` for the `error-handling` and `contradiction` category definitions, then hunt for:

- Logic errors and edge cases the change introduces: empty frames, missing columns, off-by-one on time bounds, wrong join or filter semantics.
- `error-handling` findings on changed code.
- `contradiction` findings on changed code (severity high: false claims, data-contract violations, topology-contract violations).
- Regressions: changed behavior or signatures that unchanged callers or catalog entries still depend on.

### design

Read `.claude/commands/qa-design.md` for the layering contract and the category definitions, then apply `dependency-direction`, `layering-leakage`, `node-reuse`, and `needless-abstraction` to the changed modules. When the diff touches one pipeline of a shared shape (`training`, `inference`, `backtesting`, `tuning`, `snapshot`), check the change against the sibling pipelines for divergence in node naming, structure, namespacing, or tagging (category `pipeline-structure`). The layering contract is how SOLID is judged here; do not raise generic SOLID findings detached from it.

### security

No spoke exists for this lens; the charter is self-contained. Check the changed files for:

- Secrets, credentials, or tokens in code, config, logs, or error messages; Azure credential handling in `smoke/` and submission code.
- Command or subprocess injection, and path traversal on user-supplied or config-supplied paths.
- Unsafe deserialization (pickle, `yaml.load` without a safe loader).
- Race conditions and check-then-act patterns on files or shared state.
- Unbounded loops, unbounded memory on data paths, missing timeouts on network calls.

State both exploitability and impact in the evidence. Severity high when exploitable, medium otherwise.

### tests

Read `.claude/commands/qa-tests.md` for the category definitions, then:

- Code -> test direction of `bidirectional`: changed or new src branches (error paths, gating, topology dispatch) with no test exercising them.
- New or changed tests judged under `vacuous-assertion`, `near-duplicate`, and `ad-hoc-duplication`.
- `structural-coverage`: a pipeline or registry change must keep the structural gate exercised (registry completeness, `unresolved_inputs`, `compile_check`).

### docs

Read `.claude/commands/qa-docstrings.md` for the category definitions, then:

- `signature-drift`, `false-claim`, `numpy-section`, and `misleading-example` on changed symbols and changed docstrings.
- Changed docs pages checked against the changed code they describe: stale commands, stale flags, stale file paths, broken relative links the linkchecker cannot see until the next build.
- Surface drift: a public symbol, CLI command, or justfile recipe the diff adds, renames, or removes, with no matching update in `docs/`, `mkdocs.yml` nav, or the API reference.

### simplification

Read `.claude/commands/qa-source.md` for the `duplication` and `dead-code` category definitions, then apply them to changed code only. Judge needless complexity and comment altitude directly (qa-source defines no category for them): flag complexity a named simpler construct removes, and comment blocks the diff adds or edits that restate the code or narrate incidents. Also flag code the change orphans: helpers, config fields, fixtures, or docs sections whose last user the diff removes. All chassis simplification rules apply: named concrete replacement, countable reduction, net deletion.

## Orchestration

Invoking this skill is the user's explicit opt-in to multi-agent orchestration. Use the Workflow tool; without it, fall back to sequential Agent calls with the same prompts and schemas, still batching the verifiers.

Build the lens jobs in the main loop from `DIFF_MANIFEST` (each lens gets only the file subset it reviews; every lens gets the src changes, `tests` also gets changed tests, `docs` also gets changed docs and config). Pass them via `args`. Adapt the chassis script:

```javascript
export const meta = {
  name: 'pr-review',
  description: 'Lens reviewers over the PR diff with batched adversarial verification',
  phases: [{ title: 'Review' }, { title: 'Verify' }],
}
// FINDINGS and VERDICTS: copy the schemas verbatim from .claude/commands/qa.md.
const REVIEW_MODEL = 'sonnet'   // bulk read-and-flag tier; Verify inherits the main-loop model. Do not tier Verify down.

const reviewed = (await parallel(args.lensJobs.map(j => () =>
  agent(j.prompt, { label: `review:${j.lens}`, phase: 'Review', model: REVIEW_MODEL, schema: FINDINGS }))))
  .filter(Boolean).flatMap(r => r.findings)
const seen = new Set()
const raw = reviewed.filter(f => f && !seen.has(f.id) && seen.add(f.id))

await agent(`Write this JSON array verbatim to reviews/.pr-review-checkpoint.json: ${JSON.stringify(raw)}`,
  { label: 'checkpoint', phase: 'Review' })

const B = 8, batches = []
for (let i = 0; i < raw.length; i += B) batches.push(raw.slice(i, i + B))
const verdicts = {}
for (const r of (await parallel(batches.map((b, i) => () =>
  agent(args.verifyPrompt(b), { label: `verify:batch-${i + 1}`, phase: 'Verify', schema: VERDICTS }))))
  .filter(Boolean)) for (const v of r.verdicts) verdicts[v.id] = v

return raw.map(f => ({ ...f, verdict: verdicts[f.id] ?? null }))
  .filter(f => !f.verdict || !f.verdict.refuted || !f.verdict.citation)
  .map(f => ({ ...f, severity: f.verdict?.severity_recommendation ?? f.severity }))
```

`args.verifyPrompt` bakes in the chassis verification rules plus one diff-specific rule: the verifier reads the cited diff hunk and roughly 40 lines of surrounding context first, escalating to the full file or the callers only when the window cannot settle the claim. A finding that anchors on no changed line and no consequence of one is refuted on scoping grounds regardless of whether its claim is true.

If the run halts before the report: recover from `reviews/.pr-review-checkpoint.json`, mark every finding UNVERIFIED, state which lenses did not complete, and delete the checkpoint once the report is written.

## Report

Classify surviving findings against `reviews/accepted.md`: matching IDs are suppressed from the main list and counted in an appendix line. Then present in chat:

```markdown
## PR review: <branch> vs <base>

Files: N changed (+A/-D) | Findings: X high, Y medium, Z low | Refuted in verification: R
Not reviewed: <packages/ paths if any> | Accepted-suppressed: A

### High / ### Medium / ### Low
- **[file:line](link)** (lens/category) Claim. Evidence. Suggestion.

### Clean
Lenses with no surviving findings, and anything not covered (for example a lens skipped because no file matched).
```

Use clickable `[file.py:42](src/file.py#L42)` references. With `--report`, also write the same content to `reviews/<YYYY-MM-DD>-pr-review-<branch-slug>.md` with a header carrying branch, base, merge-base, and HEAD sha.

Then next steps. Without `--fix`, offer and wait:

1. Fix all surviving findings.
2. Fix high and medium only.
3. Fix specific findings by ID.
4. No changes.

Never edit before the user chooses. With `--fix`, the flag is the confirmation: apply the surviving high and medium findings after presenting the report, re-run `just check` equivalents on the touched files if a recipe exists, and summarize what changed. Low findings are never auto-applied. Do not create OpenSpec changes and do not edit `reviews/accepted.md`; point the user to `/opsx:propose` for findings worth clustering into a change.
