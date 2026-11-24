#!/usr/bin/env python3
"""Project ledger: one file per requirement, issue, change request, decision and release.

Commands
  new <TYPE> "<title>" [--area a] [--source s] [--as name]   create the next item of a type
  build                                                       write docs/generated/ views
  lint [--commits <rev-range>]                                check items, links, roles, generated views
  release <version> [--previous <version>] [--tag <tag>]      draft REL notes and freeze views

No dependencies beyond Python 3.10. Uses PyYAML if installed; otherwise a small parser that
understands the subset these items use (scalars, inline lists, block lists, one-level maps).
Copy this file to tools/ledger.py in the project; config lives in docs/ledger.yaml.
"""
from __future__ import annotations

import argparse
import datetime as dt
import re
import shutil
import subprocess
import sys
from collections import defaultdict
from pathlib import Path

TYPES = ("REQ", "ISS", "CR", "DEC", "REL")
STATES = {
    "REQ": ["proposed", "accepted", "implemented", "verified", "deferred", "rejected", "superseded"],
    "ISS": ["open", "triaged", "in-progress", "fixed", "closed", "wont-fix", "design-intent", "duplicate"],
    "CR": ["raised", "assessed", "accepted", "applied", "rejected"],
    "DEC": ["active", "superseded"],
    "REL": ["planned", "frozen", "released"],
}
LINK_VERBS = {
    "violates", "changes", "resolved-by", "resolves", "supersedes", "superseded-by",
    "duplicate-of", "depends-on", "verified-by", "spawned", "mirror",
}
ID_RE = re.compile(r"\b(REQ|ISS|CR|DEC)-(\d{4})\b|\b(REL)-(\d+\.\d+\.\d+)\b")

# ----------------------------------------------------------------------------- yaml

def _blank_nulls(text: str) -> str:
    # Humans fill these in by hand; `accepted_by:` reads better than `accepted_by: null`.
    return re.sub(r"^(\s*[\w-]+):\s*null\s*$", r"\1:", text, flags=re.M)


try:
    import yaml as _yaml  # type: ignore

    def parse_yaml(text: str) -> dict:
        return _yaml.safe_load(text) or {}

    def dump_yaml(data: dict) -> str:
        return _blank_nulls(_yaml.safe_dump(data, sort_keys=False, allow_unicode=True, default_flow_style=False))

except ImportError:  # pragma: no cover - fallback, covers the subset ledger items use

    def _scalar(s: str):
        s = s.strip()
        if s == "" or s in ("null", "~"):
            return None
        if s in ("true", "false"):
            return s == "true"
        if s.startswith("[") and s.endswith("]"):
            inner = s[1:-1].strip()
            return [_scalar(x) for x in inner.split(",")] if inner else []
        if s.startswith("{") and s.endswith("}"):
            inner = s[1:-1].strip()
            out = {}
            for part in (inner.split(",") if inner else []):
                k, _, v = part.partition(":")
                out[k.strip()] = _scalar(v)
            return out
        if re.fullmatch(r"-?\d+", s):
            return int(s)
        if len(s) >= 2 and s[0] == s[-1] and s[0] in "'\"":
            return s[1:-1]
        return s

    def parse_yaml(text: str) -> dict:
        lines = [(len(l) - len(l.lstrip()), l.strip()) for l in text.splitlines()
                 if l.strip() and not l.lstrip().startswith("#")]

        def block(i: int, indent: int):
            if i >= len(lines):
                return None, i
            if lines[i][1].startswith("- "):
                items = []
                while i < len(lines) and lines[i][0] == indent and lines[i][1].startswith("- "):
                    items.append(_scalar(lines[i][1][2:]))
                    i += 1
                return items, i
            obj: dict = {}
            while i < len(lines) and lines[i][0] == indent and not lines[i][1].startswith("- "):
                key, _, val = lines[i][1].partition(":")
                i += 1
                if val.strip() == "":
                    # PyYAML writes block lists at the parent's indent; hand-written ones indent them.
                    if i < len(lines) and (lines[i][0] > indent or lines[i][1].startswith("- ")):
                        obj[key.strip()], i = block(i, lines[i][0])
                    else:
                        obj[key.strip()] = None
                else:
                    obj[key.strip()] = _scalar(val)
            return obj, i

        out, _ = block(0, lines[0][0] if lines else 0)
        return out or {}

    def dump_yaml(data: dict) -> str:
        out: list[str] = []

        def emit(obj, indent=0):
            pad = "  " * indent
            if isinstance(obj, dict):
                for k, v in obj.items():
                    if isinstance(v, (dict, list)) and v:
                        out.append(f"{pad}{k}:")
                        emit(v, indent + 1)
                    elif isinstance(v, list):
                        out.append(f"{pad}{k}: []")
                    elif isinstance(v, dict):
                        out.append(f"{pad}{k}: {{}}")
                    else:
                        out.append(f"{pad}{k}: {'' if v is None else v}".rstrip())
            elif isinstance(obj, list):
                for v in obj:
                    out.append(f"{pad}- {v}")

        emit(data)
        return "\n".join(out) + "\n"


# ----------------------------------------------------------------------------- io

def find_root(start: Path | None = None) -> Path:
    p = (start or Path.cwd()).resolve()
    for cand in [p, *p.parents]:
        if (cand / "docs" / "ledger.yaml").exists():
            return cand
    sys.exit("No docs/ledger.yaml found above the current directory.")


class Ledger:
    def __init__(self, root: Path):
        self.root = root
        self.cfg = parse_yaml((root / "docs" / "ledger.yaml").read_text(encoding="utf-8"))
        self.items_dir = root / self.cfg.get("items_dir", "docs/items")
        self.gen_dir = root / self.cfg.get("generated_dir", "docs/generated")
        self.rel_dir = root / self.cfg.get("releases_dir", "docs/releases")
        self.items: dict[str, dict] = {}
        self.bodies: dict[str, str] = {}
        self.errors: list[str] = []
        self.load()

    def load(self):
        self.items_dir.mkdir(parents=True, exist_ok=True)
        for f in sorted(self.items_dir.glob("*.md")):
            text = f.read_text(encoding="utf-8")
            m = re.match(r"^---\n(.*?)\n---\n?(.*)$", text, re.S)
            if not m:
                self.errors.append(f"{f.name}: no frontmatter")
                continue
            try:
                meta = parse_yaml(m.group(1))
            except Exception as e:  # noqa: BLE001
                self.errors.append(f"{f.name}: bad yaml: {e}")
                continue
            iid = meta.get("id")
            if iid != f.stem:
                self.errors.append(f"{f.name}: id field {iid!r} does not match filename")
            if iid in self.items:
                self.errors.append(f"{f.name}: duplicate id {iid}")
            self.items[iid] = meta
            self.bodies[iid] = m.group(2).strip()

    def write_item(self, meta: dict, body: str):
        path = self.items_dir / f"{meta['id']}.md"
        path.write_text("---\n" + dump_yaml(meta) + "---\n\n" + body.rstrip() + "\n", encoding="utf-8")
        return path

    # roles
    def role_of(self, name) -> set[str]:
        roles = self.cfg.get("roles") or {}
        return {r for r, names in roles.items() if names and name in names}

    def known(self, name) -> bool:
        return name == "user" or bool(self.role_of(name))

    def links(self, iid: str) -> list[tuple[str, str]]:
        out = []
        for raw in (self.items[iid].get("links") or []):
            parts = str(raw).split(None, 1)
            if len(parts) == 2:
                out.append((parts[0], parts[1].strip()))
            else:
                out.append((parts[0] if parts else "", ""))
        return out

    def inbound(self) -> dict[str, list[tuple[str, str]]]:
        inb = defaultdict(list)
        for iid in self.items:
            for verb, target in self.links(iid):
                inb[target].append((verb, iid))
        return inb


# ----------------------------------------------------------------------------- new

def cmd_new(args):
    L = Ledger(find_root())
    t = args.type.upper()
    if t not in TYPES:
        sys.exit(f"type must be one of {TYPES}")
    today = dt.date.today().isoformat()
    if t == "REL":
        if not args.version:
            sys.exit("REL needs --version")
        iid = f"REL-{args.version}"
    else:
        lo, hi = 1, 9999
        blocks = (L.cfg.get("id_blocks") or {})
        if args.as_ and args.as_ in blocks and t in blocks[args.as_]:
            lo, hi = blocks[args.as_][t]
        used = {int(k.split("-")[1]) for k in L.items if k.startswith(t + "-")}
        n = next((i for i in range(lo, hi + 1) if i not in used), None)
        if n is None:
            sys.exit(f"no free {t} id in block {lo}..{hi}")
        iid = f"{t}-{n:04d}"
    first_pm = ((L.cfg.get("roles") or {}).get("pm") or [None])[0]
    first_lead = ((L.cfg.get("roles") or {}).get("lead") or [first_pm])[0]
    meta: dict = {"id": iid, "type": t, "title": args.title, "status": STATES[t][0]}
    if t != "REL":
        meta["area"] = args.area or next(iter(L.cfg.get("areas") or {"core": 0}))
    meta["owner"] = args.owner or (first_lead if t in ("ISS", "REL") else first_pm)
    meta["created"] = today
    if t in ("REQ", "ISS", "CR"):
        meta["source"] = args.source or f"found {today}"
    if t == "REQ":
        meta.update(verify=args.verify or "", version=1, accepted_by=None, implemented_by=None,
                    verified_by=None, release=None)
    elif t == "ISS":
        meta.update(severity=args.severity or "major", triaged_by=None, closed_by=None, resolution=None, release=None)
    elif t == "CR":
        meta.update(impact={}, accepted_by=None)
    elif t == "DEC":
        meta.update(decided_by=args.by or None, why=args.why or "", affects=[])
    elif t == "REL":
        meta.update(version=args.version, tag=args.tag or f"v{args.version}", previous=args.previous,
                    claims=[], gate={"condition": "", "evidence": f"docs/reviews/{args.version}.md"},
                    released_by=None)
    meta["links"] = list(args.link or [])
    path = L.write_item(meta, args.body or "")
    print(path.relative_to(L.root))


# ----------------------------------------------------------------------------- build

def _t(items, cols, rows):
    lines = ["| " + " | ".join(cols) + " |", "| " + " | ".join("---" for _ in cols) + " |"]
    for r in rows:
        lines.append("| " + " | ".join(str(x if x is not None else "") for x in r) + " |")
    return "\n".join(lines)


def _link_list(pairs, verb=None):
    return ", ".join(f"{t} ({v})" if verb is None else t for v, t in pairs if verb is None or v == verb)


def build_views(L: Ledger) -> dict[str, str]:
    areas = L.cfg.get("areas") or {}
    inb = L.inbound()
    stamp = f"_Generated by tools/ledger.py on {dt.date.today().isoformat()}. Do not edit; edit docs/items/ and rebuild._\n"
    views = {}

    # ORD
    out = [f"# Requirements register — {L.cfg.get('project','')}\n", stamp]
    reqs = [i for i in L.items.values() if i.get("type") == "REQ"]
    by_area = defaultdict(list)
    for r in reqs:
        by_area[r.get("area", "unassigned")].append(r)
    for a in list(areas) + [x for x in by_area if x not in areas]:
        if a not in by_area:
            continue
        out.append(f"\n## {areas.get(a, a)}\n")
        out.append(_t(L, ["ID", "Requirement", "Source", "Verify", "Release", "v", "Status"],
                      [(r["id"], r.get("title"), r.get("source"), r.get("verify"), r.get("release") or r.get("milestone"),
                        r.get("version"), r.get("status")) for r in sorted(by_area[a], key=lambda x: x["id"])]))
    counts = defaultdict(int)
    for r in reqs:
        counts[r.get("status")] += 1
    out.append("\n## Totals\n")
    out.append(_t(L, ["Status", "Count"], [(s, counts[s]) for s in STATES["REQ"] if counts[s]]))
    views["ORD.md"] = "\n".join(out) + "\n"

    # TRACE
    out = ["# Traceability matrix\n", stamp,
           _t(L, ["REQ", "Title", "Status", "Evidence", "Issues", "Change requests", "Decisions"],
              [(r["id"], r.get("title"), r.get("status"),
                "<br>".join(t for v, t in L.links(r["id"]) if v == "verified-by"),
                ", ".join(s for v, s in inb.get(r["id"], []) if v == "violates"),
                ", ".join(s for v, s in inb.get(r["id"], []) if v == "changes"),
                ", ".join(d["id"] for d in L.items.values() if d.get("type") == "DEC" and r["id"] in (d.get("affects") or [])))
               for r in sorted(reqs, key=lambda x: x["id"])])]
    views["TRACE.md"] = "\n".join(out) + "\n"

    # OPEN
    out = ["# What's open\n", stamp]
    def section(title, cols, rows):
        out.append(f"\n## {title}\n")
        out.append(_t(L, cols, rows) if rows else "_None._")
    section("Proposed requirements awaiting acceptance", ["ID", "Title", "Source", "Owner"],
            [(r["id"], r.get("title"), r.get("source"), r.get("owner")) for r in reqs if r.get("status") == "proposed"])
    section("Accepted or implemented, not yet verified", ["ID", "Title", "Status", "Release", "Owner"],
            [(r["id"], r.get("title"), r.get("status"), r.get("release"), r.get("owner"))
             for r in reqs if r.get("status") in ("accepted", "implemented")])
    iss = [i for i in L.items.values() if i.get("type") == "ISS" and i.get("status") in ("open", "triaged", "in-progress", "fixed")]
    section("Open issues", ["ID", "Severity", "Title", "Violates", "Status", "Release", "Owner"],
            [(i["id"], i.get("severity"), i.get("title"), _link_list(L.links(i["id"]), "violates"), i.get("status"),
              i.get("release"), i.get("owner")) for i in sorted(iss, key=lambda x: (x.get("release") or "~", x["id"]))])
    crs = [c for c in L.items.values() if c.get("type") == "CR" and c.get("status") in ("raised", "assessed", "accepted")]
    section("Change requests awaiting decision or application", ["ID", "Title", "Changes", "Status", "Owner"],
            [(c["id"], c.get("title"), _link_list(L.links(c["id"]), "changes"), c.get("status"), c.get("owner")) for c in crs])
    rels = [r for r in L.items.values() if r.get("type") == "REL" and r.get("status") != "released"]
    section("Releases in flight", ["ID", "Title", "Status", "Claims", "Unverified claims"],
            [(r["id"], r.get("title"), r.get("status"), len(r.get("claims") or []),
              ", ".join(c for c in (r.get("claims") or []) if L.items.get(c, {}).get("status") != "verified")) for r in rels])
    views["OPEN.md"] = "\n".join(out) + "\n"

    # DECISIONS
    out = ["# Decision log\n", stamp, "Append only. To reverse a decision, add one that supersedes it.\n"]
    for d in sorted((i for i in L.items.values() if i.get("type") == "DEC"), key=lambda x: x["id"]):
        sup = " _(superseded)_" if d.get("status") == "superseded" else ""
        out.append(f"\n**{d['id']} · {d.get('created')} · {d.get('decided_by')}.** {d.get('title')}{sup}  ")
        out.append(f"**Why:** {d.get('why','')}  ")
        aff = d.get("affects") or []
        res = [t for v, t in L.links(d["id"]) if v == "resolves"]
        if aff or res:
            out.append(f"**Affects:** {', '.join(map(str, aff + res))}")
        if L.bodies.get(d["id"]):
            out.append("\n" + L.bodies[d["id"]])
    views["DECISIONS.md"] = "\n".join(out) + "\n"

    # CHANGELOG
    out = ["# Changelog\n", stamp, "One section per release, newest first. Notes are drafted from commits citing item IDs.\n"]
    for r in sorted((i for i in L.items.values() if i.get("type") == "REL"), key=lambda x: _vkey(x.get("version")), reverse=True):
        out.append(f"\n## {r.get('version')} — {r.get('title')} ({r.get('status')})\n")
        if r.get("claims"):
            out.append("**Satisfies:** " + ", ".join(r["claims"]) + "\n")
        g = r.get("gate") or {}
        if g.get("condition"):
            out.append(f"**Gate:** {g['condition']}. Evidence: `{g.get('evidence','')}`\n")
        if L.bodies.get(r["id"]):
            out.append(L.bodies[r["id"]])
    views["CHANGELOG.md"] = "\n".join(out) + "\n"
    return views


def _vkey(v):
    try:
        return tuple(int(x) for x in str(v).split("."))
    except ValueError:
        return (0,)


def cmd_build(args):
    L = Ledger(find_root())
    L.gen_dir.mkdir(parents=True, exist_ok=True)
    for name, text in build_views(L).items():
        (L.gen_dir / name).write_text(text, encoding="utf-8")
        print(f"wrote {(L.gen_dir / name).relative_to(L.root)}")
    if L.errors:
        print("\n".join("warning: " + e for e in L.errors), file=sys.stderr)


# ----------------------------------------------------------------------------- lint

def lint(L: Ledger, commits: str | None = None) -> list[str]:
    errs = list(L.errors)
    inb = L.inbound()
    for iid, it in L.items.items():
        t = it.get("type")
        if t not in TYPES:
            errs.append(f"{iid}: unknown type {t!r}")
            continue
        if it.get("status") not in STATES[t]:
            errs.append(f"{iid}: status {it.get('status')!r} not in {STATES[t]}")
        for req in ("title", "owner", "created"):
            if not it.get(req):
                errs.append(f"{iid}: missing {req}")
        if t != "REL" and it.get("area") not in (L.cfg.get("areas") or {}):
            errs.append(f"{iid}: area {it.get('area')!r} not in ledger.yaml areas")
        if it.get("owner") and not L.known(it["owner"]):
            errs.append(f"{iid}: owner {it['owner']!r} not in roles table")
        for verb, target in L.links(iid):
            if verb not in LINK_VERBS:
                errs.append(f"{iid}: unknown link verb {verb!r}")
            if ID_RE.fullmatch(target) and target not in L.items:
                errs.append(f"{iid}: link target {target} does not exist")
            if verb == "verified-by" and not ID_RE.fullmatch(target):
                p = target.split("::")[0]
                if not (L.root / p).exists():
                    errs.append(f"{iid}: evidence path {p} does not exist")

        def role_check(field, roles, when=True):
            name = it.get(field)
            if not when:
                return
            if not name:
                errs.append(f"{iid}: status {it.get('status')} requires {field}")
            elif not L.known(name):
                errs.append(f"{iid}: {field} {name!r} not in roles table")
            elif roles and name != "user" and not (L.role_of(name) & set(roles)):
                errs.append(f"{iid}: {field} {name!r} must hold one of {roles}")

        s = it.get("status")
        if t == "REQ":
            role_check("accepted_by", ["pm"], when=s not in ("proposed",))
            if s in ("implemented", "verified") and not it.get("verify"):
                errs.append(f"{iid}: {s} without a verify field")
            role_check("implemented_by", [], when=s in ("implemented", "verified"))
            role_check("verified_by", [], when=s == "verified")
            if s == "verified":
                if it.get("verified_by") and it.get("verified_by") == it.get("implemented_by"):
                    errs.append(f"{iid}: verified_by equals implemented_by; verification must be independent")
                if not any(v == "verified-by" for v, _ in L.links(iid)):
                    errs.append(f"{iid}: verified without a verified-by evidence link")
            if s == "superseded" and not any(v == "superseded-by" for v, _ in L.links(iid)):
                errs.append(f"{iid}: superseded without a superseded-by link")
            if s == "rejected" and not any(iid in (d.get("affects") or []) for d in L.items.values() if d.get("type") == "DEC"):
                errs.append(f"{iid}: rejected without a DEC listing it in affects")
        elif t == "ISS":
            if it.get("severity") not in ("blocker", "major", "minor", "cosmetic"):
                errs.append(f"{iid}: severity {it.get('severity')!r} invalid")
            role_check("triaged_by", ["lead"], when=s not in ("open",))
            role_check("closed_by", ["designer"] if s == "design-intent" else [], when=s in ("closed", "wont-fix", "design-intent", "duplicate"))
            if s == "duplicate" and not any(v == "duplicate-of" for v, _ in L.links(iid)):
                errs.append(f"{iid}: duplicate without a duplicate-of link")
            if not any(v == "violates" for v, _ in L.links(iid)) and s not in ("duplicate",):
                errs.append(f"{iid}: issue does not link `violates REQ-nnnn`")
        elif t == "CR":
            if not any(v == "changes" for v, _ in L.links(iid)):
                errs.append(f"{iid}: change request does not link `changes REQ-nnnn`")
            role_check("accepted_by", ["pm"], when=s in ("accepted", "applied", "rejected"))
            if s in ("accepted", "applied", "rejected"):
                has_dec = any(v == "resolved-by" for v, _ in L.links(iid)) or any(v == "resolves" for v, _ in inb.get(iid, []))
                if not has_dec:
                    errs.append(f"{iid}: {s} without a DEC (resolved-by / resolves link)")
        elif t == "DEC":
            if not it.get("decided_by"):
                errs.append(f"{iid}: missing decided_by")
            elif not L.known(it["decided_by"]) and it["decided_by"] not in (L.cfg.get("roles") or {}):
                errs.append(f"{iid}: decided_by {it['decided_by']!r} not a known name or role")
            if not it.get("why"):
                errs.append(f"{iid}: missing why")
            if s == "superseded" and not any(v == "superseded-by" for v, _ in L.links(iid)):
                errs.append(f"{iid}: superseded without a superseded-by link")
        elif t == "REL":
            for c in it.get("claims") or []:
                if c not in L.items:
                    errs.append(f"{iid}: claim {c} does not exist")
                elif s in ("frozen", "released") and L.items[c].get("status") != "verified":
                    errs.append(f"{iid}: {s} but claim {c} is {L.items[c].get('status')}")
            role_check("released_by", ["lead", "pm"], when=s == "released")
            if s in ("frozen", "released") and not (L.rel_dir / str(it.get("version"))).exists():
                errs.append(f"{iid}: {s} but {L.rel_dir.relative_to(L.root)}/{it.get('version')} is missing")

    # generated views up to date
    if L.gen_dir.exists():
        for name, text in build_views(L).items():
            f = L.gen_dir / name
            cur = f.read_text(encoding="utf-8") if f.exists() else ""
            strip = lambda s: re.sub(r"_Generated by .*?_\n", "", s)  # noqa: E731
            if strip(cur) != strip(text):
                errs.append(f"generated/{name} is stale; run `ledger.py build`")

    # commits cite existing ids
    if commits:
        try:
            log = subprocess.run(["git", "log", "--format=%h %s", commits], cwd=L.root, capture_output=True, text=True, check=True).stdout
        except subprocess.CalledProcessError as e:
            errs.append(f"git log failed: {e.stderr.strip()}")
            log = ""
        for line in log.splitlines():
            ids = ["-".join(x for x in m if x) for m in ID_RE.findall(line)]
            if not ids:
                errs.append(f"commit {line[:72]!r} cites no item id")
            for i in ids:
                if i not in L.items:
                    errs.append(f"commit {line[:7]} cites {i}, which does not exist")
    return errs


def cmd_lint(args):
    L = Ledger(find_root())
    errs = lint(L, args.commits)
    if errs:
        print("\n".join(errs))
        print(f"\n{len(errs)} problem(s)")
        sys.exit(1)
    print(f"ok: {len(L.items)} items, links resolve, roles valid, views current")


# ----------------------------------------------------------------------------- release

def cmd_release(args):
    L = Ledger(find_root())
    iid = f"REL-{args.version}"
    if iid not in L.items:
        rels = sorted((r for r in L.items.values() if r.get("type") == "REL"), key=lambda x: _vkey(x.get("version")))
        prev = args.previous or (rels[-1].get("version") if rels else None)
        first_lead = ((L.cfg.get("roles") or {}).get("lead") or [None])[0]
        meta = {"id": iid, "type": "REL", "title": args.title or f"Release {args.version}", "status": "planned",
                "owner": first_lead, "created": dt.date.today().isoformat(), "version": args.version,
                "tag": args.tag or f"v{args.version}", "previous": prev, "claims": [],
                "gate": {"condition": "", "evidence": f"docs/reviews/{args.version}.md"}, "released_by": None, "links": []}
        L.write_item(meta, "")
        L.load()
    rel = L.items[iid]
    prev = args.previous or rel.get("previous")
    prev_tag = L.items.get(f"REL-{prev}", {}).get("tag", f"v{prev}") if prev else None
    rng = f"{prev_tag}..HEAD" if prev_tag else "HEAD"
    try:
        log = subprocess.run(["git", "log", "--format=%h %s", rng], cwd=L.root, capture_output=True, text=True, check=True).stdout
    except subprocess.CalledProcessError:
        log = ""
    cited = defaultdict(list)
    uncited = []
    for line in log.splitlines():
        ids = ["-".join(x for x in m if x) for m in ID_RE.findall(line)]
        if ids:
            for i in ids:
                cited[i].append(line)
        else:
            uncited.append(line)
    notes = [f"## Notes (drafted from `{rng}`)\n"]
    for i in sorted(cited):
        it = L.items.get(i, {})
        notes.append(f"- **{i}** {it.get('title','(unknown item)')} — {it.get('status','')}")
        for c in cited[i]:
            notes.append(f"  - `{c}`")
    if uncited:
        notes.append("\n**Commits citing no item** (should be none):")
        notes += [f"- `{c}`" for c in uncited]
    unverified = [c for c in rel.get("claims") or [] if L.items.get(c, {}).get("status") != "verified"]
    if unverified:
        print(f"refusing to freeze: claims not verified: {', '.join(unverified)}")
        sys.exit(1)
    problems = [e for e in lint(L) if "is stale" not in e and not e.startswith(iid)]
    if problems:
        print("refusing to freeze while the lint fails:" + chr(10) + chr(10).join(problems))
        sys.exit(1)
    body = L.bodies.get(iid, "")
    body = re.sub(r"## Notes \(drafted.*", "", body, flags=re.S).rstrip()
    rel["status"] = "frozen"
    L.write_item(rel, (body + "\n\n" if body else "") + "\n".join(notes))
    L.load()
    views = build_views(L)
    L.gen_dir.mkdir(parents=True, exist_ok=True)
    for n, t in views.items():
        (L.gen_dir / n).write_text(t, encoding="utf-8")
    dest = L.rel_dir / str(args.version)
    dest.mkdir(parents=True, exist_ok=True)
    for n in views:
        shutil.copy(L.gen_dir / n, dest / n)
    ev = (rel.get("gate") or {}).get("evidence")
    if ev and (L.root / ev).exists():
        shutil.copy(L.root / ev, dest / Path(ev).name)
    print(f"{iid} frozen. Views copied to {dest.relative_to(L.root)}. Next: commit, `git tag {rel.get('tag')}`, lint, push.")


# ----------------------------------------------------------------------------- main

def main(argv=None):
    ap = argparse.ArgumentParser(prog="ledger.py", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    n = sub.add_parser("new", help="create the next item of a type")
    n.add_argument("type"); n.add_argument("title")
    n.add_argument("--area"); n.add_argument("--source"); n.add_argument("--owner"); n.add_argument("--verify")
    n.add_argument("--severity"); n.add_argument("--by"); n.add_argument("--why"); n.add_argument("--body")
    n.add_argument("--version"); n.add_argument("--tag"); n.add_argument("--previous")
    n.add_argument("--link", action="append", help='e.g. --link "violates REQ-0042"')
    n.add_argument("--as", dest="as_", help="allocate from this agent's id block")
    n.set_defaults(fn=cmd_new)

    b = sub.add_parser("build", help="write generated views"); b.set_defaults(fn=cmd_build)

    l = sub.add_parser("lint", help="check items, links, roles and views")
    l.add_argument("--commits", help="git rev range whose messages must cite existing ids, e.g. v1.3.0..HEAD")
    l.set_defaults(fn=cmd_lint)

    r = sub.add_parser("release", help="draft notes and freeze views for a version")
    r.add_argument("version"); r.add_argument("--previous"); r.add_argument("--tag"); r.add_argument("--title")
    r.set_defaults(fn=cmd_release)

    args = ap.parse_args(argv)
    args.fn(args)


if __name__ == "__main__":
    main()
