"""Controlled-sector logistics and interrupted convoys under Lua 5.1 / fake DCS."""
import contextlib
import copy
import io
import json
import tempfile
import unittest
from pathlib import Path

from test_live import Harness, LUA, build


class SupplyCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temporary = tempfile.TemporaryDirectory()
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            build(Path(cls.temporary.name))
        cls.config = json.loads((Path(cls.temporary.name) / "content.json").read_text())

    @classmethod
    def tearDownClass(cls):
        cls.temporary.cleanup()

    def setUp(self):
        self.config = copy.deepcopy(self.config)
        # A remote friendly depot exposes a cut through an intermediate sector.
        south = next(z for z in self.config["zones"] if z["id"] == "south")
        south["owner"] = "blue"
        depot = next(t for t in self.config["targets"] if t["id"] == "blue_depot")
        depot.update(zone="south", x=south["x"] + 5000, y=south["y"] + 5000)
        self.start()

    def start(self):
        self.h = Harness(self.config).start()
        self.h.run('''
            c.state.next_director=1e9;c.state.next_logistics=1e9;c.state.next_repair=1e9
            c.state.bases.ramat.resources={fuel=20,ammo=20,supply=20}
        ''')

    def convoy(self):
        self.h.run('''
            assert(mods.director.dispatch(c,c.base_defs.ramat,'SUPPLY','galilee','blue_depot'))
            for _,s in pairs(c.state.shipments)do ship=s end
            convoy=mock.groups[a.ship_groups[ship.id]];a:observe()
        ''')

    def reload(self, expression="c:snapshot()"):
        saved = self.h.run("return mods.json.encode(" + expression + ")")
        self.h = Harness(self.config)
        self.h.g.saved = saved
        self.h.run("fs.files[cfg.id]=saved")
        self.h.start()
        self.h.run('''
            for _,s in pairs(c.state.shipments)do if s.side=='blue' then ship=s end end
            convoy=mock.groups[a.ship_groups[ship.id]]
        ''')

    def test_paths_are_bounded_deterministic_and_views_are_read_only(self):
        self.h.run('''
            c.state.zones.marj.owner='blue'
            table.insert(c.zone_defs.galilee.neighbors,'marj')
            table.insert(c.zone_defs.marj.neighbors,'galilee')
            local before=mods.json.encode(c:snapshot())
            for i=1,8 do
                local p=mods.supply.path(c,'blue','south','galilee')
                assert(table.concat(p,',')=='south,golan,galilee')
                assert(not mods.supply.path(c,'blue','unknown','galilee'))
                assert(not mods.supply.path(c,'red','south','galilee'))
                assert(mods.supply.offer(c,c.base_defs.ramat).source=='blue_depot')
                rt:view()
            end
            assert(mods.json.encode(c:snapshot())==before)
            c.state.zones.golan.owner='red'
            assert(table.concat(mods.supply.path(c,'blue','south','galilee'),',')=='south,marj,galilee')
            c.zone_defs.marj.neighbors={'south','damascus'};c.zone_defs.galilee.neighbors={'golan'}
            assert(not mods.supply.path(c,'blue','south','galilee'))
            assert(#mods.supply.path(c,'blue','south','galilee',true)==3)
            for i=1,33 do cfg.zones[#cfg.zones+1]={id='oversize-'..i} end
            assert(not mods.supply.path(c,'blue','south','galilee',true))
        ''')

    def test_isolated_depot_cannot_dispatch_or_spend_and_reconnection_allows_it(self):
        self.h.run('''
            c.state.zones.golan.owner='red'
            local stock=mods.json.encode(c.state.bases);local count=c:active_count()
            local queries=mock.road_queries or 0
            local ok,why=mods.director.dispatch(c,c.base_defs.ramat,'SUPPLY','galilee','blue_depot')
            assert(not ok and why:find('Golan approach',1,true))
            assert(next(c.state.shipments)==nil and c:active_count()==count)
            assert(mods.json.encode(c.state.bases)==stock and (mock.road_queries or 0)==queries)
            c.state.bases.ramat.resources.supply=11 -- avoid an unrelated advance into the newly enemy Golan
            mods.director.logistics(c)
            for _,s in pairs(c.state.shipments)do assert(s.side~='blue') end
            assert(c.state.bases.ramat.resources.supply==11)
            c.state.zones.golan.owner='blue'
            assert(mods.director.dispatch(c,c.base_defs.ramat,'SUPPLY','galilee','blue_depot'))
        ''')

    def test_connected_source_preferred_and_wrong_side_or_destination_rejected(self):
        local = copy.deepcopy(next(t for t in self.config["targets"] if t["id"] == "blue_depot"))
        local.update(id="backup_depot", zone="galilee")
        self.config["targets"].append(local)
        self.start()
        self.h.run('''
            assert(mods.supply.offer(c,c.base_defs.ramat).source=='backup_depot')
            c.state.zones.golan.owner='red'
            assert(mods.supply.offer(c,c.base_defs.ramat).source=='backup_depot')
            assert(not mods.director.dispatch(c,c.base_defs.ramat,'SUPPLY','galilee','damascus_depot'))
            assert(not mods.director.dispatch(c,c.base_defs.ramat,'SUPPLY','south','backup_depot'))
            assert(not mods.director.dispatch(c,c.base_defs.ramat,'SUPPLY','galilee','blue_fuel'))
            assert(mods.director.dispatch(c,c.base_defs.ramat,'SUPPLY','galilee'))
            for _,s in pairs(c.state.shipments)do assert(s.source=='backup_depot' and #s.corridor.path==1) end
        ''')

    def test_cut_holds_without_delivery_then_resumes_same_force_after_cooldown(self):
        self.convoy()
        self.h.run('''
            local id=ship.id;local group=a.ship_groups[id];local deadline=ship.navigation.deadline
            local stock=mods.json.encode(c.state.bases);local queries=mock.road_queries
            c.state.time=100;c.state.zones.golan.owner='red';a:observe()
            assert(ship.corridor.state=='CUT' and convoy:getController().task.id=='Hold')
            assert(ship.navigation.attempts==0 and mock.road_queries==queries)
            mock.deliver(a,ship);a:observe();mods.director.tick(c)
            assert(ship.status=='MOVING' and not ship.delivered)
            assert(mods.json.encode(c.state.bases)==stock)
            local positions=mods.json.encode(ship.positions)
            c.state.time=299;c.state.zones.golan.owner='blue';a:observe();mods.director.tick(c)
            assert(ship.corridor.state=='RESUME' and ship.navigation.attempts==0 and not ship.delivered)
            c.state.time=300;mods.director.tick(c)
            assert(ship.corridor.state=='OPEN' and ship.navigation.attempts==1)
            assert(convoy:getController().task.id=='Mission' and a.ship_groups[id]==group)
            assert(ship.navigation.deadline==deadline and mods.json.encode(ship.positions)==positions)
            assert(mods.json.encode(c.state.bases)==stock)
            a:observe();a:observe()
            assert(ship.status=='DELIVERED' and c.state.bases.ramat.resources.supply==40)
            assert(c.count(ship.delivered)==4 and c:validate_save(c:snapshot()))
            mods.director.tick(c);assert(not c.supply_holds[id])
        ''')

    def test_alternate_corridor_retasks_without_respawn_or_stock_change(self):
        self.h.run('''
            c.state.zones.marj.owner='blue'
            table.insert(c.zone_defs.marj.neighbors,'galilee');table.insert(c.zone_defs.galilee.neighbors,'marj')
        ''')
        self.convoy()
        self.h.run('''
            local stock=mods.json.encode(c.state.bases);local group=a.ship_groups[ship.id]
            local positions=mods.json.encode(ship.positions)
            c.state.time=300;c.state.zones.golan.owner='red';a:observe()
            assert(ship.corridor.state=='RESUME' and table.concat(ship.corridor.path,',')=='south,marj,galilee')
            assert(convoy:getController().task.id=='Hold')
            mods.director.tick(c)
            assert(ship.corridor.state=='OPEN' and ship.navigation.attempts==1)
            assert(a.ship_groups[ship.id]==group and mods.json.encode(ship.positions)==positions)
            assert(mods.json.encode(c.state.bases)==stock and c:validate_save(c:snapshot()))
        ''')

    def test_road_failure_budget_survives_reload_and_control_flapping(self):
        self.convoy()
        self.h.run('''
            c.state.zones.golan.owner='red';a:observe();c.state.zones.golan.owner='blue'
            mock.no_road=true
            for i=1,3 do
                c.state.time=i*300;a:observe();mods.director.tick(c)
                assert(ship.navigation.attempts==i and ship.corridor.state~='OPEN')
            end
            mods.director.tick(c);assert(ship.corridor.state=='BLOCKED')
            assert(c:validate_save(c:snapshot()))
        ''')
        self.reload()
        self.h.run('''
            assert(ship.navigation.attempts==3 and ship.corridor.state=='BLOCKED')
            assert(convoy.data.route.points[1].speed==0 and not mock.road_queries)
            local deadline=ship.navigation.deadline
            for i=1,4 do
                c.state.time=c.state.time+300;c.state.zones.golan.owner='red';a:observe();mods.director.tick(c)
                c.state.zones.golan.owner='blue';a:observe();mods.director.tick(c)
            end
            mock.deliver(a,ship);a:observe()
            assert(ship.navigation.attempts==3 and ship.navigation.deadline==deadline)
            assert(ship.corridor.state=='BLOCKED' and ship.status=='MOVING' and not mock.road_queries)
            assert(c.state.bases.ramat.resources.supply==20 and c:validate_save(c:snapshot()))
        ''')

    def test_hold_api_failure_retries_without_delivery_or_campaign_failure(self):
        self.convoy()
        self.h.run('''
            local controller=convoy:getController();local set_task=controller.setTask;local calls=0
            controller.setTask=function()calls=calls+1;error('injected Hold failure')end
            c.state.zones.golan.owner='red';mock.deliver(a,ship)
            mock.advance(8)
            assert(calls==1 and not rt.failed and ship.status=='MOVING')
            assert(c.state.bases.ramat.resources.supply==20 and ship.navigation.attempts==0)
            controller.setTask=function(self,task)calls=calls+1;return set_task(self,task)end
            mock.advance(6)
            assert(calls==2 and controller.task.id=='Hold' and not rt.failed)
            mock.advance(12);assert(calls==2 and ship.status=='MOVING')
        ''')

    def test_partial_delivery_cut_reload_and_resume_preserve_cargo_once(self):
        self.convoy()
        self.h.run('''
            convoy.units[1].point={x=ship.destination.x,y=100,z=ship.destination.y};a:observe()
            assert(c.count(ship.delivered)==1 and c.state.bases.ramat.resources.supply==25)
            mock.kill(convoy.units[2].name)
            c.state.zones.golan.owner='red';a:observe()
            assert(c.count(ship.alive)==2 and ship.corridor.state=='CUT')
        ''')
        self.reload()
        self.h.run('''
            assert(c.count(ship.alive)==2 and c.count(ship.delivered)==1)
            assert(#convoy.units==2 and convoy.data.route.points[1].speed==0)
            mock.deliver(a,ship);a:observe();assert(c.state.bases.ramat.resources.supply==25)
            c.state.zones.golan.owner='blue';c.state.time=300;a:observe();mods.director.tick(c)
            a:observe();a:observe()
            assert(ship.status=='DELIVERED' and c.count(ship.delivered)==3)
            assert(c.state.bases.ramat.resources.supply==35 and c:validate_save(c:snapshot()))
        ''')

    def test_cut_timeout_keeps_partial_credit_and_removes_remaining_force(self):
        self.convoy()
        self.h.run('''
            convoy.units[1].point={x=ship.destination.x,y=100,z=ship.destination.y};a:observe()
            c.state.zones.golan.owner='red';a:observe();mock.deliver(a,ship)
            c.state.time=ship.navigation.deadline+1;a:observe();mods.director.tick(c)
            assert(ship.status=='DELIVERED' and ship.outcome=='TIMED_OUT' and not convoy:isExist())
            assert(c.count(ship.delivered)==1 and c.state.bases.ramat.resources.supply==25)
            assert(c:validate_save(c:snapshot()))
        ''')

    def test_loaded_cargo_survives_source_destruction_and_legacy_reload(self):
        self.convoy()
        self.h.run('''
            for i=1,4 do mock.kill('SQEL-G-blue_depot-1-'..i) end
            ship.corridor=nil
            assert(c:validate_save(c:snapshot()))
        ''')
        self.reload()
        self.h.run('''
            assert(ship.corridor.state=='OPEN' and c:target_health('blue_depot')==0)
            mock.deliver(a,ship);a:observe()
            assert(c.state.bases.ramat.resources.supply==40 and ship.status=='DELIVERED')
            assert(not mods.supply.offer(c,c.base_defs.ramat))
        ''')

    def test_cut_and_pending_resume_restore_held_before_first_observation(self):
        for resume in (False, True):
            with self.subTest(resume=resume):
                self.start();self.convoy()
                self.h.run("c.state.zones.golan.owner='red';a:observe()")
                if resume:
                    self.h.run("c.state.zones.golan.owner='blue';a:observe()")
                self.reload()
                self.h.run('''
                    assert(convoy.data.route.points[1].speed==0 and not mock.road_queries)
                    assert(ship.navigation.attempts==0 and ship.status=='MOVING')
                    assert(c:validate_save(c:snapshot()))
                ''')

    def test_legacy_disconnected_graph_restores_held_with_valid_checkpoint(self):
        self.convoy()
        self.h.run("ship.corridor=nil")
        # Older versions allowed road dispatch without a sector connection.
        for z in self.config["zones"]:
            if z["id"] == "galilee":
                z["neighbors"] = []
            if z["id"] == "golan":
                z["neighbors"].remove("galilee")
        self.reload()
        self.h.run('''
            assert(ship.corridor.state=='CUT' and #ship.corridor.path==0)
            assert(convoy.data.route.points[1].speed==0 and not mock.road_queries)
            assert(c:validate_save(c:snapshot()))
        ''')

    def test_fuel_connection_is_independent_of_ammo_and_supply_delivery(self):
        for t in self.config["targets"]:
            if t["id"] == "blue_depot": t["zone"] = "galilee"
            if t["id"] == "blue_fuel": t["zone"] = "south"
        self.start();self.convoy()
        self.h.run('''
            c.state.zones.golan.owner='red';a:observe()
            local view=rt:view();local b=view.bases[1]
            assert(b.depots==1 and b.fuel_sites==0)
            assert(mods.view.overview(view):find('Golan approach',1,true))
            mock.deliver(a,ship);a:observe()
            assert(c.state.bases.ramat.resources.fuel==20 and c.state.bases.ramat.resources.ammo==40)
            assert(c.state.bases.ramat.resources.supply==40)
            c.state.zones.golan.owner='blue';assert(rt:view().bases[1].fuel_sites==1)
        ''')

    def test_isolated_staging_and_repairs_cannot_draw_remote_base_stock(self):
        self.h.run('''
            c.state.zones.golan.owner='red'
            for i=1,4 do mock.kill('SQEL-G-marj_armor-1-'..i) end
            local stock=mods.json.encode(c.state.bases)
            assert(not mods.director.dispatch(c,c.base_defs.ramat,'ASSAULT','marj','south'))
            assert(mods.map.sector(rt:view(),'marj').stage=='SUPPLY_ISOLATED')
            for i=1,4 do mock.kill('SQEL-G-blue_depot-1-'..i) end
            c.state.bases.ramat.resources.supply=80;c.state.time=14401
            mods.director.repair(c)
            assert(c.state.targets.blue_depot.generation==1 and c.state.bases.ramat.resources.supply==80)
            c.state.zones.golan.owner='blue';mods.director.repair(c)
            assert(c.state.targets.blue_depot.generation==2 and c.state.bases.ramat.resources.supply==55)
            assert(mods.map.sector(rt:view(),'marj').stage=='AWAIT_ADVANCE')
            assert(mods.director.dispatch(c,c.base_defs.ramat,'ASSAULT','marj','south'))
        ''')

    def test_cut_enemy_convoy_remains_destroyable_as_same_objective(self):
        self.h.run('''
            assert(mods.director.dispatch(c,c.base_defs.damascus,'SUPPLY','damascus','shayrat_depot'))
            for _,s in pairs(c.state.shipments)do ship=s end
            c.state.zones.shayrat.owner='blue';a:observe()
            assert(ship.corridor.state=='CUT')
        ''')
        self.assertTrue(self.h.command("accept", target=self.h.run("return ship.id")).ok)
        self.h.run('''
            local row=mods.map.task(rt:view(),ship.id)
            assert(row.force_state=='SUPPLY_CUT' and row.impact:find('No controlled supply corridor',1,true))
            for _,u in ipairs(mock.groups[a.ship_groups[ship.id]].units)do mock.kill(u.name) end
            assert(ship.outcome=='DESTROYED' and c.state.completed==1 and not c.state.task)
            a:observe();assert(c.state.completed==1 and c:validate_save(c:snapshot()))
        ''')

    def test_checkpoint_rejects_corrupt_corridor_without_rejecting_changed_control(self):
        self.convoy()
        for change in (
            "r.state='TELEPORT'", "r.path={}", "r.path={'galilee'}",
            "r.path={'south','galilee'}", "r.path={'south','golan','south','golan','galilee'}",
            "r.path={'south','unknown','galilee'}", "r.reason=string.rep('x',301)",
            "r.state='CUT';r.reason=false", "r.path[8]='galilee'",
            "s.shipments[ship.id].source='damascus_depot'",
        ):
            with self.subTest(change=change):
                self.h.run("local s=c:snapshot();local r=s.shipments[ship.id].corridor;" + change + ";assert(not c:validate_save(s))")
        self.h.run('''
            c.state.zones.golan.owner='red'
            assert(c:validate_save(c:snapshot()))
            a:observe();assert(c:validate_save(c:snapshot()))
        ''')

    def test_native_and_f10_resources_explain_cut_without_mutating_campaign(self):
        self.convoy()
        self.h.run("c.state.zones.golan.owner='red';a:observe();rt:publish();rt:menus()")
        self.h.g.lua_path = str(LUA)
        self.h.g.ui = self.h.lua.execute((Path(__file__).parent / "ui_mock.lua").read_text())
        self.h.lua.execute((LUA / "hook.lua").read_text())
        self.h.run('''
            local before=mods.json.encode(c:snapshot())
            ui.handler.onMissionLoadEnd();ui.handler.onSimulationFrame()
            ui.window.ResourcesTab.click()
            local text=ui.window.Overview.text
            assert(text:find('Connected depots: 0',1,true) and text:find('Golan approach',1,true))
            assert(text:find('Convoys awaiting a corridor/road refresh: 1',1,true))
            local found=false
            for _,m in ipairs(mock.menus)do if not m.removed and m.name=='Campaign status' then m.fn();found=true end end
            assert(found and mock.messages[#mock.messages]:find('Golan approach',1,true))
            assert(mods.json.encode(c:snapshot())==before)
        ''')
