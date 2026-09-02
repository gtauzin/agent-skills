---
name: check
description: 'Run pre-commit hooks to lint, format, and type-check the codebase, then auto-fix all failures. Use when user says "/check", "check lint", "fix formatting", "run pre-commit", "make CI pass", or wants to ensure code passes CI checks before pushing.'
license: MIT
---

# Fix: Pre-commit Lint, Format, and Type-check

Run `pre-commit run --all-files` and auto-fix everything it reports. This mirrors CI exactly because CI runs the same command.

## Workflow

### 1. Find the project root

```bash
# Find git root from current directory
git rev-parse --show-toplevel
```

Verify `.pre-commit-config.yaml` exists at that root. If not, report and stop.

### 2. Run pre-commit (first pass)

```bash
uvx pre-commit run --all-files --show-diff-on-failure 2>&1
```

If everything passes, report success and stop.

### 3. Handle auto-fixed files

Many hooks auto-fix files on disk (ruff-format, trailing-whitespace, end-of-file-fixer, rumdl-fmt, mixed-line-ending). After the first run, these files are already modified. Stage them:

```bash
git add -u
```

### 4. Fix remaining errors

Parse the pre-commit output for hooks that failed with errors (not auto-fixes). Common ones:

| Hook          | Error type                        | Fix strategy                                           |
|---------------|-----------------------------------|--------------------------------------------------------|
| `ty`          | Type errors, stale ignore comments | Read the file, fix the type annotation or remove the unused `ty: ignore` comment |
| `interrogate` | Missing docstrings                | Add one-line docstrings to uncovered functions/classes  |
| `ruff`        | Unfixable lint violations         | Read the file, apply the fix manually                  |
| `rumdl`       | Markdown lint errors              | Read the file, fix the markdown issue                  |
| `check-yaml`  | Invalid YAML syntax              | Read the file, fix the syntax                          |
| `check-toml`  | Invalid TOML syntax              | Read the file, fix the syntax                          |

For each error:
1. Read the file at the reported line
2. Understand the error
3. Apply the minimal fix
4. Stage the fix

**ty errors specifically**: Pay attention to:
- `invalid-argument-type`: Add a type narrowing check or a cast, or fix the annotation
- `unresolved-attribute`: The type union includes `None`; add a guard or assertion
- `unused-ignore-comment`: Remove the `# ty: ignore[...]` comment as suggested
- `invalid-assignment`: Usually a key type mismatch; the variable needs a `typing.cast()` or explicit type annotation

**ty narrowing caveat**: Unlike mypy, `ty` does NOT narrow `self.attr` through `isinstance(self.attr, SomeType)` because the attribute could mutate between the check and use. When you need to narrow a `self.` attribute with a union type, assign it to a local variable using `typing.cast()`:
```python
# WRONG: ty won't narrow self._data through isinstance
if isinstance(self._data, dict):
    for k, v in self._data.items():  # ty error: object has no .items()

# RIGHT: cast to a local variable
from typing import cast
if isinstance(self._data, dict):
    data = cast(dict[str, SomeType], self._data)
    for k, v in data.items():  # works
```

### 5. Re-run pre-commit (validation)

```bash
uvx pre-commit run --all-files 2>&1
```

If it passes, report success. If not, repeat steps 3-4. Maximum 3 total iterations.

### 6. Stage all changes

```bash
git add -u
```

Report what was fixed and that files are staged (but NOT committed; the user decides when to commit).

## Output Format

```
## Pre-commit fix

Running pre-commit from: <git-root>

### Pass 1
<list which hooks passed/failed>

### Auto-fixes applied
- <file>: <what was fixed>

### Manual fixes applied
- <file:line>: <what was fixed>

### Pass 2 (verification)
All hooks passed ✓

### Staged files
<git status --short of staged changes>
```

## Important

- NEVER skip hooks or use `--no-verify`
- NEVER commit automatically; only stage. The user commits when ready.
- If a hook failure cannot be auto-fixed (e.g., `check-added-large-files`), report it clearly and stop
- Run from the git root where `.pre-commit-config.yaml` lives
- If `pre-commit` is not installed, use `uvx pre-commit` to run it without installing
