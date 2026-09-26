---
description: "QA spoke: documentation quality review across Diataxis quadrants (code correctness, API links, glossary, cross-references, clarity, accuracy, companion notebooks, consistency)."
---

# /qa-docs

> **Chassis required.** Read the hub `qa.md` FIRST (the project's `.claude/commands/qa.md` if it exists, else `~/.claude/commands/qa.md`) and follow its project discovery, ground rules, severity rubric, finding schema, orchestration, verification, and reporting. This file defines only the docs dimension.

## Phase 0 manifests

```bash
QA=~/.claude/commands/qa/scripts/qa_manifest.py
python3 $QA docs
uv run python $QA surface
```

From `docs`:

- `QUADRANT_FILES`: pages per Diataxis quadrant, read from the docs nav when one exists (mkdocs.yml) and from directory names otherwise. Every `index.md`, `changelog.md`, `tags.md`, and `glossary.md` is excluded. `Other: <title>` groups are nav sections that match no quadrant; review them under the closest quadrant rubric and name it in the report. `MISSING` entries are nav targets that do not exist.
- `GLOSSARY_TERMS`: `*[term]: definition` abbreviation lines under the docs dir. `none` makes the `glossary` category not applicable unless the profile names another glossary format.
- `NOTEBOOK_MAPPING` and `COMPANION_MARKER_PAGES`: example notebooks declaring a `"companion"` page, and pages carrying the `<!-- COMPANION_NOTEBOOKS -->` marker. When both are empty and the profile's Docs section names no other convention, the `companion` category is not applicable.
- `API_PAGES`: `qualified name -> page URL` for docs pages that document a package symbol (a page named after the symbol, or a `::: name` directive). When it is `none`, derive URLs from the profile's Docs section or the API page generator in the docs config, and state which.

From `surface`, build `API_MANIFEST`: each `SYMBOLS` line gives the qualified name, kind, and parameters; join it with `API_PAGES` for the URL. Build a short-name lookup (last segment of the qualified name) so reviewers can match unqualified names in code blocks.

## Units and batching

Units are batches of ~5 files within one quadrant, topically grouped (all pages about one feature together, all "create a ..." how-to guides together). Quadrant batches run in parallel under the chassis Workflow template. The path filter selects a quadrant (`how-to`) or a single page.

## Rubrics (portable resolution)

Each quadrant's rubric is the matching skill, resolved by name from the session's available skills: `diataxis-tutorial-writer`, `diataxis-howto-writer`, `diataxis-explanation-writer`, `diataxis-reference-writer`. Never reference rubrics by filesystem path. If a skill is unavailable, use this fallback summary: tutorials are step-by-step, encouraging, second-person, complete runnable code with rationale per action; how-to guides are direct, imperative, focused snippets, enough context to act independently; explanation is reflective, discursive, third-person, minimal illustrative code; reference is austere, declarative, precise and complete.

## Reviewer prompt (per batch)

```text
You are a documentation-quality reviewer for the {package} package (chassis rules apply; return findings in the hub JSON schema).
QUADRANT: {quadrant} | RUBRIC: read the {diataxis-*-writer} skill (or the fallback summary)
REFERENCE DATA: API_MANIFEST, GLOSSARY_TERMS, NOTEBOOK_MAPPING | PROJECT_CONTRACT: {data contract and conventions}
FILES: {full content of each file in the batch}

Work through every file and produce findings per category:

### code-correctness
For every fenced code block: package class/function names must exist in API_MANIFEST (short-name match);
constructor and call keyword arguments must match the manifest parameter list; import paths must be valid
per the manifest's qualified names and exporting packages. A code block contradicting its surrounding prose
is severity high.

### api-links
Per ## section: the FIRST prose mention of each package symbol must be a markdown link whose URL matches
the manifest URL. Only this package's symbols (skip third-party libraries). Skip when API_MANIFEST has no URLs.

### glossary
Domain terms appearing 2+ times but missing from GLOSSARY_TERMS: report with the term, count, and a proposed
`*[term]: definition` line in the suggestion field. Also report topically relevant GLOSSARY_TERMS the file
never uses. Skip when the glossary category is not applicable.

### cross-references
Only what the link checker cannot do (built-site link breakage belongs to it): missing cross-references (the
file discusses a topic another page covers but never links it; suggest the link) and links pointing at pages
that were never written.

### clarity
Apply the quadrant RUBRIC: logical flow (concepts introduced before use), explanation depth appropriate to the
quadrant, structural fitness (heading hierarchy, code-to-prose ratio), ambiguous or jargon-heavy sentences
(quote them, suggest a rewrite), topic completeness against the title.

### simpler-statement (simplification category)
- A passage that carries the same content with fewer concepts or plainer sentences; quote it, put the rewrite
  in the suggestion.
- Mechanism narration where the reader needs the rule; state the rule instead, except on explanation pages
  where discussing the mechanism is the point.

### accuracy
Claim-to-code alignment (prose says size=5, code must use size=5); parameter value reasonableness for the
demonstrated use case; output descriptions matching actual return types, shapes, or columns; cross-block
consistency (variable names, initialized-before-use) across the file. False output descriptions and
statements contradicting PROJECT_CONTRACT are severity high.

### companion
If the file carries the companion marker: look it up in NOTEBOOK_MAPPING (missing companion is a finding).
If a companion exists, read the full notebook and review bidirectionally: page -> notebook (page topics with
no notebook cell; suggest the cell) and notebook -> page (notebook content the page omits or contradicts;
the page is the source of truth, prefer notebook adaptations). Note narrative-order divergence. Summarize
per-topic coverage in the evidence field. Skip when the companion category is not applicable.

{extra categories for this dimension from the profile, if any}

Rules: cite file/section (and line where possible) for every finding; at most 6 findings per file, highest
value first; skip anything the markdown linter or link checker enforces.
```

## Consistency prompts (one per quadrant, global within it)

Input: each file's first 20 lines plus its full heading list, and the quadrant rubric. Categories: `opening-pattern`, `heading-hierarchy`, `code-block-style`, `crosslink-pattern`, `prerequisites-format`, `companion-presence`, `tone`.

1. Opening pattern: group files by opening-sentence pattern; flag deviations from the rubric's expected pattern.
2. Heading hierarchy: expected structure per rubric; if two camps exist (numbered vs unnumbered), list both and recommend one.
3. Code block style: tutorials complete and runnable; how-to focused snippets; explanation minimal; reference signatures only.
4. Cross-link directions: tutorials link to explanation and how-to; how-to to reference and explanation; explanation to tutorials and how-to; reference to source. Flag systematic gaps.
5. Prerequisites format (tutorials, how-to): bullet vs prose, linked vs unlinked; flag inconsistencies.
6. Companion presence (only when companions exist): tutorials all have companions; how-to most; explanation and reference generally none. Flag deviations.
7. Tone: per rubric; quote sentences that deviate.

## Aggregation

- Glossary candidates: collect all `glossary` findings, dedup case-insensitively by term, sum occurrence counts across files, sort descending, and render one proposed-definitions block ready to append to the glossary file.
- Quadrant summary: a table of finding counts per category per quadrant, derived entirely by counting findings (never hand-written).
