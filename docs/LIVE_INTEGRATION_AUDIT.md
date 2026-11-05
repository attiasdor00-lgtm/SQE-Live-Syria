# I01 — aircraft, tasks and world-event audit (0.1.9)

Static review dated 2026-11-05. This is not a DCS flight test.

## Evidence inspected

The supplied Foothold mission was parsed as Lua data, without executing its
scripts or bundled executable. Package/mission hashes and provenance are in
[LIVE_FOOTHOLD_REFERENCE.md](LIVE_FOOTHOLD_REFERENCE.md). Representative F-16
records use country 2, type F-16C_50, CAP group task, MHz radio frequency,
BARO waypoints, explicit speed/ETA locks and a nested route/task structure.
The supplied mission has Client parking starts; SQE Live has one Player parking
start and dynamically spawned airborne AI. Parking-only properties are removed
from airborne AI records. Different starts need different fields.

Reviewed SQE Live's generated player record, copied aircraft/payload templates,
dynamic group creation, Mission route points, task wrappers, attack/escort/orbit
parameters, return route and event-driven inventory recovery. Native group/route
patterns also appear in the supplied ZoneCommander. The supplied MOOSE build
explicitly handles both runway and legacy takeoff/landing events. MOOSE helpers
are not native DCS APIs and are not dependencies of our implementation.

Primary API references:

- [ED controller/task API](https://www.digitalcombatsimulator.com/en/support/faq/1267/):
  Mission route, AttackGroup groupId/weapon/expend/attack/altitude/direction
  parameters, Orbit pattern/point/speed/altitude, ControlledTask stop condition,
  AWACS and Tanker enroute tasks. The adapter's corresponding structures were
  compared; matching structure cannot establish AI execution or weapon effects.
- [ED singleton API](https://www.digitalcombatsimulator.com/en/support/faq/1257/):
  coalition group creation and task enums.
- [MOOSE DCS declarations](https://github.com/FlightControl-Master/MOOSE/blob/master-ng/Moose%20Development/Moose/DCS.lua):
  newer runway event names. Runtime constants are used conditionally, without
  assuming numeric IDs or requiring these constants in older environments.
- [Scratchpad hook implementation](https://github.com/rkusa/dcs-scratchpad/blob/main/Scripts/Hooks/scratchpad-hook.lua):
  a narrow cross-check of DialogLoader, Panel/Button constructors, bounds/skin
  calls and mission callbacks. It supplies examples, not the native GUI ABI.

## Concrete failures reproduced and fixed

Two new regression cases failed against the 0.1.8 adapter before the fix:
runway-only player takeoff was not registered, and a wingman who landed then
took off could retain a landing flag and be recovered when the second member
landed. Both pass with the corrected adapter.

The adapter now accepts both event families and deduplicates sortie/landing
counts. Takeoff clears landing/contact records. A runway touch alone creates a
transient observation candidate; it does not return inventory or retire a group.
Fallback confirmation requires inAir() false, finite velocity, horizontal speed
at most 5 m/s and vertical speed at most 2 m/s for fifteen continuous seconds.
These thresholds are conservative project policy, not an ED guarantee. A full
legacy LAND event can still confirm immediately when physically grounded.

AI must be near its assigned, still-friendly base (the existing 6 km envelope).
An event place, when supplied, must match its airport ID. Touch without a place
requires runway surface evidence before waiting; taxiway rollout is then allowed.
At recovery every surviving member is checked again for physical ground/base
presence. Wrong/captured bases, airborne survivors, touch-and-go, unknown or NaN
velocity cannot manufacture aircraft. Death/retirement removes pending contacts.
Contact dwell is transient and is never restored from campaign checkpoints.

Seven added contract tests cover runway-only events, duplicate legacy events,
rolling versus settled AI, touch-and-go, stale landing flags, missing velocity/
NaN, absent place/runway evidence, wrong/captured fields, and legacy-only enums.
They run actual adapter code under Lua 5.1 with explicitly injected observations.
The test double provides no independent evidence about real event timing.

## Remaining work

The initial I01 aircraft/task/event pass is complete. I02 must review native GUI
lifecycle/focus and the startup/storage boundary independently; a Foothold mission
cannot validate our custom window. The narrow Scratchpad comparison is not a
complete UI audit. Israel-profile balance and L12 long-session checks follow.
DCS execution remains necessary to establish actual task acceptance, aircraft
flight/landing, radio/tanker behavior, rendering and performance. No precise
probability of trouble-free operation follows from these static checks.
