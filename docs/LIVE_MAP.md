# Native front map — 0.1.3

L08 adds a sector schematic inside the existing Operations window. It does not
change campaign mechanics or checkpoint schema/content (`1` / `syria-1`).

## Data and selection

`operations.lua` derives the same sector ownership, front flags, neighbours,
base names and objectives that Front plan uses. `map.lua` contains only layout
and local selection functions. There are no DCS calls or campaign writes there.
Coordinates determine row order and relative horizontal placement; rows are
spaced to avoid overlap. This is not a scaled geographic map. Links mean sector
adjacency, never verified roads or actual supply connectivity.

The current six sectors and five connections fit a 368 × 300 canvas. The adapter
preallocates eight sector buttons and 48 line panels (three per connection, at
most 16 connections). Refreshing ownership, text or selection reuses those
widgets. Invalid data or an exceeded bound falls back to Front plan; adding
more sectors requires a deliberate layout revision.

Clicking a sector selects its first task, or explicitly selects no task for an
empty sector. Task rows and Previous/Next stay within the selected sector.
All sectors removes the filter. Rows paginate in groups of four. A disappearing
selected task is not replaced automatically. Session changes clear selection
and filtering before choosing that session's first available target.

Accept, Brief and Mark require an exact, still-present selected target. They
submit the existing command with its target ID, current session and revision.
The mission core remains authoritative. Support still follows an accepted
assignment before a locally highlighted target, as in 0.1.2.

## Native adapter and lifecycle

`map_ui.lua` uses native Panel/Button widgets inserted into MapCanvas. Nodes
carry their current sector ID; callbacks do not capture old snapshot objects.
All native children hide with the window and when leaving the Map tab. Tab
switching reflows the target detail panel around the four task rows.

Blue/red colour is accompanied by owner text, front asterisks and base markers.
The selected sector receives a brighter skin. Amber connections cross opposing
ownership. A disconnected, stopped or older-than-ten-second snapshot disables
commands and node/target selection, colours nodes grey, removes amber links and
labels the view STALE / last known state. This includes pausing long enough for
the status heartbeat to age. Fresh data restores the live view.

Map construction/render errors are isolated so Front plan and F10 remain
available. The status and UI diagnostic report expose map errors. Invalid
snapshot layout can recover on the next valid publication. A native constructor
failure requires reloading the UI/mission environment after correcting it.

## API evidence and validation boundary

The native API patterns were inspected in these primary source projects:

- [dcs-scratchpad hook](https://github.com/rkusa/dcs-scratchpad/blob/main/Scripts/Hooks/scratchpad-hook.lua):
  Panel.new, Button.new, setBounds, insertWidget, addMouseUpCallback and mutation
  of a skin returned by getSkin. Existing MIT notices remain included.
- [DCS-SRS overlay dialog](https://github.com/ciribob/DCS-SimpleRadioStandalone/blob/master/Scripts/DCS-SRS/UI/DCS-SRS-Overlay.dlg):
  native Panel/Static dialog declarations, background colour and text skin
  fields. Used as API evidence; no SRS source is included in this implementation.

Thirteen map tests exercise Lua 5.1 layout/selection and the real hook through
widget/API doubles. They cover read-only browsing, physical capture, filtered
task identity, F10 correspondence, empty/removed targets, stale data, session
changes, pagination, layout bounds, a fixed widget pool, failure recovery and
packaged source identity. The installation fixtures also check both map modules.

An offline bounds/text preview uses substitute fonts and is only a geometry
review. DCS is not installed here. Actual native font/skin rendering, focus,
click handling in the cockpit and performance remain unobserved. Passing these
checks does not certify in-game compatibility or terrain navigation.
