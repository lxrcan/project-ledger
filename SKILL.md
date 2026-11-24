---
name: project-ledger
description: >
  Run a project's requirements, issues, change requests, decisions and releases as one connected,
  version-controlled ledger inside the repo, with roles that own state transitions and generated
  views (requirements register, traceability matrix, changelog, release notes). Use this whenever
  the user wants to set up or run project management for a codebase: a requirements register or
  ORD, a decision log, traceability from spec to tests, change control, release gates, milestone
  tracking, an AGENTS.md or CLAUDE.md that keeps several agents or people coordinated, or asks
  "where do we track requirements / issues / decisions". Also use it during ordinary work in a repo
  that already has `docs/ledger.yaml` or `docs/items/`: before changing scope, closing an issue,
  marking something done, cutting a release or writing a final report, read this skill so the
  ledger moves with the work. Trigger even when the user only says "add a requirement",
  "log that decision", "what's open for 1.4", or "cut the release".
---

# Project ledger

One system for everything a project has to remember: what it must do (requirements), what is
wrong (issues), what should change (change requests), why (decisions) and what shipped (releases).
Every item is a file in the repo. Links between items are explicit and typed. The tables people
read are generated, never hand-edited. Because the ledger lives beside the code, checking out a
tag gives the documentation of that version for free.

This skill has a small mandatory core and optional modules. Switch a module on only when the
project needs it. A solo developer on a web app and a four-role team sharing one GPU both use the
same core.

## The one rule that makes it work

**The ledger moves in the same commit as the work.** A requirement discovered while fixing a bug
lands in the bug-fix commit. A status moves to `implemented` in the commit that implements it. A
decision is appended in the commit that acts on it. Everything else in this skill is adaptable;
this is not. A ledger updated "later" is a ledger that is wrong, and a wrong ledger is worse than
none because people trust it.

## The model

| Type | ID | What it records | Lifecycle |
| --- | --- | --- | --- |
| REQ | `REQ-0042` | Something the system must or must never do, with how it is verified | proposed → accepted → implemented → verified, or deferred, rejected, superseded |
| ISS | `ISS-0117` | A defect, incident or gap, linked to the requirement it violates | open → triaged → in-progress → fixed → closed, or wont-fix, design-intent, duplicate |
| CR | `CR-0009` | A proposed change to scope or to a requirement, with impact assessments | raised → assessed → accepted → applied, or rejected |
| DEC | `DEC-0031` | A choice that interprets or changes the spec, a convention or the process. Append only | active, superseded |
| REL | `REL-1.4.0` | A release: what it claims to satisfy, its gate evidence, its frozen docs | planned → frozen → released |

Items live in `docs/items/<ID>.md` with YAML frontmatter and a short body. Links are lines like
`changes REQ-0042`, `violates REQ-0042`, `resolves CR-0009`, `supersedes DEC-0012`,
`verified-by tests/test_x.py::name`. The full schema, every field and every link verb are in
`references/schema.md`. Read it before creating your first item in a project.

IDs are sequential per type, with an `area` field for grouping. Area-prefixed IDs read nicely but
renumber badly when areas split, so the generator groups by area instead.

**Requirements are never deleted.** Change the status. A requirement that was wrong becomes
`superseded` with a link to its replacement. History is `git log` on the file.

## Setup: starting a project on the ledger

Run this once, when the user asks to set up project management or when a repo has a brief but no
ledger. Expect it to take one commit.

1. **Read the brief or spec.** Every "must", "never", "at least" and "within" is a candidate REQ.
   Open questions and defaults the brief leaves to you are candidate DECs.
2. **Ask the module questions** (one short message, all at once). Each "yes" pulls one section
   from `references/modules.md` into the project's AGENTS.md:
   - Do two or more agents or people work the repo? → *multi-agent branching and ownership*
   - Is there something only one job can use at a time (GPU, device, staging env, rate-limited API)? → *shared resource queue and lock*
   - Does the project produce expensive artefacts (datasets, models, builds, renders)? → *generated artefacts policy*
   - Does the user watch progress somewhere other than chat (a dashboard, a viewport, a channel)? → *live status surface*
   - What breaks silently? Conventions, units, coordinate frames, encodings. Every project has at least one. → *silent-failure invariants*
3. **Write the roles table** in `docs/ledger.yaml` from `assets/templates/ledger.yaml`. Names to
   roles, including agents under their commit author names. If one person holds two roles, say so
   there; never give two roles the same power silently. Roles and what each may do are in
   `references/roles.md`.
4. **Create the items.** Copy `scripts/ledger.py` to `tools/ledger.py` in the project (it has no
   dependencies beyond Python 3.10). Create REQs with `python tools/ledger.py new REQ "title" --area <a> --source "brief §x"`,
   and one DEC per default you adopted. REQs from the brief start as `accepted`; those you
   inferred start as `proposed` for the PM to accept.
5. **Define gates.** A gate is a milestone whose exit is a verifiable check plus a stop point where
   you report to the user with evidence. Record gates as planned RELs, or as `milestone` values on
   REQs if releases are coarser than milestones.
6. **Write AGENTS.md** from `assets/templates/AGENTS.md`, the modules you switched on, the roles
   and the ownership table. Keep it short. It is what every agent reads first.
7. **Generate and commit.** `python tools/ledger.py build` writes `docs/generated/`. `python tools/ledger.py lint` must pass.
   Commit everything with a message that cites IDs, e.g. `ledger: initial register from brief (REQ-0001..REQ-0038, DEC-0001..DEC-0004)`.

## The working loop

Every task in a ledger project follows this shape. It costs a minute per task and saves the
project from drifting away from its own record.

**Before work**
- Read `docs/generated/OPEN.md` for what is open in your area and release, and `docs/PLAN.md` if
  the shared-resource module is on.
- Find the REQ or ISS you are working on. If none exists, create one first. Work that has no item
  cannot be traced, verified or released.

**During work**
- When you discover a must or must-not that isn't recorded (a tool limit, a missing spec, a rule a
  bug proved necessary), create a `proposed` REQ in the same commit. Cite the finding as `source`.
- When you find the requirement itself is wrong, don't quietly fix the requirement. File an ISS
  linked `violates REQ-nnnn`, and if the fix changes scope, raise a CR `changes REQ-nnnn`. The
  PM accepts or rejects it with a DEC. Only the DEC commit edits the requirement text and bumps its
  `version`.
- Cite IDs in every commit message: `m2: target camera sampler (REQ-0017, ISS-0004)`. The lint
  checks that cited IDs exist, and release notes are built from these citations.

**After work**
- Move the status. `implemented` when built, with `implemented_by` set to you. `verified` only by
  someone who did not implement it, with `verified_by` and a `verified-by` link to the evidence
  (a test, a review page, a measurement file). An agent verifying its own work is not verification.
- Run `python tools/ledger.py build && python tools/ledger.py lint`. Commit the generated views
  with the work. Stale views fail CI.
- Append a DEC for any choice that interprets or changes the spec, a convention, ownership or the
  process. Supersede, never edit.

## Roles

Ownership sits on state transitions, not on files. Anyone can create a REQ, ISS or CR. Only the
right role can move it through certain states, and the lint enforces this by checking the
`*_by` fields against the roles table.

| Transition | Who |
| --- | --- |
| REQ accept / reject / defer, assign to release | PM |
| REQ implemented | the implementer for that area |
| REQ verified | anyone who did not implement it |
| ISS triage (severity, release) | lead |
| ISS close | lead, or the owning role for design-intent / asset fixes |
| CR accept / reject | PM, and only with a DEC that `resolves` it |
| CR impact assessment | the role whose area it touches |
| DEC | the role whose domain it is: PM for scope and process, lead for technical, designer for design |
| REL frozen / released | lead cuts it, PM approves the notes |

Agents act under a named role from the roles table, usually implementer or lead. They may propose,
implement, file issues and raise change requests. They may not accept CRs, make scope decisions or
verify their own work. The full matrix with a worked example is in `references/roles.md`.

## Releases and gates

A release is three things committed together: a tag, a `REL-x.y.z.md` item, and a frozen copy of
the generated views in `docs/releases/x.y.z/`. The REL item says what the release claims to
satisfy; the frozen traceability matrix proves it. `python tools/ledger.py release x.y.z` does the
freezing and drafts the notes from commits since the previous tag.

A gate is a release or milestone with a stop point. At a gate, stop and report to the user with
the evidence rendered, not described: the test output, the measurement, the image grid. A gate
whose evidence is a sentence in chat has not been passed. The release review page template is in
`assets/templates/review.md`.

Order of operations: checks pass, items moved, views generated, lint clean, tag locally, then
push. Never force-push a tag.

## Final message format

End every task in a ledger project with:
- Branch and worktree, and what changed (paths).
- Items created or moved, with new statuses: `REQ-0017 → verified`, `ISS-0004 → fixed`,
  `DEC-0031 added`, `REQ-0052 proposed`.
- What you ran to check it and the real result, failures included.
- What needs a decision: proposed REQs awaiting acceptance, CRs awaiting a DEC.

This is how the PM sees what moved without reading diffs, and how proposed items get accepted
instead of rotting.

## Generated views

`python tools/ledger.py build` writes to `docs/generated/`:

| File | What it is |
| --- | --- |
| `ORD.md` | The requirements register, grouped by area, with status and verification |
| `TRACE.md` | Traceability matrix: each REQ with its tests, issues, change requests and decisions |
| `OPEN.md` | What's open: unverified REQs, open ISSs by release, CRs awaiting decision, proposed items |
| `DECISIONS.md` | The decision log in order |
| `CHANGELOG.md` | One section per REL, built from commits citing IDs |

Don't edit these by hand. Edit the items and rebuild. If you want a view that doesn't exist, add
it to the script and note it in a DEC.

## Scaling notes

- Below about 20 items, this is overkill. A single ORD table and decision log in two markdown
  files does the job; the same rules apply, only the storage differs.
- Above a few hundred items, keep the repo as the source of truth and mirror outward. A GitHub
  issue can create an `ISS` file that carries the issue URL; comments stay on GitHub, state lives
  in the file. Two sources of truth is where these systems die, so pick one and make the other a
  view. `references/workflows.md` covers the mirror.

## Where to read next

- `references/schema.md`: item fields, states, link verbs, ID rules. Read before creating items.
- `references/roles.md`: the transition matrix and a worked example of four roles handling one change.
- `references/workflows.md`: discovery, issue to change request to decision, release, gate, the GitHub mirror.
- `references/modules.md`: the five optional modules, each as a paste-ready AGENTS.md section.
- `scripts/ledger.py`: `new`, `build`, `lint`, `release`. Run `--help`.
- `assets/templates/`: item templates, `ledger.yaml`, `AGENTS.md`, `review.md`.
