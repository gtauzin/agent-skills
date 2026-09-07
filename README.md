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
