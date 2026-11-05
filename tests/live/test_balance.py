"""Solo reserves and recovery: accounting, failed native operations and long runs."""
import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from test_live import Harness, build
from balance_sim import SCENARIOS, simulate


class BalanceCase(unittest.TestCase):
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
        self.h.run("c.state.next_director=1e9;c.state.next_logistics=1e9;c.state.next_repair=1e9")

    def partial_depot(self):
        self.h.run('''
            old_name=a.ground_groups.blue_depot;old=mock.groups[old_name]
            for i=1,3 do mock.kill(old_name..'-'..i) end
            assert(c:target_health('blue_depot')==0.25 and c.state.targets.blue_depot.disabled_at==0)
        ''')

    def test_automatic_flights_leave_reserve_but_requested_support_can_use_it(self):
        self.h.run('''
            c.state.bases.ramat.resources={fuel=16,ammo=30,supply=25}
            assert(c:launch('CAP','blue',nil,true))
            assert(c.state.bases.ramat.resources.fuel==8 and c.state.bases.ramat.resources.ammo==22)
            local before=mods.json.encode(c:snapshot())
            local offer=c:flight_offer('STRIKE','blue','south_sam',true)
            assert(not offer.available and offer.code=='RESERVE')
            assert(not c:launch('STRIKE','blue','south_sam',true))
            assert(mods.json.encode(c:snapshot())==before)
            assert(c:support_offer('STRIKE','south_sam').available)
            assert(c:launch('STRIKE','blue','south_sam',false))
            assert(c.state.bases.ramat.resources.fuel==0 and c.state.bases.ramat.resources.ammo==10)
            assert(c:validate_save(c:snapshot()))
        ''')

    def test_actual_shortage_and_failed_spawn_never_debit_or_override_stock(self):
        self.h.run('''
            c.state.bases.ramat.resources={fuel=7,ammo=50,supply=50}
            assert(c:flight_offer('STRIKE','blue','south_sam',true).code=='RESOURCES')
            assert(not c:launch('STRIKE','blue','south_sam',false))
            c.state.bases.ramat.resources.fuel=100
            local stock=mods.json.encode(c.state.bases);mock.fail_spawn=true
            assert(not c:launch('STRIKE','blue','south_sam',true))
            assert(mods.json.encode(c.state.bases)==stock)
        ''')

    def test_blue_ground_funding_matches_view_and_red_has_no_player_reserve(self):
        self.h.run('''
            for i=1,5 do mock.kill('SQEL-G-south_armor-1-'..i) end
            c.state.bases.ramat.resources.supply=36
            local before=mods.json.encode(c:snapshot())
            assert(not mods.director.dispatch(c,c.base_defs.ramat,'ASSAULT','south','golan'))
            assert(mods.map.sector(rt:view(),'south').stage=='NO_SUPPLY')
            assert(mods.json.encode(c:snapshot())==before)
            c.state.bases.ramat.resources.supply=37
            assert(mods.map.sector(rt:view(),'south').stage=='AWAIT_ADVANCE')
            assert(mods.director.dispatch(c,c.base_defs.ramat,'ASSAULT','south','golan'))
            assert(c.state.bases.ramat.resources.supply==25)
            c.state.bases.damascus.resources={fuel=8,ammo=12,supply=12}
            c.state.bases.shayrat.resources={fuel=0,ammo=0,supply=0}
            assert(c:launch('STRIKE','red','blue_depot',true))
            assert(c.state.bases.damascus.resources.ammo==0)
            assert(mods.director.dispatch(c,c.base_defs.damascus,'ASSAULT','golan','south'))
            assert(c.state.bases.damascus.resources.supply==0)
        ''')

    def test_disabled_partial_depot_rebuilds_after_wait_without_duplicate_survivors(self):
        self.partial_depot()
        self.h.run('''
            local count=c:active_count()
            c.state.time=14399;mods.director.repair(c);assert(c.state.targets.blue_depot.generation==1)
            c.state.time=14400;mods.director.repair(c)
            assert(c.state.targets.blue_depot.generation==2 and not old:isExist())
            assert(c:target_health('blue_depot')==1 and c:active_count()==count+3)
            assert(c.state.bases.ramat.resources.supply==75 and c.state.bases.ramat.resources.ammo==90)
            assert(c.state.targets.blue_depot.disabled_at==false)
            local live,registered=0,0
            for name,u in pairs(mock.units)do if name:find('SQEL-G-blue_depot-',1,true) and u.alive then live=live+1 end end
            for name,r in pairs(a.registry)do if r.kind=='target' and r.id=='blue_depot' then registered=registered+1;assert(r.generation==2) end end
            assert(live==4 and registered==4 and a:world_health())
            local stock=mods.json.encode(c.state.bases);mods.director.repair(c)
            assert(mods.json.encode(c.state.bases)==stock and c:validate_save(c:snapshot()))
        ''')

    def test_partial_fuel_and_fully_destroyed_sites_share_recovery_rules(self):
        self.h.run('''
            for i=1,3 do mock.kill('SQEL-G-marj_fuel-1-'..i) end
            c.state.time=100;mock.kill('SQEL-G-marj_fuel-1-4')
            assert(c.state.targets.marj_fuel.disabled_at==0 and c.state.targets.marj_fuel.destroyed_at==100)
            c.state.time=14400;mods.director.repair(c)
            assert(c.state.targets.marj_fuel.generation==2 and c:target_health('marj_fuel')==1)
            assert(c.state.bases.damascus.resources.supply==75 and c.state.bases.damascus.resources.ammo==90)
        ''')

    def test_rebuild_spawn_failure_after_creation_rolls_back_and_retries(self):
        self.partial_depot()
        self.h.run('''
            c.state.time=14400;local stock=mods.json.encode(c.state.bases)
            local spawn=coalition.addGroup
            coalition.addGroup=function(...)spawn(...);error('injected post-create failure')end
            mods.director.repair(c)
            assert(c.state.targets.blue_depot.generation==1 and old:isExist())
            assert(a.ground_groups.blue_depot==old_name and mods.json.encode(c.state.bases)==stock)
            assert(not mock.groups['SQEL-G-blue_depot-2']:isExist())
            coalition.addGroup=spawn;mods.director.repair(c)
            assert(c.state.targets.blue_depot.generation==2 and c:target_health('blue_depot')==1 and not old:isExist())
            assert(a:world_health() and c:validate_save(c:snapshot()))
        ''')

    def test_rebuild_retirement_failure_preserves_original_force_stock_and_timer(self):
        self.partial_depot()
        self.h.run('''
            c.state.time=14400;local stock=mods.json.encode(c.state.bases)
            local destroy=old.destroy
            old.destroy=function()error('injected old-site retirement failure')end
            mods.director.repair(c)
            assert(c.state.targets.blue_depot.generation==1 and c:target_health('blue_depot')==0.25)
            assert(old:isExist() and a.ground_groups.blue_depot==old_name)
            assert(mods.json.encode(c.state.bases)==stock and not mock.groups['SQEL-G-blue_depot-2']:isExist())
            assert(c.state.targets.blue_depot.disabled_at==0)
            old.destroy=destroy;mods.director.repair(c)
            assert(c.state.targets.blue_depot.generation==2 and a:world_health())
        ''')

    def test_rebuild_needs_connection_stock_and_temporary_unit_space(self):
        self.partial_depot()
        self.h.run('''
            c.state.time=14400;c.state.zones.galilee.owner='red';mods.director.repair(c)
            assert(c.state.targets.blue_depot.generation==1)
            c.state.zones.galilee.owner='blue';c.state.bases.ramat.resources.supply=24;mods.director.repair(c)
            assert(c.state.targets.blue_depot.generation==1)
            c.state.bases.ramat.resources.supply=25;c.state.bases.ramat.resources.ammo=9;mods.director.repair(c)
            assert(c.state.targets.blue_depot.generation==1)
            c.state.bases.ramat.resources.ammo=10;c.config.unit_budget=c:active_count()+3;mods.director.repair(c)
            assert(c.state.targets.blue_depot.generation==1)
            c.config.unit_budget=c:active_count()+4;mods.director.repair(c)
            assert(c.state.targets.blue_depot.generation==2)
            assert(c.state.bases.ramat.resources.supply==0 and c.state.bases.ramat.resources.ammo==0)
        ''')

    def test_legacy_partial_site_wait_starts_at_load_and_survives_further_reload(self):
        self.partial_depot()
        self.h.run('''
            c.state.time=9000;local saved=c:snapshot();saved.targets.blue_depot.disabled_at=nil
            local resumed=mods.core.new(cfg,a,saved,'legacy',mods.targets,mods.supply)
            assert(resumed.state.targets.blue_depot.disabled_at==9000)
            resumed.state.time=10000
            local again=mods.core.new(cfg,a,resumed:snapshot(),'again',mods.targets,mods.supply)
            assert(again.state.targets.blue_depot.disabled_at==9000 and again:validate_save(again:snapshot()))
            local snapshot=again:snapshot();snapshot.targets.blue_depot.disabled_at=0
            local known=mods.core.new(cfg,a,snapshot,'known',mods.targets,mods.supply)
            assert(known.state.targets.blue_depot.disabled_at==0)
        ''')

    def test_outage_time_corruption_is_rejected(self):
        self.partial_depot()
        for expression in ("-1", "1", "0/0", "'yesterday'", "{}"):
            with self.subTest(expression=expression):
                self.h.run("local s=c:snapshot();s.targets.blue_depot.disabled_at=" + expression + ";assert(not c:validate_save(s))")

    def test_recovery_and_reserve_reports_are_read_only_and_explain_manual_spending(self):
        self.partial_depot()
        self.h.run('''
            c.state.bases.ramat.resources={fuel=8,ammo=22,supply=25}
            local before=mods.json.encode(c:snapshot())
            local view=rt:view();local text=mods.view.overview(view)
            assert(text:find('Automatic dispatch reserve: 8 fuel / 22 ammo / 25 supply',1,true))
            assert(text:find('repair review in at least 240 min',1,true))
            assert(text:find('Requested support may use reserved fuel/ammo.',1,true))
            assert(view.bases[1].ground_required==37 and not view.bases[1].ground_funded)
            assert(mods.json.encode(c:snapshot())==before)
            c.state.bases.ramat.resources.ammo=9
            assert(mods.view.overview(rt:view()):find('needs 25 supply and 10 ammo',1,true))
        ''')

    def test_unrepairable_depot_releases_finite_last_advance_stock_then_defeat(self):
        self.h.run('''
            for i=1,4 do mock.kill('SQEL-G-blue_depot-1-'..i) end
            c.state.bases.ramat.resources={fuel=0,ammo=0,supply=12}
            local funded,required=c:ground_funding(c.base_defs.ramat)
            assert(funded and required==12 and not mods.director.supply_exhausted(c))
            assert(mods.view.overview(rt:view()):find('Recovery reserve released',1,true))
            assert(mods.director.dispatch(c,c.base_defs.ramat,'ASSAULT','south','golan'))
            local ship;for _,s in pairs(c.state.shipments)do ship=s end
            mods.director.tick(c);assert(c.state.status=='ACTIVE' and c.state.bases.ramat.resources.supply==0)
            for i=1,5 do mock.kill('SQEL-G-south_armor-1-'..i) end
            mock.deliver(a,ship);a:observe();mods.director.tick(c)
            assert(c.state.zones.south.owner=='blue' and c.state.status=='DEFEAT')
            assert(c.state.bases.ramat.resources.supply==0 and c:validate_save(c:snapshot()))
            local revision=c.state.revision;mods.director.tick(c);assert(c.state.revision==revision)
        ''')

    def test_incoming_cargo_defers_supply_defeat_until_it_retires(self):
        self.h.run('''
            assert(mods.director.dispatch(c,c.base_defs.ramat,'SUPPLY','galilee','blue_depot'))
            local ship;for _,s in pairs(c.state.shipments)do ship=s end
            for i=1,4 do mock.kill('SQEL-G-blue_depot-1-'..i) end
            c.state.bases.ramat.resources={fuel=0,ammo=0,supply=0}
            assert(not mods.director.supply_exhausted(c));mods.director.tick(c)
            assert(c.state.status=='ACTIVE')
            c.state.time=ship.navigation.deadline+1;mods.director.tick(c)
            assert(ship.outcome=='TIMED_OUT' and c.state.status=='DEFEAT')
            assert(c.state.bases.ramat.resources.supply==0 and c:validate_save(c:snapshot()))
        ''')

    def test_depot_recovery_has_priority_over_other_sites_and_preserves_order(self):
        self.partial_depot()
        self.h.run('''
            for i=1,#c.target_defs.blue_hawk.types do mock.kill('SQEL-G-blue_hawk-1-'..i) end
            table.sort(cfg.targets,function(a,b)return a.id>b.id end)
            local order={};for _,d in ipairs(cfg.targets)do order[#order+1]=d.id end
            c.state.bases.ramat.resources={fuel=0,ammo=10,supply=25};c.state.time=14400
            assert(not mods.director.supply_exhausted(c))
            mods.director.repair(c)
            assert(c.state.targets.blue_depot.generation==2 and c.state.targets.blue_hawk.generation==1)
            for i,d in ipairs(cfg.targets)do assert(d.id==order[i]) end
            assert(not mods.director.supply_exhausted(c) and c.state.bases.ramat.resources.supply==0)
        ''')

    def test_six_hour_fixtures_recover_and_preserve_finite_accounting(self):
        for case in SCENARIOS:
            with self.subTest(case=case):
                report = simulate(self.config, case)
                self.assertTrue(report["valid"])
                self.assertLessEqual(report["peak_units"], self.config["unit_budget"])
                self.assertTrue(all(0 <= v <= 100 for v in report["resources"].values()))
                if case in ("low_stock_depot_loss", "quarter_strength_depot"):
                    self.assertEqual(2, report["depot_generation"])
                    self.assertEqual(1, report["depot_health"])
                    self.assertEqual(240, report["first_rebuild_minute"])
                    self.assertTrue(report["first_supply_minute"])
                if case in ("steady", "attrition"):
                    self.assertEqual(8, report["accepted"])
                if case == "corridor_cut":
                    self.assertGreaterEqual(report["first_supply_minute"], 120)
                    self.assertLess(report["first_supply_minute"], 180)
                if case == "empty_legacy_stock":
                    self.assertEqual({"fuel":0,"ammo":0,"supply":0}, report["resources"])
                    self.assertEqual(1, report["depot_generation"])
                    self.assertEqual("DEFEAT", report["status"])
