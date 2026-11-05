# G02 — Israel solo support/accounting balance (0.1.11)

This measures resource access and conservation, not DCS combat difficulty,
weapon effects, flight/road behavior, native rendering or FPS.

## Reproduced failure

The 0.1.10 Israel attrition fixture accepted 3 of 8 scheduled strike requests.
It ended with four ready F-16s: one each at Ramat David, Hatzor, Nevatim and
Hatzerim. Every base was below the two-aircraft dispatch requirement, so all four
survivors were unusable for support. This also reproduced from a fragmented-stock
checkpoint. Five blue support bases exist, but Tel Nof's F-15/AWACS/tanker stock
is not an F-16 strike pool. Aircraft at different bases are never combined into
one synthetic flight.

## Policy implemented

Requested BLUE CAP, ESCORT, SEAD and STRIKE first search all controlled compatible
bases for a funded pair. Only when no such pair exists may a request use one
ready aircraft at a controlled compatible base. A funded pair at a later base
has priority over a single at an earlier one. Automatic blue and red dispatch
retain their existing two-aircraft requirement. AWACS/tanker remain single by
their existing rules.

A single pays the full existing sortie price: CAP/ESCORT 8 fuel + 8 ammo;
SEAD/STRIKE 8 fuel + 12 ammo. It has one aircraft/payload, not the weapons or
resilience of a pair. These are conservative game-policy choices, not a claim
about real combat doctrine. The offer/reason states the count and single-aircraft
fallback, and launch acknowledgement states the dispatched count. Native UI and
F10 read the same quote. No extra confirmation or separate control is required.

No starting stock, resource grant, replacement production, transfer or checkpoint
content/schema change is introduced. Duplicate assignments, captured bases,
resource checks, active-flight and unit caps still apply. A selected pair is not
shrunk merely to bypass the global unit budget. Failed creation spends nothing;
landing and maintenance return only survivors. An active single resumes through
the existing one-aircraft maintenance policy without creating an extra aircraft.
The policy applies to legacy saves too; a one-aircraft flight was already valid.
If every suitable aircraft is destroyed, support remains unavailable.

## Eight paired six-hour workloads

Exact data: [LIVE_ISRAEL_BALANCE_RESULTS.json](LIVE_ISRAEL_BALANCE_RESULTS.json).
Baseline local packaged source: `5432deae6372e325a3703238ac1c872f7f611970`.
Its tree `e2560779808285a2b1121ee3a5a6ade4f8b84367` equals public 0.1.10 commit
`404f985a66d66242879d9a7ad2eb5e3b6794b730`. From a full public clone:

```sh
python tools/live_balance.py --scenario israel --regional --baseline-ref 404f985a66d66242879d9a7ad2eb5e3b6794b730 --output israel-balance.json
```

Every workload requests strike support at 45-minute intervals. Convoy arrivals
are injected at twenty minutes and aircraft recovery/loss at twenty-five minutes.
Steady/attrition retain the automatic air director and their original scripted
battle events. Other workloads disable automatic air to isolate player access;
logistics continues, ownership changes are scripted and assault groups receive
no injected arrivals. Their absence of observed arrival must not be confused
with a measured navigation failure.

- **Steady:** 8/8 before and after; no acceptance gain is claimed.
- **Scripted attrition:** 3/8 becomes 8/8. The new run records 17 blue aircraft
  losses versus 16 before: accepting more sorties does not make them safer.
  The loss pattern is deterministic, not a combat/survival probability model.
- **Fragmented survivors:** four ready F-16s, each at a different base, model
  ten prior F-16 losses. Requests rise from 0/8 to 8/8, all as singles. Two more
  aircraft are explicitly lost; only two F-16s remain across ready/active/
  maintenance stock. Repeat service of survivors is not replacement production.
- **Ramat David captured at minute 60:** 8/8 both runs. All subsequent accepted
  requests use other bases; two aircraft on the scripted returning flight are
  recorded lost. No alternate-base landing behavior is inferred.
- **Central sector captured at minute 60:** 8/8 both runs; Tel Nof and Hatzor
  cannot launch after capture. This preserves access from other regions.
- **Southern corridor isolation:** central/Negev depots are disabled and Sharon
  is red during minutes 60–180. Southern cargo credit is zero during the cut;
  48 southern cargo vehicles deliver after the scripted reconnection. Ramat
  David's local supply remains independent and is excluded from cut-period
  counters. Acceptance stays 8/8; the corridor rule itself was not relaxed.
- **No ready F-16s:** 0/8 before and after. Supply does not manufacture aircraft.
- **All operating blue base sectors captured at minute 60:** only the first,
  pre-capture request succeeds (1/8 both runs); all later requests cite BASE_LOST.

The two original workloads peak at 153 active units; custom workloads peak at
133 or less, under the unchanged limit of 180. Each minute validates the save,
nonnegative regional stock and unit cap. Custom workloads additionally assert
that total blue ready + active survivors + maintenance aircraft never increases,
including after delivery, recovery and maintenance. These are eight paired
accounting fixtures, not sixteen flights or observed hours in DCS.

## Tests and remaining work

Ten added tests cover pair preference across bases, manual single/full costs,
automatic/red restrictions, shortages/capture/assignments/global caps, failed
creation, recovery/loss, checkpoint resume, native/F10 read models and the eight
long workloads. Six initial focused cases failed against 0.1.10 before the fix.
Existing legacy balance fixtures are rerun; their historical paired report stays
in LIVE_BALANCE_RESULTS.json and is not overwritten by the Israel report.

G02's accounting scope is complete. L12 is next: bounded long-session update
cost, storage/registry growth and installation/recovery checks. Real DCS combat
balance, whether a lone SEAD aircraft is useful/survives, base approach behavior,
Windows integration and actual performance still require engine observation.
