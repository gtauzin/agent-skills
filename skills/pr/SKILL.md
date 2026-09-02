---
name: pr
description: 'Create a branch (if needed), commit all changes, push, and open a GitHub Pull Request. Use when user says "/pr", "open a PR", "create a pull request", "submit for review", or wants to push changes and open a PR in one step.'
license: MIT
---

# PR: Branch, Commit, Push, and Open Pull Request

Create a new branch if on the default branch, commit staged/unstaged changes, push, and open a PR with a title and description matching the repository conventions.

## Workflow

### 1. Determine repository context

```bash
# Get current branch and default branch
git branch --show-current
git remote show origin | grep 'HEAD branch' | awk '{print $NF}'

# Get remote URL to determine owner/repo
git remote get-url origin
```

Parse `owner` and `repo` from the remote URL (handles both SSH and HTTPS formats).

### 2. Detect PR title conventions

Check existing merged PRs or branch naming to infer the title format:

```bash
# Check recent PR titles via gh CLI (if available)
gh pr list --state merged --limit 5 --json title 2>/dev/null || true
```

Common patterns to detect and follow:
- **Conventional Commits**: `feat: add X`, `fix: resolve Y`, `refactor: extract Z`
- **Imperative mood**: `Add retry logic`, `Fix null pointer`
- **Ticket prefix**: `[PROJ-123] Add feature`

If a pattern is detected, follow it. Otherwise default to conventional commit style.

### 3. Check for PR template

```bash
# Look for PR template in standard locations
for f in .github/PULL_REQUEST_TEMPLATE.md .github/pull_request_template.md docs/pull_request_template.md; do
  [ -f "$f" ] && cat "$f" && break
done
```

If a template exists, fill it in with relevant content from the diff. Keep it minimal and accurate.

### 4. Create branch if needed

If the current branch is the default branch (main/master), create a new branch:

```bash
current=$(git branch --show-current)
default=$(git remote show origin | grep 'HEAD branch' | awk '{print $NF}')

if [ "$current" = "$default" ]; then
  # Derive branch name from the change type and scope
  # Examples: fix/stale-observation-state, feat/add-retry-logic, refactor/extract-utils
  git checkout -b <type>/<short-description>
fi
```

Branch naming: `<type>/<kebab-case-description>` derived from analyzing the diff.

### 5. Stage and commit

```bash
# Check if there are uncommitted changes
git status --porcelain
```

If there are unstaged/staged changes:

```bash
git add -A
git commit -m "<conventional commit message>"
```

Generate the commit message by analyzing the diff (follow the git-commit skill conventions: type, optional scope, imperative description under 72 chars).

If there are no uncommitted changes, skip this step.

### 6. Push

```bash
# Push and set upstream if needed
git push --set-upstream origin "$(git branch --show-current)"
```

### 7. Open the Pull Request

Use the `github-pull-request_create_pull_request` tool with:

- **title**: Matches detected convention (conventional commits, imperative, etc.). Under 72 chars.
- **head**: Current branch name (just the name, not `owner:branch`).
- **base**: Default branch of the repo (omit to use repo default).
- **body**: Filled PR template if one exists, otherwise a concise summary.
- **draft**: `true` by default. Only set to `false` when the user explicitly asks for a non-draft (ready-for-review) PR.

### 8. Report result

After the tool returns, report:
- PR number and URL (as a VS Code URI link)
- Target base branch
- Title used
- Draft status (note that it opened as a draft, and how to mark it ready)

## Title Generation Rules

1. Analyze the diff to determine type (`feat`, `fix`, `refactor`, `docs`, `test`, `ci`, `chore`, `perf`, `build`)
2. Determine scope from affected files/modules (optional)
3. Write description in imperative mood, present tense
4. Keep under 72 characters total
5. Match the pattern observed in the repository's recent PRs

## Body Generation Rules

1. If a PR template exists, fill in its sections:
   - **Description**: 1-2 sentence summary of what and why
   - **Type of Change**: Check the relevant box
   - **Motivation/Context**: Brief explanation, link issues if applicable
   - **Checklist**: Check items that apply
2. If no template, write a minimal body: 1-3 sentences describing the change

## Safety

- NEVER force push
- NEVER push to the default branch directly
- NEVER skip pre-commit hooks (run them if available before committing)
- If on a shared branch (not created by this workflow), ask before pushing
- If the branch already has an open PR, inform the user and ask whether to update it or create a new one
