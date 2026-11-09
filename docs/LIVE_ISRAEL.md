# Israel / Lebanon / Syria starting footprint — 0.1.16

The default single-player mission now starts with the represented Israeli
airfields blue, instead of using only the Ramat David/Golan rear area. This is a
fictional campaign layout on DCS Syria, not a surveyed polygon of national borders.
It covers the fifteen named Israeli airfields present in the pinned terrain data;
it does not add airports or detailed terrain absent from that map.

## Starting sectors and fields

- Galilee: Ramat David, Megiddo.
- Haifa/northern coast: Haifa.
- Upper Galilee: Rosh Pina, Kiryat Shmona.
- Sharon: Eyn Shemer, Herzliya.
- Central Israel: Tel Nof, Hatzor, Ben Gurion, Palmachim.
- Negev: Nevatim, Hatzerim, Teyman, Kedem.
- Golan approach remains blue. Thirty-two connected red sectors cover Lebanon
  and Syria and open progressively from Naqoura, Bint Jbeil and Quneitra.

There are 39 sectors in total. The schematic map accepts 48 nodes and 96 edges,
with a fixed widget pool. Clicking a sector lists its
airfields as well as its launch bases. Sector ownership controls the associated
airports in both the exported mission and the running campaign.

## Basing and logistics

The player remains an F-16C at Ramat David. Automatic/requested support can use
five finite bases: Ramat David, Tel Nof, Hatzor, Nevatim and Hatzerim. Palmachim
and the civilian fields are controlled airfields, not additional fighter wings.
The distribution is a gameplay abstraction, not a claim about actual basing.

The original blue total is distributed across these bases: 14 F-16C, 8 F-15C,
2 E-3A and 2 KC-135. Ramat David retains 6 F-16C and 4 F-15C; Tel Nof has 4 F-15C
and one each of AWACS/tanker; Hatzor has 4 F-16C; Nevatim has 2 F-16C and one each
of AWACS/tanker; Hatzerim has 2 F-16C. No airframes are created by capturing a field.

Central and Negev depots, fuel sites, garrisons and HAWK sites provide regional
infrastructure. The authored profile has 111 fixed target definitions, but only
the current objective of each active frontline sector is spawned. Twelve FARPs
extend supply routes. The existing 180-unit and nine-flight limits remain.
Regional stocks are 100/70/50/80/50 at the five blue bases, each for fuel, ammo
and supply. This is a larger logistics scenario than the old one-base profile;
old solo balance measurements cannot be carried over unchanged.

Only one moving same-side assault per destination is dispatched, across all
bases; a supply convoy remains tracked separately per base. This prevents five
bases from purchasing duplicate advances into the same sector. Regional depot
connections, reserve rules, physical arrival and finite aircraft still apply.

## Existing campaigns

The mission uses campaign ID `syria_israel_solo` / content `syria-israel-3`.
It starts a separate campaign. Existing checkpoints are neither translated into
the expanded layout nor reset. Their profile remains `syria_cedar_current` /
`syria-1`, available as `SQE_Live_Syria_Legacy.miz` in the same install bundle.
Open that Legacy mission to resume an old campaign. Both use the same hook/UI.

The authoring CLI accepts `--scenario israel` (default) or `--scenario legacy`.
An Israel build includes both mission files; a legacy-only build retains the
original profile. Installation/uninstallation handle the two exact mission names
and preserve unrelated missions and campaign saves.

## Tests and boundary

New profile checks cover field IDs, exported warehouse coalitions, runtime
ownership/recapture, alternative support bases, regional supply isolation,
finite aircraft, 39-node geometry/native callbacks, the ordered four-stage
chain, physical FARPs, duplicate advance prevention, six-hour accounting
fixtures and legacy checkpoint separation.
Installer contracts run against both legacy and expanded bundles.

The older regression fixtures deliberately use `syria_legacy.json`. New-profile
tests are separate, so passing old tests is not presented as expanded-map proof.
`LIVE_ISRAEL_RESULTS.json` records seven scripted six-hour runs of the new profile.
In the current-profile fixtures, steady requests are 8/8 and attrition requests
are 3/8; aircraft dispersion and losses can restrict support. This larger scenario
is not declared fully balanced from the earlier legacy results.
Those fixtures prescribe travel, losses and returns; they do not measure DCS
combat effectiveness, terrain clearance, actual driving, native rendering or FPS.

The user's Foothold mission supplied a static reference for mission/script
patterns; see LIVE_FOOTHOLD_REFERENCE.md for exactly what was inspected. No
Foothold code, mission, manual or executable is distributed with this project.
