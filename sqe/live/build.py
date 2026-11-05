"""Build a reusable Syria .miz and installable native UI. Python is authoring-only."""
from __future__ import annotations
import argparse
import contextlib
import copy
import hashlib
import io
import json
import re
import shutil
import subprocess
import tempfile
from datetime import datetime
from pathlib import Path
from . import VERSION

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def lua_literal(value):
    """Data only; preserve numeric table keys required by DCS payloads."""
    if value is None:
        return "nil"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, str):
        return '"' + value.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n").replace("\r", "\\r") + '"'
    if isinstance(value, (int, float)):
        if not __import__("math").isfinite(value):
            raise ValueError("Non-finite Lua number")
        return repr(value)
    if isinstance(value, (list, tuple)):
        return "{" + ",".join(lua_literal(v) for v in value) + "}"
    if isinstance(value, dict):
        return "{" + ",".join("[" + lua_literal(k) + "]=" + lua_literal(v) for k, v in value.items()) + "}"
    raise TypeError(type(value))


def content(campaign_id: str | None = None, scenario="israel"):
    from dcs.terrain import Syria
    from dcs import vehicles
    profiles={"israel":"syria.json","legacy":"syria_legacy.json"}
    if scenario not in profiles:
        raise ValueError("Unknown Syria scenario")
    spec = json.loads((HERE / profiles[scenario]).read_text())
    campaign_id=campaign_id or spec["id"]
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", campaign_id):
        raise ValueError("Campaign ID must contain only letters, digits, underscores or hyphens")
    spec["id"] = campaign_id
    spec["release"] = VERSION
    terrain = Syria()
    known_types = {v.id for v in vehicles.vehicle_map.values()}
    for zone in spec["zones"]:
        airport = terrain.airports[zone["airport"]]
        zone.update(x=airport.position.x + zone.pop("dx"), y=airport.position.y + zone.pop("dy"))
    zones = {z["id"]: z for z in spec["zones"]}
    for field in spec.get("airfields", []):
        a=terrain.airports[field["airport"]]
        if field["zone"] not in zones:
            raise ValueError("Unknown airfield sector")
        field.update(airport_id=a.id,x=a.position.x,y=a.position.y)
    for base in spec["bases"]:
        a = terrain.airports[base["airport"]]
        base.update(x=a.position.x, y=a.position.y, airport_id=a.id)
    for target in spec["targets"]:
        z = zones[target["zone"]]
        target.update(x=z["x"] + target.pop("dx"), y=z["y"] + target.pop("dy"))
        missing = set(target["types"]) - known_types
        if missing:
            raise ValueError(f"{target['id']}: unknown DCS vehicle types: {missing}")
    return spec, terrain


def make_aircraft_templates(mission):
    from dcs import planes, task
    from dcs.mapping import Point
    from sqe.models import Role
    from sqe.loadouts import (LoadoutLibrary, enemy_cap_loadout, enemy_arm_loadout,
                             enemy_strike_loadout)
    from sqe.aircraft import AIRCRAFT
    library = LoadoutLibrary()
    types = {"F-16C": planes.F_16C_50, "F-15C": planes.F_15C, "MiG-29S": planes.MiG_29S,
             "Su-24M": planes.Su_24M, "E-3A": planes.E_3A, "KC-135": planes.KC_135}
    out = {}
    for key, cls in types.items():
        side = "Russia" if key in ("MiG-29S", "Su-24M") else "USA"
        country = mission.country(side)
        group = mission.flight_group(country, "template-" + key, cls, None,
                                     Point(-250000, -80000, mission.terrain), altitude=6500)
        group.load_task_default_loadout(task.AWACS if key=="E-3A" else task.Refueling if key=="KC-135" else task.CAP)
        unit = group.units[0].dict()
        unit.pop("unitId", None)
        payloads = {}
        for role in ("STRIKE", "SEAD", "CAP", "ESCORT", "AWACS", "TANKER"):
            payload = copy.deepcopy(unit["payload"])
            if key in AIRCRAFT:
                payload["pylons"] = library.for_role(key, Role[role] if role in Role.__members__ else Role.CAP)
            elif key == "MiG-29S":
                payload["pylons"] = enemy_cap_loadout("MiG_29S")
            elif key == "Su-24M":
                payload["pylons"] = enemy_arm_loadout("Su_24M") if role == "SEAD" else enemy_strike_loadout("Su_24M")
            payloads[role] = payload
        out[key] = {"type": cls.id, "unit": unit, "payloads": payloads}
        country.plane_group.remove(group)
    return out


def mission_script(config):
    sources = {"json": "json.lua", "core": "core.lua", "director": "director.lua",
               "adapter": "dcs_adapter.lua", "diagnostics": "diagnostics.lua", "operations": "operations.lua", "ground": "ground.lua", "targets": "targets.lua", "supply": "supply.lua",
               "view": "view.lua", "runtime": "runtime.lua"}
    parts = ["-- SQE Live " + VERSION + "; MIT. One world, one campaign authority.\nlocal modules = {}\n"]
    for name, filename in sources.items():
        parts.append(f'modules["{name}"] = (function()\n' + (HERE / "lua" / filename).read_text() + "\nend)()\n")
    parts.append("local config = " + lua_literal(config) + "\n")
    parts.append("""
local ok,result=pcall(modules.runtime.start,config,modules,SQE_LIVE_STORAGE)
if ok then SQE_LIVE_RUNTIME=result
else
  pcall(env.error,"SQE Live startup failed: "..tostring(result))
  pcall(trigger.action.outText,"SQE Live could not start: "..tostring(result).."\\nYour save was not reset. See dcs.log.",60)
  if SQE_LIVE_STORAGE then
    pcall(function()
      local d=modules.diagnostics.new(config,modules.json,SQE_LIVE_STORAGE,"startup-failure")
      d:set("startup","FAIL",result,0)
      d:write({failed=tostring(result)},true)
    end)
    pcall(function()
      SQE_LIVE_STORAGE.publish(modules.json.encode({protocol=1,running=false,error=tostring(result),
        campaign=config.id,title=config.name,heartbeat=SQE_LIVE_STORAGE.now(),started_at=SQE_LIVE_STORAGE.now()}))
    end)
  end
end
""")
    return "".join(parts)


def build(output: Path, campaign_id=None, scenario="israel", include_legacy=True):
    from dcs import Mission, planes, task
    from dcs.mission import StartType
    from dcs.unit import Skill
    from dcs.triggers import TriggerOnce
    from dcs.condition import TimeAfter
    from dcs.action import DoScript
    from dcs.translation import String
    from sqe.loadouts import LoadoutLibrary
    from sqe.models import Role

    config, terrain = content(campaign_id,scenario)
    m = Mission(terrain=terrain)
    owners={z["id"]:z["owner"] for z in config["zones"]}
    for field in config.get("airfields", []):
        a=m.terrain.airports[field["airport"]]
        (a.set_blue if owners[field["zone"]]=="blue" else a.set_red)()
    for base in config["bases"]:
        a = m.terrain.airports[base["airport"]]
        (a.set_blue if base["side"] == "blue" else a.set_red)()
    home = m.terrain.airports["Ramat David"]
    g = m.flight_group_from_airport(m.country("USA"), "Viper Live", planes.F_16C_50,
                                   home, start_type=StartType.Cold, group_size=1)
    g.units[0].skill = Skill.Player
    g.units[0].pylons = LoadoutLibrary().for_role("F-16C", Role.STRIKE)
    g.frequency = 305
    config["player_unit"] = g.units[0].name
    config["flight_types"] = make_aircraft_templates(m)
    config["role_aircraft"] = {
        "blue": {"CAP": ["F-15C", "F-16C"], "ESCORT": ["F-15C", "F-16C"],
                 "SEAD": ["F-16C"], "STRIKE": ["F-16C"], "AWACS": ["E-3A"], "TANKER": ["KC-135"]},
        "red": {"CAP": ["MiG-29S"], "ESCORT": ["MiG-29S"], "SEAD": ["Su-24M"], "STRIKE": ["Su-24M"]}
    }
    config["arm_weapon_type"] = task.WeaponType.ARM.value
    config["auto_weapon_type"] = task.WeaponType.Auto.value
    m.start_time = datetime(*config["date"], 8, 0)
    m.weather.qnh = 760
    m.weather.season_temperature = 24
    m.description_text = String(
        config["name"]+"\n"
        "Continuous fictional single-player campaign on Syria. F-16C at Ramat David.\n"
        "Open operations: Ctrl+Shift+Q (installed UI) or radio F10 > SQE Live.\n"
        "Accept a task, read its coordinates, request support, fly, land and rearm, then accept another task.\n"
        "No next-day button or new mission is required during the session.\n"
        "AWACS 251.000 AM; tanker 252.000 AM; flight 305.000 AM.\n"
        "Check the on-screen SAVE status before quitting. Persistent destroyed units are restored next session.\n"
        "This is a development release: actual DCS flight and GUI validation remain outstanding.\n"
        "Not made or supported by Eagle Dynamics. Requires the Syria map and F-16C module."
    )
    trig = TriggerOnce(comment="SQE Live runtime")
    trig.add_condition(TimeAfter(1))
    trig.add_action(DoScript(String(mission_script(config))))
    m.triggerrules.triggers.append(trig)
    output.mkdir(parents=True, exist_ok=True)
    missions = output / "Missions"; missions.mkdir(exist_ok=True)
    miz = missions / "SQE_Live_Syria.miz"
    m.save(str(miz))
    scripts = output / "Scripts" / "SQE-Live"; scripts.mkdir(parents=True, exist_ok=True)
    for name in ("json.lua", "storage.lua", "storage_boot.lua", "view.lua", "map.lua", "map_ui.lua", "Operations.dlg"):
        shutil.copy2(HERE / "lua" / name, scripts / name)
    hooks = output / "Scripts" / "Hooks"; hooks.mkdir(parents=True, exist_ok=True)
    shutil.copy2(HERE / "lua" / "hook.lua", hooks / "SQE-Live.lua")
    for name in ("Install-SQE-Live.ps1", "Uninstall-SQE-Live.ps1", "Install.cmd",
                 "Collect-Diagnostics.ps1", "Collect-Diagnostics.cmd"):
        shutil.copy2(HERE / "install" / name, output / name)
    for source, name in ((ROOT / "LICENSE", "LICENSE.txt"),
                         (ROOT / "docs" / "LIVE_USER_GUIDE.md", "START_HERE.md"),
                         (ROOT / "docs" / "LIVE_USER_GUIDE_HE.md", "START_HERE_HE.md"),
                         (ROOT / "docs" / "LIVE_VALIDATION.md", "VALIDATION.md")):
        shutil.copy2(source, output / name)
    notices = output / "licenses"; notices.mkdir(exist_ok=True)
    shutil.copy2(HERE / "lua" / "JSON_LICENSE.txt", notices / "json-MIT.txt")
    shutil.copy2(HERE / "lua" / "SCRATCHPAD_LICENSE.txt", notices / "scratchpad-MIT.txt")
    (output / "content.json").write_text(json.dumps(config, indent=2), encoding="utf-8")
    try:
        source_commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True, stderr=subprocess.DEVNULL).strip()
    except (OSError, subprocess.CalledProcessError):
        source_commit = "source archive; see included VERSION.txt"
    (output / "VERSION.txt").write_text(f"SQE Live {VERSION}\nUpstream 807643b33fa88f19329177c6c420a5f8feb942e8\nSource {source_commit}\n")
    if scenario=="israel" and include_legacy:
        with tempfile.TemporaryDirectory() as temporary:
            previous=build(Path(temporary),scenario="legacy",include_legacy=False)
            shutil.copy2(previous,missions/"SQE_Live_Syria_Legacy.miz")
    hashes = {str(p.relative_to(output)).replace("\\", "/"): hashlib.sha256(p.read_bytes()).hexdigest()
              for p in sorted(output.rglob("*")) if p.is_file() and p.name != "SHA256SUMS.json"}
    (output / "SHA256SUMS.json").write_text(json.dumps(hashes, indent=2))
    return miz


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "dist" / "SQE-Live-Syria")
    parser.add_argument("--campaign-id")
    parser.add_argument("--scenario",choices=("israel","legacy"),default="israel")
    args = parser.parse_args()
    with contextlib.redirect_stdout(io.StringIO()):
        result = build(args.output, args.campaign_id,args.scenario)
    print(result)


if __name__ == "__main__":
    main()
