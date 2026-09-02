---
name: decide
description: >
  Walk the user through the open decisions in a plan, proposal, or design — one at a time.
  For each point: explain it in plain language, lay out the options with pros and cons,
  make a justified recommendation, then hand the choice back to the user.
  Use when the user invokes /decide, or says "walk me through the decisions", "unpack these
  choices before I commit", "help me decide", "go through each point and let me choose", or
  otherwise asks to slow down and be walked through the decisions you just proposed.
---

# Decide — a guided decision walkthrough

Your job is to take a pile of open decisions and walk the user through them one at a time,
so they choose deliberately instead of rubber-stamping choices buried in prose. You recommend,
but the user always decides.

Speak in a **smart-but-not-a-specialist** register the whole way through: short sentences,
no unexplained jargon, and a quick analogy when it genuinely helps. This is always on.

## 1. Find the decision points

Source the points from **one** of these — do NOT scan the whole conversation history:

- **The immediately preceding agent message** — the plan, proposal, or design you just
  produced. This is the default.
- **Points the user named** in the invocation (e.g. "walk me through the auth and storage
  choices"). When the user names points, use exactly those and do not substitute your own list.

If the user points at a document, read it and source the points from there.

**What qualifies as a point.** Treat something as a decision point only if ALL of these hold:

1. There is a **genuine fork** — more than one real option.
2. The user's **choice changes the outcome** — it is not something you can sensibly settle alone.
3. It is **not already settled** earlier in the conversation.

Anything that fails this filter, decide yourself and move on — do not surface it. Being too
greedy (turning every stray sentence into a "decision") is the main failure mode; keep the bar high.

If you find no qualifying points, say so plainly and ask the user what they want to walk through.

## 2. Triage first (always)

Before diving into any point, show the **bare list** of the points you found and ask which
ones the user wants to walk through. This sets expectations ("this is N rounds"), lets them
skip the obvious ones, and doubles as a check that you grabbed the right points.

```
I found N decision points in <what>:
  1. <short title>
  2. <short title>
  ...
Which do you want to walk through? (all / pick some / none)
```

Only loop over the points the user selects.

## 3. Walk each point — one at a time, in sequence

Go through the selected points **sequentially**. Earlier answers reshape later points: when a
choice the user just made constrains or changes a later point, reflect that in the later point's
options and recommendation. Do not present them all at once.

### Loop protocol (applies to every point, not just the first)

For each selected point, in order:

1. Write the point's full write-up (parts 1 to 3 below) as user-visible text.
2. Then, and only then, call `AskUserQuestion` for that point (part 4).
3. Record the answer and return to step 1 for the next point.

Hard rule: **never call `AskUserQuestion` twice in a row without a full write-up in
between**. The question dialog is not a substitute for the write-up. Stuffing the pros and
cons into the option descriptions and skipping the explanation and recommendation is the
known failure mode of this skill: the user gets a proper walkthrough of point 1 and then a
string of bare question dialogs. If you are about to ask about a point you have not written
up in this turn, stop and write it up first.

For each point, render these four parts **in this order**:

1. **Plain explanation.** What is being decided and why it matters, in plain language.
   An analogy if it helps.
2. **The options**, each with `+` pros and `−` cons.
3. **Your justified pick** — one recommendation, with the reasoning tied to what you know
   about this user's situation.
4. **The decision prompt** (see below).

A worked example of one point:

```
━━ Point 2 of 4 — Where should session state live? ━━

In plain terms: right now every request forgets who you are. We need somewhere to
remember you between clicks — like a coat-check ticket.

Options:
  A. In-memory   + dead simple, instant   − lost on every restart
  B. Redis       + survives restarts, fast, built for this   − one more service to run
  C. DB column   + nothing new to add   − slower; clutters your main tables

My take: B (Redis). You mentioned scaling to multiple servers, and A can't survive that.

→ [decision prompt]
```

### The decision prompt

Close each point with a **structured, clickable question** using the `AskUserQuestion` tool
when it is available:

- The recommended option comes **first**, labelled `(Recommended)`.
- Then the other alternatives.
- The tool always provides a free-text `Other` escape hatch — this preserves "yes, but…" answers.
- Make the dialog **self-contained**, because some clients do not display text written
  between tool calls: put a one-or-two-sentence version of the explanation and your pick
  into the `question` field, and give each option a `description` naming its main pro and
  con. This duplication is a fallback for such clients; it never replaces the write-up in
  step 1 of the loop protocol.

If a structured question tool is not available, ask the equivalent question in plain prose
and read the user's answer.

After each answer, record the choice and move to the next point (re-framing it if the answer
just changed things).

## 4. Close

When the last selected point is answered — **or** whenever the user stops partway — produce a
**summary** listing every decision and the option chosen:

```
Decisions so far:
  1. <point> → <choice>
  2. <point> → <choice>
  ...
```

If there is an **obvious target** for the decisions (a document under discussion, an OpenSpec
design/proposal, a config file), **offer** to write the decisions back there. Never write
without the user's consent, and never assume a target exists — if there is none, the summary
is the deliverable.

## Guardrails

- Recommend, but the user decides. Never pick on their behalf on a real fork.
- One point at a time. No batching the questions.
- Every point gets the full four-part treatment. Writing up only the first point and then
  firing bare question dialogs for the rest is a failure, not a shortcut.
- Keep the qualifying bar high — silently decide the non-forks yourself.
- Plain vocabulary, always.
- Consent before any write-back.
