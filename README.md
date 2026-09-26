# agent-skills

Global Claude Code skills and commands, the contents of `~/.claude/skills` and
`~/.claude/commands`.

## Install on a new machine

```bash
git clone git@github.com:gtauzin/agent-skills.git ~/.agents
mkdir -p ~/.claude
ln -sfn ~/.agents/skills ~/.claude/skills
ln -sfn ~/.agents/commands ~/.claude/commands
```

## Azure ML compute instance

The compute instance home directory is lost when the instance is deleted or
recreated. Clone into the workspace file share instead and symlink into `~/.claude`:

```bash
git clone git@github.com:gtauzin/agent-skills.git ~/cloudfiles/code/Users/<you>/.agents
mkdir -p ~/.claude
ln -sfn ~/cloudfiles/code/Users/<you>/.agents/skills ~/.claude/skills
ln -sfn ~/cloudfiles/code/Users/<you>/.agents/commands ~/.claude/commands
```

The file share is CIFS and does not support symlinks inside it, so keep the
symlink on the local disk pointing in.

## QA command family

`/qa` (hub) and `/qa-source`, `/qa-docstrings`, `/qa-tests`, `/qa-design`,
`/qa-surface`, `/qa-docs`, `/qa-assets` (spokes) run verified, multi-agent quality
reviews of a Python package and write `reviews/<date>-qa.md` in the project. They
are package-independent:

- `commands/qa/scripts/qa_manifest.py` computes every deterministic input (package
  and layout, lint and CI gates, review units, import graph, public surface, test
  suites, docs quadrants). Run `python3 ~/.claude/commands/qa/scripts/qa_manifest.py -h`
  from a project root to see the subcommands.
- Project facts the script cannot detect (data contract, layering rules, check-suite
  conventions) go in the project's `.claude/qa-profile.md`. `/qa --init-profile`
  drafts it from the project's `CLAUDE.md` and docs.

A project that keeps its own `.claude/commands/qa*.md` shadows the global copies.
