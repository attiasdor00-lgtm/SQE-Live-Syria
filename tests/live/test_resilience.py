"""Observed position and convoy failure scenarios; no actual DCS/terrain claim."""
import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from test_live import Harness, build


class ResilienceCase(unittest.TestCase):
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

    def convoy(self, kind="SUPPLY"):
        self.h.g.convoy_kind = kind
        self.h.run('''
            c.state.next_director=1e9;c.state.next_logistics=1e9;c.state.next_repair=1e9
            c.state.bases.ramat.resources={fuel=20,ammo=20,supply=80}
            local supply=convoy_kind=='SUPPLY'
            assert(mods.director.dispatch(c,c.base_defs.ramat,convoy_kind,supply and 'galilee' or 'south',supply and 'blue_depot' or 'golan'))
            for _,s in pairs(c.state.shipments)do ship=s end
            convoy=mock.groups[a.ship_groups[ship.id]];a:observe()
        ''')

    def displaced_target(self):
        self.h.run('''
            d=c.target_defs.south_armor
            local state=c.copy(c.state.targets[d.id]);state.generation=state.generation+1;state.positions={}
            mock.groups[a.ground_groups[d.id]]:destroy()
            land.getSurfaceType=function(p)return p.x>=d.x+900 and 1 or 3 end
            local ok,why=a:spawn_target(d,state);assert(ok,why)
            land.getSurfaceType=function()return 1 end
            c.state.targets[d.id]=state;a:observe()
            anchor=a:target_point(d);assert(c.distance(anchor,d)>900)
        ''')

    def test_displaced_target_brief_ui_mark_and_attack_destination_agree(self):
        self.displaced_target()
        self.assertTrue(self.h.command("mark", target="south_armor").ok)
        self.h.run('''
            local mark=mock.marks[a.markers[d.id]].point
            assert(mark.x==anchor.x and mark.z==anchor.y)
            local coordinates,elevation,p=a:coordinates(d)
            assert(p.unit==anchor.unit and mock.messages[#mock.messages]:find(coordinates,1,true))
            rt:publish();local view=mods.json.decode(fs.status_text)
            local row=mods.map.task(view,d.id)
            assert(math.abs(row.x-anchor.x)<0.001 and math.abs(row.y-anchor.y)<0.001 and row.coordinates==coordinates)
            assert(row.elevation_ft==elevation and row.position_reference=='Live group vehicle')
            local destination=a:destination({target=d.id,base='ramat'})
            assert(destination.x==anchor.x and destination.y==anchor.y)
        ''')

    def test_mark_tracks_surviving_radar_then_vehicle_and_clears_on_destruction(self):
        self.assertTrue(self.h.command("mark", target="damascus_sam").ok)
        self.h.run('''
            local d=c.target_defs.damascus_sam;local id=a.markers[d.id]
            assert(a:target_point(d).unit=='SQEL-G-damascus_sam-1-1')
            mock.kill('SQEL-G-damascus_sam-1-1');a:observe()
            local p=a:target_point(d);assert(p.unit=='SQEL-G-damascus_sam-1-3' and p.reference=='Live radar')
            assert(mock.marks[id].point.x==p.x and mock.marks[id].point.z==p.y)
            mock.kill('SQEL-G-damascus_sam-1-3');mock.kill('SQEL-G-damascus_sam-1-4');a:observe()
            assert(a:target_point(d).unit=='SQEL-G-damascus_sam-1-2')
            assert(a:target_point(d).reference=='Live group vehicle')
            mock.kill('SQEL-G-damascus_sam-1-2');a:observe()
            assert(not mock.marks[id] and not a:coordinates(d))
        ''')
        self.assertFalse(self.h.command("mark", target="damascus_sam").ok)

    def test_unobserved_target_never_falls_back_to_saved_or_planned_coordinates(self):
        self.h.run('''
            a:observe();mock.groups[a.ground_groups.south_armor]:destroy()
            assert(c.count(c.state.targets.south_armor.alive)==5)
            assert(next(c.state.targets.south_armor.positions))
            assert(not a:coordinates(c.target_defs.south_armor))
            rt:publish();local row=mods.map.task(mods.json.decode(fs.status_text),'south_armor')
            assert(row.x==false and row.y==false and row.position_reference=='Unavailable')
            local before=mods.json.encode(c.state.bases)
            assert(not c:launch('STRIKE','blue','south_armor',false))
            assert(mods.json.encode(c.state.bases)==before)
        ''')
        self.assertFalse(self.h.command("brief", target="south_armor").ok)

    def test_marker_api_failure_isolated_from_world_updates_and_recovers(self):
        self.assertTrue(self.h.command("mark", target="south_armor").ok)
        self.h.run('''
            local action=trigger.action.markToCoalition
            local u=mock.units['SQEL-G-south_armor-1-1'];u.point.x=u.point.x+50
            trigger.action.markToCoalition=function()error('injected marker failure')end
            mock.advance(4);assert(not rt.failed and mock.warning:find('marker update failed',1,true))
            trigger.action.markToCoalition=action
            mock.advance(2);assert(mock.marks[a.markers.south_armor].point.x==u.point.x)
            -- Explicit refresh at the same point must also retry a failed add.
            trigger.action.markToCoalition=function()error('same-position marker failure')end
            local text,ok=a:brief(c.target_defs.south_armor,true)
            assert(not ok and not mock.marks[a.markers.south_armor])
            trigger.action.markToCoalition=action
            mock.advance(2);assert(mock.marks[a.markers.south_armor].point.x==u.point.x)
        ''')

    def test_displaced_survivor_coordinates_remain_correct_after_reload(self):
        self.displaced_target()
        self.h.run("mock.kill('SQEL-G-south_armor-2-1');a:observe()")
        anchor = self.h.run("local p=a:target_point(d);return p.x,p.y")
        saved = self.h.run("return mods.json.encode(c:snapshot())")
        resumed = Harness(self.config)
        resumed.g.saved = saved
        resumed.run("fs.files[cfg.id]=saved")
        resumed.start()
        after = resumed.run("local p=a:target_point(c.target_defs.south_armor);return p.x,p.y")
        for expected, actual in zip(anchor, after):
            self.assertAlmostEqual(expected, actual, places=3)
        self.assertEqual(4, resumed.run("return c.count(c.state.targets.south_armor.alive)"))

    def test_road_plan_bounds_samples_and_rejects_invalid_or_remote_paths(self):
        self.h.run('''
            local ground=mods.ground;local path={}
            for i=0,1000 do path[#path+1]={x=i*10,y=0} end
            local plan=assert(ground.plan(path,{x=0,y=0},{x=10000,y=0}))
            assert(#plan.points<=18 and plan.length==10000)
            for i,p in ipairs(plan.points) do
                assert(p.action=='On Road')
                if i>1 then assert(c.distance(p,plan.points[i-1])>=1) end
            end
            assert(not ground.plan({},path[1],path[#path]))
            assert(not ground.plan({{x=0,y=0},{x=0/0,y=0}},path[1],path[#path]))
            assert(not ground.plan(path,{x=-5000,y=0},path[#path]))
            assert(not ground.plan(path,path[1],{x=0/0,y=0}))
            assert(not ground.plan({{x=0,y=0},{x=200000,y=0},{x=100,y=0}},{x=0,y=0},{x=100,y=0}))
            local huge={};for i=1,20001 do huge[i]={x=i,y=0} end
            assert(not ground.plan(huge,huge[1],huge[#huge]))
        ''')

    def test_missing_road_path_or_api_never_spends_or_spawns_a_new_convoy(self):
        self.h.run('''
            local before=mods.json.encode(c.state.bases);local count=c:active_count()
            local path_api=land.findPathOnRoads
            for _,mode in ipairs({'missing','failure','unavailable'}) do
                mock.no_road=mode=='missing';mock.road_error=mode=='failure'
                if mode=='unavailable' then land.findPathOnRoads=nil else land.findPathOnRoads=path_api end
                assert(not mods.director.dispatch(c,c.base_defs.ramat,'ASSAULT','south','golan'))
                assert(next(c.state.shipments)==nil and c:active_count()==count)
                assert(mods.json.encode(c.state.bases)==before)
            end
            land.findPathOnRoads=path_api;mock.no_road=false;mock.road_error=false
            assert(mods.director.dispatch(c,c.base_defs.ramat,'ASSAULT','south','golan'))
        ''')

    def test_stalled_convoy_replans_from_observed_position_without_teleport_or_charge(self):
        self.convoy()
        self.h.run('''
            for _,u in ipairs(convoy.units) do u.point.x=u.point.x+5000;u.point.z=u.point.z+3000 end
            a:observe();local resources=mods.json.encode(c.state.bases)
            local positions=mods.json.encode(ship.positions);local group=a.ship_groups[ship.id]
            mock.advance(302)
            assert(ship.navigation.attempts==1 and not rt.failed)
            local route=convoy:getController().task.params.route
            assert(route.points[1].x==convoy.units[1].point.x and route.points[1].y==convoy.units[1].point.z)
            assert(#route.points<=18 and a.ship_groups[ship.id]==group)
            assert(mods.json.encode(ship.positions)==positions and mods.json.encode(c.state.bases)==resources)
        ''')

    def test_route_retries_are_bounded_and_throttled_across_convoys(self):
        self.convoy()
        self.h.run('''
            assert(mods.director.dispatch(c,c.base_defs.ramat,'ASSAULT','south','golan'));a:observe()
            local function attempts()
                local total=0;for _,s in pairs(c.state.shipments)do total=total+s.navigation.attempts end;return total
            end
            c.state.time=300;a:observe();mods.director.tick(c);assert(attempts()==1)
            c.state.time=302;a:observe();mods.director.tick(c);assert(attempts()==1)
            c.state.time=310;a:observe();mods.director.tick(c);assert(attempts()==2)
            for i=1,10 do c.state.time=c.state.time+310;a:observe();mods.director.tick(c) end
            assert(attempts()==6)
            local queries=mock.road_queries
            c.state.time=c.state.time+310;a:observe();mods.director.tick(c)
            assert(attempts()==6 and mock.road_queries==queries)
            for _,s in pairs(c.state.shipments)do assert(s.navigation.state=='BLOCKED') end
            assert(rt:view().bases[1].delayed==1)
            assert(mods.map.sector(rt:view(),'south').delayed_columns==1)
        ''')

    def test_regular_physical_movement_does_not_trigger_stall_retries(self):
        self.convoy()
        self.h.run('''
            for i=1,4 do
                mock.advance(240)
                for _,u in ipairs(convoy.units) do u.point.x=u.point.x+70 end
                a:observe()
            end
            assert(ship.navigation.attempts==0 and ship.navigation.state=='MOVING')
        ''')

    def test_failed_retry_keeps_campaign_running_and_later_route_recovers(self):
        self.convoy()
        self.h.run('''
            local stock=mods.json.encode(c.state.bases);local count=c:active_count()
            mock.road_error=true;mock.advance(302)
            assert(not rt.failed and ship.navigation.attempts==1)
            assert(ship.navigation.last_error:find('Road path query failed',1,true))
            mock.road_error=false
            local controller=convoy:getController();local set_task=controller.setTask
            controller.setTask=function()error('injected controller failure')end
            mock.advance(300)
            assert(not rt.failed and ship.navigation.attempts==2)
            assert(ship.navigation.last_error:find('controller failure',1,true))
            controller.setTask=set_task;mock.advance(300)
            assert(not rt.failed and ship.navigation.attempts==3 and not ship.navigation.last_error)
            assert(mods.json.encode(c.state.bases)==stock and c:active_count()==count)
            assert(c:validate_save(c:snapshot()))
        ''')

    def test_retry_budget_survives_reload_and_exhausted_convoy_can_physically_recover(self):
        self.convoy()
        self.h.run("mock.advance(910);assert(ship.navigation.attempts==3)")
        saved = self.h.run("return mods.json.encode(c:snapshot())")
        resumed = Harness(self.config)
        resumed.g.saved = saved
        resumed.run("fs.files[cfg.id]=saved")
        resumed.start()
        resumed.run('''
            local ship;for _,s in pairs(c.state.shipments)do ship=s end
            assert(ship.navigation.attempts==3)
            local queries=mock.road_queries;mock.advance(310)
            assert(ship.navigation.attempts==3 and mock.road_queries==queries and ship.navigation.state=='BLOCKED')
            mock.deliver(a,ship);a:observe()
            assert(ship.status=='DELIVERED' and c.state.bases.ramat.resources.fuel==40)
            assert(not rt.failed and c:validate_save(c:snapshot()))
        ''')

    def test_partial_supply_credits_only_arrived_vehicles_once(self):
        self.convoy()
        self.h.run('''
            local active=c:active_count()
            for i=1,3 do convoy.units[i].point={x=ship.destination.x,y=100,z=ship.destination.y} end
            a:observe()
            assert(ship.status=='MOVING' and c.count(ship.delivered)==3 and c.count(ship.alive)==1)
            assert(c.state.bases.ramat.resources.fuel==35 and c:active_count()==active-3)
            a:observe();assert(c.state.bases.ramat.resources.fuel==35)
            assert(c:validate_save(c:snapshot()))
            convoy.units[4].point={x=ship.destination.x,y=100,z=ship.destination.y}
            a:observe();assert(ship.status=='DELIVERED' and c.state.bases.ramat.resources.fuel==40)
            a:observe();assert(c.state.bases.ramat.resources.fuel==40)
            assert(c:validate_save(c:snapshot()))
        ''')

    def test_partial_delivery_reload_preserves_credit_and_remaining_vehicle_identity(self):
        self.convoy()
        self.h.run('''
            for i=1,3 do convoy.units[i].point={x=ship.destination.x,y=100,z=ship.destination.y} end
            a:observe()
        ''')
        saved = self.h.run("return mods.json.encode(c:snapshot())")
        resumed = Harness(self.config)
        resumed.g.saved = saved
        resumed.run("fs.files[cfg.id]=saved")
        resumed.start()
        resumed.run('''
            local ship;for _,s in pairs(c.state.shipments)do ship=s end
            local g=mock.groups[a.ship_groups[ship.id]]
            assert(#g.units==1 and g.units[1].name=='SQEL-C-'..ship.id..'-4')
            assert(c.state.bases.ramat.resources.fuel==35 and c.count(ship.delivered)==3)
            mock.kill(g.units[1].name);a:observe()
            assert(ship.status=='DELIVERED' and c.state.bases.ramat.resources.fuel==35)
            assert(c:validate_save(c:snapshot()))
        ''')

    def test_legacy_convoy_restores_held_when_roads_fail_then_recovers_without_reset(self):
        self.convoy()
        self.h.run("ship.navigation=nil;ship.delivered=nil")
        saved = self.h.run("return mods.json.encode(c:snapshot())")
        resumed = Harness(self.config)
        resumed.g.saved = saved
        resumed.run("fs.files[cfg.id]=saved;mock.no_road=true")
        resumed.start()
        resumed.run('''
            local ship;for _,s in pairs(c.state.shipments)do ship=s end
            local group=a.ship_groups[ship.id];local count=c:active_count();local stock=mods.json.encode(c.state.bases)
            assert(ship.navigation.state=='BLOCKED' and not rt.failed)
            mock.no_road=false;mock.advance(302)
            assert(ship.navigation.attempts==1 and ship.navigation.state=='MOVING' and not rt.failed)
            assert(a.ship_groups[ship.id]==group and c:active_count()==count)
            assert(mods.json.encode(c.state.bases)==stock and c:validate_save(c:snapshot()))
        ''')

    def test_convoy_navigation_and_delivery_corruption_rejected(self):
        self.convoy()
        for change in (
            "s.shipments[id].navigation.attempts=4",
            "s.shipments[id].navigation.deadline=s.shipments[id].started+21601",
            "s.shipments[id].navigation.watch['1'].at=s.time+1",
            "s.shipments[id].navigation.route_length=0/0",
            "s.shipments[id].delivered={['1']=true}",
        ):
            with self.subTest(change=change):
                self.h.run("local id=ship.id;local s=c:snapshot();" + change + ";assert(not c:validate_save(s))")

    def test_assault_straggler_still_requires_arrival_and_waiting_force_does_not_expire(self):
        self.convoy("ASSAULT")
        self.h.run('''
            for i=1,3 do convoy.units[i].point={x=ship.destination.x,y=100,z=ship.destination.y} end
            a:observe();assert(ship.status=='MOVING' and c.state.zones.south.owner=='red')
            mock.deliver(a,ship);a:observe()
            assert(ship.navigation.state=='WAITING' and ship.status=='MOVING')
            c.state.time=ship.navigation.deadline+1;a:observe();mods.director.tick(c)
            assert(ship.status=='MOVING' and convoy:isExist() and ship.navigation.attempts==0)
            for i=1,5 do mock.kill('SQEL-G-south_armor-1-'..i) end
            a:observe();assert(ship.status=='ARRIVED' and c.state.zones.south.owner=='blue')
        ''')

    def test_convoy_deadline_adapts_to_route_and_keeps_partial_delivery(self):
        self.convoy()
        self.h.run('''
            local dummy={started=100}
            assert(mods.ground.initialize(dummy,100,90000).deadline==19900)
            dummy={started=100};assert(mods.ground.initialize(dummy,100,300000).deadline==21700)
            for i=1,3 do convoy.units[i].point={x=ship.destination.x,y=100,z=ship.destination.y} end
            a:observe();local queries=mock.road_queries
            c.state.time=ship.navigation.deadline+1;a:observe();mods.director.tick(c)
            assert(ship.status=='DELIVERED' and c.state.bases.ramat.resources.fuel==35)
            assert(not convoy:isExist() and mock.road_queries==queries)
            assert(c.count(ship.delivered)==3 and c:validate_save(c:snapshot()))
        ''')
