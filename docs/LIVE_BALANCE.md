# Solo accounting balance — 0.1.7 / L11

This is a first resource/recovery pass. It does not certify DCS combat difficulty,
aircraft effectiveness, road navigation, UI rendering or FPS.

## Reproduced problems

In 0.1.6, a base starting at 30 fuel/ammo/supply after depot destruction used its
last resources on automatic flights and an advance. Six fixture hours later it
had 6 fuel, 2 ammo and 18 supply, below the 25 supply / 10 ammo repair cost. It
remained ACTIVE with no source of new supplies. A quarter-strength depot was
also offline indefinitely: eligibility required above 25% health, but repair
required complete destruction. These were separate accounting/repair defects.

## Rules now implemented

- Automatic blue air dispatch leaves 8 fuel and 22 ammo per base. Requested
  support uses ordinary costs and may consume them. These are floors within
  existing stock, not a second inventory or a grant. Red has no player reserve.
- Automatic ground dispatch normally leaves 25 supply: 37 required, 12 spent.
  Without a connected depot or affordable connected depot repair, the reserve
  is released and the existing stock can fund finite last advances at 12 each.
- Depots/fuel sites at or below 25% strength qualify for reconstruction after
  four hours, at a repair review. Paid repair still needs a controlled connection,
  25 supply and 10 ammo. Depots take priority, then fuel, then other repairable
  sites. Ordinary armour is not rebuilt. Other sites retain full-destruction rules.
- The adapter stages a replacement, retires old survivors and cleans old registry
  entries, then the director commits the state and payment. Failure to create or
  retire rolls back the replacement and retains stock. Temporary unit space for
  the whole replacement is required; this is deliberately conservative.
- With no funded advance, connected depot, affordable connected depot repair or
  moving surviving blue ground force, remaining enemy sectors trigger DEFEAT.
  Inbound supply and assaults defer that decision. A physically stalled force
  still has its existing deadline/waiting rules; this is not automatic rescue.

The reserve numbers are game-design choices: one requested strike (8 fuel/12
ammo), one site repair (10 ammo/25 supply). The inherited four-hour repair delay
and supply cadence are unchanged. There is no claim of doctrinal realism.
No aircraft, stock or convoy is granted on reload or defeat. Spending reserved
ammo manually can prevent repair; finite last advances can still lose.

## Reproducible comparison

Run `tools/live_balance.py`; exact outputs are in
[LIVE_BALANCE_RESULTS.json](LIVE_BALANCE_RESULTS.json). The baseline local source
is `1b2143166b4a73cb0fdf46a3defe43dd84338a1f`; its tree
`4291573a50b686341d17f486ebe69a9ec35f8bfd` matches public import commit
`08102d69f82c4c86679149d4f0cb0df9afc772f0` in this repository.
The public ref can be used with `--baseline-ref` from a full clone.

Seven paired fixtures each run six campaign hours, with one-minute accounting
steps. Flights return at 25 minutes, convoys arrive at 20 minutes, and attacks,
casualties and control changes are explicit scripted inputs. No simulated weapon
hit, AI driving, terrain clearance or combat probability is claimed.

- **Steady support requests:** 8 of 8 scheduled requests accepted, versus 2 of 8
  before. Final ammo is 20 versus 0. Scripted south capture still occurs at
  minute 110 in both versions, so preserving a reserve does not stop this advance.
- **Low-stock depot loss:** depot rebuilds at minute 240 and first cargo arrives
  at minute 275. Before, no rebuild/delivery occurred in six hours. New south
  capture is delayed to minute 335 instead of 35: recovery protection has a cost.
- **Quarter-strength depot:** now rebuilt at minute 240, first supply at 275;
  before, the site remained at 25% and no supply arrived.
- **Fuel-site loss:** both restore the site under the inherited repair timing;
  the new run retains 14 fuel versus 6. Ammo/supply delivery remains independent.
- **Corridor interruption:** both deliver at minute 140 after the scripted
  reconnection at 120. The new run retains 22 ammo versus 2. This fixture moves
  the blue depot to South, uses a blue South garrison and red Golan defenders,
  then scripts their loss/reconnection. The shipped scenario is unchanged.
- **Scripted attrition:** 8 of 8 requests accepted versus 1 of 8, with actual
  fixture aircraft/cargo losses retained and stock within limits.
- **Empty legacy stock with a destroyed depot:** remains at zero and generation
  one. It now records DEFEAT instead of an ACTIVE state with no recovery. No
  reserve is fabricated for an already exhausted checkpoint.

These measurements demonstrate resource access and accounting, not that eight
support sorties will survive or win in DCS. They are synthetic workload results,
not a statistical estimate of player outcomes. The combined report measures this
release's changes; focused tests isolate reserve, rebuild and exhaustion rules.

## Persistence and failure checks

Optional `target.disabled_at` retains outage time. Known complete destruction
times are reused. A legacy partial site's unknown outage starts at the first
upgraded load; subsequent loads retain it. Invalid/future timestamps are rejected.

Fifteen balance tests cover exact reserve boundaries, requested/manual spending,
red behavior, partial reconstruction, spawn-after-create failure, failed retirement
and retry, missing stock/control/unit space, depot priority, read-only reports,
legacy reload, last advances, inbound cargo, defeat and the seven longer fixtures.
Rebuild failure does not debit resources or leave an extra live target group.
The native/F10 read model describes the same thresholds as dispatch and repair.

C2 dispatch penalties, new logistics geography and combat doctrine are outside
this pass. Existing depot/fuel/SAM/armour consequences remain the reasons to
choose different targets. L12 is next; real DCS play balance remains provisional.
