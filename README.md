# agent-skills

Personal Claude Code skills, the contents of `~/.claude/skills`.

The shared Evolta skills (the Diataxis writers, the QA family, `pr-review`, `pr`,
`git-commit`, `polish-changelog`, `marimo-notebook`, `docker-expert`,
`uv-package-manager`, `opsx-review` and `opsx-explain`) moved to the `evolta` plugin in
Evolta-Technologies/EvoltaPackageUtils. Install the plugin to get them.

## Install on a new machine

```bash
git clone git@github.com:gtauzin/agent-skills.git ~/.agents
mkdir -p ~/.claude
ln -sfn ~/.agents/skills ~/.claude/skills
```

## Azure ML compute instance

The compute instance home directory is lost when the instance is deleted or
recreated. Clone into the workspace file share instead and symlink into `~/.claude`:

```bash
git clone git@github.com:gtauzin/agent-skills.git ~/cloudfiles/code/Users/<you>/.agents
mkdir -p ~/.claude
ln -sfn ~/cloudfiles/code/Users/<you>/.agents/skills ~/.claude/skills
```

The file share is CIFS and does not support symlinks inside it, so keep the
symlink on the local disk pointing in.
