# SQE Live 0.1.11 — validation boundary

Release date: 2026-11-05. Target: local Windows DCS, Syria, F-16C.
Upstream base: 807643b33fa88f19329177c6c420a5f8feb942e8 (SQE 0.41.135).

## Automated checks

Result: **177 live/installation tests passed**, plus all **95 original SQE smoke
sections passed**. Python 3.12.14, Lupa 2.8 / Lua 5.1; pydcs pinned by requirements.
The ZIP and every install-file checksum were verified after packaging.

The suite in tests/live runs the actual Lua modules under Lua 5.1 (Lupa 2.8).
It covers generated .miz execution with a DCS contract double, native GUI
callbacks, assignments and duplicate/stale commands, force and inventory
limits, deaths, landing/recovery, logistics/capture, persistence and installation.
The double deliberately has no flight model, ballistics, AI or terrain data.

- Ten Israel attrition/support cases cover manual singles at full cost, funded
  pair preference, captured/empty bases, conservation and failed dispatch,
  recovery/reload, shared native/F10 quotes and eight six-hour regional workloads.
  The paired 0.1.10 comparison is in LIVE_ISRAEL_BALANCE_RESULTS.json; simulated
  requests improve 3/8 to 8/8 under attrition, not measured combat effectiveness.
- Nine UI/startup boundary cases were added: cold/same-second stale status,
  long-load session exclusion, stop/load widget failures, callback/log/report
  exceptions, non-finite timestamps and execution of the installed storage bridge
  after standard API sanitization. The native DCS environment initializer is
  supplied as a contract, not executed. See LIVE_UI_STORAGE_AUDIT.md.
- Seven runway-event regression cases cover both event families, duplicate
  notifications, touchdown versus stable ground roll, touch-and-go, stale landed
  wingmen, wrong/captured airfields, absent runway evidence and invalid velocity.
  See LIVE_INTEGRATION_AUDIT.md for primary sources, fixes; the separate I02 audit is in LIVE_UI_STORAGE_AUDIT.md.
- The shipped Israel profile is checked separately from legacy regressions:
  fifteen field IDs and BLUE mission warehouse coalitions agree with runtime
  ownership; loss/recapture affects the correct fields; regional bases/supply
  remain available independently; eleven map nodes fit; duplicate advances are
  blocked; old checkpoint identity remains separate. Both missions are installed
  and uninstalled while unrelated files are preserved. Three six-hour profile
  scenarios run in the contract suite, with seven scripted runs in the included
  current-profile report. Those runs peak at 153 active units, not a measured FPS.
- Foothold was selectively inspected as supplied static data. Its native group
  and Mission/route patterns are useful references; its MOOSE helpers, client
  slots and scripts are not execution evidence for SQE Live. See
  LIVE_FOOTHOLD_REFERENCE.md for the exact scope and hashes.
- Fifteen solo-balance tests cover automatic reserve boundaries versus explicit
  requests, last advances, red costs, partial-site recovery, outage migration,
  failed creation after a group exists, retirement failure/rollback/retry, finite
  stock, depot priority, incoming cargo, terminal exhaustion and read-only reports.
  Seven paired six-hour accounting fixtures compare 0.1.6 and 0.1.7, including
  scripted attrition and a two-hour corridor interruption. These historical legacy-profile results do not establish balance of the expanded map.
  Support requests in the steady fixture improve from 2/8 to 8/8; depot repair restores first cargo
  at minute 275 in the low-stock/partial-site fixtures. Travel/returns/combat events
  are prescribed inputs; these are not DCS difficulty or navigation estimates.
- Seventeen supply-connectivity scenarios cover disconnected depots, deterministic
  alternative paths, fuel-only isolation, pause/resume, unchanged IDs/positions,
  Hold failure and retry, shared road-attempt budgets, control flapping, partial
  delivery/deaths/reload, timeout, source destruction, held startup, legacy
  disconnected graphs, isolated staging/reconstruction, enemy objective completion,
  corrupt corridor data and matching native/F10 reports. No automatic fuel,
  ammunition or supply credit occurs while the convoy corridor is closed.
- Three defects were reproduced against 0.1.4 before correction: a failed
  completion notification stopped campaign updates; an explicit missing target
  selected an unrelated first row; an immediate convoy checkpoint could not
  restore when its road query failed. Those cases now pass, as does a legacy
  empty-position convoy checkpoint whose source was destroyed after dispatch.
- Fifteen dynamic-objective scenarios cover discovery from existing inventory,
  observed moving positions, last survivors, native Map/F10 identity, assignment
  and support through assault-to-garrison transitions, exactly-once completion,
  partial/full delivery, timeout, destination loss, reload, rejected friendly/
  missing targets, return-command failure, save corruption and repeated cleanup.
  AttackGroup references and route contents are inspected, not flown by an AI.
- Forced placement more than 900 metres from the nominal target agrees across
  briefing, status, F10 mark and attack approach point. Radar losses select the
  next observed survivor; complete destruction removes the mark. Missing
  observations do not return planned coordinates or spend on a new attack.
- Marker failures, including an explicit refresh at an unchanged position,
  recover without stopping the world. Reload preserves surviving references.
- Road paths reject invalid/oversized data, remote endpoints and extreme
  detours, and produce no more than 18 route points. Missing/failed queries
  reject new dispatch without spending or duplicating forces.
- Stalled columns retry from their actual positions, without teleporting,
  respawning or additional charges. Three retries per journey and global
  throttling are enforced; controller/query errors do not halt the campaign.
  Regular movement avoids retries; exhausted budgets persist through reload
  and still allow an ordinary road-stalled convoy to arrive physically.
  A convoy explicitly held by a corridor cut additionally requires a successful
  road refresh; an exhausted budget leaves that convoy held until timeout.
- Partial supply is credited only for arriving survivors, once per vehicle,
  across repeated observations, subsequent losses and save/reload. Assault
  capture still requires all survivors to arrive and all defenders to be gone.
  Deadline handling preserves prior deliveries and exempts arrived assaults
  waiting for defenders. Legacy saves without navigation/delivery fields load;
  restored convoys can wait for a road query to recover. Corrupt new fields fail.
- Map geometry preserves sector/connection identity, stays within its canvas,
  separates nodes and rejects malformed/oversized graphs. A physical capture
  changes control/front markers without shifting the layout.
- Map browsing does not mutate or spend. Native callbacks filter targets, page
  through lists, preserve an empty selection after target removal, show the same
  briefing as F10, and submit the selected target to the real command bridge.
- Stale snapshots disable map/target actions and use last-known styling; fresh
  snapshots recover. A session change clears the filter. Invalid layout/native
  widget construction falls back to Front plan without stopping campaign updates.
- Visible controls are checked for overlap on all four tabs; hiding the window
  also hides dynamic children. One hundred refreshes do not add native widgets.
  A separate offline geometry preview checked labels with substitute fonts;
  this is not a DCS screenshot or verification of native skin/font rendering.
- The install bundle includes the tested map modules. Installer/uninstaller
  fixtures verify they are added and removed while unrelated edits/saves remain.
- Sector objectives track defending survivors, actual column arrival, capture,
  supply/force limits and base loss. Occupying garrisons remain capture blockers.
- CAS cannot complete while its last defender survives; legacy residual armour
  and still-operating low-strength SAM radars remain taskable. Save schema/content
  remain unchanged; read-only sector plans survive a save/reload.
- Support quotes and dispatch use identical eligibility checks, including changed
  resources after a quote, maintenance, target assignment and duplicate support.
  Reads never mutate/spend. Fuel-site consequences agree with convoy delivery
  and paid repair; UI tabs, recommendation selection and F10 use the live model.

- Six simulated campaign hours with repeated AI losses, landings, physical
  convoy arrival observations, resources, checkpoints and bounded registries.
- Twenty save/reload cycles preserve destroyed aircraft without duplicating
  maintenance or ready aircraft.
- Injected status, command-read/acknowledgement, save-write, F10 menu and
  diagnostic-file errors leave world updates running and recover after repair.
  Duplicate command retries do not purchase support twice. Authoritative engine
  errors and invalid inventory stop updates while retaining the last checkpoint.
- Partial force-spawn failure cleans up owned groups without deleting the player
  or writing a checkpoint. Corrupt-save startup errors remain reportable even if
  the status channel also fails. Checks do not mutate the campaign state.
- UI creation errors and recovery are observed through the actual hook against
  fake widgets. Wrong-session/stale heartbeats cannot pass the connection check.
- Diagnostic report paths/payloads are bounded. The PowerShell collector fixture
  includes only the selected reports and bounded SQE log excerpt, preserves the
  campaign save, and excludes unrelated files and unrelated log entries.
- Actual temporary-file IO covers atomic checkpoint rotation, recovery of a
  corrupt primary, filesystem sanitization, bounded command batches and paths.
- Native window button/hotkey callbacks are exercised with fake widgets and
  the real command bridge/core. Layout bounds are checked, not actual rendering.
- Install, reinstall and uninstall are executed with PowerShell 7.4.7 on Linux
  against temporary installation/profile fixtures, including paths with spaces,
  CRLF files and unrelated edits/saves. This does not validate Windows registry
  autodetection, UAC, Windows PowerShell 5.1, antivirus or a real DCS installation.
- Mission ZIP integrity, embedded Lua syntax/execution, Syria map, single player
  slot, armed F-16, one live trigger, package hashes and supported vehicle types
  are checked.

Final test output and the current Israel paired accounting report are included in the release's Validation folder.
The original SQE headless smoke suite was rerun separately for 0.1.11 and passed.

## Required real-game validation

DCS is not installed in the build environment. These remain unverified:

- Mission startup in current DCS and real native dxgui rendering/focus.
- Terrain/building clearance and reachable road routes on Syria.
- Actual combat effectiveness, AI route following, attack execution, escort,
  tanker contacts/radio menus, AWACS and airfield recovery behavior.
- Player rearm/refuel and multiple flown sorties in the same session.
- Real shutdown/load sequence, long-session reliability and multiplayer checks.
- Frame time, FPS and memory on the player's PC.

The 180-unit/9-flight limits are code limits, not a performance measurement.
The release is an installable development build with automated verification;
it is not described as flight-tested or as full feature parity with SQE.

These pending observations do not block further development or assign the user
a manual test task. In-game automatic diagnostics record API/data observations;
they cannot supply the real-game evidence listed above.
