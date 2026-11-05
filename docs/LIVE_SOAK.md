# L12 — runtime retention, cleanup and recovery (0.1.12)

Measured 2026-11-06 with Python 3.12.14 / Lupa Lua 5.1. DCS was not executed.

## Reproduced failure and policy

A registered aircraft can receive an ejection/unit-loss notification while its
object still reports existence and positive life. The core correctly records a
loss, but the old adapter only removed registrations after physical disappearance.
After a fully lost flight's five-minute history expired, its group lookup could
also be discarded, leaving a live object/registration that no longer belonged
to a counted flight. Three focused regressions failed against 0.1.11.

The adapter now retires an aircraft recorded lost on the next observation,
outside the native event callback. This is explicit cleanup policy for aircraft
already irrecoverable in campaign state. It does not infer a loss for a healthy
wingman or destroy another flight. Completed groups are retired before history
expiry; orphan groups whose state was purged are also cleaned. Successful flight
retirement clears registry/contact entries. No stock is refunded for a loss;
only surviving landed members enter maintenance. Cleanup failure stops updates
and retains the last checkpoint rather than silently continuing with a mismatch.

This reproduces a contract edge case, not an observation that every DCS ejection
leaves a living aircraft indefinitely. Native destruction/event ordering remains
part of actual-engine acceptance.

## Workload and exact artifacts

- [Six-hour current run](LIVE_SOAK_RESULTS.json): 10,800 scheduled two-second
  updates using the actual runtime, director, adapter, publication and save code.
- [One-hour baseline probe](LIVE_SOAK_BASELINE.json): 1,800 updates with the
  adapter from packaged 0.1.11 source `4770ee4ef6ffcff4a4a884b39240525147b6c94c`.
  Its tree equals public `a0a12db3773ff7fc5df39b3012d02a85203d67fd`. The other runtime
  modules are unchanged by this fix. This is not a paired six-hour timing study.

Both workloads explicitly inject one complete blue-flight ejection, later
landings at ten minutes and supply arrivals at twenty minutes. They do not
simulate AI, weapons, flight or road navigation. Every thirty minutes 32 briefing
commands are queued; the bridge returns sorted batches of at most 16. The
in-memory bridge double was corrected to honor that real filesystem contract.
After-update metrics are sampled every two seconds; half-hour rows are retained.
The known pre-update burst is 32; an after-update queue peak of 16 is not a
universal limit on arbitrary external command input.

The baseline probe retained two living recorded-loss objects through its final
sample. The corrected six-hour run retained none. Current observed maxima:

- Registered units: 152; active campaign units: 153 / 180.
- Flight/group lookup entries: 10; shipment/group entries: 44.
- Campaign log: 80; command journal: 128; diagnostic history: 32.
- Checkpoint: 60580 bytes, below the 4 MiB bridge limit.
- Status publication: 105444 bytes, below the 512 KiB limit.
- Command queue after updates: 16 at peak and zero at the end.

Checkpoint size grows while recent shipment history accumulates: 54,833 bytes
at three hours, then half-hour samples fluctuate around 54–56 KB and finish at
55,183 bytes. Histories are retained deliberately and age out; the report does
not claim every retained map is empty or bounded by these exact observed maxima
for every possible workload.

Recorded host invocation median/p95/max were 11.698 / 22.697 / 99.353 ms.
These include Python/Lua invocation and contract-double work, and were measured
on a shared build host. They exclude DCS processing, rendering and real filesystem
latency. Metrics sampling itself is outside the timed update. Do not convert
these numbers to FPS, a DCS script budget or a prediction for the target PC.
The double deliberately retains historical entity/message objects for assertions;
these are excluded from runtime-map counts. No process-RAM/GC claim is made.

## Persistence, backlog and failure checks

Nine added cases cover partial/full ejection, cleanup after state purge, live
wingman/other-flight isolation, retirement failure/checkpoint preservation,
idempotent retirement, one-hour map/journal/queue bounds, twenty default-profile
resume cycles with one recorded aircraft loss, and actual filesystem recovery.

The disk fixture rotates twenty checkpoint payloads, drains 600 unique commands
in batches of at most 16, repeatedly replaces only the two fixed diagnostic
files, corrupts the primary, and restores the retained previous payload. No
command or temporary files remain. This low-level bridge test uses payloads;
valid campaign checkpoint/resume behavior is checked separately by the Lua core.
Existing PowerShell installation/reinstallation/uninstallation fixtures run for
both profiles, preserving unrelated edits and saves. These are Linux/PowerShell
fixtures, not Windows registry/UAC or real DCS shutdown acceptance.

Reproduce current measurement:

```sh
python tools/live_soak.py --hours 6 --output runtime-soak.json
```

From a full public clone, reproduce the baseline adapter probe:

```sh
python tools/live_soak.py --hours 1 --baseline-ref a0a12db3773ff7fc5df39b3012d02a85203d67fd --output baseline-probe.json
```

## Remaining acceptance boundary

L12's build-environment scope is complete. V01 is actual DCS acceptance: mission
startup, native UI/focus, event/destruction ordering, AI support/landing, physical
roads, save/exit/reload and frame time on target hardware. It remains pending;
this release is a development candidate, not 1.0 or a game-validated beta.
This is not assigned as a manual test task to the user. Further specific code
fixes can continue, but cannot substitute for the missing engine observations.
