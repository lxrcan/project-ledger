# Roles and transitions

Ownership sits on state transitions, not on files. This keeps the ledger open to discovery, since
anyone can file an item, while keeping control over the moves that cost money or change scope.

The roles table lives in `docs/ledger.yaml`. Names map to roles, including agents under the
author name they commit with. The lint reads the `*_by` fields on items and checks them against
the table. A transition recorded by the wrong role fails `ledger.py lint` rather than being
forbidden only by convention.

## The four default roles

Projects can rename or add roles. These four cover most software projects with a design or asset
component. If a project has only one or two people, map one name to several roles and say so in the
config comment. Doing that explicitly is fine. Doing it silently is how a PM ends up accepting
their own change requests without noticing.

| Role | Accountable for |
| --- | --- |
| **pm** | Scope. What is in, what is out, what ships when |
| **lead** | Technical delivery. Triage, architecture, merges, gate evidence |
| **designer** | Intent. How it should look and behave, and whether what was built matches |
| **implementer** | Building it. One or more people or agents, usually scoped to an area |

## Transition matrix

| Item | Anyone may | pm | lead | designer | implementer |
| --- | --- | --- | --- | --- | --- |
| REQ | propose | accept, reject, defer, assign release | mark implemented | mark implemented (design items) | mark implemented (own area) |
| REQ verified | | by whoever did not implement it, any role | | | |
| ISS | file | | triage: severity, release, owner. Close fixed / wont-fix | close design-intent | mark fixed (own area) |
| CR | raise | accept or reject, only with a DEC | assess feasibility and cost | assess design impact | assess impact on own area |
| DEC | | scope and process | technical | design | within own area's conventions |
| REL | | declares content, approves notes, marks released | cuts tag, confirms gate evidence, marks frozen | signs off design acceptance | signs off own-area acceptance |

Two rules stay fixed across projects:

1. **Verification is done by someone other than the implementer.** This includes agents. An agent
   that built a feature and then ran its own test has produced evidence, not verification. Someone
   else looks at the evidence and sets `verified_by`.
2. **Acceptance of scope changes belongs to one role.** CR acceptance and REQ acceptance are the
   PM's. In a small team the PM may also be the lead or the user, but the config says so.

## How the lint enforces it

For each item the lint checks the recorded actor against the roles table:

| Field | Required role |
| --- | --- |
| REQ `accepted_by` (status beyond proposed) | pm |
| REQ `verified_by` | any role, and not equal to `implemented_by` |
| ISS `triaged_by` | lead |
| ISS `closed_by` with `design-intent` | designer |
| CR `accepted_by` | pm, and a `resolved-by DEC` link must exist |
| DEC `decided_by` | present (any role, or `user`) |
| REL `released_by` | lead or pm |

Unknown names fail the lint. Add people and agents to the roles table before they act.

## Agents

An agent acts under a named role, usually implementer or lead, and its commits carry that name.
It may:

- propose REQs, file ISSs, raise CRs
- implement and mark `implemented`
- write impact assessments on CRs for its area
- append DECs within its role's domain
- cut a release when it holds the lead role

It may not accept CRs, make scope decisions, verify its own work or edit a requirement's text
outside a DEC commit. Its final message lists every proposed item so the PM can accept or reject
them. Proposed items that nobody accepts are the usual way a ledger rots, so agents should name
them every time, not only when asked.

## A worked example: four roles, one change

1. The 3D implementer finds that the placeholder car cannot satisfy a lighting requirement, and
   files `ISS-0117 violates REQ-0042`, severity major.
2. The lead triages it. It isn't a bug; the requirement assumed something impossible. The lead
   raises `CR-0009 changes REQ-0042`, sets ISS-0117 to `wont-fix` with `spawned CR-0009`, and
   assigns the designer for impact.
3. The designer writes the impact note on CR-0009 with a proposed rewording, and moves it to
   `assessed`.
4. The PM accepts with `DEC-0031 resolves CR-0009`. The DEC commit edits REQ-0042's text, bumps
   its `version` to 2, sets CR-0009 to `accepted` then `applied`, and REQ-0042 back to
   `accepted` because the implemented version no longer matches the requirement.
5. The implementer builds it, cites REQ-0042 in the commit, sets `implemented`.
6. The lead or designer runs the verification, sets `verified_by`, and adds a `verified-by` link
   to the evidence. The PM assigns it to the release.

Every step is one commit touching one or two item files. The history of the change is
`git log -- docs/items/REQ-0042.md`.
