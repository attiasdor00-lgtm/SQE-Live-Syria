# Runtime resilience — 0.1.4 / H01

The 0.1.3 review reproduced a terrain-displaced force more than 900 metres from
its nominal briefing/mark, and an assault column blocked by one remote survivor.
H01 was prioritized ahead of L09. It improves observed positions and convoy
failure handling; it does not certify actual DCS navigation or rendering.

## Observed target reference

`dcs_adapter.target_point` selects an existing, living unit from the registered
target group, preferring a surviving radar. It never substitutes the nominal
site centre or the saved position of a dead/unobserved unit. Coordinates,
elevation, status rows, F10 briefings/marks and strike approach geometry use this
reference. Missing observations yield an unavailable position and reject a new
strike/SEAD launch before inventory changes. Area patrols may retain their sector.

Explicit Mark requests update immediately. Existing marks update after a change
of reference unit or movement of at least ten metres; full destruction clears
the mark. Marker API errors are isolated and retried on subsequent observations.
No automatic cockpit waypoint upload is added. The reference is a vehicle, not
a guarantee that a single coordinate covers the entire dispersed group.

## Road planning and progress

The pure `ground.lua` module validates and bounds road paths and tracks progress.
The DCS adapter performs `land.findPathOnRoads("roads", x, y, tx, ty)` queries.
The API signature and vec2 path iteration were checked in the primary
[MIST source](https://github.com/mrSkortch/MissionScriptingTools/blob/master/mist.lua).
No MIST code or runtime dependency is included.

Paths have at most 20,000 input points and 16 sampled road waypoints, plus up to
two off-road connectors. Consecutive coincident points are collapsed. The
reported road endpoints must be within 2,500 metres of origin/destination.
Routes over 300 km or extreme detours are rejected. Validation bounds data and
connectors, not collision geometry, bridge usability, traffic or tactical safety.
Actual DCS path-query cost is unmeasured. Queries occur on dispatch/restore and
bounded retries, not on every position observation.

New dispatch fails without charging stock when no acceptable road path is
reported. A supply convoy's new origin uses the observed depot reference.
Restored survivors keep their IDs and positions. If their route query fails,
they spawn held and retain a retry opportunity instead of aborting campaign
initialization. Stationary garrisons do not require a road query.

Every surviving vehicle outside the 1,200-metre arrival area has a progress
sample. Fifty metres of displacement refreshes that sample. Five simulation
minutes without progress triggers a route refresh from the current group lead.
There are at most three attempts per journey, at least five minutes between
attempts, and at least ten seconds between retries across the campaign. A
controller/query error is logged without stopping world updates. Retry counts,
samples and deadlines persist; movement after exhausted retries can still recover.
This is a bounded retry, not a guarantee of an alternative unobstructed road.

The journey deadline is `started + clamp(route_length/5 + 1800, 10800, 21600)`.
An assault already inside the arrival area and waiting for defenders does not
expire as a failed journey. Other overdue survivors are retired, as in the
previous abstraction, with an explicit outcome in the log. Front plan and
Resources expose delayed columns/convoys. No retry teleports or respawns a force.

## Partial supply and capture

Each supply vehicle physically observed inside the arrival area contributes
five of the convoy's maximum twenty resource points, subject to the existing
stock cap and operating-fuel-source rule. Its delivery is recorded before its
world unit is retired. Delivered flags and live flags cannot overlap. Repeated
observations, duplicate death events and reload cannot credit it twice.
Undelivered survivors retain their original indices when restored. A final
loss/timeout preserves prior deliveries; `DELIVERED` can therefore mean partial
delivery, with the exact count in the delivery ledger/log.

Assault capture still requires every surviving column vehicle to arrive and
all defending armour/garrisons to be eliminated. This avoids crediting remote
vehicles as an occupying force. Retries mitigate straggler stalls; they cannot
guarantee elimination of that DCS AI failure mode. Partial assault occupation
would require a separate representation of the split force.

## Persistence and verification

Schema 1 / syria-1 remains compatible with 0.1.0–0.1.3 checkpoints. Navigation
and delivery fields are optional on legacy saves and validated when present.
No old save is rewritten merely to inspect it. New saves retain unit budgets,
identity, deliveries and bounded retry counters.

The added Lua 5.1 scenarios cover forced displacement, radar loss, missing
observations, marker failure, reload, road-query failure, bounded paths,
stationary versus moving vehicles, retry throttling, partial delivery,
corruption, held restore and capture/deadline behavior. API doubles provide
road geometry and movement; they do not implement DCS terrain or driving AI.
The full release check results are in LIVE_VALIDATION.md.
