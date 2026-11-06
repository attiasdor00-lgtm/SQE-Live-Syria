"""Meaningful contract tests under Lua 5.1. Requires requirements-live-test.txt."""
from __future__ import annotations
import contextlib
import copy
import hashlib
import io
import json
import os
import shutil
import subprocess
import tempfile
import unittest
import zipfile
from pathlib import Path
from lupa.lua51 import LuaRuntime
from sqe.live.build import HERE, ROOT, build as build_scenario, lua_literal, mission_script

def build(output, campaign_id=None):
    """Retain legacy regression fixtures; test_geography covers the shipped default."""
    return build_scenario(output,campaign_id,scenario="legacy")

LUA = HERE / "lua"


class Harness:
    def __init__(self, config):
        self.lua = LuaRuntime(unpack_returned_tuples=True)
        self.g = self.lua.globals()
        self.g.cfg = self.lua.eval(lua_literal(config))
        self.g.mock = self.lua.execute((Path(__file__).parent / "dcs_mock.lua").read_text())
        self.g.mods = self.lua.table()
        for name, file in {"json":"json", "core":"core", "director":"director", "adapter":"dcs_adapter",
                           "diagnostics":"diagnostics", "operations":"operations", "ground":"ground", "targets":"targets", "supply":"supply", "view":"view", "map":"map", "runtime":"runtime"}.items():
            self.g.mods[name] = self.lua.execute((LUA / (file + ".lua")).read_text())
        self.lua.execute("mock.add_player(cfg);fs=mock.memory_storage()")

    def run(self, source):
        return self.lua.execute(source)

    def start(self):
        self.run("rt=mods.runtime.start(cfg,mods,fs); c=rt.core; a=c.adapter")
        return self

    def command(self, action, **kw):
        self.g.args = self.lua.eval(lua_literal(dict(action=action, **kw)))
        return self.run("""
            args.id=args.id or c:id("test-");args.session=args.session or c.session
            args.revision=args.revision or c.state.revision
            return c:command(args)
        """)


class ReleaseCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temporary = tempfile.TemporaryDirectory()
        cls.bundle = Path(cls.temporary.name) / "bundle"
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            build(cls.bundle)
        cls.config = json.loads((cls.bundle / "content.json").read_text())

    @classmethod
    def tearDownClass(cls):
        cls.temporary.cleanup()

    def setUp(self):
        self.h = Harness(self.config).start()

    def test_built_mission_contains_one_player_and_live_trigger(self):
        from dcs import lua
        with zipfile.ZipFile(self.bundle / "Missions/SQE_Live_Syria.miz") as z:
            self.assertIsNone(z.testzip())
            m = lua.loads(z.read("mission").decode())["mission"]
            self.assertEqual("Syria", m["theatre"])
            self.assertEqual(8*3600, m["start_time"])
            plane_groups = []
            for side in m["coalition"].values():
                for country in side["country"].values():
                    plane_groups.extend(country.get("plane", {}).get("group", {}).values())
            self.assertEqual(1, len(plane_groups))
            player = plane_groups[0]["units"][1]
            self.assertEqual("F-16C_50", player["type"])
            self.assertEqual("Player", player["skill"])
            self.assertGreater(len(player["payload"]["pylons"]), 4)
            self.assertEqual(1, len(m["trigrules"]))
            # Compile the actual packaged mission and trigger Lua in the target language.
            self.h.lua.execute("assert(loadstring(...))", z.read("mission").decode())
            trigger_text = m["trigrules"][1]["actions"][1]["text"]
            self.h.lua.execute("assert(loadstring(...))", trigger_text)
            other = Harness(self.config)
            other.g.SQE_LIVE_STORAGE = other.g.fs
            other.lua.execute(trigger_text)
            self.assertIsNotNone(other.g.SQE_LIVE_RUNTIME)
            other.run("mock.advance(400);assert(not SQE_LIVE_RUNTIME.failed)")

    def test_bundle_hashes_and_lua51_syntax(self):
        manifest = json.loads((self.bundle / "SHA256SUMS.json").read_text())
        for name, expected in manifest.items():
            self.assertEqual(expected, hashlib.sha256((self.bundle/name).read_bytes()).hexdigest(), name)
        for path in list(LUA.glob("*.lua")) + list(LUA.glob("*.dlg")):
            self.h.lua.execute("assert(loadstring(...))", path.read_text())

    def test_ui_layout_fits_window_without_overlapping_controls(self):
        self.h.lua.execute((LUA / "Operations.dlg").read_text())
        children = list(self.h.g.dialog.children.values())
        for p in [c.params.bounds for c in children]:
            self.assertGreaterEqual(p.x, 0)
            self.assertLessEqual(p.x+p.w, 940)
            self.assertLessEqual(p.y+p.h, 680)  # allowance for native header
        bounds = [c.params.bounds for c in children if c.params.visible]
        for i,p in enumerate(bounds):
            for q in bounds[i+1:]:
                overlap = p.x < q.x+q.w and q.x < p.x+p.w and p.y < q.y+q.h and q.y < p.y+p.h
                self.assertFalse(overlap)

    def test_repeated_commands_do_not_spend_twice(self):
        first = self.h.command("support", role="SEAD", target="south_sam", id="repeat")
        self.assertTrue(first.ok)
        before = self.h.run("return mods.json.encode(c.state.bases)")
        self.assertTrue(self.h.command("support", role="SEAD", target="south_sam", id="repeat").ok)
        self.assertEqual(before, self.h.run("return mods.json.encode(c.state.bases)"))
        self.assertEqual(1, self.h.run("local n=0;for _ in pairs(c.state.flights)do n=n+1 end;return n"))

    def test_old_session_and_revision_do_not_mutate(self):
        before = self.h.run("return mods.json.encode(c:snapshot())")
        self.assertFalse(self.h.command("accept", target="south_sam", session="old-session", id="stale").ok)
        self.assertFalse(self.h.command("accept", target="south_sam", revision=999, id="rev").ok)
        self.assertEqual(before, self.h.run("return mods.json.encode(c:snapshot())"))

    def test_spawn_failure_does_not_debit_stock(self):
        before = self.h.run("return mods.json.encode(c.state.bases)")
        self.h.run("mock.fail_spawn=true")
        self.assertFalse(self.h.command("support", role="CAP").ok)
        self.assertEqual(before, self.h.run("return mods.json.encode(c.state.bases)"))

    def test_radar_kill_completes_sead_and_enables_dead_in_same_session(self):
        self.assertTrue(self.h.command("accept", target="south_sam").ok)
        self.h.run('mock.kill("SQEL-G-south_sam-1-1")')
        self.assertEqual(1, self.h.g.c.state.completed)
        self.assertFalse(self.h.g.c.state.task)
        self.assertTrue(self.h.command("accept", target="south_sam").ok)
        self.assertEqual("DEAD", self.h.g.c.state.task.role)
        self.h.run('for i=2,4 do mock.kill("SQEL-G-south_sam-1-"..i) end')
        self.assertEqual(2, self.h.g.c.state.completed)
        self.assertEqual(0.2, self.h.run('return c:target_health("south_sam")'))

    def test_multiple_player_sorties_keep_campaign(self):
        self.h.run("""
            for i=1,2 do
                mock.emit({id=world.event.S_EVENT_TAKEOFF,initiator=mock.player})
                mock.emit({id=world.event.S_EVENT_TAKEOFF,initiator=mock.player})
                mock.emit({id=world.event.S_EVENT_LAND,initiator=mock.player})
            end
            assert(c.state.pilot.sorties==2 and c.state.pilot.landings==2)
        """)

    def test_loss_deduplicated_and_only_survivors_recover(self):
        self.assertTrue(self.h.command("support", role="CAP").ok)
        self.h.run("""
            for _,f in pairs(c.state.flights) do flight=f end
            mock.kill("SQEL-A-"..flight.id.."-1")
            mock.land_flight(a,flight)
            assert(flight.status=="COMPLETE")
            assert(c.state.maintenance[1].count==1)
            c:tick(601)
            assert(c.state.bases.ramat.ready["F-15C"]==7)
            assert(c:validate_save(c:snapshot()))
        """)

    def test_enemy_or_remote_landing_does_not_return_stock(self):
        self.assertTrue(self.h.command("support", role="CAP").ok)
        self.h.run("""
            for _,f in pairs(c.state.flights) do flight=f end
            local g=mock.groups[a.air_groups[flight.id]]
            for _,u in ipairs(g.units) do
                mock.emit({id=world.event.S_EVENT_LAND,initiator=u,place={getID=function()return 999 end}})
            end
            assert(flight.status~="COMPLETE" and #c.state.maintenance==0)
        """)

    def test_landed_wingman_recovers_when_last_airborne_member_dies(self):
        self.assertTrue(self.h.command("support", role="CAP").ok)
        self.h.run("""
            for _,f in pairs(c.state.flights) do flight=f end
            local u=mock.groups[a.air_groups[flight.id]].units[1]
            local b=c.base_defs.ramat;u.point={x=b.x,y=100,z=b.y}
            mock.emit({id=world.event.S_EVENT_LAND,initiator=u})
            mock.kill("SQEL-A-"..flight.id.."-2")
            a:observe()
            assert(flight.status=="COMPLETE" and c.state.maintenance[1].count==1)
        """)

    def test_runway_events_player_settles_and_deduplicates(self):
        self.h.run("""
            mock.emit({id=54,initiator=mock.player})
            mock.emit({id=3,initiator=mock.player})
            assert(c.state.pilot.sorties==1)
            mock.emit({id=55,initiator=mock.player})
            mock.advance(10);assert(c.state.pilot.landings==0)
            mock.advance(10);assert(c.state.pilot.landings==1)
            mock.emit({id=4,initiator=mock.player})
            assert(c.state.pilot.landings==1)
        """)

    def test_runway_touch_requires_settled_ai_at_assigned_base(self):
        self.h.command("support", role="CAP")
        self.h.run("""
            for _,f in pairs(c.state.flights) do flight=f end
            local b=c.base_defs[flight.base]
            for _,u in ipairs(mock.groups[a.air_groups[flight.id]].units) do
                u.point={x=b.x,y=100,z=b.y};u.velocity={x=40,y=0,z=0}
                mock.emit({id=55,initiator=u,place={getID=function()return b.airport_id end}})
            end
            mock.advance(30);assert(flight.status~="COMPLETE")
            for _,u in ipairs(mock.groups[a.air_groups[flight.id]].units) do u.velocity={x=0,y=0,z=0} end
            mock.advance(10);assert(flight.status~="COMPLETE")
            mock.advance(10);assert(flight.status=="COMPLETE")
            assert(#c.state.maintenance==1 and c.state.maintenance[1].count==2)
        """)

    def test_touch_and_go_does_not_recover_aircraft(self):
        self.h.command("support", role="CAP")
        self.h.run("""
            for _,f in pairs(c.state.flights) do flight=f end
            local b=c.base_defs[flight.base]
            for _,u in ipairs(mock.groups[a.air_groups[flight.id]].units) do
                u.point={x=b.x,y=100,z=b.y}
                mock.emit({id=55,initiator=u,place={getID=function()return b.airport_id end}})
            end
            mock.advance(6)
            for _,u in ipairs(mock.groups[a.air_groups[flight.id]].units) do
                u.point.y=500;mock.emit({id=54,initiator=u})
            end
            mock.advance(30)
            assert(flight.status~="COMPLETE" and #c.state.maintenance==0)
            assert(next(a.contacts)==nil)
        """)

    def test_departed_wingman_cannot_be_recovered_by_later_landing(self):
        self.h.command("support", role="CAP")
        self.h.run("""
            for _,f in pairs(c.state.flights) do flight=f end
            local b=c.base_defs[flight.base]
            local units=mock.groups[a.air_groups[flight.id]].units
            units[1].point={x=b.x,y=100,z=b.y}
            mock.emit({id=4,initiator=units[1]})
            units[1].point.y=500;mock.emit({id=54,initiator=units[1]})
            units[2].point={x=b.x,y=100,z=b.y}
            mock.emit({id=4,initiator=units[2]})
            a:observe()
            assert(flight.status~="COMPLETE" and #c.state.maintenance==0)
            mock.kill(units[1].name);a:observe()
            assert(flight.status=="COMPLETE" and c.state.maintenance[1].count==1)
        """)

    def test_touch_without_place_requires_runway_and_velocity(self):
        self.h.command("support", role="CAP")
        self.h.run("""
            for _,f in pairs(c.state.flights) do flight=f end
            local b=c.base_defs[flight.base]
            local units=mock.groups[a.air_groups[flight.id]].units
            for _,u in ipairs(units) do
                u.point={x=b.x,y=100,z=b.y};mock.emit({id=55,initiator=u})
            end
            mock.advance(20);assert(flight.status~="COMPLETE")
            mock.surface=land.SurfaceType.RUNWAY
            for _,u in ipairs(units) do
                mock.emit({id=55,initiator=u});u.getVelocity=false
            end
            mock.advance(20);assert(flight.status~="COMPLETE")
            for _,u in ipairs(units) do u.getVelocity=function()return {x=0/0,y=0,z=0} end end
            mock.advance(20);assert(flight.status~="COMPLETE")
            for _,u in ipairs(units) do u.getVelocity=function()return {x=0,y=0,z=0} end end
            mock.advance(20);assert(flight.status=="COMPLETE")
        """)

    def test_touch_cannot_recover_at_wrong_or_captured_airfield(self):
        self.h.command("support", role="CAP")
        self.h.run("""
            for _,f in pairs(c.state.flights) do flight=f end
            local b=c.base_defs[flight.base]
            local units=mock.groups[a.air_groups[flight.id]].units
            for _,u in ipairs(units) do
                u.point={x=b.x,y=100,z=b.y}
                mock.emit({id=55,initiator=u,place={getID=function()return 999 end}})
            end
            mock.advance(20);assert(flight.status~="COMPLETE")
            for _,u in ipairs(units) do
                mock.emit({id=55,initiator=u,place={getID=function()return b.airport_id end}})
            end
            c.state.zones[b.zone].owner="red"
            a:observe()
            assert(next(a.contacts)==nil and #c.state.maintenance==0)
        """)

    def test_legacy_event_constants_still_work_without_runway_events(self):
        self.h.run("""
            world.event.S_EVENT_RUNWAY_TAKEOFF=nil;world.event.S_EVENT_RUNWAY_TOUCH=nil
            mock.emit({id=3,initiator=mock.player});mock.emit({id=4,initiator=mock.player})
            assert(c.state.pilot.sorties==1 and c.state.pilot.landings==1)
        """)

    def test_rtb_clears_engagement_tasks(self):
        self.h.command("support", role="CAP")
        self.h.run("""
            for _,f in pairs(c.state.flights) do
                assert(a:control_flight(f,"rtb"))
                local route=mock.groups[a.air_groups[f.id]]:getController().task.params.route
                assert(#route.points==3 and route.points[3].type=="Land")
                for _,t in ipairs(route.points[1].task.params.tasks) do assert(t.id=="WrappedAction") end
            end
        """)

    def test_attack_route_enables_assigned_fire_and_escort_has_air_targets(self):
        self.h.command("support", role="SEAD", target="south_sam")
        self.h.command("support", role="ESCORT")
        self.h.run("""
            for _,f in pairs(c.state.flights) do
                local route=mock.groups[a.air_groups[f.id]].data.route
                if f.role=="SEAD" then
                    local tasks=route.points[2].task.params.tasks
                    assert(tasks[1].params.action.params.name==0 and tasks[1].params.action.params.value==2)
                    assert(tasks[2].id=="AttackGroup" and tasks[2].params.weaponType==32768)
                else
                    local tasks=route.points[1].task.params.tasks;local escort=tasks[#tasks]
                    assert(escort.id=="Escort" and escort.params.targetTypes[1]=="Planes")
                end
            end
        """)

    def test_safe_spawn_rejects_water_without_spending(self):
        self.h.run("""
            local before=c.state.bases.ramat.resources.supply
            land.getSurfaceType=function()return 2 end
            assert(not mods.director.dispatch(c,c.base_defs.ramat,"ASSAULT","south","golan"))
            assert(c.state.bases.ramat.resources.supply==before)
        """)

    def test_convoy_needs_surviving_vehicles_at_destination(self):
        self.h.run("""
            c.state.bases.ramat.resources.fuel=20
            assert(mods.director.dispatch(c,c.base_defs.ramat,"SUPPLY","galilee","blue_depot"))
            for _,s in pairs(c.state.shipments)do ship=s end
            local g=mock.groups[a.ship_groups[ship.id]]
            g.units[1].point={x=ship.destination.x,y=100,z=ship.destination.y}
            -- A dead vehicle's last nearby position cannot deliver remote survivors.
            mock.kill(g.units[1].name)
            a:observe();assert(ship.status=="MOVING")
            assert(c.state.bases.ramat.resources.fuel==20)
            mock.deliver(a,ship);a:observe()
            assert(ship.status=="DELIVERED" and c.state.bases.ramat.resources.fuel==35)
            a:observe();assert(c.state.bases.ramat.resources.fuel==35)
        """)

    def test_destroyed_fuel_source_blocks_fuel_replenishment(self):
        self.h.run("""
            for i=1,#c.target_defs.blue_fuel.types do c:lose_target("blue_fuel",i) end
            c.state.bases.ramat.resources.fuel=10;c.state.bases.ramat.resources.ammo=10
            mods.director.dispatch(c,c.base_defs.ramat,"SUPPLY","galilee","blue_depot")
            for _,s in pairs(c.state.shipments)do mock.deliver(a,s)end
            a:observe()
            assert(c.state.bases.ramat.resources.fuel==10 and c.state.bases.ramat.resources.ammo==30)
        """)

    def test_territory_requires_arrival_and_elimination_of_defenders(self):
        self.h.run("""
            mods.director.dispatch(c,c.base_defs.ramat,"ASSAULT","south","golan")
            for _,s in pairs(c.state.shipments)do ship=s end
            mock.deliver(a,ship);a:observe()
            assert(c.state.zones.south.owner=="red" and ship.status=="MOVING")
            for i=1,#c.target_defs.south_armor.types do mock.kill("SQEL-G-south_armor-1-"..i) end
            a:observe()
            assert(c.state.zones.south.owner=="blue" and ship.status=="ARRIVED")
            local occupied=c:active_count()
            assert(occupied>=4)
            mods.director.dispatch(c,c.base_defs.damascus,"ASSAULT","south","marj")
            for _,s in pairs(c.state.shipments)do if s.side=="red" then counter=s end end
            mock.deliver(a,counter);a:observe()
            assert(c.state.zones.south.owner=="blue" and counter.status=="MOVING")
            for i=1,4 do mock.kill("SQEL-C-"..ship.id.."-"..i) end
            a:observe()
            assert(c.state.zones.south.owner=="red" and counter.status=="ARRIVED")
        """)

    def test_ground_garrisons_count_toward_budget_and_repair_respects_budget(self):
        self.h.run("""
            for i=1,#c.target_defs.south_armor.types do c:lose_target("south_armor",i) end
            mods.director.dispatch(c,c.base_defs.ramat,"ASSAULT","south","golan")
            for _,s in pairs(c.state.shipments)do ship=s end
            local before=c:active_count();mods.director.arrived(c,ship.id)
            assert(before==c:active_count())
            c.config.unit_budget=c:active_count()
            assert(not c:launch("CAP","blue",nil,false))
            assert(not mods.director.dispatch(c,c.base_defs.ramat,"ASSAULT","marj","south"))
        """)

    def test_restore_preserves_losses_resources_objective_and_clock(self):
        self.h.command("accept", target="south_sam")
        self.h.command("support", role="CAP")
        self.h.run("""
            for _,f in pairs(c.state.flights)do flight=f end
            mock.kill("SQEL-A-"..flight.id.."-1")
            mock.kill("SQEL-G-marj_armor-1-1")
            c:tick(100)
            saved=c:snapshot()
            resumed=mods.core.new(cfg,a,saved,"new-session",mods.targets,mods.supply)
            assert(resumed.state.time==100)
            assert(resumed.state.task.target=="south_sam")
            assert(not resumed.state.targets.marj_armor.alive["1"])
            assert(resumed.state.bases.ramat.resources.fuel==92)
            assert(#resumed.state.maintenance==1 and resumed.state.maintenance[1].count==1)
            assert(next(resumed.state.flights)==nil)
            assert(resumed:validate_save(resumed:snapshot()))
        """)

    def test_invalid_nested_saves_rejected(self):
        cases = [
            's.maintenance[1]={base="bogus",aircraft="F-16C",count=1,due=100}',
            's.targets.south_sam.positions["1"]={x="bad",y=2}',
            's.targets.south_sam.alive["1"]=1',
            's.bases.ramat.ready["F-16C"]=1000',
            's.pilot.sorties=-1',
            's.shipments.bad={id="bad"}',
            's.task={target="blue_depot",role="STRIKE",accepted=0}',
            's.log[1]={time=0,text={}}',
            's.maintenance[1]={base="ramat",aircraft="F-16C",count=2,due=10}',
        ]
        for corruption in cases:
            with self.subTest(corruption=corruption):
                self.assertFalse(self.h.run("local s=c:snapshot();"+corruption+";return c:validate_save(s)")[0])

    def test_runtime_recovers_valid_previous_save_and_refuses_total_corruption(self):
        h = Harness(self.config)
        h.run("""
            local probe=mods.core.new(cfg,mods.adapter.new(cfg,mods.core.copy),nil,"old",mods.targets,mods.supply)
            probe.state.completed=4
            fs.files[cfg.id..".prev"]=mods.json.encode(probe:snapshot())
            fs.files[cfg.id]="truncated"
        """)
        h.start()
        self.assertTrue(h.g.rt.used_backup)
        self.assertEqual(4, h.g.c.state.completed)
        broken = Harness(self.config)
        broken.run('fs.files[cfg.id]="{";fs.files[cfg.id..".prev"]="{"')
        ok = broken.run("local ok=pcall(mods.runtime.start,cfg,mods,fs);return ok")
        self.assertFalse(ok)
        self.assertEqual("{", broken.g.fs.files[self.config["id"]])

    def test_file_bridge_commands_and_f10_share_authority(self):
        self.h.run("""
            fs.queue.cmd=mods.json.encode({id="cmd",session=c.session,revision=c.state.revision,action="accept",target="south_sam"})
            mock.advance(2)
            assert(c.state.task.target=="south_sam" and fs.queue.cmd==nil)
            rt:invoke("abort")
            assert(c.state.task==false)
            local view=mods.json.decode(fs.status_text)
            assert(view.results.cmd.ok and view.protocol==1)
            assert(view.tasks[1].coordinates and view.tasks[1].elevation_ft)
        """)

    def test_native_hook_buttons_drive_live_commands_and_reject_stale_sessions(self):
        self.h.g.lua_path=str(LUA)
        self.h.g.ui=self.h.lua.execute((Path(__file__).parent/"ui_mock.lua").read_text())
        self.h.lua.execute((LUA/"hook.lua").read_text())
        self.h.run("""
            assert(ui.handler,ui.last_log)
            ui.load_mission()
            ui.hotkeys["Ctrl+Shift+q"]()
            assert(ui.window.cursor and ui.window.Accept.enabled)
            ui.window.Accept.click()
            assert(not ui.window.Accept.enabled)
            mock.advance(2);ui.handler.onSimulationFrame()
            assert(c.state.task and ui.window.Status.text:find("OK:",1,true))
            ui.window.SEAD.click()
            mock.advance(2);ui.handler.onSimulationFrame()
            assert(next(c.state.flights) and ui.window.Status.text:find("dispatched",1,true))
            ui.window.Hold.click();mock.advance(2);ui.handler.onSimulationFrame()
            for _,f in pairs(c.state.flights)do assert(f.status=="HOLD")end
            ui.window.Push.click();mock.advance(2);ui.handler.onSimulationFrame()
            for _,f in pairs(c.state.flights)do assert(f.status=="ENROUTE")end
            ui.window.Save.click();mock.advance(2);ui.handler.onSimulationFrame()
            assert(ui.window.Status.text:find("Saved",1,true))
            ui.window.Close.click()
            assert(not ui.window.cursor and not ui.window.Overview.visible)
            mock.clock=mock.clock+20;ui.handler.onSimulationFrame()
            assert(not ui.window.Accept.enabled)
            ui.handler.onSimulationStop();ui.hotkeys["Ctrl+Shift+q"]()
            assert(not ui.window.cursor)
        """)

    def test_twenty_resume_cycles_do_not_duplicate_airframes(self):
        self.h.command("support", role="CAP")
        self.h.run("""
            for _,f in pairs(c.state.flights)do mock.kill("SQEL-A-"..f.id.."-1")end
            local current=c
            for i=1,20 do
                current=mods.core.new(cfg,a,mods.json.decode(mods.json.encode(current:snapshot())),"resume-"..i,mods.targets,mods.supply)
                assert(current:validate_save(current:snapshot()))
            end
            assert(#current.state.maintenance==1)
            current:tick(601)
            assert(current.state.bases.ramat.ready["F-15C"]==7)
        """)

    def test_campaign_reports_save_failures_without_claiming_success(self):
        self.h.run("""
            fs.fail_save=true
            local result=c:command({id="save-failure",session=c.session,action="save"})
            assert(not result.ok and result.message:find("SAVE ERROR",1,true))
            mock.advance(2)
            assert(not rt.failed)
            assert(mods.json.decode(fs.status_text).save_status:find("SAVE ERROR",1,true))
        """)

    def test_peripheral_failures_do_not_stop_campaign_and_recover(self):
        cases = [
            ("fs", "publish", "error('disk offline')", "status_channel"),
            ("fs", "publish", "return false,'disk offline'", "status_channel"),
            ("fs", "commands", "error('queue unavailable')", "command_read"),
            ("fs", "commands", "return nil,'queue unavailable'", "command_read"),
            ("fs", "report", "error('report unavailable')", "diagnostic_file"),
            ("missionCommands", "addCommandForGroup", "error('menu unavailable')", "f10_menu"),
        ]
        for owner, method, failure, check in cases:
            with self.subTest(method=method, failure=failure):
                h=Harness(self.config).start()
                h.run(f"original={owner}.{method};{owner}.{method}=function(){failure} end;rt.menu_signature=nil")
                h.run("mock.advance(200);assert(not rt.failed and c.state.time==200);assert(next(c.state.flights))")
                self.assertEqual("FAIL", h.g.rt.diagnostics.checks[check].status)
                h.run(f"{owner}.{method}=original;mock.advance(62)")
                self.assertEqual("PASS", h.g.rt.diagnostics.checks[check].status)

    def test_ack_failure_does_not_repeat_support_purchase(self):
        self.h.run("""
            local ack=fs.ack
            fs.ack=function()error('queue locked')end
            fs.queue.support=mods.json.encode({id='support',session=c.session,revision=c.state.revision,
                action='support',role='CAP'})
            mock.advance(2)
            local bases=mods.json.encode(c.state.bases)
            mock.advance(4)
            assert(not rt.failed and fs.queue.support)
            assert(rt.diagnostics.checks.command_ack.status=='FAIL')
            assert(mods.json.encode(c.state.bases)==bases)
            local n=0;for _ in pairs(c.state.flights)do n=n+1 end;assert(n==1)
            fs.ack=ack;mock.advance(2)
            assert(not fs.queue.support and rt.diagnostics.checks.command_ack.status=='PASS')
        """)

    def test_checkpoint_exception_is_reported_then_readback_recovers(self):
        self.h.run("""
            local save=fs.save;local previous=fs.files[cfg.id]
            fs.save=function()error('disk offline')end
            mock.advance(62)
            assert(not rt.failed and c.state.time==62 and rt.last_save==0)
            assert(fs.files[cfg.id]==previous and rt.diagnostics.checks.checkpoint_write.status=='FAIL')
            fs.save=save;mock.advance(60)
            assert(rt.diagnostics.checks.checkpoint_write.status=='PASS')
            assert(rt.diagnostics.checks.save_readback.status=='PASS' and rt.last_save>0)
        """)

    def test_invalid_runtime_inventory_stops_before_overwriting_checkpoint(self):
        self.h.run("""
            local previous=fs.files[cfg.id];local writes=fs.writes
            c.state.bases.ramat.ready['F-16C']=10000
            assert(not a:save(c:snapshot()))
            assert(rt.failed and rt.diagnostics.checks.campaign_updates.status=='FAIL')
            mock.advance(40)
            mock.emit({id=world.event.S_EVENT_MISSION_END})
            assert(fs.files[cfg.id]==previous and fs.writes==writes and c.state.time==0)
            assert(mods.json.decode(fs.status_text).running==false)
        """)

    def test_engine_exception_stops_updates_and_retains_checkpoint(self):
        self.h.run("""
            local previous=fs.files[cfg.id]
            a.observe=function()error('unexpected world error')end
            mock.advance(2);local stopped_at=c.state.time;mock.advance(30)
            assert(rt.failed and c.state.time==stopped_at and fs.files[cfg.id]==previous)
            local report=mods.json.decode(fs.reports.runtime)
            assert(report.stopped and report.summary:find('issue',1,true))
        """)

    def test_partial_startup_rolls_back_owned_groups_without_saving(self):
        h=Harness(self.config)
        h.run("""
            local spawn=coalition.addGroup;local count=0
            coalition.addGroup=function(...)
                count=count+1;if count==3 then error('injected startup failure')end
                return spawn(...)
            end
            local ok,why=pcall(mods.runtime.start,cfg,mods,fs)
            assert(not ok and tostring(why):find('World initialization failed',1,true))
            assert(count==3 and fs.writes==0 and mock.player:isExist())
            for name,g in pairs(mock.groups)do if name~='player' then assert(not g:isExist()) end end
            local report=mods.json.decode(fs.reports.runtime)
            assert(report.checks[1].id=='startup' and report.checks[1].status=='FAIL')
        """)

    def test_embedded_startup_failure_is_reported_without_resetting_save(self):
        h=Harness(self.config)
        h.run("fs.files[cfg.id]='{';SQE_LIVE_STORAGE=fs;fs.publish=function()error('status disk failure')end")
        h.lua.execute(mission_script(self.config))
        self.assertIsNone(h.g.SQE_LIVE_RUNTIME)
        self.assertEqual("{", h.g.fs.files[self.config["id"]])
        report=json.loads(h.g.fs.reports.runtime)
        self.assertTrue(report["stopped"])
        self.assertEqual("FAIL", report["checks"][0]["status"])
        self.assertIn("NOT been reset", report["checks"][0]["detail"])

    def test_diagnostics_observe_without_mutating_or_claiming_flight_validation(self):
        self.h.run("""
            local before=mods.json.encode(c:snapshot());local writes=fs.writes
            rt.diagnostics:inspect(rt);rt.diagnostics:write(rt,true)
            assert(before==mods.json.encode(c:snapshot()) and fs.writes==writes)
            assert(rt.diagnostics.checks.player_sorties.status=='UNOBSERVED')
            assert(rt.diagnostics.checks.combat_results.status=='UNOBSERVED')
            assert(rt.diagnostics.checks.ui_hook.status=='UNOBSERVED')
            local report=mods.json.decode(fs.reports.runtime)
            assert(report.flight_validation:find('UNOBSERVED',1,true))
            local ui={session=c.session,heartbeat=fs.now(),window_created=true,status_connected=true,error=false}
            fs.report('ui',mods.json.encode(ui));rt.diagnostics:inspect(rt)
            assert(rt.diagnostics.checks.ui_hook.status=='PASS')
            ui.heartbeat=fs.now()-91;fs.report('ui',mods.json.encode(ui));rt.diagnostics:inspect(rt)
            assert(rt.diagnostics.checks.ui_hook.status=='WARN')
            ui.session='previous';fs.report('ui',mods.json.encode(ui));rt.diagnostics:inspect(rt)
            assert(rt.diagnostics.checks.ui_hook.status=='UNOBSERVED')
            fs.files[cfg.id]='truncated';rt.diagnostics:inspect(rt)
            assert(rt.diagnostics.checks.save_readback.status=='FAIL' and fs.files[cfg.id]=='truncated')
        """)

    def test_native_hook_reports_creation_failure_and_recovers(self):
        self.h.g.lua_path=str(LUA)
        self.h.g.ui=self.h.lua.execute((Path(__file__).parent/"ui_mock.lua").read_text())
        self.h.run("""
            loader=require('DialogLoader');spawn=loader.spawnDialogFromFile
            loader.spawnDialogFromFile=function()error('widget failure')end
        """)
        self.h.lua.execute((LUA/"hook.lua").read_text())
        self.h.run("""
            ui.load_mission()
            rt.diagnostics:inspect(rt)
            assert(rt.diagnostics.checks.ui_hook.status=='FAIL')
            assert(not mods.json.decode(fs.reports.ui).window_created)
            loader.spawnDialogFromFile=spawn
            mock.advance(6);ui.handler.onSimulationFrame();rt.diagnostics:inspect(rt)
            assert(not rt.failed and rt.diagnostics.checks.ui_hook.status=='PASS')
            assert(ui.window.Status.text:find('Automatic checks',1,true))
            ui.handler.onSimulationStop();rt.diagnostics:inspect(rt)
            assert(rt.diagnostics.checks.ui_hook.status=='WARN')
        """)

    def test_six_hour_runtime_with_losses_landings_and_supplies(self):
        self.h.run("""
            local peak=0
            for interval=1,720 do
                mock.advance(30)
                assert(not rt.failed,tostring(rt.failed))
                for id,f in pairs(c.state.flights) do
                    if f.status~="COMPLETE" and c.state.time-f.started>240 then
                        if interval%5==0 then
                            for _,u in ipairs(mock.groups[a.air_groups[id]].units)do if u.alive then mock.kill(u.name);break end end
                        end
                        mock.land_flight(a,f)
                    end
                end
                for _,s in pairs(c.state.shipments)do
                    if s.status=="MOVING" and c.state.time-s.started>900 then mock.deliver(a,s) end
                end
                if interval%40==0 then
                    local ok,why=c:validate_save(c:snapshot());assert(ok,why)
                end
                assert(c:active_count()<=cfg.unit_budget)
                peak=math.max(peak,c:active_count())
            end
            assert(c.state.time==21600)
            assert(fs.writes>=720 and #c.state.log<=80)
            assert(c.state.bases.ramat.ready["F-15C"]<=8)
            local n=0;for _ in pairs(a.registry)do n=n+1 end
            assert(n<=cfg.unit_budget+30,"registry grew without bound")
            local saved=mods.json.decode(fs.files[cfg.id])
            assert(c:validate_save(saved))
        """)

    def test_cas_requires_last_defender_and_legacy_remainder_stays_taskable(self):
        self.assertTrue(self.h.command("accept",target="south_armor").ok)
        self.h.run("""
            for i=1,4 do mock.kill('SQEL-G-south_armor-1-'..i) end
            assert(c.state.task and c.state.completed==0 and c:target_health('south_armor')==0.2)
            local found=false;for _,t in ipairs(c:tasks())do if t.id=='south_armor' then found=true end end;assert(found)
            local legacy=c:snapshot();legacy.task=false;legacy.completed=1
            local resumed=mods.core.new(cfg,a,legacy,'legacy-checkpoint',mods.targets,mods.supply)
            found=false;for _,t in ipairs(resumed:tasks())do if t.id=='south_armor' then found=true end end;assert(found)
            assert(resumed.state.completed==1 and resumed:validate_save(resumed:snapshot()))
            mock.kill('SQEL-G-south_armor-1-5')
            assert(not c.state.task and c.state.completed==1)
        """)

    def test_live_radar_is_taskable_even_below_general_strike_threshold(self):
        self.h.run("""
            for i=2,5 do mock.kill('SQEL-G-south_sam-1-'..i) end
            local found=false
            for _,t in ipairs(c:tasks())do if t.id=='south_sam' then found=t.role=='SEAD' end end
            assert(found and c:target_health('south_sam')==0.2)
        """)
        self.assertTrue(self.h.command("accept",target="south_sam").ok)
        self.h.run("mock.kill('SQEL-G-south_sam-1-1');assert(c.state.completed==1 and not c.state.task)")

    def test_sector_plan_follows_defenders_column_and_physical_capture(self):
        self.h.run("""
            local function sector(id)
                for _,s in ipairs(rt:view().front.sectors)do if s.id==id then return s end end
            end
            assert(sector('south').stage=='WEAKEN_DEFENDERS')
            assert(sector('marj').stage=='BEHIND_FRONT')
            assert(rt:view().front.recommended_task=='south_armor')
            for i=1,3 do mock.kill('SQEL-G-south_armor-1-'..i) end
            assert(sector('south').stage=='AWAIT_ADVANCE' and sector('south').defenders==2)
            mods.director.logistics(c)
            for _,s in pairs(c.state.shipments)do if s.side=='blue' and s.zone=='south' then column=s end end
            assert(column and sector('south').stage=='COVER_ADVANCE')
            for i=4,5 do mock.kill('SQEL-G-south_armor-1-'..i) end
            assert(sector('south').stage=='AWAIT_ARRIVAL' and c.state.zones.south.owner=='red')
            mock.deliver(a,column);a:observe()
            assert(sector('south').stage=='HELD' and sector('marj').stage=='WEAKEN_DEFENDERS')
            assert(c.state.zones.south.owner=='blue')
        """)

    def test_sector_plan_explains_supply_unit_limit_and_lost_base(self):
        self.h.run("""
            for i=1,5 do mock.kill('SQEL-G-south_armor-1-'..i) end
            local function stage()return mods.operations.sectors(c)[3].stage end
            c.state.bases.ramat.resources.supply=11;assert(stage()=='NO_SUPPLY')
            c.state.bases.ramat.resources.supply=36;assert(stage()=='NO_SUPPLY')
            c.state.bases.ramat.resources.supply=37;assert(stage()=='AWAIT_ADVANCE')
            c.config.unit_budget=c:active_count()+3;assert(stage()=='UNIT_LIMIT')
            c.config.unit_budget=180;c.state.zones.galilee.owner='red'
            assert(stage()=='NO_BASE' and c:support_offer('CAP').code=='BASE_LOST')
            assert(rt:view().bases[1].operational==false)
        """)

    def test_operations_reads_do_not_mutate_or_spend_and_status_stays_bounded(self):
        self.h.run("""
            local before=mods.json.encode(c:snapshot());local writes=fs.writes
            for i=1,20 do local v=rt:view();mods.view.front(v);mods.view.support(v,v.front.recommended_task) end
            assert(before==mods.json.encode(c:snapshot()) and fs.writes==writes and next(c.journal)==nil)
            local quote=c:support_offer('CAP','south_armor');quote.cost.fuel=0
            assert(c:support_offer('CAP','south_armor').cost.fuel==8)
            rt:publish();assert(#fs.status_text<512*1024)
        """)

    def test_support_quote_and_dispatch_agree_including_changes_after_quote(self):
        self.h.run("""
            local quote=c:support_offer('CAP','south_armor');assert(quote.available and quote.count==2)
            c.state.bases.ramat.resources.fuel=0
            local before=mods.json.encode(c:snapshot())
            local blocked=c:support_offer('CAP','south_armor');assert(blocked.code=='RESOURCES')
            local result=c:command({id='blocked',session=c.session,revision=c.state.revision,
                action='support',role='CAP',target='south_armor'})
            assert(not result.ok and result.message==blocked.reason)
            assert(before==mods.json.encode(c:snapshot()) and not next(c.state.flights))
            c.state.bases.ramat.resources.fuel=100
            assert(c:command({id='ready',session=c.session,revision=c.state.revision,
                action='support',role='CAP',target='south_armor'}).ok)
            assert(c.state.bases.ramat.resources.fuel==92 and c:support_offer('CAP','south_armor').code=='ASSIGNED')
        """)

    def test_support_quote_waits_for_maintenance_and_uses_current_assignment(self):
        self.h.run("c.state.bases.ramat.ready['F-15C']=2;c.state.bases.ramat.ready['F-16C']=0")
        self.assertTrue(self.h.command("support",role="CAP",target="south_armor").ok)
        self.h.run("""
            assert(c:support_offer('CAP','marj_armor').code=='AIRCRAFT')
            for _,f in pairs(c.state.flights)do mock.land_flight(a,f) end
            assert(c:support_offer('CAP','marj_armor').code=='AIRCRAFT')
            assert(c:support_offer('CAP','marj_armor').reason:find('2 in maintenance',1,true))
            c:tick(600);assert(c:support_offer('CAP','marj_armor').available)
        """)
        h=Harness(self.config).start()
        self.assertTrue(h.command("accept",target="south_armor").ok)
        h.run("""
            assert(c:support_offer('STRIKE','damascus_depot').target=='south_armor')
            local sead=c:support_offer('SEAD','damascus_depot')
            assert(sead.target=='south_sam' and sead.available)
        """)
        self.assertTrue(h.command("support",role="SEAD",target="damascus_depot").ok)
        h.run("for _,f in pairs(c.state.flights)do assert(f.target=='south_sam') end")

    def test_supply_consequence_matches_delivery_and_site_repair(self):
        self.h.run("""
            assert(mods.operations.impact(c,'marj_fuel'):find('last operating source',1,true))
            assert(mods.operations.impact(c,'damascus_depot'):find('1 other source',1,true))
            for i=1,4 do mock.kill('SQEL-G-marj_fuel-1-'..i) end
            for i=1,4 do mock.kill('SQEL-G-damascus_depot-1-'..i) end
            assert(mods.operations.impact(c,'shayrat_depot'):find('last operating source',1,true))
            c.state.bases.damascus.resources.fuel=10;c.state.bases.damascus.resources.ammo=10
            assert(mods.director.dispatch(c,c.base_defs.damascus,'SUPPLY','damascus','shayrat_depot'))
            for _,s in pairs(c.state.shipments)do mock.deliver(a,s) end;a:observe()
            assert(c.state.bases.damascus.resources.fuel==10 and c.state.bases.damascus.resources.ammo==30)
            assert(mods.operations.impact(c,'marj_fuel'):find('offline',1,true))
            c:tick(14401);mods.director.repair(c)
            assert(c:target_health('marj_fuel')==1)
            assert(mods.operations.impact(c,'marj_fuel'):find('last operating source',1,true))
        """)

    def test_sector_plan_survives_reload_and_includes_occupying_garrisons(self):
        self.h.run("""
            for i=1,5 do mock.kill('SQEL-G-south_armor-1-'..i) end
            assert(mods.director.dispatch(c,c.base_defs.damascus,'ASSAULT','south','marj'))
            for _,s in pairs(c.state.shipments)do column=s end
            mock.deliver(a,column);a:observe()
            local sector=mods.operations.sectors(c)[3]
            assert(sector.garrison==4 and sector.defenders==4 and sector.stage=='WEAKEN_DEFENDERS')
            local saved=mods.json.decode(mods.json.encode(c:snapshot()))
            local resumed=mods.core.new(cfg,a,saved,'resumed',mods.targets,mods.supply)
            assert(mods.json.encode(mods.operations.sectors(c))==mods.json.encode(mods.operations.sectors(resumed)))
            assert(resumed:validate_save(resumed:snapshot()))
        """)

    def test_front_tabs_recommendation_and_support_buttons_follow_live_state(self):
        self.h.g.lua_path=str(LUA)
        self.h.g.ui=self.h.lua.execute((Path(__file__).parent/"ui_mock.lua").read_text())
        self.h.lua.execute((LUA/"hook.lua").read_text())
        self.h.run("""
            ui.load_mission()
            assert(ui.window.Overview.text:find('FRONT PLAN',1,true))
            ui.window.Next.click();ui.window.Recommended.click()
            assert(ui.window.Target.text:find('Southern armoured',1,true))
            assert(not c.state.task and next(fs.queue)==nil)
            ui.window.SupportTab.click();assert(ui.window.Overview.text:find('Cost: 8 fuel',1,true))
            ui.window.ResourcesTab.click();assert(ui.window.Overview.text:find('Connected depots: 1',1,true))
            ui.window.Accept.click();mock.advance(2);ui.handler.onSimulationFrame()
            assert(c.state.task.target=='south_armor' and c.state.task.role=='CAS')
            c.state.bases.ramat.resources.fuel=0;c:note('Fuel exhausted in fixture')
            mock.advance(2);ui.handler.onSimulationFrame();ui.window.SupportTab.click()
            assert(not ui.window.CAP.enabled and ui.window.Overview.text:find('insufficient fuel',1,true))
            c.state.bases.ramat.resources.fuel=100;c:note('Fuel restored in fixture')
            mock.advance(2);ui.handler.onSimulationFrame();assert(ui.window.CAP.enabled)
        """)

    def test_f10_front_and_support_reports_share_authoritative_view(self):
        self.h.run("""
            local found={}
            for _,menu in ipairs(mock.menus)do
                if menu.name=='Front and sector objectives' or menu.name=='Support availability' then found[menu.name]=menu.fn end
            end
            local before=mods.json.encode(c:snapshot())
            found['Front and sector objectives']()
            assert(mock.messages[#mock.messages]==mods.view.front(rt:view()))
            found['Support availability']()
            assert(mock.messages[#mock.messages]==mods.view.support(rt:view(),false))
            assert(before==mods.json.encode(c:snapshot()))
        """)


class StorageCase(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.lua = LuaRuntime(unpack_returned_tuples=True)
        g = self.lua.globals()
        def mkdir(path):
            try:
                os.mkdir(path)
                return True
            except FileExistsError:
                return None, "exists"
        def attributes(path):
            try:
                s=os.stat(path)
                return self.lua.table_from({"mode":"directory" if os.path.isdir(path) else "file","size":s.st_size})
            except FileNotFoundError:
                return None
        g.py_mkdir=mkdir;g.py_attributes=attributes
        g.py_names=lambda p: self.lua.table_from(os.listdir(p))
        self.lua.execute("""
            lfs={mkdir=py_mkdir,attributes=py_attributes,dir=function(path)
                local names=py_names(path);local i=0;return function()i=i+1;return names[i]end
            end}
            original_rename=os.rename
            os.rename=function(from,to)
                if fail_destination and string.find(to,fail_destination,1,true) then return nil,"injected rename failure" end
                return original_rename(from,to)
            end
        """)
        self.lua.globals().factory=self.lua.execute((LUA/"storage.lua").read_text())
        self.lua.globals().root=self.temp.name + "/SQE-Live"
        self.lua.execute("fs=factory.new(root)")

    def tearDown(self):
        self.temp.cleanup()

    def test_actual_files_rotate_and_survive_sanitization(self):
        self.lua.execute("""
            assert(fs.save("campaign","one"));assert(fs.save("campaign","two"))
            assert(fs.load("campaign",false)=="two" and fs.load("campaign",true)=="one")
            io=nil;lfs=nil;os=nil
            assert(fs.save("campaign","three"))
            assert(fs.load("campaign",false)=="three" and fs.load("campaign",true)=="two")
            assert(fs.enqueue("cmd-1","{}"));local q=fs.commands();assert(#q==1 and q[1].text=="{}")
            fs.ack("cmd-1");assert(#fs.commands()==0)
        """)

    def test_repeated_disk_checkpoints_and_command_backlog_recover_bounded_files(self):
        self.lua.execute("""
            for i=1,20 do assert(fs.save('stress',tostring(i))) end
            assert(fs.load('stress')=='20' and fs.load('stress',true)=='19')
            for i=1,600 do assert(fs.enqueue('stress-'..i,tostring(i))) end
            local seen={};local total=0
            while true do
                local batch=fs.commands();assert(#batch<=16)
                if #batch==0 then break end
                for _,x in ipairs(batch)do
                    assert(not seen[x.id] and tonumber(x.text))
                    seen[x.id]=true;total=total+1;assert(fs.ack(x.id))
                end
            end
            assert(total==600)
            for i=1,120 do assert(fs.report(i%2==0 and 'ui' or 'runtime',tostring(i))) end
        """)
        folder=Path(self.temp.name)/'SQE-Live'
        self.assertEqual([],list((folder/'commands').iterdir()))
        self.assertEqual({'diagnostics-ui.json','diagnostics-runtime.json'},
                         {p.name for p in folder.glob('diagnostics-*')})
        (folder/'campaigns/stress.json').write_text('corrupted')
        self.lua.execute("""
            assert(fs.restore_previous('stress',fs.load('stress',true)))
            assert(fs.load('stress')=='19' and fs.load('stress',true)=='19')
        """)
        self.assertFalse(list(folder.rglob('*.tmp')))

    def compat_io(self):
        self.lua.execute("""
            local native_open=io.open
            io.open=function(path,mode)
                if (mode=='wb' and deny_open) or (mode=='rb' and deny_read) then return nil end
                local f,why=native_open(path,mode)
                if not f or mode~='wb' then return f,why end
                return {
                    write=function(_,text)
                        if throw_write then error('injected write exception') end
                        if explicit_write_error then return nil,'injected disk full' end
                        f:write(truncate_write and text:sub(1,1) or text)
                        if not nil_write then return true end
                    end,
                    close=function()
                        local ok,err=f:close();was_closed=true
                        if throw_close then error('injected close exception') end
                        if false_close then return false end
                        if not nil_close then return ok,err end
                    end
                }
            end
        """)
        self.lua.globals().factory=self.lua.execute((LUA/'storage.lua').read_text())
        self.lua.execute('fs=factory.new(root)')

    def test_nil_write_and_close_require_exact_readback_before_success(self):
        self.compat_io()
        self.lua.execute("""
            nil_write=true;nil_close=true
            io=nil;os=nil;lfs=nil;require=nil;package=nil
            assert(fs.save('compat','one'))
            assert(fs.save('compat','two'))
            assert(fs.load('compat')=='two' and fs.load('compat',true)=='one')
            assert(fs.publish('live') and fs.status()=='live')
            assert(fs.report('ui','ok') and fs.read_report('ui')=='ok')
            assert(fs.enqueue('command','{}') and fs.commands()[1].text=='{}')
        """)

    def test_silent_partial_write_does_not_rotate_valid_checkpoints(self):
        self.compat_io()
        self.lua.execute("""
            assert(fs.save('compat','first') and fs.save('compat','second'))
            nil_write=true;nil_close=true;truncate_write=true
            local ok,why=fs.save('compat','a new checkpoint')
            assert(not ok and type(why)=='string' and #why>0)
            assert(fs.load('compat')=='second' and fs.load('compat',true)=='first')
            assert(was_closed)
        """)
        self.assertFalse(list(Path(self.temp.name).rglob('*.tmp')))

    def test_explicit_io_failures_are_not_treated_as_nil_compatibility(self):
        self.compat_io()
        self.lua.execute("""
            assert(fs.save('compat','first') and fs.save('compat','second'))
            for _,flag in ipairs({'explicit_write_error','false_close','throw_write','throw_close','deny_open'})do
                _G[flag]=true
                local ok,why=fs.save('compat','replacement')
                _G[flag]=nil
                assert(not ok and type(why)=='string' and #why>0,flag)
                assert(fs.load('compat')=='second' and fs.load('compat',true)=='first')
            end
            assert(was_closed)
        """)
        self.assertFalse(list(Path(self.temp.name).rglob('*.tmp')))

    def test_silent_read_open_failure_reports_an_error_for_existing_file(self):
        self.compat_io()
        self.lua.execute("""
            assert(fs.save('compat','valid'))
            deny_read=true
            local value,why=fs.load('compat')
            assert(value==nil and type(why)=='string' and #why>0 and why~='missing')
        """)

    def test_nil_io_contract_connects_actual_bridge_runtime_and_ui_save(self):
        self.compat_io()
        bundle=Path(self.temp.name)/'bundle'
        with contextlib.redirect_stdout(io.StringIO()),contextlib.redirect_stderr(io.StringIO()):
            build_scenario(bundle)
        config=json.loads((bundle/'content.json').read_text())
        g=self.lua.globals();g.cfg=self.lua.eval(lua_literal(config));g.lua_path=str(LUA)
        g.mock=self.lua.execute((Path(__file__).parent/'dcs_mock.lua').read_text())
        self.lua.execute('mock.add_player(cfg);nil_write=true;nil_close=true;SQE_LIVE_STORAGE=fs')
        g.ui=self.lua.execute((Path(__file__).parent/'ui_mock.lua').read_text())
        self.lua.execute((LUA/'hook.lua').read_text())
        self.lua.execute('ui.handler.onMissionLoadBegin()')
        self.lua.execute(mission_script(config))
        self.lua.execute("""
            assert(SQE_LIVE_RUNTIME and not SQE_LIVE_RUNTIME.failed)
            ui.handler.onMissionLoadEnd();ui.handler.onSimulationFrame()
            ui.hotkeys['Ctrl+Shift+q']()
            assert(ui.window.Save.enabled and ui.window.Status.text:find('LIVE',1,true))
            ui.window.Save.click();mock.advance(2);ui.handler.onSimulationFrame()
            assert(ui.window.Status.text:find('Saved',1,true))
            assert(fs.read_report('runtime') and fs.read_report('ui'))
            assert(fs.load(cfg.id) and #fs.commands()==0)
        """)

    def test_ordinary_and_mixed_io_success_conventions_work(self):
        self.compat_io()
        self.lua.execute("""
            for _,flag in ipairs({'nil_write','nil_close'})do
                _G[flag]=true
                assert(fs.save('compat',flag));assert(fs.load('compat')==flag)
                _G[flag]=nil
            end
        """)

    def test_path_and_payload_limits(self):
        self.lua.execute("""
            assert(not fs.save("../outside","x"))
            assert(not fs.enqueue("bad/name","{}"))
            assert(not fs.enqueue("cmd",string.rep("x",8193)))
            assert(not fs.save("campaign",string.rep("x",4*1024*1024+1)))
        """)
        self.assertFalse((Path(self.temp.name)/"outside").exists())

    def test_rotation_failure_preserves_existing_primary(self):
        self.lua.execute("""
            assert(fs.save("campaign","good"))
            fail_destination=".prev"
            assert(not fs.save("campaign","new"))
            assert(fs.load("campaign",false)=="good")
        """)

    def test_failed_recovery_keeps_valid_previous_checkpoint(self):
        self.lua.execute("""
            assert(fs.save("campaign","good"))
            assert(fs.save("campaign","bad"))
            fail_destination=".invalid"
            assert(not fs.restore_previous("campaign","good"))
            assert(fs.load("campaign",true)=="good")
            fail_destination=nil
            assert(fs.restore_previous("campaign","good"))
            assert(fs.load("campaign",false)=="good" and fs.load("campaign",true)=="good")
        """)

    def test_bounded_command_batch(self):
        self.lua.execute("""
            for i=1,20 do assert(fs.enqueue("c-"..i,"{}")) end
            assert(#fs.commands()==16)
            for _,v in ipairs(fs.commands())do fs.ack(v.id)end
            assert(#fs.commands()==4)
        """)

    def test_diagnostic_reports_are_bounded_fixed_paths_and_survive_sanitization(self):
        self.lua.execute("""
            assert(not fs.report('../outside','x'))
            assert(not fs.report('runtime',string.rep('x',128*1024+1)))
            assert(not fs.read_report('campaigns/campaign'))
            io=nil;lfs=nil;os=nil
            assert(fs.report('runtime','first') and fs.report('runtime','second'))
            assert(fs.report('ui','heartbeat'))
            assert(fs.read_report('runtime')=='second' and fs.read_report('ui')=='heartbeat')
        """)


class InstallerCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pwsh=os.environ.get("SQE_TEST_PWSH") or shutil.which("pwsh") or shutil.which("powershell")
        if not cls.pwsh:
            raise unittest.SkipTest("PowerShell unavailable; install/uninstall execution not tested")
        cls.temp=tempfile.TemporaryDirectory()
        cls.bundle=Path(cls.temp.name)/"release bundle"
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            build(cls.bundle)

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def setUp(self):
        self.case=tempfile.TemporaryDirectory()
        self.dcs=Path(self.case.name)/"DCS fixture"
        self.profile=Path(self.case.name)/"Saved Games"/"DCS test"
        (self.dcs/"Scripts").mkdir(parents=True)
        self.script=self.dcs/"Scripts/MissionScripting.lua"
        self.original=("dofile('Scripts/ScriptingSystem.lua')\r\n"
                       "local function sanitizeModule(name)\r\n"
                       "  _G[name] = nil\r\nend\r\n"
                       "sanitizeModule('io')\r\nsanitizeModule('os')\r\nsanitizeModule('lfs')\r\n"
                       "-- unrelated extension stays here\r\n")
        self.script.write_bytes(self.original.encode())

    def tearDown(self):
        self.case.cleanup()

    def install(self, script="Install-SQE-Live.ps1", ok=True):
        p=subprocess.run([self.pwsh,"-NoLogo","-NoProfile","-File",str(self.bundle/script),
                          "-DcsPath",str(self.dcs),"-SavedGamesPath",str(self.profile)],capture_output=True,text=True)
        if ok:
            self.assertEqual(0,p.returncode,p.stdout+p.stderr)
        else:
            self.assertNotEqual(0,p.returncode)
        return p

    def test_installed_bootstrap_executes_before_standard_sanitization(self):
        self.install()
        lua = LuaRuntime(unpack_returned_tuples=True)
        g = lua.globals()
        def mkdir(path):
            Path(path).mkdir(exist_ok=True)
            return True
        def attributes(path):
            p=Path(path)
            if not p.exists():
                return None
            return lua.table_from({"mode":"directory" if p.is_dir() else "file", "size":p.stat().st_size})
        g.py_mkdir=mkdir;g.py_attributes=attributes
        g.py_names=lambda path: lua.table_from(os.listdir(path))
        g.profile_root=self.profile.as_posix()+"/"
        lua.execute("""
            lfs={mkdir=py_mkdir,attributes=py_attributes,writedir=function()return profile_root end,
                dir=function(path)
                    local names=py_names(path);local i=0
                    return function()i=i+1;return names[i]end
                end}
            local native_dofile=dofile
            dofile=function(path)
                -- DCS's native environment initialization is unavailable here.
                -- Supply its lfs contract, then execute every installed SQE file.
                if path=='Scripts/ScriptingSystem.lua' then return end
                return native_dofile(path)
            end
        """)
        lua.execute(self.script.read_text()+"\nrequire=nil;package=nil;loadlib=nil")
        lua.execute("""
            assert(io==nil and os==nil and lfs==nil and require==nil and package==nil)
            assert(SQE_LIVE_STORAGE and SQE_LIVE_STORAGE.session())
            local f=SQE_LIVE_STORAGE
            assert(f.save('bootstrap','first') and f.save('bootstrap','second'))
            assert(f.load('bootstrap')=='second' and f.load('bootstrap',true)=='first')
            assert(f.publish('status') and f.status()=='status')
            assert(f.enqueue('command','{}') and #f.commands()==1)
            assert(f.ack('command') and #f.commands()==0)
            assert(f.report('runtime','boot-ok') and f.read_report('runtime')=='boot-ok')
            assert(io==nil and os==nil and lfs==nil and require==nil and package==nil)
        """)
        self.assertEqual('second',(self.profile/'SQE-Live/campaigns/bootstrap.json').read_text())
        self.assertEqual('first',(self.profile/'SQE-Live/campaigns/bootstrap.json.prev').read_text())

    def test_install_idempotent_uninstall_preserves_other_edits_and_saves(self):
        self.install()
        content=self.script.read_bytes()
        self.assertEqual(1,content.count(b"-- SQE-LIVE BRIDGE BEGIN"))
        self.assertLess(content.index(b"-- SQE-LIVE"),content.index(b"local function sanitizeModule"))
        self.assertIn(b"sanitizeModule('io')",content)
        self.assertTrue((self.profile/"Scripts/Hooks/SQE-Live.lua").exists())
        for name in ("map.lua", "map_ui.lua"):
            self.assertTrue((self.profile/"Scripts/SQE-Live"/name).exists())
        self.assertTrue((self.profile/"Missions/SQE-Live/SQE_Live_Syria.miz").exists())
        self.install()
        self.assertEqual(content,self.script.read_bytes())
        save=self.profile/"SQE-Live/campaigns/test.json"
        save.parent.mkdir(exist_ok=True);save.write_text('{"keep":true}')
        other=self.profile/"Scripts/Hooks/other.lua";other.write_text("-- keep")
        with self.script.open("ab") as f:f.write(b"-- later extension\r\n")
        self.install("Uninstall-SQE-Live.ps1")
        self.assertEqual((self.original+"-- later extension\r\n").encode(),self.script.read_bytes())
        self.assertEqual('{"keep":true}',save.read_text())
        self.assertTrue(other.exists())
        self.assertFalse((self.profile/"Scripts/Hooks/SQE-Live.lua").exists())
        for name in ("map.lua", "map_ui.lua"):
            self.assertFalse((self.profile/"Scripts/SQE-Live"/name).exists())

    def test_unsupported_layout_and_partial_markers_fail_without_changes(self):
        for text in ("-- no sanitizer", "-- SQE-LIVE BRIDGE BEGIN\n"+self.original):
            self.script.write_text(text)
            self.install(ok=False)
            self.assertEqual(text.encode(),self.script.read_bytes())
            self.assertFalse((self.profile/"Scripts/Hooks/SQE-Live.lua").exists())

    def test_diagnostic_collector_selects_only_reports_and_bounded_sqe_log(self):
        self.install()
        root=self.profile/"SQE-Live"
        (root/"diagnostics-runtime.json").write_text('{"checks":[]}')
        (root/"diagnostics-ui.json").write_text('{"window_created":true}')
        (root/"unrelated.txt").write_text('do not collect')
        (root/"campaigns").mkdir(exist_ok=True)
        save=root/"campaigns/current.json";save.write_text('{"keep":true}')
        (self.profile/"Logs").mkdir()
        log=self.profile/"Logs/dcs.log"
        log.write_text('old SQE Live entry\n' + 'unrelated entry\n'*2000 +
                       ''.join(f'[SQE Live] check {i}\n' for i in range(250)))
        output=Path(self.case.name)/"diagnostic bundle.zip"
        result=subprocess.run([self.pwsh,"-NoLogo","-NoProfile","-File",
                               str(self.bundle/"Collect-Diagnostics.ps1"),
                               "-SavedGamesPath",str(self.profile),"-OutputPath",str(output)],
                              capture_output=True,text=True)
        self.assertEqual(0,result.returncode,result.stdout+result.stderr)
        with zipfile.ZipFile(output) as z:
            self.assertEqual({'README.txt','installation.json','diagnostics-runtime.json',
                              'diagnostics-ui.json','sqe-log-excerpt.txt'},set(z.namelist()))
            excerpt=z.read('sqe-log-excerpt.txt').decode('utf-8-sig')
            self.assertEqual(200,len(excerpt.splitlines()))
            self.assertIn('check 249',excerpt)
            self.assertNotIn('old SQE Live entry',excerpt)
            self.assertNotIn('unrelated entry',excerpt)
            self.assertEqual(self.config_version(),json.loads(z.read('installation.json').decode('utf-8-sig'))['version'])
        self.assertEqual('{"keep":true}',save.read_text())

    @staticmethod
    def config_version():
        from sqe.live import VERSION
        return VERSION


if __name__ == "__main__":
    unittest.main()
