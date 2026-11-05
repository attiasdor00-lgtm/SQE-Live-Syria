# I02 — native window, startup and storage boundary (0.1.10)

Review dated 2026-11-05. This is a source/contract audit, not native DCS acceptance.

## Primary implementation and API references

- [Scratchpad's native hook](https://github.com/rkusa/dcs-scratchpad/blob/main/Scripts/Hooks/scratchpad-hook.lua)
  demonstrates DialogLoader, Skin, Panel/Button, bounds, focus/cursor, a hidden
  top-level window that retains hotkeys, and mission/frame/stop callbacks. Our
  hook uses that existing MIT-attributed pattern; this review does not import
  additional Scratchpad code or establish undocumented widget internals.
- [Archived ED Control API text](https://github.com/Zaretto/acEFM/blob/master/DCS-API/DCS_ControlAPI.md)
  lists mission-load/simulation callbacks and documents that a callback return
  value can break the remaining hook chain. This is an archived copy, not proof
  of the user's current DCS ABI. Our callbacks deliberately return no values.
- [DCS-gRPC initialization instructions](https://github.com/DCS-gRPC/rust-server#readme)
  and [Witchcraft initialization](https://github.com/jboecker/dcs-witchcraft)
  show mission-environment injection before sanitizeModule. They do not prove
  our narrower file bridge works; the installed-bridge regression tests it
  independently. General io/os/lfs/require/package access remains removed from
  the simulated mission environment.

## Reproduced problems and corrections

Five of the seven initial UI regression cases failed against the 0.1.9 hook:
old same-second disk status accepted at cold load, old session accepted through
another mission load, widget errors escaping stop/load cleanup, and errors in
input/frame diagnostic paths escaping their callback boundary. These are
explicit contract fixtures, not observations from a running DCS installation.

LoadBegin now records both the last observed session and the session found in
the pre-load status file. Neither can become the next live connection, even if
its start timestamp equals the load boundary. Status is accepted only inside a
mission and at/after LoadBegin; a new session may initialize during a long terrain
load. Pending commands and selection are cleared independently of window updates.
The UI fixture now exposes newly initialized runtime status after LoadBegin,
instead of treating a pre-load disk snapshot as the new mission's publication.

Stop clears mission/current-status/pending state before touching widgets. Hiding
releases cursor and attempts text focus release before skin/visibility changes.
The stop diagnostic retains the ended session identity for attribution, with
in_mission/status_connected false; it cannot become a live connection.
Failures are recorded locally; user, button, map and toggle callbacks contain
exceptions and return no values to DCS. A subsequent update/toggle can recover
when the injected widget fault is removed. This cannot force a broken native
widget implementation to release input or guarantee native focus behavior.

The hook rejects non-finite heartbeat/start timestamps. The added timestamp
regression preserves a valid prior view rather than accepting an overflowing
numeric exponent as a new live session.

The session fence relies on an observed prior session or a readable pre-load
snapshot. It is not a nonce handshake with the engine. An unobserved file that
reappears during the same second after a failed/missing baseline read cannot be
unambiguously attributed from timestamps alone. Core command session/revision
checks remain the final mutation gate; this audit does not claim perfect process
identity or live synchronization under every filesystem failure.

## Installed bootstrap execution

A new PowerShell fixture installs the actual bundle into temporary DCS/profile
folders, then executes the resulting patched MissionScripting.lua in Lua 5.1.
The native ScriptingSystem.lua initialization is replaced with a supplied lfs
contract; the installed storage_boot.lua and storage.lua execute unchanged.
After the standard io/os/lfs sanitization, require/package/loadlib are also
removed. The captured bridge still saves/rotates/reads checkpoints, publishes
status, queues/acknowledges commands and writes/reads diagnostics using actual
temporary files. It does not re-enable the removed global APIs.

This checks installation order and captured filesystem references on Linux,
not the real DCS environment initializer, Windows filesystem behavior, registry
profile detection, UAC, game updates, or an actual DCS shutdown sequence.
Existing rotation, corrupt-primary recovery and failure-preservation tests remain
in the suite; no broader filesystem access was introduced by this change.

## Validation boundary and next task

Nine test cases were added: seven UI lifecycle cases on the shipped Israel
profile, and the installed-bootstrap test executed for both default and legacy
bundles. Existing UI/map fixtures now model the load
boundary explicitly. Full suite results are in LIVE_VALIDATION.md and the release
Validation logs. No checkpoint content ID/schema changes are needed.

I02's source/contract scope is complete. G02 accounting results are now in
LIVE_ISRAEL_BALANCE.md; L12 bounded long-session/product checks follow. Real widget skins,
hotkey registration/focus, DCS startup/sanitization, process shutdown and Windows
installation still require actual-engine observation. No FPS or flight assurance
is inferred from these tests.
