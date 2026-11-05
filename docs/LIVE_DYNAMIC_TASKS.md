# Dynamic ground-force objectives — 0.1.5 / L09

This release follows H01 with debugging, then dynamic target discovery. It keeps
one live mission, native Operations/F10 and the existing shipment inventory.
There is no additional force simulation or browser UI.

## Reproduced 0.1.4 defects

1. A thrown `outText` during objective completion escaped the death-event handler
   and stopped the campaign after the objective had been credited. Completion
   notifications are now best effort, with completion committed once beforehand.
2. `view.selected(view, explicit_missing_id)` returned the first unrelated task.
   Only an omitted ID may select the default; an explicit missing ID stays empty.
3. A save immediately after convoy creation could contain no observed positions.
   A failed road query on restore was then treated as a failed new dispatch,
   aborting startup. Spawn now records available initial unit observations, and
   the restore path explicitly permits holding an existing force without a road.

All three regressions failed against the previous code before correction. A
fourth scenario verifies an old empty-position snapshot after depot destruction.
Such an old snapshot has no position to recover: it uses the saved source area.
New checkpoints capture initial observations before the next scheduled update.

## Shared identity and presentation

`targets.lua` resolves static target definitions and dynamic shipment records.
Dynamic definitions are derived; they are never another saved unit inventory.
Shipment IDs are stable through movement, capture, reload and losses. Save
validation forbids shipment/static-target ID collisions and missing references.

Supply convoys produce STRIKE cards; assault columns and occupying garrisons
produce CAS cards. Only active hostile survivors are offered. All remaining
vehicles must be destroyed, including the last supply truck; the fixed-site
25% STRIKE threshold does not apply. Existing static objective rules remain.
Priorities of 75 for assaults and 45 for supply are presentation choices for this
scenario, not tactical doctrine. Existing front/assignment ranking still applies.

The schematic filters by destination sector. It does not locate a moving vehicle
in the sector it physically crosses. Briefing/status/F10 coordinates come from
the same observed surviving unit. Existing marks follow movement, loss of the
reference unit and transition to a garrison. Missing observations are unavailable.
F10 labels update when an assault becomes a garrison; UI selection retains its ID.

## Objective outcomes and support

An optional shipment `outcome` distinguishes DESTROYED from DELIVERED,
TIMED_OUT and DESTINATION_LOST. The existing `status` still controls lifecycle
and inventory. For example, a partially delivered convoy whose remaining trucks
are destroyed can retain status DELIVERED and outcome DESTROYED. Its delivered
ledger remains credited; the objective concerns only its remaining vehicles.

An assault becoming a garrison retains its assignment. Destruction completes
once; delivery, withdrawal or loss of the destination clears the assignment
without completion. Duplicate events cannot add credit. Removed forces are
never replaced by another target in the selection or assignment.

Strike route construction binds AttackGroup to the actual shipment group.
Hold/Push retains the ID; Push uses a current observed approach reference.
When a target ends, bound support is instructed to return to base. A failed
controller call leaves the original reference intact and retries after ten
seconds while that flight remains active. Referenced terminal force records
are retained until release; successful return clears the target reference.
This guarantees data/task identity, not real DCS attack effectiveness.

SEAD against dynamic forces is explicitly unavailable; the player selects a SAM
separately. Fixed-site non-SAM SEAD behavior remains documented in the user guide.
AWACS/tanker requests have no target binding. The autonomous air director still
selects its existing fixed-site priorities; L09 does not change its doctrine.

## Save compatibility and validation

Schema 1 / syria-1 remains readable from releases 0.1.0–0.1.4. Legacy outcome
fields may be absent; the code does not infer successful destruction from a
retired record. New dynamic assignments and flight references are checked against
the candidate saved shipments, including their side and role where applicable.
Existing interrupted-aircraft maintenance behavior is preserved. Downgrading a
save with a dynamic assignment to 0.1.4 is not supported.

Tests run actual Lua modules with API/widget doubles and inspect controller task
references, persistence, inventory, native callbacks and cleanup. They do not
model driving, weapons, combat, terrain, skin/font rendering or FPS. See
LIVE_VALIDATION.md for the final release results and unobserved DCS boundaries.
