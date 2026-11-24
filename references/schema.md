# Item schema

Every item is one file: `docs/items/<ID>.md`. YAML frontmatter, then a short body. The body is for
humans: the rationale, the impact note, the acceptance argument. The frontmatter is for the
generator and the lint.

## IDs

`<TYPE>-<nnnn>` with four digits, sequential per type: `REQ-0042`, `ISS-0117`, `CR-0009`,
`DEC-0031`. Releases use their version: `REL-1.4.0`. `ledger.py new` allocates the next number.
Never reuse a number, even for a rejected item.

Why sequential rather than area-prefixed (`OR-WLD-07`): areas split and merge as a project grows,
and renumbering breaks every commit message that cited the old ID. The `area` field gives the same
grouping in the generated views without the fragility.

## Common fields

| Field | Required | Meaning |
| --- | --- | --- |
| `id` | yes | Matches the filename |
| `type` | yes | REQ, ISS, CR, DEC, REL |
| `title` | yes | One line, imperative or declarative, under 100 characters |
| `status` | yes | From the type's lifecycle below |
| `area` | yes except REL | A key from `areas` in `ledger.yaml` |
| `owner` | yes | Who is accountable for the next move. A name from the roles table |
| `created` | yes | ISO date |
| `source` | REQ, ISS, CR | Where it came from: `brief §3`, `ISS-0117`, `found 2026-11-24 while …`, a URL |
| `release` | no | The REL it belongs to, e.g. `1.4.0` |
| `milestone` | no | A milestone label when releases are coarser than milestones |
| `links` | no | List of `<verb> <target>` strings, see below |

## Type-specific fields

**REQ**

| Field | Meaning |
| --- | --- |
| `verify` | How the requirement is checked. A test name, a measurement with threshold, a manual procedure. A REQ without this cannot reach `implemented` |
| `version` | Integer, starts at 1. Bumped only by a DEC commit that changes the requirement text |
| `accepted_by` | Name. Set when status leaves `proposed`. Must hold the PM role |
| `implemented_by` | Name. Set at `implemented` |
| `verified_by` | Name. Set at `verified`. Must differ from `implemented_by` |

Lifecycle: `proposed → accepted → implemented → verified`. Side exits: `deferred` (accepted, moved
out of the current stage), `rejected` (dropped, with a DEC saying why), `superseded` (replaced,
with a `superseded-by REQ-nnnn` link).

**ISS**

| Field | Meaning |
| --- | --- |
| `severity` | `blocker`, `major`, `minor`, `cosmetic` |
| `triaged_by` | Name. Set at `triaged`. Lead role |
| `closed_by` | Name. Set at any closing status |
| `resolution` | Free text on close: the commit, or why not |

Lifecycle: `open → triaged → in-progress → fixed → closed`. Side exits: `wont-fix`,
`design-intent` (behaviour is as designed; the designer closes it), `duplicate` (with a
`duplicate-of ISS-nnnn` link). An ISS that reveals the requirement was wrong does not close as
fixed. It spawns a CR and closes as `wont-fix` with the CR linked.

**CR**

| Field | Meaning |
| --- | --- |
| `impact` | Map of role to one-line assessment: `lead: 2 days, touches loader`, `designer: no visual change` |
| `accepted_by` | Name. PM role. Set at `accepted` or `rejected` |

Lifecycle: `raised → assessed → accepted → applied`, or `assessed → rejected`. `accepted` and
`rejected` both require a `resolved-by DEC-nnnn` link; the lint checks it. `applied` means the
target REQ has been edited and its `version` bumped, in the same commit.

**DEC**

| Field | Meaning |
| --- | --- |
| `decided_by` | Name, or `user`, or a role. Required |
| `why` | One or two sentences. Required. A decision without a reason can't be revisited |
| `affects` | List of IDs, paths or document names |

Lifecycle: `active`, `superseded` (with `superseded-by DEC-nnnn`). Never edit a DEC's text after
the commit that created it. Write a new one.

**REL**

| Field | Meaning |
| --- | --- |
| `version` | Semantic or milestone version, matches the ID and the git tag |
| `tag` | The git tag name |
| `previous` | The previous REL, so notes can be built from `previous..tag` |
| `claims` | List of REQ IDs this release claims to satisfy. The generator checks each is `verified` at freeze |
| `gate` | Optional. The gate's exit condition in one line, and `evidence:` a path to the review page |
| `released_by` | Name. Lead or PM |

Lifecycle: `planned → frozen → released`. `frozen` means `docs/releases/<version>/` exists and the
tag is created locally. `released` means pushed and published.

## Link verbs

Links are strings `"<verb> <target>"`. Targets are item IDs, or paths for evidence. The lint
checks that every item target exists.

| Verb | From → to | Meaning |
| --- | --- | --- |
| `violates` | ISS → REQ | The issue is a failure of this requirement |
| `changes` | CR → REQ | The change request proposes to alter this requirement |
| `resolved-by` | CR → DEC | The decision that accepted or rejected the CR |
| `resolves` | DEC → CR, DEC → ISS | The inverse, written on the DEC |
| `supersedes` / `superseded-by` | REQ ↔ REQ, DEC ↔ DEC | Replacement |
| `duplicate-of` | ISS → ISS | |
| `depends-on` | REQ → REQ | Verification order |
| `verified-by` | REQ → path or `path::test` | Evidence: a test, a review page, a measurement file |
| `spawned` | ISS → CR, REQ → ISS | What this item gave rise to |
| `mirror` | ISS → URL | The external tracker item this file mirrors |

Write links on the item that was created later, and let the generator show both directions. The
exception is `resolves` on a DEC, because the DEC commit is where the CR's fate is sealed.

## Example

```markdown
---
id: REQ-0017
type: REQ
title: Target cameras are sampled within the trained elevation and distance envelope
status: verified
area: data
owner: lead
created: 2026-11-23
source: brief §Data
verify: tests/test_sampler.py::test_envelope passes; probe grid in docs/reviews/m2-gate.md shows no out-of-envelope poses
version: 2
accepted_by: lorcan
implemented_by: lead-agent
verified_by: lorcan
release: 0.2.0
links:
  - verified-by tests/test_sampler.py::test_envelope
  - verified-by docs/reviews/m2-gate.md
---

The viewer's orbit limits are read from the same config, so the user can never request a pose the
model has not seen. Version 2 widened the elevation range after CR-0003 (DEC-0011).
```

## Where the files go

```
docs/
  ledger.yaml          project config: areas, roles, modules, paths
  items/               one file per item
  generated/           built by ledger.py, committed, never hand-edited
  releases/<ver>/      frozen copy of generated/ at each release, plus the review page
  reviews/             gate review pages with images (JPEG, modest width)
  PLAN.md              only if the shared-resource module is on
```
