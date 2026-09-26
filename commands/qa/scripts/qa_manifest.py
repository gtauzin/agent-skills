#!/usr/bin/env python3
"""Deterministic Phase 0 manifests for the /qa command family.

Every manifest here has ground truth in the repository, so it is computed by parsing
and set operations, not by an agent. The /qa hub and its spokes feed this output to
reviewers and never substitute agent guesses for it. Each subcommand exits non-zero
with a message on stderr rather than print a partial result.

Subcommands:

    profile    package, layout, deterministic gates, convention files, docs, review state
    changed    CHANGED_FILES since the commit of the latest report covering a dimension
    units      review units packed under a line and file budget
    imports    IMPORT_GRAPH between subpackages, cycles, and never-imported modules
    surface    SURFACE_MANIFEST: exports, signatures, in-package bases (imports the package)
    tests      TEST_INVENTORY and systematic-check suite detection
    docs       QUADRANT_FILES, GLOSSARY_TERMS, NOTEBOOK_MAPPING, API_PAGES

Run from the project root. Only `surface` imports the package, so only it needs the
project environment:

    python3 ~/.claude/commands/qa/scripts/qa_manifest.py profile
    uv run python ~/.claude/commands/qa/scripts/qa_manifest.py surface

`--package NAME` and `--source-root PATH` override package detection; the hub passes
them when `.claude/qa-profile.md` names the package.
"""

from __future__ import annotations

import argparse
import ast
import re
import subprocess
import sys
from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:  # Python < 3.11
    try:
        import tomli as tomllib
    except ModuleNotFoundError:
        tomllib = None

NON_PACKAGE_DIRS = {"tests", "test", "docs", "examples", "scripts", "benchmarks", "build", "dist"}
DOCS_SKIP = {"index.md", "changelog.md", "tags.md", "glossary.md"}
QUADRANT_PATTERNS = [
    ("Tutorials", re.compile(r"tutorial|getting.started|quick.?start|learn", re.I)),
    ("How-to Guides", re.compile(r"how.?to|guide|recipe|cookbook", re.I)),
    ("Explanation", re.compile(r"explanation|concept|background|understand|architecture|design", re.I)),
    ("Reference", re.compile(r"reference|api", re.I)),
]
SYSTEMATIC_PATTERNS = {
    "parametrize_with_checks": re.compile(r"\bparametrize_with_checks\b"),
    "check_estimator": re.compile(r"\bcheck_estimator\b"),
    "yield-checks generator": re.compile(r"\b_yield_\w+_checks\b"),
    "inventory sweep": re.compile(r"\ball_(estimators|functions|classes)\s*\("),
}
EXCLUSION_NAME = re.compile(r"(skip|xfail|exclude|ignore|known_fail)", re.I)


class ManifestError(RuntimeError):
    """Raised on any condition that must halt the run rather than guess."""


# --------------------------------------------------------------------------- #
# Project discovery
# --------------------------------------------------------------------------- #


def read_toml(path: Path) -> dict:
    if tomllib is None:
        raise ManifestError(
            f"cannot parse {path.name}: needs Python >= 3.11 or the tomli package "
            f"(this is Python {sys.version.split()[0]}); rerun with the project's interpreter"
        )
    return tomllib.loads(path.read_text())


def read_pyproject(root: Path) -> dict:
    path = root / "pyproject.toml"
    return read_toml(path) if path.exists() else {}


def resolve_package(root: Path, package: str | None, source_root: str | None) -> tuple[str, Path]:
    """Return (import name, source root relative to the project root)."""
    if source_root:
        src = Path(source_root)
        if not (root / src / "__init__.py").exists():
            raise ManifestError(f"--source-root {src} has no __init__.py")
        return package or src.name, src
    if package:
        for cand in (Path("src") / package, Path(package)):
            if (root / cand / "__init__.py").exists():
                return package, cand
        raise ManifestError(f"package {package!r} not found under src/ or the project root")

    dist = read_pyproject(root).get("project", {}).get("name", "")
    wanted = re.sub(r"[-.]+", "_", dist).lower()
    if (root / "src").is_dir():
        cands = [p for p in sorted((root / "src").iterdir()) if (p / "__init__.py").exists()]
    else:
        cands = [
            p
            for p in sorted(root.iterdir())
            if p.is_dir() and p.name not in NON_PACKAGE_DIRS and (p / "__init__.py").exists()
        ]
    if len(cands) == 1:
        return cands[0].name, cands[0].relative_to(root)
    for p in cands:
        if p.name == wanted:
            return p.name, p.relative_to(root)
    names = ", ".join(p.name for p in cands) or "none"
    raise ManifestError(f"cannot pick the package (dist name {dist!r}, candidates: {names}); pass --package")


def py_files(base: Path) -> list[Path]:
    return sorted(p for p in base.rglob("*.py") if "__pycache__" not in p.parts)


def line_count(path: Path) -> int:
    return sum(1 for _ in path.open(encoding="utf-8", errors="replace"))


def subpackage_of(module: Path, src: Path) -> str:
    """First path component under the source root, or '(root)' for top-level modules."""
    rel = module.relative_to(src)
    return rel.parts[0] if len(rel.parts) > 1 else "(root)"


def git(root: Path, *args: str) -> str:
    out = subprocess.run(["git", *args], cwd=root, capture_output=True, text=True)
    if out.returncode != 0:
        raise ManifestError(f"git {' '.join(args)} failed: {out.stderr.strip()}")
    return out.stdout


def docs_config(root: Path) -> tuple[str, Path | None, Path]:
    """Return (engine, config file, docs dir)."""
    if (root / "mkdocs.yml").exists():
        text = (root / "mkdocs.yml").read_text()
        m = re.search(r"^docs_dir:\s*['\"]?([^'\"\s]+)", text, re.M)
        return "mkdocs", root / "mkdocs.yml", root / (m.group(1) if m else "docs")
    if (root / "zensical.toml").exists():
        data = read_toml(root / "zensical.toml")
        return "zensical", root / "zensical.toml", root / data.get("project", {}).get("docs_dir", "docs")
    if (root / "docs" / "conf.py").exists():
        return "sphinx", root / "docs" / "conf.py", root / "docs"
    return "none", None, root / "docs"


def latest_reports(root: Path) -> list[Path]:
    return sorted((root / "reviews").glob("*-qa.md"))


def report_header(path: Path) -> dict:
    text = "\n".join(path.read_text().splitlines()[:12])
    scope = re.search(r"^Scope:\s*(.+?)\s*/\s*(\S+)", text, re.M)
    sha = re.search(r"^Commit:\s*([0-9a-f]{7,40})", text, re.M)
    dims = []
    if scope:
        raw = re.sub(r"\(.*?\)", "", scope.group(1))
        dims = [d.strip() for d in raw.split(",") if d.strip()]
    return {
        "dims": dims,
        "path": scope.group(2) if scope else "all",
        "sha": sha.group(1) if sha else None,
    }


# --------------------------------------------------------------------------- #
# profile
# --------------------------------------------------------------------------- #


def cmd_profile(root: Path, pkg: str, src: Path, args: argparse.Namespace) -> None:
    pyproject = read_pyproject(root)
    project = pyproject.get("project", {})
    tools = pyproject.get("tool", {})
    print(
        f"PROJECT\troot={root}\tdist={project.get('name', '?')}\trequires-python={project.get('requires-python', '?')}"
    )
    layout = "src" if src.parts[0] == "src" else "flat"
    print(f"PACKAGE\timport={pkg}\tsource_root={src}\tlayout={layout}")

    subs: dict[str, list[int]] = {}
    for f in py_files(root / src):
        subs.setdefault(subpackage_of(f, root / src), []).append(line_count(f))
    total = sum(sum(v) for v in subs.values())
    print(f"SUBPACKAGES\t{len(subs)}\tmodules={sum(len(v) for v in subs.values())}\tlines={total}")
    for name, counts in sorted(subs.items()):
        print(f"  {name}\tmodules={len(counts)}\tlines={sum(counts)}")

    tests = root / "tests"
    n_tests = len(list(tests.rglob("test_*.py"))) if tests.is_dir() else 0
    print(f"TESTS\tdir={'tests' if tests.is_dir() else 'none'}\ttest_files={n_tests}")

    print("GATES")
    print(f"  pyproject [tool.*]: {', '.join(sorted(tools)) or 'none'}")
    ruff = tools.get("ruff", {})
    lint = ruff.get("lint", ruff)
    if ruff:
        print(f"  ruff select: {lint.get('select', lint.get('extend-select', 'default'))}")
        print(f"  ruff ignore: {lint.get('ignore', [])}")
        conv = lint.get("pydocstyle", {}).get("convention")
        print(f"  docstring convention: {conv or 'unset'}")
    if "interrogate" in tools:
        cfg = tools["interrogate"]
        print(f"  interrogate: fail-under={cfg.get('fail-under', '?')} ignore-module={cfg.get('ignore-module', False)}")
    addopts = tools.get("pytest", {}).get("ini_options", {}).get("addopts", "")
    addopts = " ".join(addopts) if isinstance(addopts, list) else addopts
    print(f"  pytest doctest-modules: {'--doctest-modules' in addopts}")
    hooks = []
    for name in (".pre-commit-config.yaml", ".pre-commit-config.yml"):
        if (root / name).exists():
            hooks += re.findall(r"^\s*-\s*id:\s*([\w.-]+)", (root / name).read_text(), re.M)
    if (root / "prek.toml").exists():
        hooks += re.findall(r'\bid\s*=\s*"([\w.-]+)"', (root / "prek.toml").read_text())
    print(f"  pre-commit hooks: {', '.join(hooks) or 'none'}")
    for jf in ("justfile", "Justfile", ".justfile"):
        if (root / jf).exists():
            recipes = [
                m.group(1)
                for m in re.finditer(r"^@?([A-Za-z_][\w-]*)(?:\s+[^:\n=]*)?:(?!=)", (root / jf).read_text(), re.M)
                if m.group(1) not in {"set", "alias", "export", "import", "mod"}
            ]
            print(f"  just recipes: {', '.join(recipes)}")
            break
    wf = sorted((root / ".github" / "workflows").glob("*.y*ml"))
    names = []
    for w in wf:
        m = re.search(r"^name:\s*['\"]?(.+?)['\"]?\s*$", w.read_text(), re.M)
        names.append(f"{w.name} ({m.group(1) if m else '?'})")
    print(f"  ci workflows: {'; '.join(names) or 'none'}")

    engine, cfg, docs_dir = docs_config(root)
    cfg_rel = cfg.relative_to(root) if cfg else "none"
    docs_rel = docs_dir.relative_to(root) if docs_dir.exists() else "none"
    print(f"DOCS\tengine={engine}\tconfig={cfg_rel}\tdocs_dir={docs_rel}")

    conv_files = [
        "CLAUDE.md",
        "AGENTS.md",
        "CONTRIBUTING.md",
        ".github/copilot-instructions.md",
        ".claude/qa-profile.md",
    ]
    print("CONVENTIONS\t" + "\t".join(f"{c}={'yes' if (root / c).exists() else 'no'}" for c in conv_files))
    for base in (".claude/skills", ".github/skills"):
        d = root / base
        if d.is_dir():
            print(f"SKILLS\t{base}: {', '.join(sorted(p.name for p in d.iterdir() if (p / 'SKILL.md').exists()))}")
    cmds = root / ".claude" / "commands"
    if cmds.is_dir():
        print(f"COMMANDS\t.claude/commands: {', '.join(sorted(str(p.relative_to(cmds)) for p in cmds.rglob('*.md')))}")

    accepted = root / "reviews" / "accepted.md"
    n_acc = len(re.findall(r"^\s*-\s*`[^`]+`", accepted.read_text(), re.M)) if accepted.exists() else 0
    print(f"REVIEWS\taccepted={'reviews/accepted.md' if accepted.exists() else 'none'} ({n_acc} ids)")
    for rep in latest_reports(root)[-3:]:
        h = report_header(rep)
        print(f"  {rep.relative_to(root)}\tdims={','.join(h['dims']) or '?'}\tpath={h['path']}\tcommit={h['sha']}")


# --------------------------------------------------------------------------- #
# changed
# --------------------------------------------------------------------------- #


def cmd_changed(root: Path, pkg: str, src: Path, args: argparse.Namespace) -> None:
    """Base the diff on the latest report that covered this dimension over this path."""
    want_path = args.path or "all"
    for rep in reversed(latest_reports(root)):
        h = report_header(rep)
        covers_dim = not args.dimension or "all" in h["dims"] or args.dimension in h["dims"]
        covers_path = h["path"] == "all" or want_path.startswith(h["path"])
        if not (covers_dim and covers_path and h["sha"]):
            continue
        ok = subprocess.run(
            ["git", "rev-parse", "--verify", "--quiet", f"{h['sha']}^{{commit}}"], cwd=root, capture_output=True
        )
        if ok.returncode != 0:
            continue
        print(f"INCREMENTAL\tbase={h['sha']}\treport={rep.relative_to(root)}")
        print(git(root, "diff", f"{h['sha']}..HEAD", "--name-only").rstrip())
        return
    print(
        f"FULL\t(no prior report covering {args.dimension or 'these dimensions'} over {want_path} with a resolvable SHA)"
    )


# --------------------------------------------------------------------------- #
# units
# --------------------------------------------------------------------------- #


def pack(files: list[Path], root: Path, max_lines: int, max_files: int) -> list[list[tuple[Path, int]]]:
    """Greedy packing in path order, so modules with a shared prefix stay together."""
    batches, cur, cur_lines = [], [], 0
    for f in files:
        n = line_count(f)
        if cur and (cur_lines + n > max_lines or len(cur) >= max_files):
            batches.append(cur)
            cur, cur_lines = [], 0
        cur.append((f, n))
        cur_lines += n
    if cur:
        batches.append(cur)
    return batches


def read_changed(arg: str | None) -> set[str] | None:
    if arg is None:
        return None
    text = sys.stdin.read() if arg == "-" else Path(arg).read_text()
    return {line.strip() for line in text.splitlines() if line.strip() and not line.startswith(("INCREMENTAL", "FULL"))}


def cmd_units(root: Path, pkg: str, src: Path, args: argparse.Namespace) -> None:
    changed = read_changed(args.changed)
    scope = root / (args.path or src)
    if not scope.exists():
        raise ManifestError(f"path filter {args.path} does not exist")
    if args.kind == "source" and not scope.resolve().is_relative_to((root / src).resolve()):
        raise ManifestError(f"path filter {args.path} is not under the source root {src}")
    groups: dict[str, list[Path]] = {}
    if args.kind == "source":
        for f in py_files(scope):
            rel = str(f.relative_to(root))
            if changed is not None and rel not in changed:
                continue
            groups.setdefault(subpackage_of(f, root / src), []).append(f)
    else:
        tests = root / "tests"
        if not tests.is_dir():
            raise ManifestError("no tests/ directory")
        want_sub = None
        if args.path:
            for base in (root / src, tests):
                if scope.resolve().is_relative_to(base.resolve()):
                    want_sub = subpackage_of(scope.resolve() / "x.py", base.resolve())
                    break
            else:
                raise ManifestError(f"path filter {args.path} is under neither {src} nor tests/")
        for f in sorted(tests.rglob("test_*.py")):
            rel = f.relative_to(tests)
            sub = rel.parts[0] if len(rel.parts) > 1 else "(root)"
            if want_sub and sub != want_sub:
                continue
            groups.setdefault(sub, []).append(f)
        if changed is not None:
            keep = {}
            for sub, files in groups.items():
                paired = [str(p.relative_to(root)) for p in py_files(root / src / sub)] if sub != "(root)" else []
                if changed & ({str(p.relative_to(root)) for p in files} | set(paired)):
                    keep[sub] = files
            groups = keep
    n = 0
    for sub, files in sorted(groups.items()):
        pair = ""
        if args.kind == "tests":
            pair_dir = src / sub if sub != "(root)" else src
            pair = f"\tpaired={pair_dir if (root / pair_dir).exists() else 'none'}"
        for i, batch in enumerate(pack(files, root, args.max_lines, args.max_files), 1):
            n += 1
            lines = sum(c for _, c in batch)
            listing = ", ".join(str(f.relative_to(root)) for f, _ in batch)
            print(f"UNIT\t{sub}#{i}\tlines={lines}{pair}\tfiles={listing}")
    print(f"TOTAL\tunits={n}")


# --------------------------------------------------------------------------- #
# imports
# --------------------------------------------------------------------------- #


def module_name(path: Path, src: Path, pkg: str) -> str:
    parts = list(path.relative_to(src).with_suffix("").parts)
    if parts[-1] == "__init__":
        parts = parts[:-1]
    return ".".join([pkg, *parts])


def iter_imports(tree: ast.AST, this_mod: str, is_pkg: bool):
    """Yield (absolute module name, type_only) for every import in the module."""

    def walk(node: ast.AST, type_only: bool):
        for child in ast.iter_child_nodes(node):
            if isinstance(child, ast.If) and "TYPE_CHECKING" in ast.unparse(child.test):
                for sub in child.body:
                    yield from walk_node(sub, True)
                for sub in child.orelse:
                    yield from walk_node(sub, type_only)
                continue
            yield from walk_node(child, type_only)

    def walk_node(node: ast.AST, type_only: bool):
        if isinstance(node, ast.Import):
            for a in node.names:
                yield a.name, type_only
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                base = this_mod.split(".")
                base = base if is_pkg else base[:-1]
                base = base[: len(base) - (node.level - 1)]
                mod = ".".join(base + ([node.module] if node.module else []))
            else:
                mod = node.module or ""
            yield mod, type_only
            for a in node.names:
                yield f"{mod}.{a.name}", type_only
        yield from walk(node, type_only)

    yield from walk(tree, False)


def cmd_imports(root: Path, pkg: str, src: Path, args: argparse.Namespace) -> None:
    base = root / src
    modules = {module_name(f, base, pkg): f for f in py_files(base)}
    edges: dict[tuple[str, str], bool] = {}
    imported: set[str] = set()
    for mod, f in modules.items():
        tree = ast.parse(f.read_text(), filename=str(f))
        rel = f.relative_to(base)
        a = rel.parts[0] if len(rel.parts) > 1 else "(root)" if f.name == "__init__.py" else f"{f.stem}.py"
        for target, type_only in iter_imports(tree, mod, f.name == "__init__.py"):
            if not target.startswith(pkg + "."):
                continue
            if target in modules:
                imported.add(target)
            first = target.split(".")[1]
            b = first if (base / first).is_dir() else f"{first}.py" if (base / f"{first}.py").exists() else "(root)"
            if a != b:
                edges[(a, b)] = edges.get((a, b), True) and type_only
    print("EDGES (importer -> imported subpackage or top-level module; (root) = the package __init__;")
    print("       [type-only] = only under TYPE_CHECKING)")
    for (a, b), type_only in sorted(edges.items()):
        print(f"  {a} -> {b}{'  [type-only]' if type_only else ''}")

    graph: dict[str, set[str]] = {}
    for (a, b), type_only in edges.items():
        if not type_only:
            graph.setdefault(a, set()).add(b)
    print("CYCLES (runtime edges only)")
    cycles = strongly_connected(graph)
    for comp in cycles:
        print(f"  {' <-> '.join(sorted(comp))}")
    if not cycles:
        print("  none")

    print(
        "NEVER_IMPORTED (not imported by any in-package module; candidates for dead-module, check exports and entry points)"
    )
    for mod, f in sorted(modules.items()):
        if f.name in {"__init__.py", "__main__.py"} or mod in imported:
            continue
        print(f"  {mod}\t{f.relative_to(root)}")


def strongly_connected(graph: dict[str, set[str]]) -> list[set[str]]:
    index, low, stack, on, out, counter = {}, {}, [], set(), [], [0]

    def visit(v: str) -> None:
        index[v] = low[v] = counter[0]
        counter[0] += 1
        stack.append(v)
        on.add(v)
        for w in graph.get(v, ()):
            if w not in index:
                visit(w)
                low[v] = min(low[v], low[w])
            elif w in on:
                low[v] = min(low[v], index[w])
        if low[v] == index[v]:
            comp = set()
            while True:
                w = stack.pop()
                on.discard(w)
                comp.add(w)
                if w == v:
                    break
            if len(comp) > 1:
                out.append(comp)

    for v in sorted(graph):
        if v not in index:
            visit(v)
    return out


# --------------------------------------------------------------------------- #
# surface
# --------------------------------------------------------------------------- #


def cmd_surface(root: Path, pkg: str, src: Path, args: argparse.Namespace) -> None:
    import importlib
    import inspect
    import pkgutil
    import warnings

    sys.path.insert(0, str((root / src).parent))
    # Some packages (kedro) escalate their own warnings to errors unless -W was given.
    sys.warnoptions.append("ignore")
    warnings.simplefilter("ignore")
    try:
        top = importlib.import_module(pkg)
    except Exception as exc:  # the whole manifest depends on this import
        raise ManifestError(f"cannot import {pkg}: {type(exc).__name__}: {exc}") from exc

    modules = [top]
    errors = []
    for info in pkgutil.walk_packages(top.__path__, pkg + ".", onerror=errors.append):
        try:
            modules.append(importlib.import_module(info.name))
        except Exception as exc:
            errors.append(f"{info.name}: {type(exc).__name__}: {exc}")

    def describe(obj: object) -> tuple[str, str, str]:
        """(kind, parameters, in-package bases) of an exported object."""
        if inspect.ismodule(obj):
            return "module", "", ""
        kind = "class" if inspect.isclass(obj) else "function" if callable(obj) else "other"
        try:
            params = ",".join(p for p in inspect.signature(obj).parameters if p != "self") if kind != "other" else ""
        except (TypeError, ValueError):
            params = ""
        bases = ""
        if kind == "class":
            bases = ",".join(b.__name__ for b in obj.__mro__[1:] if (b.__module__ or "").split(".")[0] == pkg)
        return kind, params, bases

    missing = object()
    rows: dict[str, dict] = {}
    exported_ids: set[int] = set()
    for mod in (m for m in modules if hasattr(m, "__path__")):
        exports = list(getattr(mod, "__all__", []))
        print(f"EXPORTS\t{mod.__name__}\t{len(exports)}\t{', '.join(exports)}")
        for name in exports:
            obj = getattr(mod, name, missing)
            if obj is missing:
                kind, params, bases, qual = "MISSING", "", "", f"{mod.__name__}.{name}"
            else:
                exported_ids.add(id(obj))
                kind, params, bases = describe(obj)
                qual = (
                    f"{obj.__module__}.{obj.__qualname__}"
                    if kind in {"class", "function"} and hasattr(obj, "__qualname__")
                    else f"{mod.__name__}.{name}"
                )
            row = rows.setdefault(qual, {"kind": kind, "params": params, "bases": bases, "via": []})
            row["via"].append(mod.__name__)
    print("SYMBOLS (qualified name, kind, parameters, exporting packages, in-package bases)")
    for qual, r in sorted(rows.items()):
        bases = f"\tbases={r['bases']}" if r["bases"] else ""
        print(f"  {qual}\t{r['kind']}\t{r['params']}\texported_from={','.join(r['via'])}{bases}")

    print(
        "UNEXPORTED_PUBLIC (public classes/functions defined in the package but in no __all__; a signal, often deliberate)"
    )
    n = 0
    for mod in modules:
        for name, obj in sorted(vars(mod).items()):
            if name.startswith("_") or id(obj) in exported_ids:
                continue
            if not (inspect.isclass(obj) or inspect.isfunction(obj)) or obj.__module__ != mod.__name__:
                continue
            n += 1
            kind, params, _ = describe(obj)
            print(f"  {mod.__name__}.{name}\t{kind}\t{params}")
    if not n:
        print("  none")
    print("IMPORT_ERRORS (modules that failed to import, e.g. optional dependencies)")
    for e in errors or ["none"]:
        print(f"  {e}")

    print("DEPRECATIONS (static scan of the source root)")
    hits = 0
    pat = re.compile(r"DeprecationWarning|FutureWarning|PendingDeprecationWarning|@deprecated|deprecated\(")
    for f in py_files(root / src):
        for i, line in enumerate(f.read_text().splitlines(), 1):
            if pat.search(line):
                hits += 1
                print(f"  {f.relative_to(root)}:{i}\t{line.strip()[:120]}")
    if not hits:
        print("  none")


# --------------------------------------------------------------------------- #
# tests
# --------------------------------------------------------------------------- #


def cmd_tests(root: Path, pkg: str, src: Path, args: argparse.Namespace) -> None:
    tests = root / "tests"
    if not tests.is_dir():
        raise ManifestError("no tests/ directory")
    test_files = sorted(tests.rglob("test_*.py"))
    src_mods = [f for f in py_files(root / src) if f.name != "__init__.py"]
    print(f"INVENTORY\tsrc_modules={len(src_mods)}\ttest_files={len(test_files)}")

    markers: dict[str, int] = {}
    for p in test_files:
        for m in re.findall(r"pytest\.mark\.(\w+)", p.read_text()):
            markers[m] = markers.get(m, 0) + 1
    print(f"MARKERS\t{dict(sorted(markers.items(), key=lambda kv: -kv[1]))}")

    tested = {p.stem.removeprefix("test_") for p in test_files}
    unmatched = sorted(
        str(f.relative_to(root)) for f in src_mods if not f.name.startswith("_") and f.stem not in tested
    )
    print("UNMATCHED (public modules with no name-matched test file; a signal, never a finding by itself)")
    for u in unmatched or ["none"]:
        print(f"  {u}")

    scan = test_files + list(tests.rglob("conftest.py")) + py_files(root / src)
    suite: dict[Path, list[str]] = {}
    for f in scan:
        text = f.read_text()
        found = [name for name, pat in SYSTEMATIC_PATTERNS.items() if pat.search(text)]
        if found:
            suite[f] = found
    gens = sorted({g for f in py_files(root / src) for g in re.findall(r"def (_yield_\w+_checks)", f.read_text())})
    print("SYSTEMATIC_SUITE (files using a check-suite or inventory-sweep pattern)")
    for f, found in sorted(suite.items()):
        print(f"  {f.relative_to(root)}\t{', '.join(found)}")
    if not suite:
        print("  none (no systematic check suite detected; coverage-gap is not applicable)")
    print(f"GENERATORS\t{', '.join(gens) or 'none'}")

    print("EXCLUSION_LISTS (module-level skip/xfail/exclude containers in suite test files)")
    entries: list[str] = []
    declaring: set[Path] = set()
    for f in (f for f in suite if f.is_relative_to(tests)):
        for node in ast.parse(f.read_text()).body:
            if isinstance(node, ast.Assign):
                targets = node.targets
            elif isinstance(node, ast.AnnAssign) and node.value is not None:
                targets = [node.target]
            else:
                continue
            names = [getattr(t, "id", "") for t in targets]
            if not any(EXCLUSION_NAME.search(n) for n in names):
                continue
            declaring.add(f)
            try:
                value = ast.literal_eval(node.value)
            except ValueError:
                value = ast.unparse(node.value)[:300]
            print(f"  {f.relative_to(root)}:{node.lineno}\t{','.join(names)}\t{value}")
            if isinstance(value, dict):
                entries += [k for k in value if isinstance(k, str)]
            elif isinstance(value, (set, list, tuple, frozenset)):
                entries += [v for v in value if isinstance(v, str)]
    if not entries:
        print("  none")
        return
    print("EXCLUDED_ENTRY_COVERAGE (COVERED = another test file names it and runs a check suite; GAP otherwise)")
    texts = {f: f.read_text() for f in test_files if f not in declaring}
    for name in sorted(set(entries)):
        hits = [f for f, text in texts.items() if name in text]
        suite_hits = [f for f in hits if set(suite.get(f, ())) - {"inventory sweep"}]
        where = ", ".join(str(f.relative_to(root)) for f in (suite_hits or hits)[:2]) or "-"
        print(f"  {'COVERED' if suite_hits else 'GAP'}\t{name}\t{where}")


# --------------------------------------------------------------------------- #
# docs
# --------------------------------------------------------------------------- #


def parse_mkdocs_nav(text: str) -> list[tuple[int, str | None, str | None]]:
    """(indent, title, path) for every nav entry, in order. Regex-based: the nav may carry !!python tags."""
    out, inside = [], False
    for line in text.splitlines():
        if re.match(r"^nav:\s*$", line):
            inside = True
            continue
        if inside and re.match(r"^\S", line):
            break
        if not inside:
            continue
        m = re.match(r"^(\s*)-\s+(?:(.+?):\s*)?(\S+\.md)?\s*$", line)
        if not m:
            m2 = re.match(r"^(\s*)-\s+(.+?):\s*$", line)
            if m2:
                out.append((len(m2.group(1)), m2.group(2).strip("'\""), None))
            continue
        out.append((len(m.group(1)), (m.group(2) or "").strip("'\"") or None, m.group(3)))
    return out


def classify(title: str | None, path: str | None) -> str | None:
    for quad, pat in QUADRANT_PATTERNS:
        if (title and pat.search(title)) or (path and pat.search(path.split("/")[-2] if "/" in path else "")):
            return quad
    return None


def cmd_docs(root: Path, pkg: str, src: Path, args: argparse.Namespace) -> None:
    engine, cfg, docs_dir = docs_config(root)
    if not docs_dir.is_dir():
        raise ManifestError(f"no docs directory ({docs_dir.relative_to(root)})")
    print(f"DOCS\tengine={engine}\tdocs_dir={docs_dir.relative_to(root)}")

    quads: dict[str, list[str]] = {}
    source = "directory names"
    if engine == "mkdocs":
        nav = parse_mkdocs_nav(cfg.read_text())
        if nav:
            source = "mkdocs.yml nav"
            top = min(i for i, _, _ in nav)
            current = None
            for indent, title, path in nav:
                if indent == top:
                    current = classify(title, None) or (f"Other: {title}" if title else "Other")
                if path and current:
                    quads.setdefault(current, []).append(path)
    if not quads:
        for f in sorted(docs_dir.rglob("*.md")):
            rel = str(f.relative_to(docs_dir))
            dirs = f.relative_to(docs_dir).parts[:-1]
            quad = next((q for q, pat in QUADRANT_PATTERNS if any(pat.search(d) for d in dirs)), None)
            quads.setdefault(quad or "Other", []).append(rel)
    print(f"QUADRANT_FILES (from {source}; index, changelog, tags, glossary excluded)")
    for quad, files in quads.items():
        kept = [f for f in files if Path(f).name not in DOCS_SKIP and (docs_dir / f).exists()]
        missing = [f for f in files if not (docs_dir / f).exists()]
        if not kept and not missing:
            continue
        print(f"  {quad}\t{len(kept)}")
        for f in kept:
            print(f"    {f}")
        for f in missing:
            print(f"    MISSING {f}")

    print("GLOSSARY_TERMS (*[term]: definition lines under the docs dir)")
    n = 0
    for f in sorted(docs_dir.rglob("*.md")):
        for m in re.finditer(r"^\*\[([^\]]+)\]:\s*(.+)$", f.read_text(), re.M):
            n += 1
            print(f"  {f.relative_to(root)}\t{m.group(1)}\t{m.group(2)[:100]}")
    if not n:
        print("  none (no abbreviation glossary; the glossary category is not applicable)")

    print("NOTEBOOK_MAPPING (companion page -> notebook)")
    n = 0
    examples = root / "examples"
    for f in py_files(examples) if examples.is_dir() else []:
        m = re.search(r'"companion"\s*:\s*"([^"]+)"', f.read_text())
        if m:
            n += 1
            print(f"  {m.group(1)}\t{f.relative_to(root)}")
    if not n:
        print("  none")
    marker = "<!-- COMPANION_NOTEBOOKS -->"
    markers = [str(f.relative_to(root)) for f in sorted(docs_dir.rglob("*.md")) if marker in f.read_text()]
    print(f"COMPANION_MARKER_PAGES\t{len(markers)}\t{', '.join(markers)}")

    print(f"API_PAGES (docs pages documenting a {pkg} symbol: name-as-filename or ::: directive)")
    n = 0
    for f in sorted(docs_dir.rglob("*.md")):
        rel = f.relative_to(docs_dir)
        names = set(re.findall(rf"^:::\s*({re.escape(pkg)}(?:\.\w+)*)", f.read_text(), re.M))
        if f.stem.startswith(pkg + "."):
            names.add(f.stem)
        for name in sorted(names):
            n += 1
            print(f"  {name}\t/{rel.with_suffix('')}/")
    if not n:
        print("  none (API pages are generated at build time or absent; derive links from the docs config)")


# --------------------------------------------------------------------------- #
# main
# --------------------------------------------------------------------------- #


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--package", help="import name override")
    parser.add_argument("--source-root", help="package directory override, relative to the project root")
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("profile")
    p = sub.add_parser("changed")
    p.add_argument("--dimension", help="only reports whose Scope line covers this dimension")
    p.add_argument("--path", help="only reports whose scope path contains this path")
    p = sub.add_parser("units")
    p.add_argument("kind", choices=["source", "tests"])
    p.add_argument("--path", help="path filter under the project root (a subpackage directory)")
    p.add_argument("--changed", help="file (or - for stdin) holding CHANGED_FILES; restricts units to them")
    p.add_argument("--max-lines", type=int, default=1800)
    p.add_argument("--max-files", type=int, default=5)
    for name in ("imports", "surface", "tests", "docs"):
        sub.add_parser(name)
    args = parser.parse_args()

    root = Path.cwd()
    try:
        pkg, src = resolve_package(root, args.package, args.source_root)
        {
            "profile": cmd_profile,
            "changed": cmd_changed,
            "units": cmd_units,
            "imports": cmd_imports,
            "surface": cmd_surface,
            "tests": cmd_tests,
            "docs": cmd_docs,
        }[args.cmd](root, pkg, src, args)
    except ManifestError as exc:
        print(f"qa_manifest {args.cmd}: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
