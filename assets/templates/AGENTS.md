# AGENTS.md — <Project>

Instructions for every agent and person working in this repo. Read this first, then
`docs/generated/OPEN.md`.

## The project

<Two or three sentences: what it is, for whom, what done looks like.>

| Document | What it is |
| --- | --- |
| `<brief path>` | The original spec. Don't edit it. |
| `docs/ledger.yaml` | Areas, roles, modules. |
| `docs/items/` | The ledger: one file per requirement (REQ), issue (ISS), change request (CR), decision (DEC), release (REL). Where the brief and the ledger differ, the ledger wins. |
| `docs/generated/` | Views built by `tools/ledger.py build`. Never hand-edited. Start with `OPEN.md`. |
| `docs/reviews/` | Gate review pages with evidence. |

## The ledger moves with the work

- **Requirements are written when discovered.** A must or must-not that isn't recorded gets a
  `proposed` REQ in the same commit as the work that found it. Never delete an item; change its status.
- **Statuses move with the work.** `implemented` when built, `verified` when someone who did not
  build it has checked the evidence.
- **Scope changes go through a CR and a DEC.** Only a DEC commit edits a requirement's text.
- **Decisions are appended, never edited.** Supersede instead.
- **Commit messages cite IDs:** `m2: camera sampler (REQ-0017, ISS-0004)`.
- **Before asking for a merge:** `python tools/ledger.py build && python tools/ledger.py lint`, and commit the generated views.

Roles and who may move what are in `docs/ledger.yaml` and enforced by the lint. Agents propose,
implement, file and raise; they don't accept scope or verify their own work.

<!-- Paste the sections for the modules that are on, from the project-ledger skill's references/modules.md:
     multi-agent branching and ownership · shared resource queue and lock · generated artefacts policy ·
     live status surface · silent-failure invariants -->

## Environment

<OS, shells, runtimes, how to run checks. Quote paths with spaces.>

## Stop points

Stop and report to the user, with rendered evidence, at:

1. <gate 1>
2. <gate 2>

## Final message format

End every task with:
- Branch and worktree, and what changed (paths).
- Items created or moved, with new statuses.
- What you ran to check it, and the result: real output, failures included.
- What needs a decision: proposed REQs, CRs awaiting a DEC, anything blocked.
