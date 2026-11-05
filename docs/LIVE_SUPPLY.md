# Supply connectivity — 0.1.6 / L10

The `supply.lua` module distinguishes controlled campaign connectivity from a
native road route. It does not implement terrain polygons or tactical safety.
The six-sector Syria layout and content version are unchanged.

## Eligibility

- A new supply convoy requires a same-side operating depot above 25% strength,
  its owned source sector, its owned destination base and a friendly sector path.
- Breadth-first search is bounded to 32 configured sectors, uses sorted neighbor
  IDs, and selects the fewest hops. Multiple eligible depots sort by hop count,
  then source ID. Read queries do not change state or purchase anything.
- Fuel credit separately requires an operating fuel site connected to the base.
  A fuel cutoff does not remove existing fuel, ammunition or supply stock.
- An assault's staging sector must connect to its funding base. Rebuilding a
  destroyed site also requires that connection; costs and repair delays remain.
- Cargo already dispatched survives destruction of its source. Sector ownership,
  surviving vehicles and arrival conditions still apply.

## Interrupted journey

`OPEN` permits ordinary physical delivery. Losing control of a corridor sector
sets `CUT` and issues Hold. If an alternative controlled path exists, or the
original path is restored, the convoy enters `RESUME` and remains held until its
native route can be refreshed successfully from an observed surviving vehicle.

The original three route attempts, five-minute cooldown, global ten-second
throttle and three-to-six-hour journey deadline apply. A closed corridor consumes
no road attempts. Successful refresh returns it to `OPEN`; exhaustion leaves a
held convoy `BLOCKED` until timeout. This includes attempts previously spent on
ordinary road stalls. Reconnection and reload never reset the budget or deadline.
Those numbers are inherited game limits, not real-world logistics estimates.

Hold failures are isolated and retried every ten simulation seconds. Delivery
remains gated even if DCS rejects the physical Hold command; stopping the engine's
vehicles cannot be guaranteed from this environment. Route retries do not create
new groups, reposition vehicles, charge again or refund spent resources.

Arriving vehicles deliver once, with prior deliveries retained across cuts,
losses and reload. A held convoy may still be destroyed as an existing dynamic
objective. Timeout/destination loss does not award destruction credit. Expiry
retires the remaining cargo, retaining any earlier credits. Assaults already
dispatched use the existing capture and waiting rules instead of this Hold policy.

## Checkpoints and presentation

Optional `shipment.corridor` records the source-to-destination sector sequence,
state and explanation. Checkpoint validation rejects unknown/repeated/nonadjacent
sectors, wrong endpoints, invalid state and invalid reason. Ownership may change
before the next observation; that is reconciled on startup/update, not rejected
as save corruption. Empty paths are accepted only for a closed legacy journey
whose configured graph has no possible connection.

Older saves derive a corridor on restoration. CUT/RESUME/BLOCKED survivors spawn
held before the first observation. Their delivery ledger, IDs, positions and
navigation limits survive. Hold retry bookkeeping is transient and cleaned when
a shipment retires. No save schema/content-version reset is required.

Resources and F10 Campaign status count connected sources and held convoys.
Front plans explain isolated staging; dynamic objectives show their supply state.
The blocked-sector explanation uses one deterministic shortest graph path; it
does not claim those sectors are the only possible way to restore connectivity.

## Validation boundary

`tests/live/test_supply.py` exercises real Lua 5.1 modules against fake DCS APIs:
eligibility, alternative paths, Hold failure, cooldown, partial cargo, losses,
reload, legacy saves, timeout, objective completion, isolated reconstruction,
corrupt saves and native/F10 read-only reports. Existing navigation tests cover
global retry throttling and ordinary road recovery.

No engine driving, path geofencing, bridge clearance, combat AI, native rendering
or FPS was measured. The default depots are local to their base sectors; red fuel
from Marj and assault staging already cross sector connections. Longer depot
corridors in the tests are explicit fixtures, not a new shipped Syria layout.
