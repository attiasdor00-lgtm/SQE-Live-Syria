# SQE Live 0.1.6 — Syria

A development conversion of SQE to one continuously running DCS mission.
Code and mission are provided; actual DCS flight/rendering validation is pending.
This is a fictional blue/red conflict, not an operational model of present forces.

## Install and fly

Requires Windows DCS, the Syria terrain and F-16C module. No Python, paid server,
network service or extra aircraft mods are needed to run the supplied mission.

1. Extract the entire release ZIP. Open the **SQE-Live-Syria** folder.
2. Close DCS and double-click **Install.cmd**. The installer detects common
   installation/profile paths or asks for the full paths if ambiguous.
3. If Windows denies access to the DCS installation, open PowerShell as
   administrator and use the command below with your actual paths. Keep the
   Saved Games path pointing to your regular user's profile.
4. Start DCS. Open **Missions → SQE-Live → SQE_Live_Syria**.
5. You start cold in an F-16C at Ramat David. Press **Ctrl+Shift+Q** for the
   clickable Operations window, or use radio **F10 → SQE Live**.
6. Check the save status. Select a target, Accept it, read the coordinates and
   request support. Fly the sortie, land and rearm, then accept another task.
   The same world continues while you do this.

Example explicit installation:

    powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\Install-SQE-Live.ps1 -DcsPath "C:\Program Files\Eagle Dynamics\DCS World" -SavedGamesPath "C:\Users\YourName\Saved Games\DCS"

The installer copies the mission and UI into Saved Games and adds one marked
block to DCS's Scripts/MissionScripting.lua. It backs that file up first.
The normal io/os/lfs sanitization remains in place; the bridge exposes only
bounded campaign/status/command file operations under Saved Games/DCS/SQE-Live.
DCS repair/update can remove this block; rerun the installer afterward.
This modifies a DCS installation script; multiplayer integrity-check acceptance
has not been verified. This release targets local single-player use.

## What is implemented

- One reusable mission with six connected sectors from Galilee through southern
  Syria to Damascus and Shayrat, and 17 persistent target groups.
- F-16C player sorties; blue and red AI CAP, SEAD and strike missions generated
  during play. Actual DCS unit deaths determine losses and task completion.
- Native clickable in-game window: front, aircraft/resources, targets,
  coordinates, progress, active support flights, campaign log and save status.
- Map tab with six clickable sectors, control colours, front connections and
  base markers. Sector selection filters the task list; task selection opens
  the matching briefing. Browsing does not assign tasks or spend resources.
- Front plan, Resources and Support tabs: sector objectives, pending ground
  arrival, supply/force-limit blockers, target consequences and launch readiness.
  Select suggested task highlights a target; Accept still requires your action.
- Target assignment, briefings, F10 map marks, abort, CAP, escort, SEAD, strike,
  AWACS and tanker requests. Hold/Push control requested blue combat flights.
- Finite AI airframes and abstract fuel/ammunition/supply budgets. A failed spawn
  spends nothing. Surviving AI landings return airframes after ten minutes of
  maintenance; destroyed/missing aircraft do not return.
- Physical supply convoys. Only surviving vehicles which actually reach the
  destination deliver supplies; each arriving vehicle delivers its own share,
  even while another vehicle is delayed. Fuel replenishment also requires a surviving,
  friendly fuel site. Destroying depots interrupts new supply convoys.
- Ground advances across adjacent sectors after their defenders are weakened.
  Capture requires arrival and elimination of defending armour/garrisons.
  Captured base ownership blocks the former owner's new launches.
- Road-network queries before dispatch, bounded retries after a convoy stops
  making progress, and delayed-column notices in Front plan / Resources.
- Destroyed non-armour sites can rebuild after four campaign hours, only while
  their sector is friendly and sufficient supply/ammunition exists.
- Autosave every 30 simulation seconds and after state changes; manual save;
  previous-checkpoint recovery; duplicate/stale UI command protection.
- Automatic diagnostics with checkpoint readback, UI connection observation,
  startup/state checks and failure history. Peripheral file/menu failures do
  not stop campaign updates. Invalid campaign state retains the last checkpoint.
- Unit budget 180 including garrisons; at most nine AI flights. This is a
  performance bound, not an FPS claim.

## Flying and support

Mission starts at 08:00 local time in clear weather. Coordinates use degrees and
decimal minutes with target elevation in feet. Enter them manually into the
F-16 steerpoint system; there is no automatic cockpit programming.
Briefings, Operations and F10 marks use an observed surviving vehicle rather
than the planned site centre. A surviving radar is preferred for SAM sites.
Other vehicles may be spread out. Existing marks follow a changed reference
vehicle and movement of at least ten metres; pressing Mark refreshes immediately.
When no surviving unit can be observed, coordinates are unavailable and no new
strike flight is dispatched. Entered cockpit steerpoints do not update themselves.

- **SEAD** destroys the designated search/tracking radar units. The remaining
  launchers can then appear as a **DEAD** objective.
- **CAS** completes when every vehicle in the defending group is destroyed.
  Remaining defenders stay taskable, including those in 0.1.1 saves where a
  partial CAS objective already completed. Existing completion counts are kept.
- **STRIKE / DEAD** against fixed sites completes when no more than 25% of the target group survives.
  A still-operating SAM radar remains a SEAD target even below that threshold.
  AI kills count because this is a shared campaign objective.
- **SEAD support** for a fixed non-SAM objective selects the nearest surviving enemy
  radar site. A selected SAM with its radars already destroyed cannot receive a
  redundant SEAD request. **Strike support** uses your assigned task, or the selected target
  if there is no assignment.
- **AWACS:** 251.000 AM. **Tanker:** 252.000 AM. **Combat flights:** 305.000 AM.
  AI task/radio menu behavior still needs a live DCS test. No TACAN guarantee.
- AI reinforcements enter airborne near their base. They return to an airfield;
  cold-start/taxi/departure simulation for AI has not been implemented.
- The player's rearm/refuel uses normal DCS ground crew and mission warehouses;
  it is not debited from the AI campaign supply ledger.

Close Operations with its button or Ctrl+Shift+Q to return the mouse to the
cockpit. Commands execute on the mission's next update, usually within two
simulation seconds. While paused, they wait. A rejected stale command asks you
to refresh/retry; it does not apply a second time.

## Reading the front

**Front plan** explains each sector's next step: weaken its defending ground
forces, cover an advancing column, wait for physical arrival, or resolve a
resource/unit-limit blocker. Ground capture still requires all defending armour
and occupying garrisons to be eliminated. An air strike alone does not capture.
Enemy supply convoys, assault columns and occupying garrisons have their own
task cards in Map and F10, including newly created forces.

Task briefings describe the actual campaign consequence. The last operating
depot blocks new supply convoys when disabled; the last fuel site blocks fuel
replenishment. Existing stocks are retained, and another operating source can
keep replenishment going only through a controlled sector corridor. C2 targets currently provide objective credit without
an additional dispatch penalty. Recommendations are optional front priorities,
not a promise that a route is tactically safe.

**Resources** shows friendly operating bases, connected supply/fuel sources and incoming
convoys. **Support** shows available aircraft, launch costs and reasons a request
is unavailable, including maintenance and captured bases. Disabled support
buttons reflect the displayed state; the mission rechecks before spending.
An accepted assignment takes priority over the target highlighted for browsing.

The same front and availability reports are available under **F10 → SQE Live**.

## Using the front map

Operations opens on **Map**. Click a sector, then a task row to read its briefing.
**Previous / Next** cycle through that sector's targets. **All sectors** removes
the filter; lists longer than four targets show another page as you cycle.
**Select suggested task** selects the campaign recommendation and its sector.
Press **Accept task** to assign it, **Brief / coords** to display its coordinates,
or **Mark on map** to mark that same target on DCS's F10 map.

Blue means friendly control, red means enemy control, **\*** marks a front sector
and **[B]** marks a sector containing a base. Amber links join opposing sectors.
This is a schematic of campaign connections, not a terrain map: spacing is not
to scale and links are not verified roads, supply routes or safe flight paths.
The briefing and F10 mark provide the actual target location.

A sector with no task cards shows its situation and disables target actions.
If the selected target disappears, select a new target explicitly. The UI never
silently assigns a target from elsewhere. After ten seconds without a fresh
status heartbeat, the map turns grey, shows **STALE / last known state**, and
disables commands until fresh data arrives. This can occur while DCS is paused.
Starting a different session clears the sector filter and prior selection.
If the map widget cannot load, Front plan and F10 remain available.
Existing 0.1.0–0.1.5 campaign saves remain compatible when upgrading. Loading a
new dynamic assignment in an older release is not supported.

## Tasks created during the campaign

Enemy forces appear automatically in their destination sector: **Supply convoy**
as STRIKE, **Assault column** and **Occupying garrison** as CAS. These cards use
the actual existing group and show its surviving vehicles, current state and
observed reference position. The sector map is still a schematic; a moving
force belongs to its destination sector, not necessarily the sector it is
physically crossing. Use Brief / coordinates or Mark on map for its live location.

Every remaining vehicle must be destroyed to complete one of these objectives,
including supply STRIKE tasks. An arriving assault keeps the same assignment
as it becomes a garrison. Cargo delivered by an enemy convoy remains credited
to its base; destroying its remaining vehicles prevents only their deliveries.
Full delivery, timeout or a lost destination ends the assignment without
destruction credit. Disappearing selections are left empty for an explicit choice.

Strike support attacks that force's group. Hold / Push retains its identity;
Push refreshes the approach from the currently observed reference. When the
force ends, attached support is instructed to return to base. Failed return
commands retry at ten-second intervals while the flight remains active, without
changing to another target. A moving force is not a radar objective: select a
SAM separately for SEAD. AWACS and tanker requests are independent of the target.

Save/reload preserves the force ID, surviving vehicles and active assignment.
As with other support, interrupted surviving aircraft enter maintenance rather
than resuming in the air. This release does not add fog of war or player task
selection to the autonomous air director; automatic air priorities are unchanged.

## Supply connectivity and interrupted corridors

A new supply convoy needs a live friendly depot connected to its base through
friendly controlled sectors. Fuel credit independently requires a live connected
fuel site; ammo and supply can still arrive while the fuel connection is cut.
Existing base stock is retained. A destroyed depot does not erase cargo already
loaded, provided its sector corridor remains controlled.

Losing a sector on a convoy's corridor issues Hold and blocks delivery, including
vehicles physically near the destination. A newly available alternative or a
restored corridor must obtain a successful native road refresh from the actual
survivor position before delivery resumes. This shares the existing three-attempt
budget, five-minute retry interval, global ten-second throttle and original
three-to-six-hour deadline. Reload and repeated control changes reset none of
these. A corridor-held convoy with no retries left stays held until timeout.
Partial deliveries and casualties remain accounted for once, across reload.

Resources and F10 Campaign status explain disconnected sources and held convoys.
Assault staging and reconstruction of destroyed sites also require a controlled
connection to their funding base. An assault already dispatched continues under
the existing capture rules; it is not paused by this supply-convoy policy.

The sector graph is an abstract campaign gate, not road geofencing. No sector
polygons constrain the native road path to friendly territory. Default Syria
depots share their base sectors; red fuel from Marj and ground staging have
connections through other sectors. Scenario geography is unchanged in 0.1.6.

## Convoy delays and partial supply delivery

A new convoy requires a reported road path near its origin and destination.
If the query fails, dispatch is deferred without charging supply. Road data
does not guarantee that bridges, buildings or traffic are navigable in DCS.

A vehicle outside the arrival area is considered delayed after five simulation
minutes without moving fifty metres. The convoy can receive up to three route
refreshes from its current position, with at least five minutes between retries.
Retries across all convoys are separated by at least ten simulation seconds.
They preserve unit identity, survivors and resources. Delays appear in the
campaign log, sector plan and base resource view.

Supply is credited once per arriving vehicle. Destroyed or overdue cargo is
never credited. Arrival still uses the existing 1,200-metre destination area.
Assault capture continues to require all surviving column vehicles in that area
and elimination of defending armour/garrisons. An assault already at its
destination can wait for defenders to be cleared without expiring as a failed
journey. Other journeys have a route-dependent three-to-six-hour deadline;
remaining overdue vehicles are retired, preserving any supply already delivered.

Reload restores only undelivered survivors of a partially delivered convoy.
If a road query fails during reload, those existing vehicles are restored held
and can retry; the entire campaign does not fail merely because that query failed.
These behaviours were checked with API doubles. Actual road following and the
effectiveness of retries still require DCS observation.

## Save, resume and reset

Save location:

    Saved Games\DCS\SQE-Live\campaigns\syria_cedar_current.json

The previous checkpoint has a **.prev** suffix. A bad primary recovered from a
valid checkpoint is retained as **.invalid**. If neither checkpoint is valid,
startup stops without silently starting a fresh campaign.

Before quitting, use Save and check for a successful status. Relaunch the same
mission to resume. Ground survivors, losses, positions, front, resources,
objectives and campaign clock persist. The player starts at base again.
Surviving AI interrupted by shutdown enter ten-minute maintenance on reload;
their expended resources and destroyed wingmen stay lost. Convoys/garrisons
reappear at their saved positions.

This is campaign reconstruction, not a full DCS save game: cockpit switches,
player fuel/weapons, flying missiles, detailed damage and airborne trajectories
are not restored. Offline wall-clock time does not advance the campaign.
Current health of surviving damaged units resets on reconstruction.

For a new campaign, close DCS and move **both** the primary JSON and .prev file
to a backup folder. Do not remove only the primary: .prev would restore it.
Reinstalling or uninstalling preserves your campaign.

## Automatic diagnostics

No separate test sortie is required for these checks. On mission startup and
every 60 simulation seconds, SQE checks the campaign state, registered forces,
the last acknowledged checkpoint, and the UI heartbeat when available. The
window shows a short summary; **F10 → SQE Live → Automatic diagnostics** shows
details. The checks observe normal play and do not spend resources or fly sorties.

The local files are **SQE-Live/diagnostics-runtime.json** and
**SQE-Live/diagnostics-ui.json** under the DCS profile. PASS means only that the
named data/API check succeeded. Player sorties and objective completions remain
UNOBSERVED until events occur. A responsive UI hook does not prove that the
window rendered correctly. Actual AI tactics, roads and performance stay pending.

If a report is useful later, run **Collect-Diagnostics.cmd** from the extracted
package. It makes a local ZIP with those reports, installation metadata and up
to 200 SQE Live entries from the last 2000 DCS log lines. It never uploads,
includes no campaign saves, and does not modify the campaign. Local paths may
appear in the report. Reinstall the latest package to update the mission and UI/bridge together.

## Troubleshooting

- **F10 works but UI/save do not:** rerun installation after a DCS repair/update;
  confirm the same Saved Games profile is used by DCS.
- **UI says offline:** unpause and wait several seconds. Check the marked bridge
  and Saved Games/DCS/Logs/dcs.log for "SQE Live" / "SQE-Live".
- **No support available:** inspect ready aircraft, resources and flight limits.
  Automatic friendly operations use the same finite pool.
- **Campaign updates stopped:** keep the saves and dcs.log. Restarting may load
  the last valid checkpoint. Do not overwrite the save with guessed values.
- **No target progress:** the objective is a group; SAMs have specific radar
  requirements. Map marks reference an observed surviving group vehicle; use
  the targeting pod to locate the other vehicles.

## Remove

    powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\Uninstall-SQE-Live.ps1 -SavedGamesPath "C:\Users\YourName\Saved Games\DCS"

This removes exact package files and its marked script block. It preserves
saves, other hooks, unrelated script edits and backups.

## Validation still needed in DCS

The included automated tests cover state/commands, loss/recovery, logistics,
save failure/reload, UI callbacks with a fake DCS API, and the generated mission.
They cannot prove real DCS behavior. Development can continue without a manual
test from the user. When a DCS test environment is available, acceptance covers:

1. Mission opens, 17 ground groups spawn without terrain/building conflicts,
   player can start, and the window renders and returns mouse control.
2. Assignment, brief/coordinates and map marks agree with targets on terrain.
3. AI SEAD/strike attacks, CAP/escort, AWACS and tanker task/radio behavior.
4. AI landings recover inventory, convoys find usable roads, and sectors capture.
5. Two player sorties in one session; exit/reload preserves a destroyed target.
6. FPS/frame time on the actual PC during a two-hour campaign run.

No runtime flight test, rendering test, terrain road test, installer test on a
real Windows DCS installation or measured performance result is claimed.
Not yet converted: upstream pilot roster/morale, all aircraft/theatres, detailed
integrated air defence, carrier operations, exact airborne resume, multiplayer
authority, a geographic terrain map panel or automatic cockpit waypoint upload.

## Build from source

From the Source folder, Python 3.12 and Git:

    python -m venv .venv
    .venv\Scripts\pip install -r requirements.txt -r requirements-live-test.txt
    .venv\Scripts\python -m sqe.live.build
    .venv\Scripts\python -m unittest discover -s tests/live -v

Installer fixture tests run when PowerShell is on PATH (or SQE_TEST_PWSH points
to it). They are skipped if PowerShell is unavailable. To make the combined
install/source ZIP from a Git checkout, stage the reviewed files and run:

    .venv\Scripts\python -m sqe.live.package

Content is sqe/live/syria.json. Runtime modules are sqe/live/lua; installation
scripts are sqe/live/install. The original SQE generator remains available
separately; its end-of-day simulator never runs against this live world.

Based on SQE commit 807643b33fa88f19329177c6c420a5f8feb942e8 (0.41.135).
MIT license; original SQE, rxi/json.lua and dcs-scratchpad notices are included.
This project is not affiliated with Eagle Dynamics or presented as an upstream
SQE release.
