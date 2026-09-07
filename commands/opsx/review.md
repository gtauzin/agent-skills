---
name: "OPSX: Review"
description: Review an OpenSpec change and emit a blocking verdict (ready / needs-work / blocked) - task/spec/design consistency, grounding, testing, and Diataxis docs adequacy
allowed-tools: Bash(openspec:*)
category: Workflow
tags: [workflow, review, experimental, gate]
---

Review an OpenSpec change and return one **verdict** with the findings that justify it.

This is the semantic gate the opsx lifecycle is missing. `openspec validate` checks the
structural floor (deltas exist, scenarios present); this checks everything above it:
does the bundle tell one consistent story, is it grounded in the repo, is it testable,
is it documented in the right Diátaxis quadrant, and does its delta apply cleanly to
canonical. It borrows the `/qa` chassis discipline (severity, finding schema,
adversarial verification) but its output is a change-scoped gate, not a
`reviews/*-qa.md` snapshot.

**Input**: The argument after `/opsx:review` is the change name (kebab-case). If
omitted, infer the change from conversation context; if ambiguous, run
`openspec list --json` and use the **AskUserQuestion tool** to let the user pick.
Announce: "Reviewing change: <name>".

**This command is read-only.** It never edits the change, fixes findings, creates
changes, or archives/syncs. It only reads and reports. Recommending a fix is not
applying it: the user decides, and `/opsx:apply` does the work.

**Portability.** The deterministic manifest (Step 1) is fully generic: it needs only the
openspec CLI and the standard change-bundle layout, so it works in any OpenSpec repo.
The judgment layer (Step 2) references EvoltaForecast specifics (the `/qa` chassis
finding schema and severity, the house data/topology contract, the 80% new-file
coverage gate). In another project, treat those as this-repo defaults: resolve the
`qa-tests` and `diataxis-*-writer` rubrics by name if present (fall back to inline
summaries otherwise), and substitute that project's own conventions for the house
architecture and CI gates. The finding shape used throughout is
`{id, dimension, severity, category, file, claim, evidence, suggestion}`.

---

## Step 1 - Run the deterministic manifest first

Everything with ground truth in the repo is decided by a script, not by you. Run the
manifest that ships next to this command (it finds the target OpenSpec repo by walking
up from the current directory, so run it from inside the repo):

```bash
python3 ~/.claude/commands/opsx/scripts/review_manifest.py all <change-name>
```

(If this command is installed project-locally instead of globally, use
`.claude/commands/opsx/scripts/review_manifest.py`.)

This emits JSON with: `validate` (the precondition gate), `lifecycle` (propose-time
vs archive-time), `deterministic_findings` (already in the finding schema, already
gating), `traceability.requirement_task_candidates` and `what_changes`,
`modified.review_pairs` (canonical + delta bodies for you to judge staleness),
`grounding.symbols_for_agent`, and `cross_change.overlaps`.

**If the manifest exits non-zero, stop and report the error.** Never substitute a
guess for manifest data (the qa manifest rule).

**Precondition gate (the exclusion rule).** If `validate.passed` is `false`, return
`blocked` immediately, cite the validate issues, and do NO semantic review. Never emit
a finding that `openspec validate`, CI, ruff, ty, interrogate, linkchecker, or the
coverage gate already enforce (formatting, import order, scenario existence, delta
headers, docstring coverage, built-site links). Those are deterministic gates; this
review lives above them.

## Step 2 - Judge only what the manifest could not

The deterministic findings already stand. Your job is the semantic layer. Scale the
effort to the change: a one-task docs fix gets a single inline pass; a substantial
change (new capability, design.md, many tasks) earns the Workflow fan-out below. For
each dimension, produce findings in the hub schema (see `.claude/commands/qa.md` for
the exact JSON shape and the severity rubric; use the change-oriented rubric below).

Dimensions (mode from `lifecycle.mode`):

- **Coherence** - confirm each `requirement_task_candidates` link is a *real*
  implementing link, not just keyword overlap. A requirement whose best candidate is a
  weak or wrong task is a `high` "requirement will not be built". Confirm each
  `what_changes` bullet has an implementing task, and that no task does work no bullet
  or requirement motivates (orphan task = hidden scope). Confirm nothing violates a
  stated non-goal / out-of-scope.
- **Spec quality** - requirements normative (SHALL/MUST), atomic, and testable;
  scenarios concrete and falsifiable (observable WHEN/THEN), covering edge/negative
  cases, not happy-path only; no implementation leakage (function names, libraries
  belong in design.md, not specs).
- **Disjunctive outcomes** - for each delta scenario whose THEN offers more than one way to
  comply ("do X, **or** record the reason in Y"), check that the change states which branch it
  takes and that the branch it takes has its own verification task. A change satisfying one
  branch while its verification exercises the other is a `high`. This is distinct from
  traceability, which is judged per requirement and passes as soon as any scenario is verified:
  the cheap branch is a mechanical edit a grep can confirm, the other is an obligation to write
  something down that no grep confirms, so the branch that silently does not happen is invisible
  to the traceability check. Raise it as a **judgment** finding, never a manifest entry: an "or"
  joining two branches of compliance and an "or" joining two halves of one consequence are not
  distinguishable by text, so a false positive must be refutable rather than blocking outright.
  Confirmed by the verifier, it blocks.
- **MODIFIED staleness** - for each `modified.review_pairs` entry, compare
  `canonical_body` against `delta_body` and the artifact on disk: does the delta assume
  a canonical baseline that reality has moved past? A stale delta is a `high`.
- **Design** - present iff warranted (missing for a complex change, or heavy ceremony
  for a trivial one, are both findings); decisions justified with alternatives;
  respects house architecture (polars-only, kedro topology, pydantic parameter
  families, yohou conformance, the data contract: `time`, `vintage_time`,
  `{entity}__{column}` panels, `SCHEMA_MAP`). A design reaching for pandas or bypassing
  the schema layer is a `high`.
- **Testing** - resolve the `qa-tests` skill by name for the rubric. Every requirement
  must trace to a verify/test task; a task adding a `src/evolta_forecast/` file with no
  covering test task is a `high` (fails the coverage gate and ships an unverified
  requirement). Match expected verification to change type: code → unit tests +
  `kedro check-pipelines`/smoke where a pipeline is touched; docs → `mkdocs build
  --strict` + link check; notebook → doctest/execution.
- **Docs (Diátaxis)** - resolve the matching `diataxis-*-writer` skill **by name, never
  by path** (fallback summary in `qa-docs` if unavailable). A user-facing `what_changes`
  bullet with no doc task ships undocumented (`medium`); docs planned in the wrong
  quadrant (a procedure filed as reference) is a finding. Judge the explanation-vs-
  reference boundary where the change touches docs.
- **Grounding** - the manifest already gated paths. Resolve `grounding.symbols_for_agent`
  (pipelines, datasets, recipes, jobs, symbols) against the repo and the qa-surface /
  qa-docs manifests; a reference to something that does not exist and the change does
  not create is a finding. Sanity-check the proposal's "current behavior" claims and
  any numbers against reality.
- **Scope / risk** - scope bounded and non-goals honored; blast radius on shared
  contracts (schemas, topology, config families) matched by design + test depth;
  migration/rollback addressed for interface or data changes; ceremony proportional.
- **Archive-time only** (when `lifecycle.mode == archive-time`) - all tasks checked;
  the implementation actually matches the plan (spot-check the delivered files exist
  and do what the tasks claim); the delta applies cleanly to canonical (no drift since
  the change was written).

## Step 3 - Verify judgment findings adversarially (only verified findings block)

Deterministic findings from the manifest are already trustworthy and can block. Every
**judgment** finding you raised must survive an adversarial refute pass before it can
raise the verdict, exactly as the qa chassis verifies. Batch findings (~8) and, for
each, try to REFUTE it excerpt-first (read the cited window; open the full file only
if the window cannot settle it):

- Refuted with citation → drop it.
- Confirmed with citation → keep; it can block.
- Cannot confirm or refute → keep as **advisory**, downgrade one severity level; an
  advisory finding is reported but SHALL NOT raise the verdict to `blocked` on its own.

## Step 4 - Derive the verdict and report

Verdict from the highest severity among surviving findings that are eligible to block
(deterministic findings, plus adversarially confirmed judgment findings):

- any eligible `high` → **blocked**
- else any eligible `medium` → **needs-work**
- else → **ready**

Qualify a `ready`/`needs-work` verdict by `lifecycle.mode`: `ready-to-apply` at
propose-time, `ready-to-archive` at archive-time. Advisory-only findings never move the
verdict past `needs-work`.

Report to the user (do not write a file unless asked).

### Write for a reader who has not opened the artifacts

Assume the reader has **not read the proposal, design, specs, or tasks** and does not
know the OpenSpec vocabulary. A finding that only makes sense to someone holding the
bundle in their head is a failed finding. So:

- **Quote or paraphrase the artifact before judging it.** Never write "requirement 3 is
  not testable"; write "the spec asks that forecasts be 'reasonably fresh', and does not
  say what counts as fresh, so nobody can write a test that decides pass or fail."
- **Plain words.** Say "the plan" not "the bundle", "the written rule" not "the
  normative requirement", "the list of steps" not "tasks.md", "reference page" not
  "reference quadrant". Spell out any term you must keep, once: "a *delta* (the patch
  this change would apply to the saved spec)".
- **Say the consequence in the real world.** What breaks, for whom, when? "This ships a
  pipeline nobody tested, so a bad forecast reaches the dashboard silently" beats
  "missing test coverage".
- **Style:** no em-dashes or en-dashes anywhere in the report. Use a colon, comma,
  parentheses, or a second sentence.
- Cite `file:line` so the reader can look, but the finding must be understandable
  without looking.

### Shape of the report

```
Verdict: <blocked | needs-work | ready-to-apply | ready-to-archive>
Change: <name> | Mode: <propose-time | archive-time> | validate: <pass|fail>
Findings: H high, M medium, L low (X deterministic, Y verified, Z advisory)
```

Then one short paragraph, jargon-free, saying what this change is trying to do and
whether it is safe to proceed.

Then **one section per finding**, most severe first, each written as:

```
### <n>. <plain-language title of the problem>
`high | medium | low` · <dimension> · <deterministic | verified | advisory> · file:line

**What the plan says:** the relevant part, quoted or paraphrased.
**Why it is a problem:** the concrete consequence, in one or two sentences.

**Options**
1. <option name>: <what it means in practice, 1-2 sentences>
   - Pros: ...
   - Cons: ...
2. <option name>: ...
   - Pros: ...
   - Cons: ...
3. Leave it as is: <what that costs>
   - Pros / Cons: ...

**Recommendation:** <one option, and the reason in one sentence>
```

Give options only where there is a genuine fork. When a finding has exactly one sane
fix, skip the options block, state the fix, and say why it is the only reasonable one.
Keep "leave it as is" as an option whenever it is survivable, and be honest about its
cost. Group `low` and advisory findings into a single short "Minor notes" list with a
line each; do not spend an options block on them.

### Close by handing the decision back

After the findings, ask the user to decide. Use the **AskUserQuestion tool**, one
question per blocking finding (up to its limit, most severe first; if there are more,
ask about the top ones and list the rest for a follow-up round). Put the recommended
option first and mark it `(Recommended)`. Offer the real alternatives, including
proceeding as-is where that is defensible.

This stays read-only: record the answers, restate the resulting plan, and stop.
Applying the decisions is the apply step's job, in a separate step the user asks for.

---

## Orchestration (substantial changes)

Invoking `/opsx:review` on a substantial change is opt-in to multi-agent
orchestration; use the Workflow tool with the `/qa` chassis template: one reviewer per
dimension in a `Review` phase (pass the manifest JSON as context so reviewers judge
edges, not existence), then **batched** adversarial verifiers in a `Verify` phase
(~8 findings each, never one agent per finding), then synthesize the verdict. Tier the
bulk reviewers to a cheaper model and keep verification on the main model, as the
chassis does. The deterministic findings enter the report pre-confirmed and skip
verification.
