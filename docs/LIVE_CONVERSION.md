# SQE Live — Syria conversion

Work begins 2026-10-29, from upstream SQE 0.41.135, commit
807643b33fa88f19329177c6c420a5f8feb942e8. This is a separate development branch.

The user authorized the full conversion and selected Syria where possible.
One development task is active at a time; no delegated agents.

## Target behavior

One mission per session, multiple player sorties, a continuously advancing
campaign, an in-game clickable operations window, F10 commands through the same
command service, autonomous opposing forces, bounded unit counts, and persistent
losses and resources. No Python process or network service while flying.

## Sequential work

1. Live state, commands and save contracts — IMPLEMENTED AND AUTOMATED TESTS PASS.
2. Syria content and base-mission export — IMPLEMENTED; MIZ STRUCTURALLY VERIFIED.
3. DCS unit lifecycle, tasking and continuous campaign — IMPLEMENTED; CONTRACT TESTS PASS.
4. Native operations window and installation — IMPLEMENTED; CALLBACK/FIXTURE TESTS PASS.
5. Regression, simulation and packaging — COMPLETE; INSTALL/SOURCE ZIP VERIFIED.
6. Automatic diagnostics and failure isolation (0.1.1) — IMPLEMENTED; FAILURE/RECOVERY TESTS PASS.
7. Actionable sector objectives and support availability (0.1.2) — IMPLEMENTED; CONTRACT/RELOAD/UI TESTS PASS.
8. Interactive native front map (0.1.3) — IMPLEMENTED; GEOMETRY/SELECTION/CALLBACK TESTS PASS.
9. Observed coordinates and convoy resilience (0.1.4 / H01) — IMPLEMENTED; POSITION/RETRY/DELIVERY/RELOAD TESTS PASS.
10. Debugging and dynamic ground-force task cards (0.1.5 / L09) — IMPLEMENTED; LIFECYCLE/RELOAD/AI-REFERENCE/NATIVE-CALLBACK TESTS PASS.
11. Controlled supply connectivity (0.1.6 / L10) — IMPLEMENTED; CUT/RESUME/CARGO/RELOAD/VIEW TESTS PASS.
12. Solo reserves and recovery (0.1.7 / L11) — IMPLEMENTED; PAIRED ACCOUNTING/FAILURE/RELOAD TESTS PASS.
13. Israel blue rear area (0.1.8 / G01) — IMPLEMENTED; DEFAULT-PROFILE/OWNERSHIP/MULTI-BASE/LEGACY TESTS PASS.

Actual DCS acceptance is outstanding for the complete release. See
LIVE_VALIDATION.md for the test boundary and LIVE_USER_GUIDE.md for limitations.
Real-game acceptance is deferred and does not block further implementation.
The user is not assigned a manual test task. Continue one development task at a
time, with automated checks, and keep unobserved DCS behavior explicitly pending.

## Continuation after 0.1.11

### Next task — L12: bounded long-session and product checks

Status: READY. Measure update cost, save size, registry/queue growth and repeated
installation/recovery in the contract environment. Address concrete failures,
retain actual DCS flight/rendering/FPS/Windows acceptance as pending.

### Completed task — G02: Israel-profile solo support attrition accounting

Manual blue combat support searches funded pairs across all friendly compatible
bases, then permits one survivor at full sortie cost. Automatic/red rules and
finite stock remain intact. Ten tests and eight paired regional workloads cover
attrition, capture, corridor isolation and exhaustion. See
LIVE_ISRAEL_BALANCE.md; the historical legacy report remains separate.

### Completed task — I02: native window, startup and storage contract audit

Observed pre-load/ended sessions are excluded from the new UI connection;
state cleanup precedes fallible widget updates. Callbacks contain exceptions
and return no values. Nine new cases cover lifecycle failures and execution of
the installed bridge across API sanitization. See LIVE_UI_STORAGE_AUDIT.md for
sources and limitations. Actual DCS rendering/startup/Windows acceptance remains
pending; this does not declare the integration tested in game.

### Completed task — I01: aircraft/task/event integration pass

Representative flight records and native task structures were compared against
ED documentation and supplied mission data. Seven new regressions cover runway
and legacy events, conservative touchdown fallback and stale landing flags.
Two failures were reproduced against 0.1.8 and fixed. See
LIVE_INTEGRATION_AUDIT.md. The remaining UI/startup/storage scope is explicit I02,
not claimed complete. No actual DCS flight or rendering acceptance is implied.

### Completed task — G01: Israel blue starting footprint

User priority change after L11: Israel is the blue rear area. Implemented the
fifteen named Israeli airfields available in the pinned Syria data, eleven
sectors, five support bases and regional logistics. Same-side advances share a
destination gate across bases. Old campaigns retain a separate Legacy mission
and unchanged checkpoint identity. The supplied Foothold archive received a
selective static inspection; its code/assets are not distributed. See
LIVE_ISRAEL.md and LIVE_FOOTHOLD_REFERENCE.md.

### Following task — L12: load checks and product completion

Status: READY. Inspect measured Lua/update/registry costs, packaging and startup
failure modes; finish the install/release workflow and record the game-validation
boundary. Native DCS flight, driving, rendering and FPS require a DCS environment.
Do not assign the user a manual test as a prerequisite for further offline work.

### Completed task — L11: first solo accounting balance pass

Status: implementation and automated accounting checks complete; actual play
balance remains provisional. Automatic blue dispatch preserves requested-support
and site-repair resources. Disabled partial depots/fuel sites can recover after
four hours, and depot reconstruction takes priority. Last advances may spend a
released reserve; terminal supply exhaustion records defeat instead of an active
softlock. Seven paired six-hour fixtures compare 0.1.6 and 0.1.7. See
LIVE_BALANCE.md and LIVE_BALANCE_RESULTS.json for results and limitations. C2
still has no dispatch penalty; that is not represented as an implemented effect.

### Completed task — L10: supply connectivity and interrupted routes

Status: DONE for implementation and automated checks; real DCS acceptance pending.
Controlled sector paths gate depots, fuel credit, assault staging and paid repair.
Interrupted supply convoys hold, retain all prior cargo/losses and resume only
after a successful bounded road refresh. Alternative graph paths and reload keep
the existing force identity, retry budget and journey deadline. UI/F10 expose
isolation and its cause. Existing checkpoints derive the new corridor when loaded.
See LIVE_SUPPLY.md for exact rules and the distinction from native road routing.

### Completed task — H01: observed coordinates and convoy resilience

Status: implementation complete; release checks recorded in LIVE_VALIDATION.md.
The user approved fixing the runtime risks identified in the 0.1.3 review before
adding L09. Completed sequentially: observed surviving-unit coordinates in
briefings, F10 marks and attack approach points; then bounded road-route
validation, stalled-column retries and physical per-vehicle supply delivery.
Checkpoint compatibility, finite force accounting and physical capture
requirements remain. No new task categories or UI rewrite. See LIVE_RESILIENCE.md.
Actual DCS terrain/AI/rendering acceptance remains pending; retries do not prove
that the engine will navigate every road or obstacle.

### Completed task — L08: interactive native front map

Status: DONE for implementation and automated checks; real DCS acceptance pending.
Added a bounded sector schematic to the existing
native Operations window, clickable sector filtering and target selection,
control colours and explicit stale-data handling. Links describe sector
adjacency, not roads, terrain clearance or tactical safety. Shared authoritative
commands remain unchanged; map clicks only change local selection.

Scope: pure map layout/selection module, native widget adapter, existing
Operations data/UI integration, packaging, tests and documentation. Validated
geometry, node/edge identity, captures, empty sectors, disappearing targets,
stale/session changes, button callbacks and F10 correspondence. Actual dxgui
rendering remains unverified until DCS is available. No new campaign mechanics.
The complete suite passes 68 tests, plus the 95-section upstream smoke suite.
See LIVE_MAP.md for the map's boundaries and native API references.

### Completed task — L09: dynamic ground-force task cards

Status: DONE for implementation and automated checks; real DCS acceptance pending.
The read-only targets module discovers enemy supply convoys, assault columns and
occupying garrisons using existing shipment IDs and inventory. Map, F10, saves and
strike support use the same lookup. Assault-to-garrison transitions retain the
assignment; destruction completes once, while delivery/timeout does not award
destruction credit. Retired targets trigger a bounded-frequency return command
for attached support. See LIVE_DYNAMIC_TASKS.md for the contracts and debug fixes.

Exit checks: spawned hostile forces appear with current coordinates; enemy
garrisons blocking recapture are taskable; full destruction completes once;
arrival transitions and save/reload preserve identity and surviving units;
friendly/destroyed forces cannot be accepted; map/F10/AI support share the same
target lookup. Supply-route connectivity was subsequently completed in L10; the first solo accounting balance pass was completed in L11.

### Completed task — L07: actionable sector objectives

Status: DONE for implementation and automated checks; real DCS acceptance pending.
Delivered a live front plan, meaningful target
consequences and support availability in Operations and F10. Armour objectives
must account for the last defender required by the actual capture rule. Existing
checkpoints remain compatible. Scope: core task/launch queries, shared defender
counting, a pure operations read model, runtime/view/hook integration, tests and
release documentation. No new terrain, IADS, flight doctrine or interactive map.

Exit checks: partial armour destruction cannot hide a capture blocker; sector
steps follow losses, dispatched columns and observed capture; displayed support
availability uses the same checks as dispatch; reads never spend resources;
reload preserves the plan; native callbacks and F10 expose the same data.

The interactive map uses existing sector IDs, positions, neighbours, objectives
and authoritative commands. Browsing does not assign a task or spend resources.
No external browser is needed in flight. Version 0.1.5 adds task cards for
garrisons/convoys. Version 0.1.6 adds controlled supply connectivity and interruption handling.
Performance tuning follows measurements when a DCS
environment becomes available. Do not mark the full release flight-tested until
that evidence exists; it is a release-quality boundary, not a development gate.

0.1.1 records startup, state/inventory constraints, registered units, checkpoint
readback, UI heartbeat and observed sortie/objective events. Status-file, queue,
acknowledgement, F10 and diagnostic-file failures are isolated from world updates.
Invalid authoritative state stops updates before replacing the last checkpoint.
Partial force initialization is rolled back. Reports remain local and can be
collected with one script; no external service or automatic upload is involved.

0.1.2 adds Front plan / Resources / Support tabs and local target recommendation,
with matching F10 reports. Quotes and launch share one eligibility function. CAS
now requires every defender in its target group; a surviving SAM radar remains
taskable even below the general strike threshold. Schema 1 / syria-1 checkpoints
remain compatible. The read model never spends resources or alters saved state.

0.1.3 adds Map as the default Operations tab. Sector clicks filter task rows;
selection, pagination and detail remain local to the UI. Existing commands still
perform all mutations. Blue/red control, front links and base markers update
from the live snapshot. Stale maps turn grey and reject actions. The diagram is
a sector schematic, not a geographic terrain map or proof of traversable roads.

## Design decisions

- Retain upstream aircraft data and loadout selection for mission authoring.
- Port runtime campaign decisions to Lua. Do not run the upstream end-of-day
  simulator against entities represented in the running mission.
- A single Lua campaign core owns state. GUI and F10 issue commands to it.
- A narrowly scoped storage bridge retains filesystem access only beneath
  Saved Games/DCS/SQE-Live; DCS io/lfs sanitization stays enabled.
- Reconstruct campaign state between sessions, not cockpit switch states or
  missiles in flight. Interrupted AI sorties recover surviving airframes;
  destroyed aircraft remain lost. Supplies in transit resume as shipments.
- First content: fictional blue/red conflict on Syria; F-16C player aircraft.
- Validate terrain placement at runtime with land height/surface checks.
- Keep all inputs bounded and commands idempotent; campaign and session IDs
  prevent delayed commands from crossing mission loads.
- Six sectors, seventeen target groups, finite AI inventories, physical supply
  and assault columns, base ownership, SEAD/DEAD transitions and repair.
- Aircraft enter airborne; player resupply uses normal DCS ground crew, separate
  from the AI resource ledger. No exact cockpit or airborne save/resume.
- Native dxgui Operations and F10 use the same authority. No website or external
  browser is required in flight.

## Verification boundary

DCS is not installed here. Automated Lua/Python tests and generated .miz
inspection are possible. Real rendering, cockpit interaction, AI flight behavior,
terrain/building clearance and performance require a Windows DCS flight test.
The release must not claim that those tests were performed.
