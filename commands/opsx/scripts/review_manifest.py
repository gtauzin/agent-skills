#!/usr/bin/env python3
"""Deterministic Phase-0 manifest for /opsx:review.

This is the deterministic heart of the change-review skill. Every check here has
ground truth in the repository, so it is decided by parsing and set operations, not
by an agent. The skill consumes this manifest and judges only the semantic edges it
surfaces (candidate task<->requirement links) plus the inherently-judgment dimensions.

Subcommands (one per task 1.1-1.5), each fails loud (non-zero, stderr message) rather
than emitting a partial result:

    traceability   proposal <-> tasks <-> requirements <-> Impact <-> delta dirs
    modified       every ## MODIFIED requirement vs its canonical text
    grounding      referenced paths resolved against the repo
    cross-change   other active changes / unsynced predecessors on shared capabilities
    lifecycle      propose-time vs archive-time, from task completion
    all            run every check + validate, emit the combined manifest JSON

Findings use the qa chassis schema (id, dimension, severity, category, file, claim,
evidence, suggestion) so the skill merges deterministic and agent findings directly.

Usage:
    python3 review_manifest.py all <change-name>
    python3 review_manifest.py traceability <change-name>
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path


class ManifestError(RuntimeError):
    """Raised on any condition that must halt the run rather than guess."""


# --------------------------------------------------------------------------- #
# Repo / change discovery
# --------------------------------------------------------------------------- #
def find_repo_root(start: Path) -> Path:
    """Walk up until we find an openspec/changes directory."""
    for base in (start, *start.parents):
        if (base / "openspec" / "changes").is_dir():
            return base
    raise ManifestError(
        f"no openspec/changes found at or above {start}; run from the repo"
    )


def change_dir(root: Path, name: str) -> Path:
    active = root / "openspec" / "changes" / name
    if active.is_dir():
        return active
    archived = root / "openspec" / "changes" / "archive" / name
    if archived.is_dir():
        return archived
    raise ManifestError(f"change '{name}' not found under openspec/changes/[archive/]{name}")


def read(path: Path) -> str:
    if not path.is_file():
        raise ManifestError(f"expected file is missing: {path}")
    return path.read_text(encoding="utf-8")


# --------------------------------------------------------------------------- #
# Markdown parsers (self-contained; openspec show --json drops requirement names)
# --------------------------------------------------------------------------- #
def split_h2(md: str) -> dict[str, str]:
    """Map each '## Heading' to its body text."""
    sections: dict[str, str] = {}
    current = None
    buf: list[str] = []
    for line in md.splitlines():
        m = re.match(r"^##\s+(.+?)\s*$", line)
        if m and not line.startswith("###"):
            if current is not None:
                sections[current] = "\n".join(buf)
            current = m.group(1).strip()
            buf = []
        else:
            buf.append(line)
    if current is not None:
        sections[current] = "\n".join(buf)
    return sections


def top_level_bullets(section: str) -> list[str]:
    """Top-level '- ' bullets (column 0), joined with their continuation lines."""
    bullets: list[str] = []
    cur: list[str] | None = None
    for line in section.splitlines():
        if re.match(r"^-\s+\S", line):
            if cur is not None:
                bullets.append(" ".join(cur))
            cur = [line[1:].strip()]
        elif cur is not None and (line.startswith("  ") or line.startswith("\t")):
            cur.append(line.strip())
        elif cur is not None and not line.strip():
            continue
        else:
            if cur is not None:
                bullets.append(" ".join(cur))
                cur = None
    if cur is not None:
        bullets.append(" ".join(cur))
    return bullets


def parse_capabilities(section: str) -> dict[str, list[str]]:
    """Capability names under ### New/Modified Capabilities (backticked slugs)."""
    out = {"new": [], "modified": []}
    bucket = None
    for line in section.splitlines():
        h = re.match(r"^###\s+(New|Modified)\s+Capabilities", line, re.I)
        if h:
            bucket = "new" if h.group(1).lower() == "new" else "modified"
            continue
        if bucket:
            m = re.match(r"^-\s+`([a-z0-9][a-z0-9-]*)`", line)
            if m:
                out[bucket].append(m.group(1))
    return out


# path-like tokens: contain a slash and a filename, e.g. src/foo/bar.py, .claude/x/Y.md
PATH_RE = re.compile(r"[A-Za-z0-9_.][A-Za-z0-9_./-]*/[A-Za-z0-9_./-]+\.[A-Za-z0-9]+")


def extract_paths(text: str) -> set[str]:
    found = set()
    for m in PATH_RE.finditer(text):
        # strip wrapping backticks/parens and trailing punctuation, but NOT a leading dot
        # (leading dots are significant: .claude/, .github/)
        p = m.group(0).strip("`").lstrip("(").rstrip("`.,;:)")
        if "://" in p:  # ignore urls
            continue
        found.add(p)
    return found


_DEP_LINE = re.compile(
    r"\b(reuse|reuses|consum\w*|without modif\w*|governed by|out of scope|unchanged|"
    r"no source|not modif\w*)\b",
    re.I,
)


def deliverable_impact_paths(section: str) -> set[str]:
    """Impact paths on lines that describe deliverables, excluding reused dependencies.

    Impact lists both files the change delivers (need an implementing task) and files it
    merely reuses without touching (must not be flagged for lacking a task).
    """
    out: set[str] = set()
    for line in section.splitlines():
        if _DEP_LINE.search(line):
            continue
        out |= extract_paths(line)
    return out


def parse_tasks(md: str) -> list[dict]:
    tasks = []
    for line in md.splitlines():
        m = re.match(r"^\s*-\s+\[([ xX])\]\s+(\d+(?:\.\d+)*)\s+(.*)$", line)
        if m:
            tasks.append(
                {
                    "id": m.group(2),
                    "checked": m.group(1).lower() == "x",
                    "text": m.group(3).strip(),
                }
            )
    return tasks


def parse_requirement_blocks(md: str) -> list[dict]:
    """Parse '### Requirement: name' blocks, tracking the '## X Requirements' op above.

    Works for both delta files (## ADDED/MODIFIED/... Requirements) and canonical
    specs (no op header -> op is None).
    """
    blocks: list[dict] = []
    op = None
    name = None
    buf: list[str] = []
    scen: list[str] = []

    def flush():
        if name is not None:
            blocks.append(
                {"operation": op, "name": name, "body": "\n".join(buf).strip(), "scenarios": scen}
            )

    for line in md.splitlines():
        opm = re.match(r"^##\s+(ADDED|MODIFIED|REMOVED|RENAMED)\s+Requirements", line, re.I)
        if opm:
            flush()
            name, buf, scen = None, [], []
            op = opm.group(1).upper()
            continue
        rm = re.match(r"^###\s+Requirement:\s+(.+?)\s*$", line)
        if rm:
            flush()
            name, buf, scen = rm.group(1).strip(), [], []
            continue
        sm = re.match(r"^####\s+Scenario:\s+(.+?)\s*$", line)
        if sm:
            scen.append(sm.group(1).strip())
        if name is not None:
            buf.append(line)
    flush()
    return blocks


def normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip().lower()


def path_grounded(root: Path, p: str) -> bool:
    """A path is grounded if it exists at the repo root, or if stripping leading
    ./ and ../ segments (relative references from a nested file) lands on a real file."""
    if (root / p).exists():
        return True
    segs = list(Path(p).parts)
    while segs and segs[0] in (".", ".."):
        segs.pop(0)
    return bool(segs) and (root / Path(*segs)).exists()


def referenced_in_text(p: str, blob: str) -> bool:
    """Whether an Impact path is plausibly named by a task. Tasks often reference files
    by prose ('the mechanism page') rather than path, so match the full path, the
    basename, or a distinctive stem of the basename/parent dir (>=5 chars)."""
    if p.lower() in blob or Path(p).name.lower() in blob:
        return True
    stems = re.findall(r"[a-z0-9]{5,}", (Path(p).stem + " " + Path(p).parent.name).lower())
    return any(s in blob for s in stems)


# --------------------------------------------------------------------------- #
# openspec CLI wrappers
# --------------------------------------------------------------------------- #
def openspec_json(root: Path, args: list[str]) -> dict:
    proc = subprocess.run(
        ["npx", "openspec", *args, "--json"],
        cwd=root,
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0 and not proc.stdout.strip():
        raise ManifestError(f"openspec {' '.join(args)} failed: {proc.stderr.strip()}")
    try:
        return json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        raise ManifestError(f"openspec {' '.join(args)} returned non-JSON: {exc}") from exc


def validate(root: Path, name: str) -> dict:
    proc = subprocess.run(
        ["npx", "openspec", "validate", name, "--strict", "--json"],
        cwd=root,
        capture_output=True,
        text=True,
    )
    try:
        data = json.loads(proc.stdout)
        item = (data.get("items") or [{}])[0]
        return {"passed": bool(item.get("valid")), "issues": item.get("issues", [])}
    except json.JSONDecodeError:
        return {"passed": proc.returncode == 0, "issues": [], "raw": proc.stderr.strip()}


# --------------------------------------------------------------------------- #
# Finding helper (qa chassis schema)
# --------------------------------------------------------------------------- #
def finding(cat, sev, file, claim, evidence, suggestion, slug):
    return {
        "id": f"proposal:{file}:{slug}",
        "dimension": "proposal",
        "severity": sev,
        "category": cat,
        "file": file,
        "claim": claim,
        "evidence": evidence,
        "suggestion": suggestion,
        "source": "deterministic",
    }


# --------------------------------------------------------------------------- #
# Checks
# --------------------------------------------------------------------------- #
def check_traceability(root: Path, name: str) -> dict:
    cdir = change_dir(root, name)
    proposal = read(cdir / "proposal.md")
    tasks_md = read(cdir / "tasks.md") if (cdir / "tasks.md").is_file() else ""
    secs = split_h2(proposal)

    caps = parse_capabilities(secs.get("Capabilities", ""))
    proposal_caps = set(caps["new"]) | set(caps["modified"])
    delta_dirs = {p.name for p in (cdir / "specs").glob("*") if p.is_dir()} if (cdir / "specs").is_dir() else set()

    what_changes = top_level_bullets(secs.get("What Changes", ""))
    impact_paths = extract_paths(secs.get("Impact", ""))
    deliverables = deliverable_impact_paths(secs.get("Impact", ""))
    tasks = parse_tasks(tasks_md)
    task_blob = normalize(" ".join(t["text"] for t in tasks))

    # delta requirements across all capability delta files
    reqs: list[dict] = []
    for cap in delta_dirs:
        f = cdir / "specs" / cap / "spec.md"
        if f.is_file():
            for b in parse_requirement_blocks(read(f)):
                reqs.append({"capability": cap, **b})

    findings: list[dict] = []

    # capability <-> delta dir (deterministic, firm)
    for cap in sorted(proposal_caps - delta_dirs):
        findings.append(finding(
            "traceability", "high", f"openspec/changes/{name}/proposal.md",
            f"Capability '{cap}' is named in the proposal but has no specs/{cap}/spec.md delta.",
            f"Capabilities section lists '{cap}'; specs/ dirs: {sorted(delta_dirs) or 'none'}",
            f"Add specs/{cap}/spec.md or remove '{cap}' from Capabilities.",
            f"capability-{cap}-no-delta"))
    for cap in sorted(delta_dirs - proposal_caps):
        findings.append(finding(
            "traceability", "medium", f"openspec/changes/{name}/specs/{cap}/spec.md",
            f"Delta dir specs/{cap}/ exists but '{cap}' is not named in the proposal's Capabilities.",
            f"specs/ dirs include '{cap}'; Capabilities: {sorted(proposal_caps) or 'none'}",
            f"Add '{cap}' to Capabilities or remove the delta dir.",
            f"delta-{cap}-no-capability"))

    # Impact deliverable -> referenced by a task (reused dependencies are excluded)
    for p in sorted(deliverables):
        if not referenced_in_text(p, task_blob):
            findings.append(finding(
                "traceability", "low", f"openspec/changes/{name}/proposal.md",
                f"Impact lists '{p}' but no task references it.",
                f"Impact path '{p}' absent from tasks.md text",
                "Add a task that touches this file, or drop it from Impact.",
                f"impact-{re.sub(r'[^a-z0-9]+','-',p.lower()).strip('-')}-no-task"))

    # requirement -> task: keyword-overlap candidate (semantic link left to the agent)
    req_candidates = []
    for r in reqs:
        keywords = _keywords(r["name"])
        best = _best_task(keywords, tasks)
        req_candidates.append({
            "capability": r["capability"], "operation": r["operation"], "requirement": r["name"],
            "scenario_count": len(r["scenarios"]),
            "candidate_task": best["id"] if best else None,
            "candidate_overlap": best["score"] if best else 0.0,
        })

    return {
        "counts": {
            "capabilities": len(proposal_caps), "delta_dirs": len(delta_dirs),
            "what_changes": len(what_changes), "impact_paths": len(impact_paths),
            "tasks": len(tasks), "requirements": len(reqs),
        },
        "findings": findings,
        "requirement_task_candidates": req_candidates,
        "what_changes": what_changes,
        "note": "requirement<->task links are keyword candidates; the skill confirms each semantically.",
    }


_STOP = {"the", "a", "an", "of", "and", "or", "to", "for", "in", "on", "is", "are",
         "with", "by", "per", "at", "no", "not", "its", "explanation", "requirement"}


def _keywords(name: str) -> set[str]:
    return {w for w in re.findall(r"[a-z0-9]+", name.lower()) if w not in _STOP and len(w) > 2}


def _best_task(keywords: set[str], tasks: list[dict]) -> dict | None:
    if not keywords:
        return None
    best = None
    for t in tasks:
        tw = set(re.findall(r"[a-z0-9]+", t["text"].lower()))
        score = len(keywords & tw) / len(keywords)
        if best is None or score > best["score"]:
            best = {"id": t["id"], "score": round(score, 2)}
    return best


def check_modified(root: Path, name: str) -> dict:
    cdir = change_dir(root, name)
    findings: list[dict] = []
    review_pairs: list[dict] = []
    specs_dir = cdir / "specs"
    if not specs_dir.is_dir():
        return {"findings": findings, "review_pairs": review_pairs, "note": "no deltas"}
    # An archived change is already synced: its ADDED requirements now live in canonical
    # by design, so canonical-drift checks are moot and would false-fire. Skip them.
    if "archive" in cdir.parts:
        return {
            "findings": findings,
            "review_pairs": review_pairs,
            "note": "change is archived (already synced); canonical-drift checks skipped",
        }

    for cap_dir in sorted(specs_dir.glob("*")):
        if not cap_dir.is_dir():
            continue
        cap = cap_dir.name
        delta_blocks = parse_requirement_blocks(read(cap_dir / "spec.md"))
        canonical_path = root / "openspec" / "specs" / cap / "spec.md"
        canonical = {b["name"]: b for b in parse_requirement_blocks(read(canonical_path))} if canonical_path.is_file() else {}
        cap_file = f"openspec/changes/{name}/specs/{cap}/spec.md"

        for b in delta_blocks:
            op, rname = b["operation"], b["name"]
            slug = re.sub(r"[^a-z0-9]+", "-", rname.lower()).strip("-")
            if op == "MODIFIED":
                if rname not in canonical:
                    findings.append(finding(
                        "spec-delta", "high", cap_file,
                        f"MODIFIED '{rname}' has no matching requirement in canonical {cap}.",
                        f"canonical {canonical_path} lacks a '### Requirement: {rname}'",
                        "Use ADDED instead, or fix the requirement name to match canonical.",
                        f"modified-{slug}-no-canonical"))
                elif normalize(canonical[rname]["body"]) == normalize(b["body"]):
                    findings.append(finding(
                        "spec-delta", "medium", cap_file,
                        f"MODIFIED '{rname}' is identical to canonical; the delta changes nothing.",
                        f"delta body == canonical body for '{rname}'",
                        "Remove the no-op MODIFIED or make the intended change explicit.",
                        f"modified-{slug}-noop"))
                else:
                    review_pairs.append({
                        "capability": cap, "requirement": rname,
                        "canonical_body": canonical[rname]["body"],
                        "delta_body": b["body"],
                        "judge": "Is the delta's intended change consistent with current reality, "
                                 "or does it assume a canonical baseline that has since changed (stale)?",
                    })
            elif op == "ADDED":
                if rname in canonical:
                    findings.append(finding(
                        "spec-delta", "high", cap_file,
                        f"ADDED '{rname}' already exists in canonical {cap}.",
                        f"canonical {canonical_path} already defines '{rname}'",
                        "Use MODIFIED to change the existing requirement instead of ADDED.",
                        f"added-{slug}-duplicates-canonical"))
            elif op in ("REMOVED", "RENAMED"):
                if rname not in canonical:
                    findings.append(finding(
                        "spec-delta", "high", cap_file,
                        f"{op} '{rname}' names a requirement absent from canonical {cap}.",
                        f"canonical {canonical_path} has no '{rname}'",
                        f"Fix the requirement name; {op} must target an existing requirement.",
                        f"{op.lower()}-{slug}-no-canonical"))
    return {"findings": findings, "review_pairs": review_pairs}


def check_grounding(root: Path, name: str) -> dict:
    cdir = change_dir(root, name)
    findings: list[dict] = []
    text = ""
    for fn in ("proposal.md", "design.md", "tasks.md"):
        if (cdir / fn).is_file():
            text += "\n" + read(cdir / fn)

    referenced = extract_paths(text)
    # paths the change introduces: create/add/author/write verbs near the path, or Impact "New"
    introduced: set[str] = set()
    for line in text.splitlines():
        if re.search(r"\b(new|creat|add|author|writ)\w*\b", line, re.I):
            introduced |= extract_paths(line)

    unresolved = []
    for p in sorted(referenced):
        if path_grounded(root, p):
            continue
        if p in introduced:
            continue
        # ignore prose ellipses ('.../point/reduction.py') and placeholder example paths
        if "..." in p or p.startswith(("http", "specs/<", "src/<")) or "<" in p:
            continue
        unresolved.append(p)
        findings.append(finding(
            "grounding", "medium", f"openspec/changes/{name}/proposal.md",
            f"Referenced path '{p}' does not exist and no task introduces it.",
            f"'{p}' not found under repo root and not matched by a create/add task",
            "Fix the path, or add a task that creates it, or mark it as new in Impact.",
            f"unresolved-{re.sub(r'[^a-z0-9]+','-',p.lower()).strip('-')}"))

    # backticked symbol tokens handed to the agent (not auto-flagged; too noisy to gate)
    symbols = sorted({m for m in re.findall(r"`([a-z_][a-z0-9_]+(?:\.[a-z0-9_]+)+|[A-Z][A-Za-z0-9]+)`", text)})
    return {
        "findings": findings,
        "unresolved_paths": unresolved,
        "symbols_for_agent": symbols[:60],
        "note": "paths are gated deterministically; symbols are handed to the agent to resolve.",
    }


def check_cross_change(root: Path, name: str) -> dict:
    cdir = change_dir(root, name)
    my_caps = {p.name for p in (cdir / "specs").glob("*") if p.is_dir()} if (cdir / "specs").is_dir() else set()
    listing = openspec_json(root, ["list"])
    findings: list[dict] = []
    overlaps = []
    for ch in listing.get("changes", []):
        other = ch["name"]
        if other == name:
            continue
        odir = root / "openspec" / "changes" / other / "specs"
        ocaps = {p.name for p in odir.glob("*") if p.is_dir()} if odir.is_dir() else set()
        shared = my_caps & ocaps
        if not shared:
            continue
        status = ch.get("status", "?")
        overlaps.append({"change": other, "shared_capabilities": sorted(shared), "status": status})
        if status == "complete":
            findings.append(finding(
                "cross-change", "high", f"openspec/changes/{name}/",
                f"Completed-but-unarchived change '{other}' modifies shared capability {sorted(shared)}.",
                f"'{other}' status={status}, shares {sorted(shared)}",
                "Resolve sync ordering: archive/sync the predecessor first or reconcile the deltas.",
                f"predecessor-{other}"))
        else:
            findings.append(finding(
                "cross-change", "medium", f"openspec/changes/{name}/",
                f"Active change '{other}' also modifies shared capability {sorted(shared)}.",
                f"'{other}' status={status}, shares {sorted(shared)}",
                "Coordinate the two deltas to avoid a merge/sync collision.",
                f"collision-{other}"))
    return {"findings": findings, "overlaps": overlaps}


def check_lifecycle(root: Path, name: str) -> dict:
    """Infer review mode. Prefer the openspec CLI for progress; fall back to counting
    tasks.md checkboxes when the CLI does not know the change (e.g. it is archived).
    Progress is not critical-path data, so this degrades soft rather than failing loud.
    """
    cdir = change_dir(root, name)
    archived = "archive" in cdir.parts
    total = complete = 0
    artifacts_complete = None
    try:
        prog = openspec_json(root, ["instructions", "apply", "--change", name]).get("progress", {})
        total, complete = prog.get("total", 0), prog.get("complete", 0)
        artifacts_complete = openspec_json(root, ["status", "--change", name]).get("isComplete")
    except ManifestError:
        tasks = parse_tasks(read(cdir / "tasks.md")) if (cdir / "tasks.md").is_file() else []
        total, complete = len(tasks), sum(1 for t in tasks if t["checked"])
    if archived:
        mode = "archived"
    else:
        mode = "archive-time" if total > 0 and complete == total else "propose-time"
    return {"mode": mode, "archived": archived, "tasks_total": total,
            "tasks_complete": complete, "artifacts_complete": artifacts_complete}


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
CHECKS = {
    "traceability": check_traceability,
    "modified": check_modified,
    "grounding": check_grounding,
    "cross-change": check_cross_change,
    "lifecycle": check_lifecycle,
}


def run_all(root: Path, name: str) -> dict:
    manifest = {"change": name, "validate": validate(root, name)}
    for key, fn in CHECKS.items():
        manifest[key] = fn(root, name)
    det = [f for k in ("traceability", "modified", "grounding", "cross-change")
           for f in manifest[k].get("findings", [])]
    manifest["deterministic_findings"] = det
    manifest["summary"] = {
        "mode": manifest["lifecycle"]["mode"],
        "validate_passed": manifest["validate"]["passed"],
        "deterministic_finding_counts": {
            sev: sum(1 for f in det if f["severity"] == sev) for sev in ("high", "medium", "low")
        },
        "review_pairs": len(manifest["modified"].get("review_pairs", [])),
    }
    return manifest


def main(argv: list[str]) -> int:
    if len(argv) < 2 or argv[0] not in {*CHECKS, "all"}:
        sys.stderr.write(
            "usage: review_manifest.py {traceability|modified|grounding|cross-change|lifecycle|all} <change>\n"
        )
        return 2
    cmd, name = argv[0], argv[1]
    try:
        root = find_repo_root(Path.cwd())
        result = run_all(root, name) if cmd == "all" else CHECKS[cmd](root, name)
    except ManifestError as exc:
        sys.stderr.write(f"ERROR: {exc}\n")
        return 1
    json.dump(result, sys.stdout, indent=2)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
