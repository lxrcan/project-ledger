# project-ledger

A Claude Code skill for running a project's requirements, issues, change requests, decisions and
releases as one connected, version-controlled ledger inside the repo.

- One file per item under `docs/items/`, with typed links between them.
- Roles own state transitions, not files. A lint enforces them.
- Generated views: requirements register, traceability matrix, what's open, decision log, changelog.
- Releases freeze the views beside the tag, so checking out a version gives its documentation.
- Optional modules for multi-agent branching, a shared scarce resource, generated artefacts, a live
  status surface and silent-failure invariants.

## Install

Clone into your Claude Code skills directory:

```
git clone https://github.com/lxrcan/project-ledger "~/.claude/skills/project-ledger"
```

Then in any repo with a brief, ask Claude to set up project management. The skill's setup
procedure is in `SKILL.md`. The helper script `scripts/ledger.py` is copied into the project as
`tools/ledger.py` and needs only Python 3.10.

## Layout

```
SKILL.md                 the skill: model, setup, working loop, roles, releases
references/schema.md     fields, states, link verbs
references/roles.md      transition matrix and a worked example
references/workflows.md  discovery, bug, change request, release, gate, tracker mirror
references/modules.md    optional AGENTS.md sections
assets/templates/        item templates, ledger.yaml, AGENTS.md, review page
scripts/ledger.py        new · build · lint · release
```
