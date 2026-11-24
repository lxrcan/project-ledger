# Workflows

Each flow is a short sequence of commits. The commit boundary is the unit of discipline: an item
moves in the commit that does the work it records.

## Discovery during work

You are implementing REQ-0017 and find that the export tool silently truncates filenames over 64
characters. That is a must-not the project didn't know about.

1. `python tools/ledger.py new REQ "Export filenames stay under 64 characters" --area export --source "found 2026-11-24 while implementing REQ-0017; tool truncates silently"`
2. Set `verify` to something checkable, even if crude: "audit script reports zero truncated names".
3. Leave status `proposed`. Set `owner` to the PM.
4. Commit it with the work: `m2: exporter (REQ-0017); found REQ-0052 proposed`.
5. Name it in your final message under "needs a decision".

If the discovery is urgent and blocks you, implement the fix anyway and mark the REQ `proposed`
with `implemented_by` set. The PM accepting it later moves it to `implemented` in one step. Don't
wait for acceptance to unblock yourself; do wait for acceptance before calling it part of the
spec.

## Bug

A plain defect against an existing requirement.

1. `ledger.py new ISS "Panel freezes after 3 minutes of orbiting" --area viewer --source "found 2026-11-24 during gate drive"` with `violates REQ-0023`, severity.
2. Lead triages: `triaged_by`, release, owner. Status `triaged`.
3. Implementer fixes, cites `ISS-0118` in the commit, sets `fixed` with `resolution: <commit>`.
4. Lead or verifier confirms, sets `closed`, `closed_by`.

If a REQ has three or more ISSs against it, that is a sign the requirement's `verify` field is too
weak. Raise a CR to strengthen it rather than fixing a fourth bug.

## Issue that turns out to be a wrong requirement

1. ISS filed as above.
2. Lead triages and realises the requirement can't be met as written. Raise
   `CR-nnnn changes REQ-xxxx`, link `spawned CR-nnnn` on the ISS, set ISS `wont-fix` with the
   resolution "requirement under change, see CR-nnnn".
3. Roles whose area is touched write one line each under `impact` on the CR. Status `assessed`.
4. PM decides. Create `DEC-nnnn` with `decided_by`, `why`, `resolves CR-nnnn`, `affects: [REQ-xxxx]`.
   In the same commit: CR gets `resolved-by DEC-nnnn`, status `accepted` (or `rejected`, and stop
   here). Edit the REQ's text, bump `version`, set its status back to `accepted` if it had been
   implemented under the old wording. CR to `applied`.
5. Implementation and verification as for any REQ.

The reason the REQ edit lives in the DEC commit and nowhere else: `git log -- docs/items/REQ-xxxx.md`
then shows exactly one commit per version, each pointing at the decision that caused it.

## Decision without a change request

Interpretations, conventions, process, ownership. Anything a future reader might ask "why is it
like this?" about.

1. `ledger.py new DEC "Driving side stays left" --area world` with `decided_by`, `why`, `affects`.
2. Commit with the work it governs.

Don't batch decisions into a weekly write-up. By then the reason has been forgotten or
rationalised.

## Release

1. Check `docs/generated/OPEN.md`. Every REQ in `claims` must be `verified`. If one isn't, either
   verify it now or move it to the next release with a one-line DEC.
2. Gate evidence: write `docs/reviews/<version>.md` from `assets/templates/review.md`. Images as
   JPEG, modest width. Stop and show the user. A gate passed in chat with no rendered evidence
   has not been passed.
3. `python tools/ledger.py release <version>` creates or updates `REL-<version>.md`, drafts notes
   from commits since `previous`, copies `docs/generated/` to `docs/releases/<version>/`, and
   sets the REL to `frozen`. Review the notes; the PM approves them.
4. Commit, tag locally, `ledger.py lint`, then push the branch and the tag. Then publish
   (GitHub release or equivalent) with the notes, linking the review page. Set REL `released`,
   `released_by`. Commit.

Order matters: freeze, tag, lint, push. A tag pushed before the lint is a tag you cannot fix
without force-pushing, and force-pushing a tag is on the never list.

## Gate (milestone stop point)

Same as a release but the version may be a milestone label, `m2-gate`, and there may be no
publishing step. The stop and show is not optional. Gates exist so the user can redirect before
the expensive next stage; a gate reported after the next stage has started is theatre.

## Mirroring an external tracker

When people file through GitHub Issues, Jira or similar, keep the repo as the single source of
truth and treat the tracker as an inbox and a comment thread.

- An inbound tracker issue gets an `ISS` file with `links: [mirror <url>]`. The agent or lead
  creates it at triage.
- State lives in the file. The tracker label is set from the file by a sync script or by hand,
  never the other way round.
- Comments stay on the tracker. The ISS body carries only the triage summary and resolution.
- Closing the file closes the tracker issue with a comment naming the commit and release.

Two-way sync is tempting and is how two sources of truth arise. If the team insists on managing
state in the tracker, drop the ISS type from the ledger entirely and link REQs to tracker URLs via
`verified-by` and `source`. Half-mirrored is the worst option.

## Agents working in parallel

Each agent has its own branch and worktree (see `modules.md`, multi-agent branching). Items are
files, so two agents adding items on different branches will both allocate the next ID and
collide at merge. Avoid this by:

- allocating IDs on the lead's branch only, with the lead creating the item and the agent filling it, or
- giving each agent an ID block in `ledger.yaml` (`id_blocks: {builder: [REQ-0200, REQ-0299]}`), which `ledger.py new --as builder` honours.

The second is simpler in practice. Collisions on the generated views are expected and harmless:
rebuild after merge.
