# Optional modules

Each module is a section to paste into the project's AGENTS.md, with placeholders in angle
brackets. Include a module only when the setup question for it was answered yes. A short AGENTS.md
that every agent actually reads beats a complete one that nobody does.

---

## Module: multi-agent branching and ownership

Include when two or more agents or people work the repo.

```markdown
## Who owns what

| Area | Owner | Paths |
| --- | --- | --- |
| <area> | <role or name> | `<paths>` |
| Ledger structure, releases | pm | `docs/ledger.yaml`, `docs/items/REL-*`, `docs/releases/` |
| Items | anyone may create; transitions per `docs/ledger.yaml` roles | `docs/items/` |

Don't edit another owner's paths. If you need a change there, file an ISS or raise a CR assigned
to them, and say so in your final message.

## Branching

Several agents share this machine. One working tree shared by two agents means one branch switch
overwrites the other's files. So:

1. The main checkout stays on `main` and stays clean. Nobody develops in it. The lead only merges
   and makes docs-only commits there.
2. Each agent works in its own worktree under `.worktrees/` (git-ignored):
   `git worktree add ".worktrees/<slug>" -b <branch> main`
3. Branch names: `<milestone>/<topic>`, `fix/<topic>`, `docs/<topic>`.
4. Commit small and often. Run the checks and `ledger.py lint` before asking for a merge.
5. Merging is the lead's job: `git merge --no-ff <branch>` into `main`, only after checks pass and
   the items are moved. Tag gates and releases.
6. Never force-push, rebase or amend shared commits, reset someone else's branch, delete another
   agent's branch or worktree, or commit generated data.
7. To pick up `main`, merge it into your branch. Don't rebase.
8. When a branch is merged, remove its worktree and delete the branch.

Item IDs: each agent allocates from its block in `docs/ledger.yaml` (`ledger.py new --as <name>`).
```

---

## Module: shared resource queue and lock

Include when something can only be used by one job at a time: a GPU, a test device, a staging
environment, a rate-limited API, a licence seat.

```markdown
## The <resource>

Only one heavy job uses the <resource> at a time. Before starting one, read `docs/PLAN.md` and
check the lock.

`docs/PLAN.md` holds the job queue: number, job, owner, branch, expected duration, state. Update
it when you add, finish or reorder a job. The user can reorder anything.

`<lockfile path>` (git-ignored) holds JSON: owner, job, pid (optional), started, expected end.
- If the resource is idle and the lock is absent, write the lock, run, delete the lock.
- A lock with a pid expires when that process exits. A lock without a pid holds until its owner
  deletes it.
- Never delete someone else's lock. Ask.

Run long jobs detached, writing to a log file, and watch the log. Don't poll with sleeps.
```

---

## Module: generated artefacts policy

Include when the project produces things that are expensive to recreate: datasets, trained
models, rendered frames, compiled assets, large builds.

```markdown
## Generated artefacts are append-only

Never delete or regenerate existing <artefacts> to fix bad samples. Fix the generator, record the
bad items in `<exclude list or audit tool>`, and generate new ones under new identifiers.

Full regeneration is reserved for convention bugs that invalidate everything, and only with the
user's approval, recorded as a DEC.

Artefacts are not committed. `<paths>` are git-ignored. What is committed is the config that
produced them (`<config path>`, versioned) and the manifest that lists them.

A change to generator config changes the artefacts, so it needs a DEC and a bump of the config
`version`.
```

---

## Module: live status surface

Include when the user follows progress somewhere other than the chat: a dev server viewport, a
dashboard, a training monitor, a channel.

```markdown
## The user is watching <surface>

<How to reach it, how it is started, what it reads.>

When your focus moves to a different part of the work, update `<status file>` so the surface
follows. Keep its `label` short and current: it is the user's caption for what you are doing.

At gates, the evidence goes on the surface or in a review page, not in chat.
```

---

## Module: silent-failure invariants

Include always, unless the user says there are none. Coordinate frames, units, encodings, index
bases, timezones, byte order, colour spaces: things that produce wrong output and no error.

```markdown
## Conventions that fail silently

These are fixed by <REQ IDs>. Change them only by DEC.

- <invariant 1, stated precisely, e.g. "world Z up, OpenCV camera convention, row-major cam_to_world, pixel centres at +0.5">
- <invariant 2>

A violation here trains to mush, renders upside down or loses a day, and raises no error. Before
any expensive stage, run `<the check>` (<REQ ID>). Don't start the expensive stage until it passes.
```

---

## Choosing

| Project | Modules |
| --- | --- |
| Solo web app | invariants only (timezones, encodings) |
| Two agents, one machine, ML training | branching, shared resource, generated artefacts, invariants, probably status surface |
| Team with design and 3D, no heavy compute | branching, generated artefacts (exports), invariants |
| Data pipeline with a rate-limited upstream API | shared resource (the API quota), generated artefacts, invariants |
