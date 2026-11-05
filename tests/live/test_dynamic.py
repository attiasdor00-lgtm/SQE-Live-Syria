"""Live shipment objectives through the real Lua core, bridge and native hooks."""
import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from test_live import Harness, LUA, build


class DynamicCase(unittest.TestCase):
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
        self.h = Harness(self.config).start()
        self.h.run('''
            c.state.next_director=1e9;c.state.next_logistics=1e9;c.state.next_repair=1e9
            function clear_defenders(ship)
                for _,d in ipairs(cfg.targets)do
                    if d.zone==ship.zone and d.side~=ship.side and d.kind=='ARMOR' then
                        for i=1,#d.types do mock.kill(a.ground_groups[d.id]..'-'..i) end
                    end
                end
            end
            function kill_ship(ship)
                for _,u in ipairs(mock.groups[a.ship_groups[ship.id]].units)do
                    if u.alive then mock.kill(u.name) end
                end
            end
        ''')

    def convoy(self, kind="ASSAULT"):
        self.h.g.convoy_kind = kind
        self.h.run('''
            c.state.bases.damascus.resources={fuel=20,ammo=20,supply=80}
            local supply=convoy_kind=='SUPPLY'
            assert(mods.director.dispatch(c,c.base_defs.damascus,convoy_kind,supply and 'damascus' or 'golan',supply and 'damascus_depot' or 'south'))
            for _,s in pairs(c.state.shipments)do if s.kind==convoy_kind and s.side=='red' then ship=s end end
            convoy=mock.groups[a.ship_groups[ship.id]];a:observe();rt:publish();rt:menus()
        ''')
        return self.h.run("return ship.id")

    def ui(self):
        self.h.g.lua_path = str(LUA)
        self.h.g.ui = self.h.lua.execute((Path(__file__).parent / "ui_mock.lua").read_text())
        self.h.lua.execute((LUA / "hook.lua").read_text())
        self.h.run('''
            ui.load_mission()
            ui.hotkeys['Ctrl+Shift+q']()
        ''')

    def test_dynamic_discovery_uses_existing_inventory_and_reads_do_not_mutate(self):
        self.convoy()
        self.convoy("SUPPLY")
        self.h.run('''
            assert(mods.director.dispatch(c,c.base_defs.ramat,'SUPPLY','galilee','blue_depot'))
            local before=mods.json.encode(c:snapshot());local dynamic=0
            for _,t in ipairs(rt:view().tasks)do if t.dynamic then
                dynamic=dynamic+1;assert(c.state.shipments[t.id] and not c.state.targets[t.id])
                local s=c.state.shipments[t.id]
                assert(s.side=='red' and t.survivors==4 and t.zone==s.zone)
                assert(t.role==(s.kind=='ASSAULT' and 'CAS' or 'STRIKE'))
            end end
            assert(dynamic==2 and mods.json.encode(c:snapshot())==before)
        ''')

    def test_moving_coordinates_marks_and_last_survivor_remain_taskable(self):
        identity = self.convoy("SUPPLY")
        self.assertTrue(self.h.command("mark", target=identity).ok)
        self.h.run('''
            local marker=a.markers[ship.id]
            for _,u in ipairs(convoy.units)do u.point.x=u.point.x+2400 end
            a:observe();rt:publish()
            local p=a:target_point((c:target(ship.id)))
            local row=mods.map.task(mods.json.decode(fs.status_text),ship.id)
            assert(math.abs(row.x-p.x)<0.001 and row.position_reference=='Live convoy vehicle')
            assert(mock.marks[marker].point.x==p.x)
            for i=1,3 do mock.kill(convoy.units[i].name) end
            a:observe();rt:publish()
            row=mods.map.task(mods.json.decode(fs.status_text),ship.id)
            assert(row and row.health==0.25 and row.survivors==1)
            assert(a:target_point((c:target(ship.id))).unit==convoy.units[4].name)
            assert(mock.marks[marker].point.x==convoy.units[4].point.x)
        ''')
        self.assertTrue(self.h.command("accept", target=identity).ok)

    def test_native_map_f10_and_assignment_use_same_live_force(self):
        identity = self.convoy()
        self.ui()
        self.h.run('''
            local before=mods.json.encode(c:snapshot())
            ui.sector('Golan').click();ui.window.MapTask1.click()
            assert(ui.window.Target.text:find('Assault column '..ship.id,1,true))
            assert(next(fs.queue)==nil and mods.json.encode(c:snapshot())==before)
            ui.window.Brief.click();mock.advance(2);ui.handler.onSimulationFrame()
            local brief=mock.messages[#mock.messages];local f10
            for _,item in ipairs(mock.menus)do
                if item.name=='Brief / coordinates' and item.parent.name=='CAS / Assault column '..ship.id then f10=item.fn end
            end
            assert(f10);f10();assert(mock.messages[#mock.messages]==brief)
            ui.window.Accept.click();mock.advance(2);ui.handler.onSimulationFrame()
            assert(c.state.task.target==ship.id and c.state.task.role=='CAS')
        ''')
        self.assertEqual(identity, self.h.run("return c.state.task.target"))

    def test_assault_arrival_keeps_assignment_group_and_updates_garrison_menu(self):
        identity = self.convoy()
        self.assertTrue(self.h.command("accept", target=identity).ok)
        self.assertTrue(self.h.command("mark", target=identity).ok)
        self.assertTrue(self.h.command("support", role="STRIKE").ok)
        self.h.run('''
            local group=convoy:getID();clear_defenders(ship);mock.deliver(a,ship);a:observe();rt:menus();rt:publish()
            assert(ship.status=='ARRIVED' and c.state.zones.golan.owner=='red')
            assert(c.state.task.target==ship.id and c.state.completed==0 and convoy:getID()==group)
            local row=mods.map.task(mods.json.decode(fs.status_text),ship.id)
            assert(row.name=='Occupying garrison '..ship.id and row.force_state=='GARRISON')
            assert(row.position_reference=='Live garrison vehicle' and c:defenders('golan','blue',false)==4)
            assert(mock.marks[a.markers[ship.id]].text:find('Occupying garrison',1,true))
            local found=false
            for _,item in ipairs(mock.menus)do if item.name=='CAS / Occupying garrison '..ship.id then found=true end end
            assert(found)
            local f;for _,flight in pairs(c.state.flights)do f=flight end
            assert(f.target==ship.id and a:control_flight(f,'push'))
            local attack=mock.groups[a.air_groups[f.id]]:getController().task.params.route.points[2].task.params.tasks[2]
            assert(attack.id=='AttackGroup' and attack.params.groupId==group)
        ''')

    def test_destruction_completes_once_and_reload_does_not_restore_the_force(self):
        identity = self.convoy()
        self.assertTrue(self.h.command("accept", target=identity).ok)
        self.h.run("kill_ship(ship);a:observe();c:check_task();assert(c.state.completed==1 and not c.state.task);assert(ship.outcome=='DESTROYED')")
        saved = self.h.run("return mods.json.encode(c:snapshot())")
        resumed = Harness(self.config)
        resumed.g.saved = saved
        resumed.run("fs.files[cfg.id]=saved")
        resumed.start()
        resumed.g.identity = identity
        resumed.run('''
            mock.advance(4);assert(c.state.completed==1 and not c.state.task)
            assert(not mods.map.task(rt:view(),identity) and not a.ship_groups[identity])
            assert(c:validate_save(c:snapshot()))
        ''')

    def test_delivery_removes_task_without_credit_and_returns_support(self):
        identity = self.convoy("SUPPLY")
        self.assertTrue(self.h.command("accept", target=identity).ok)
        self.assertTrue(self.h.command("mark", target=identity).ok)
        self.assertTrue(self.h.command("support", role="STRIKE").ok)
        self.h.run('''
            local marker=a.markers[ship.id];mock.deliver(a,ship);a:observe();mock.advance(2)
            assert(ship.outcome=='DELIVERED' and not c.state.task and c.state.completed==0)
            assert(not mods.map.task(rt:view(),ship.id) and not mock.marks[marker] and not a.markers[ship.id])
            assert(c.state.bases.damascus.resources.fuel==40)
            for _,f in pairs(c.state.flights)do
                assert(f.status=='RTB' and f.target==false)
                local route=mock.groups[a.air_groups[f.id]]:getController().task.params.route
                for _,p in ipairs(route.points)do for _,task in ipairs(p.task.params.tasks)do assert(task.id~='AttackGroup') end end
            end
            assert(c:validate_save(c:snapshot()))
        ''')
        self.assertFalse(self.h.command("accept", target=identity).ok)
        self.assertFalse(self.h.command("support", target=identity, role="STRIKE").ok)

    def test_partial_delivery_retains_objective_for_undelivered_survivors(self):
        identity = self.convoy("SUPPLY")
        self.assertTrue(self.h.command("accept", target=identity).ok)
        self.h.run('''
            convoy.units[1].point={x=ship.destination.x,y=100,z=ship.destination.y};a:observe()
            assert(c.state.bases.damascus.resources.fuel==25 and c.state.task.target==ship.id)
            local row=mods.map.task(rt:view(),ship.id)
            assert(row.survivors==3 and row.impact:find('1/4 vehicles already delivered',1,true))
            kill_ship(ship);a:observe();c:check_task()
            assert(ship.status=='DELIVERED' and ship.outcome=='DESTROYED')
            assert(c.state.completed==1 and not c.state.task and c.state.bases.damascus.resources.fuel==25)
        ''')

    def test_timeout_and_captured_destination_do_not_award_destruction(self):
        for outcome in ("TIMED_OUT", "DESTINATION_LOST"):
            with self.subTest(outcome=outcome):
                self.setUp()
                identity = self.convoy("SUPPLY")
                self.assertTrue(self.h.command("accept", target=identity).ok)
                if outcome == "TIMED_OUT":
                    self.h.run("c.state.time=ship.navigation.deadline+1;mods.director.tick(c)")
                else:
                    self.h.run("c.state.zones.damascus.owner='blue';mock.deliver(a,ship);a:observe()")
                self.h.g.expected_outcome = outcome
                self.h.run('''
                    assert(ship.outcome==expected_outcome and not c.state.task and c.state.completed==0)
                    assert(c.state.bases.damascus.resources.fuel==20 and c:validate_save(c:snapshot()))
                ''')

    def test_assignment_survivors_and_bound_support_survive_save_reload(self):
        identity = self.convoy()
        self.assertTrue(self.h.command("accept", target=identity).ok)
        self.assertTrue(self.h.command("support", role="STRIKE").ok)
        self.h.run("mock.kill(convoy.units[1].name);a:observe();clear_defenders(ship);mock.deliver(a,ship);a:observe()")
        saved = self.h.run("return mods.json.encode(c:snapshot())")
        resumed = Harness(self.config)
        resumed.g.saved = saved
        resumed.run("fs.files[cfg.id]=saved")
        resumed.start()
        resumed.g.identity = identity
        resumed.run('''
            local s=c.state.shipments[identity]
            assert(s.status=='ARRIVED' and not s.alive['1'] and c.count(s.alive)==3)
            assert(c.state.task.target==identity and c.state.completed==0)
            assert(#mock.groups[a.ship_groups[identity]]:getUnits()==3)
            assert(next(c.state.flights)==nil and #c.state.maintenance==1)
            assert(mods.map.task(rt:view(),identity).name=='Occupying garrison '..identity)
            assert(c:validate_save(c:snapshot()))
        ''')

    def test_support_attacks_the_observed_dynamic_group_and_push_keeps_identity(self):
        identity = self.convoy()
        self.assertTrue(self.h.command("support", target=identity, role="STRIKE").ok)
        self.h.run('''
            local f;for _,flight in pairs(c.state.flights)do f=flight end
            local ai=mock.groups[a.air_groups[f.id]]
            assert(f.target==ship.id and ai.data.route.points[2].task.params.tasks[2].params.groupId==convoy:getID())
            local before=ai.data.route.points[2].x
            for _,u in ipairs(convoy.units)do u.point.x=u.point.x+5000 end
            a:observe();assert(a:control_flight(f,'hold'));assert(a:control_flight(f,'push'))
            local route=ai:getController().task.params.route
            assert(route.points[2].x~=before and route.points[2].task.params.tasks[2].params.groupId==convoy:getID())
            assert(f.target==ship.id and not c:support_offer('SEAD',ship.id).available)
            assert(c:validate_save(c:snapshot()))
        ''')

    def test_friendly_missing_and_unobserved_force_cannot_spend_support_stock(self):
        identity = self.convoy()
        self.h.run('''
            assert(mods.director.dispatch(c,c.base_defs.ramat,'ASSAULT','south','golan'))
            local before=mods.json.encode(c.state.bases)
            for _,s in pairs(c.state.shipments)do if s.side=='blue' then
                assert(not c:support_offer('STRIKE',s.id).available)
                assert(not c:launch('STRIKE','blue',s.id,false))
            end end
            assert(not c:launch('STRIKE','blue','missing',false))
            convoy:destroy()
            assert(not c:launch('STRIKE','blue',ship.id,false))
            assert(mods.json.encode(c.state.bases)==before)
        ''')
        self.assertFalse(self.h.command("mark", target=identity).ok)

    def test_failed_return_command_retries_without_retargeting_or_dangling_save(self):
        identity = self.convoy()
        self.assertTrue(self.h.command("support", target=identity, role="STRIKE").ok)
        self.h.run('''
            local f;for _,flight in pairs(c.state.flights)do f=flight end
            local ctl=mock.groups[a.air_groups[f.id]]:getController();local set=ctl.setTask;local calls=0
            ctl.setTask=function()calls=calls+1;error('injected return failure')end
            kill_ship(ship);a:observe();f.expires=0;mock.advance(2);c:reconcile_support();c:reconcile_support()
            assert(calls==1 and f.target==ship.id and not rt.failed)
            c.state.time=ship.navigation.deadline+601;mods.director.tick(c)
            assert(c.state.shipments[ship.id] and c:validate_save(c:snapshot()))
            ctl.setTask=set;c:reconcile_support();mods.director.tick(c)
            assert(f.status=='RTB' and f.target==false and not c.state.shipments[ship.id])
            assert(c:validate_save(c:snapshot()))
        ''')

    def test_dynamic_outcome_and_reference_corruption_rejected(self):
        identity = self.convoy()
        self.assertTrue(self.h.command("accept", target=identity).ok)
        self.h.run('''
            local saved=c:snapshot();assert(c:validate_save(saved))
            saved.task.target='missing';assert(not c:validate_save(saved))
            saved=c:snapshot();saved.task.role='SEAD';assert(not c:validate_save(saved))
            saved=c:snapshot();saved.shipments[ship.id].outcome='DESTROYED';assert(not c:validate_save(saved))
            saved=c:snapshot();saved.shipments[ship.id].status='LOST';saved.shipments[ship.id].outcome='DESTROYED'
            assert(not c:validate_save(saved))
            saved=c:snapshot();saved.shipments[ship.id].outcome=nil
            assert(c:validate_save(saved))
            saved=c:snapshot();saved.task=false
            saved.shipments.south_armor=saved.shipments[ship.id];saved.shipments[ship.id]=nil
            saved.shipments.south_armor.id='south_armor'
            assert(not c:validate_save(saved))
        ''')

    def test_removal_clears_native_selection_and_never_selects_another_force(self):
        self.convoy("SUPPLY")
        self.ui()
        self.h.run('''
            ui.sector('Damascus').click()
            for i=1,20 do
                if ui.window.Target.text:find('Supply convoy '..ship.id,1,true) then break end
                ui.window.Next.click()
            end
            assert(ui.window.Target.text:find('Supply convoy '..ship.id,1,true))
            mock.deliver(a,ship);a:observe();mock.advance(2);ui.handler.onSimulationFrame()
            assert(not ui.window.Accept.enabled and not ui.window.Brief.enabled)
            assert(ui.window.Target.text:find('No player target selected',1,true))
            ui.window.Accept.click();assert(next(fs.queue)==nil and not c.state.task)
        ''')

    def test_repeated_force_lifecycles_release_marks_and_registry_entries(self):
        for _ in range(12):
            identity = self.convoy("SUPPLY")
            self.assertTrue(self.h.command("mark", target=identity).ok)
            self.h.run('''
                mock.deliver(a,ship);a:observe()
                c.state.time=ship.navigation.deadline+601;mods.director.tick(c);a:observe()
                assert(not c.state.shipments[ship.id] and not a.ship_groups[ship.id])
                assert(next(a.markers)==nil and next(mock.marks)==nil)
                for _,r in pairs(a.registry)do assert(r.kind~='shipment') end
                assert(c:validate_save(c:snapshot()))
            ''')
