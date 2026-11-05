# Uploaded Foothold reference — scope of inspection

Reference provided by the user:
`Foothold_SY_extended_4.2.5_Multi_Language_Coldwar-Modern.zip`.
Package SHA256: `f26febe7126e6081d63da3f0eae82f263d7a2d5fa07922591da8f7ebad68339d`.
Inner mission member SHA256:
`2635e96bccd608809239b63dcf06c19508eb90f01798e22f8184da89b0317d41`.

The archive was inspected as data. No bundled executable or mission Lua was
executed. The mission/scripts were not imported into SQE Live or published here.

## Observations from the supplied files

- The mission declares Syria, contains 62 Client slots and 10 F-16C_50 entries.
  SQE Live instead creates one Player slot. These are different mission shapes.
- Embedded scripts include `footholdSyriaSetup.lua`, `zoneCommanderv2.lua`, a
  MOOSE build dated 2026-06-14, CTLD, AIEN, EWRS and localization/configuration.
  Their presence does not make those libraries dependencies of SQE Live.
- The setup assigns zone sides and explicit inter-zone supply/attack connections,
  with references to Ramat David, Rosh Pina and Ben Gurion. It also mentions
  Palmachim and Tel Nof. Its start-mode rules are not a definition of our blue
  starting territory; the user explicitly requested Israel as the blue rear area.
- Targeted engine-call inspection found native `coalition.addGroup` with a
  country ID and group category, and controller Mission tasks whose parameters
  contain `route.points`. Those structures agree with the corresponding pattern
  used in our adapter. Escort tasking uses a group ID and explicit parameters.
- This is a selective static inspection of entrypoints and representative calls,
  not a complete review of the approximately two-million-byte zone commander.
  It does not establish that our own task parameters, aircraft or UI work in DCS.

## Consequences for our project

All fifteen named Israeli fields in the project's pinned Syria catalogue now
start blue, with regional sectors and five support bases. The mission export and
runtime use the same ownership records. Existing campaigns keep a separate
Legacy mission. The changes are implemented independently, without copying the
reference's scripts, initial coalition settings or dependency stack.

The first aircraft/task/event integration pass is recorded in
[LIVE_INTEGRATION_AUDIT.md](LIVE_INTEGRATION_AUDIT.md), including two reproduced
failures and the independent runway-event fix. MOOSE-backed behavior must not
be assumed to exist in our standalone Lua code. Foothold does not supply evidence
for our custom native Operations window, storage bridge or long-session performance;
those remain separate work.
