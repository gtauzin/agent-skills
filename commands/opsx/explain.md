---
name: "OPSX: Explain"
description: Write a temporary markdown note explaining a change in plain language, after explore or after propose
allowed-tools: Bash(openspec:*)
category: Workflow
tags: [workflow, explain, experimental, writing]
---

Write a throwaway markdown note that explains the change to a person who never opened
the bundle and was not in the conversation.

Use it at either seam of the lifecycle:

- **after `/opsx:explore`** to freeze loose thinking into something readable before it
  evaporates, while no bundle exists yet
- **after `/opsx:propose`** to render the proposal, design, specs, and tasks as one
  narrative a reviewer can read in two minutes instead of opening five files

The note is a reading aid, not an artifact. It never enters the change bundle and is
never committed.

---

**Store selection:** If the user names a store (a store is a standalone OpenSpec repo
registered on this machine) or the work lives in one, run `openspec store list --json`
to discover registered store ids, then pass `--store <id>` on the commands that read
specs and changes (`status`, `list`, `show`, `context`). Without a store, commands act
on the nearest local `openspec/` root.

**Input**: The argument after `/opsx:explain` is the change name (kebab-case), or a
short topic if there is no change yet. If omitted, infer from the conversation. If a
bundle is plausible but ambiguous, run `openspec list --json` and use the
**AskUserQuestion tool** to let the user pick.

## Step 1 - Pick the mode

Run `openspec status --change "<name>" --json` when a name resolves.

- **Bundle mode**: the change exists. Read every artifact the status JSON reports under
  `artifactPaths.<artifact>.existingOutputPaths` (proposal, design, specs, tasks). These
  are the source of truth for the note.
- **Explore mode**: no bundle, or the name is only a topic. The source of truth is the
  conversation itself plus whatever you read in the repo while exploring. Say so in the
  note, and be explicit that nothing is committed to yet.

Do not create a bundle to get out of explore mode. Explaining the thinking is the point.

## Step 2 - Write the note

Write one markdown file. Choose the path in this order:

1. the session scratchpad directory, if this session was given one
2. otherwise `${TMPDIR:-/tmp}/opsx-explain/`

Name it `<change-name>-explain.md`, or `<topic-slug>-explain.md` in explore mode.
Rerunning overwrites the same path; if the user wants the previous note kept, move it
first and say that you did.

Structure, adapted to what actually exists (drop sections with nothing real to say
rather than padding them):

| Section | What goes in it |
| ------- | --------------- |
| One-paragraph summary | What changes and why, in the reader's vocabulary |
| The problem | What is broken or missing today, with the concrete symptom |
| What we are doing about it | The shape of the change, not a task list |
| Key decisions | Each decision, the alternative rejected, and why |
| What this does not do | Scope boundaries and deliberate omissions |
| Open questions | Only the ones a reader could actually answer |
| Where the detail lives | Paths to proposal, design, specs, tasks (bundle mode only) |

## Step 3 - Report

Give the note as a **markdown link** so the user can open it in one click, never as bare
text or a backticked path: `[<file-name>.md](<absolute-or-workspace-relative-path>)`.
Use a workspace-relative path when the note landed inside the project, and the absolute
path otherwise. Then add a two or three line gist inline so they can judge whether to
open it. Do not paste the whole note back into the conversation.

**Writing rules**

- Plain language over OpenSpec vocabulary. "Requirement", "delta", "capability", and
  "artifact" mean nothing to the reader; spell out the actual thing.
- Quote the bundle or the conversation before characterizing it, so the reader can see
  you did not invent the claim.
- Prefer the concrete consequence over the abstract rationale: what a person will be
  able to do, or stop having to do.
- No em-dashes or en-dashes anywhere in the note.
- Mark uncertainty as uncertainty. An explanation that smooths over an unresolved
  decision is worse than no explanation.

**Guardrails**

- Read-only apart from the note itself. Never edit the change, fix anything you notice,
  create a change, implement, or archive.
- Never write the note inside the change directory, and never stage or commit it.
- Do not invent decisions, rationale, or scope that the bundle and the conversation do
  not support. A thin note about a thin change is the correct output.
- If you notice a real problem while reading (contradiction, missing task, stale spec),
  mention it once to the user after reporting the path, and point at `/opsx:review`
  rather than judging it here.
