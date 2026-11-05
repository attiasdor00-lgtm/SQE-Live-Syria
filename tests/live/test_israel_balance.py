"""Israel solo attrition/accounting boundaries; not a DCS combat simulation."""
import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from test_live import Harness, LUA
from sqe.live.build import build


class IsraelBalanceCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory()
        with contextlib.redirect_stdout(io.StringIO()),contextlib.redirect_stderr(io.StringIO()):
            build(Path(cls.temp.name))
        cls.config=json.loads((Path(cls.temp.name)/'content.json').read_text())

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def setUp(self):
        self.h=Harness(self.config).start()
        self.h.run('''
            c.state.next_director=1e9;c.state.next_logistics=1e9;c.state.next_repair=1e9
            function fragment()
                for _,b in ipairs(cfg.bases)do
                    if b.side=='blue' then
                        for ac in pairs(c.state.bases[b.id].ready)do c.state.bases[b.id].ready[ac]=1 end
                    end
                end
            end
        ''')

    def test_requested_support_can_use_a_stranded_single_at_full_cost(self):
        self.h.run('''
            fragment();local before=mods.json.encode(c:snapshot())
            local q=c:support_offer('STRIKE','south_sam')
            assert(q.available and q.count==1 and q.base=='ramat')
            assert(q.reason:find('single',1,true) and q.cost.ammo==12 and q.cost.fuel==8)
            assert(mods.json.encode(c:snapshot())==before)
            assert(not c:flight_offer('STRIKE','blue','south_sam',true).available)
            assert(c:launch('STRIKE','blue','south_sam',false))
            for _,f in pairs(c.state.flights)do
                assert(f.count==1 and c.count(f.alive)==1 and #mock.groups[a.air_groups[f.id]].units==1)
            end
            assert(c.state.bases.ramat.ready['F-16C']==0)
            assert(c.state.bases.ramat.resources.fuel==92 and c.state.bases.ramat.resources.ammo==88)
            assert(c:validate_save(c:snapshot()))
        ''')

    def test_funded_pair_at_another_base_has_priority_over_single(self):
        self.h.run('''
            fragment();c.state.bases.hatzor.ready['F-16C']=2
            local q=c:flight_offer('STRIKE','blue','south_sam')
            assert(q.available and q.count==2 and q.base=='hatzor')
            c.state.bases.hatzor.resources.ammo=11
            q=c:flight_offer('STRIKE','blue','south_sam')
            assert(q.available and q.count==1 and q.base=='ramat')
            c.state.zones.galilee.owner='red'
            q=c:flight_offer('STRIKE','blue','south_sam')
            assert(q.available and q.count==1 and q.base=='nevatim')
        ''')

    def test_automatic_blue_and_red_dispatch_do_not_use_single_fallback(self):
        self.h.run('''
            fragment()
            assert(not c:flight_offer('CAP','blue',nil,true).available)
            for _,b in ipairs(cfg.bases)do if b.side=='red' then
                for ac in pairs(c.state.bases[b.id].ready)do c.state.bases[b.id].ready[ac]=1 end
            end end
            assert(not c:flight_offer('CAP','red',nil,true).available)
            assert(not c:flight_offer('CAP','red',nil,false).available)
            assert(c:support_offer('AWACS',nil).count==1 and c:support_offer('TANKER',nil).count==1)
        ''')

    def test_fallback_respects_resources_capture_assignment_and_global_limits(self):
        self.h.run('''
            fragment()
            for _,b in ipairs(cfg.bases)do if b.side=='blue' then c.state.bases[b.id].resources.ammo=11 end end
            assert(c:flight_offer('STRIKE','blue','south_sam').code=='RESOURCES')
            c.state.bases.ramat.resources.ammo=12
            cfg.unit_budget=c:active_count()
            assert(c:flight_offer('STRIKE','blue','south_sam').code=='UNIT_LIMIT')
            cfg.unit_budget=180;cfg.max_flights=0
            assert(c:flight_offer('STRIKE','blue','south_sam').code=='FLIGHT_LIMIT')
            cfg.max_flights=9
            assert(c:launch('STRIKE','blue','south_sam',false))
            c.state.bases.hatzor.resources.ammo=12
            assert(c:flight_offer('STRIKE','blue','south_sam').code=='ASSIGNED')
            for _,id in ipairs({'galilee','central','negev'})do c.state.zones[id].owner='red' end
            assert(c:flight_offer('STRIKE','blue','south_sam').code=='BASE_LOST')
        ''')

    def test_pair_is_not_reduced_just_to_bypass_unit_budget(self):
        self.h.run('''
            cfg.unit_budget=c:active_count()+1
            assert(c:flight_offer('STRIKE','blue','south_sam').code=='UNIT_LIMIT')
            assert(next(c.state.flights)==nil)
        ''')

    def test_failed_single_spawn_retains_all_stock(self):
        self.h.run('''
            fragment();local before=mods.json.encode(c.state.bases)
            mock.fail_spawn=true
            assert(not c:launch('SEAD','blue','south_sam',false))
            assert(mods.json.encode(c.state.bases)==before and next(c.state.flights)==nil)
        ''')

    def test_single_survivor_recovers_once_and_lost_single_does_not_return(self):
        self.h.run('''
            fragment();assert(c:launch('STRIKE','blue','south_sam',false))
            local f;for _,v in pairs(c.state.flights)do f=v end
            mock.land_flight(a,f);mock.land_flight(a,f)
            assert(#c.state.maintenance==1 and c.state.maintenance[1].count==1)
            c:tick(600);assert(c.state.bases.ramat.ready['F-16C']==1)
            assert(c:launch('STRIKE','blue','south_sam',false))
            for _,v in pairs(c.state.flights)do if v.status~='COMPLETE' then mock.kill(a.air_groups[v.id]..'-1') end end
            c:tick(600);assert(c.state.bases.ramat.ready['F-16C']==0 and #c.state.maintenance==0)
            assert(c:validate_save(c:snapshot()))
        ''')

    def test_active_single_checkpoint_resume_does_not_create_aircraft(self):
        self.h.run("fragment();assert(c:launch('STRIKE','blue','south_sam',false))")
        saved=self.h.run('return mods.json.encode(c:snapshot())')
        resumed=Harness(self.config);resumed.g.saved=saved
        resumed.run('fs.files[cfg.id]=saved');resumed.start()
        resumed.run('''
            assert(c.state.bases.ramat.ready['F-16C']==0 and #c.state.maintenance==1)
            assert(c.state.maintenance[1].count==1)
            c:tick(600);assert(c.state.bases.ramat.ready['F-16C']==1)
            assert(c:validate_save(c:snapshot()))
        ''')

    def test_native_and_f10_support_read_models_explain_single_aircraft(self):
        self.h.run('fragment();rt:publish()')
        self.h.g.lua_path=str(LUA)
        self.h.g.ui=self.h.lua.execute((Path(__file__).parent/'ui_mock.lua').read_text())
        self.h.lua.execute((LUA/'hook.lua').read_text())
        self.h.run('''
            ui.load_mission();ui.window.SupportTab.click()
            assert(ui.window.Overview.text:find('single',1,true))
            local seen=false
            for _,m in ipairs(mock.menus)do if m.name=='Support availability' then
                m.fn();seen=true;assert(mock.messages[#mock.messages]:find('single',1,true))
            end end
            assert(seen)
        ''')

    def test_eight_six_hour_regional_workloads_preserve_finite_stock_and_local_supply(self):
        from regional_balance_sim import REGIONAL_SCENARIOS, simulate_regional
        for case in REGIONAL_SCENARIOS:
            with self.subTest(case=case):
                r=simulate_regional(self.config,case)
                self.assertTrue(r['valid'])
                self.assertLessEqual(r['peak_units'],180)
                for b in r['bases'].values():
                    self.assertTrue(all(v>=0 for v in b['ready'].values()))
                    self.assertTrue(all(0<=v<=100 for v in b['resources'].values()))
                if case in ('steady','attrition','fragmented_survivors','ramat_captured','central_captured','corridor_isolation'):
                    self.assertEqual(8,r['accepted'])
                if case=='fragmented_survivors':
                    self.assertEqual(8,r['single_requests'])
                    self.assertEqual(2,r['aircraft_losses'])
                    self.assertEqual(r['initial_aircraft']-r['seeded_aircraft_losses']-r['aircraft_losses'],r['final_aircraft'])
                if case=='ramat_captured':
                    self.assertTrue(all(q['base']!='ramat' for q in r['requests'] if q['minute']>=60 and q['accepted']))
                if case=='central_captured':
                    self.assertTrue(all(q['base'] not in ('tel_nof','hatzor') for q in r['requests'] if q['minute']>=60 and q['accepted']))
                if case=='corridor_isolation':
                    self.assertEqual(0,r['deliveries_during_cut'])
                    self.assertGreater(r['deliveries_after_reconnect'],0)
                    self.assertGreater(r['delivered'].get('ramat',0),0)
                if case=='exhausted_aircraft':
                    self.assertEqual(0,r['accepted'])
                    self.assertTrue(all(q['code']=='AIRCRAFT' for q in r['requests']))
                if case=='all_bases_lost':
                    self.assertEqual(1,r['accepted'])
                    self.assertTrue(all(q['code']=='BASE_LOST' for q in r['requests'] if q['minute']>=60))
