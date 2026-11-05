"""Lost-airframe cleanup and retained runtime data; no native DCS execution."""
import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from test_live import Harness
from sqe.live.build import build


class RetentionCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory()
        with contextlib.redirect_stdout(io.StringIO()),contextlib.redirect_stderr(io.StringIO()):build(Path(cls.temp.name))
        cls.config=json.loads((Path(cls.temp.name)/'content.json').read_text())

    @classmethod
    def tearDownClass(cls):cls.temp.cleanup()

    def setUp(self):
        self.h=Harness(self.config).start()
        self.h.run('''
            c.state.next_director=1e9;c.state.next_logistics=1e9;c.state.next_repair=1e9
            assert(c:launch('CAP','blue',nil,false))
            for _,f in pairs(c.state.flights)do flight=f end
            group=mock.groups[a.air_groups[flight.id]]
        ''')

    def test_partial_ejection_retires_only_recorded_lost_member(self):
        self.h.run('''
            local u=group.units[1]
            mock.emit({id=world.event.S_EVENT_EJECTION,initiator=u})
            assert(u:isExist() and not flight.alive['1'])
            a:observe()
            assert(not u:isExist() and group.units[2]:isExist() and flight.status~='COMPLETE')
            assert(not a.registry[u.name] and #c.state.maintenance==0)
            mock.land_flight(a,flight)
            assert(c.state.maintenance[1].count==1 and c:validate_save(c:snapshot()))
        ''')

    def test_complete_ejection_cleans_live_group_and_registry_after_state_purge(self):
        self.h.run('''
            for _,u in ipairs(group.units)do mock.emit({id=world.event.S_EVENT_EJECTION,initiator=u}) end
            assert(group:isExist() and flight.status=='COMPLETE')
            c:tick(302);assert(not c.state.flights[flight.id])
            a:observe()
            assert(not group:isExist() and not a.air_groups[flight.id])
            for _,u in ipairs(group.units)do assert(not a.registry[u.name] and not u:isExist()) end
            assert(#c.state.maintenance==0 and c.state.bases.ramat.ready['F-15C']==2)
        ''')

    def test_completed_flight_cleans_group_before_five_minute_history_purge(self):
        self.h.run('''
            for _,u in ipairs(group.units)do mock.emit({id=world.event.S_EVENT_UNIT_LOST,initiator=u}) end
            a:observe()
            assert(not group:isExist() and c.state.flights[flight.id])
            assert(next(a.contacts)==nil and next(a.landed)==nil)
            for _,u in ipairs(group.units)do assert(not a.registry[u.name]) end
        ''')

    def test_live_wingman_and_other_flight_are_not_cleaned(self):
        self.h.run('''
            assert(c:launch('AWACS','blue',nil,false))
            local awacs;for _,f in pairs(c.state.flights)do if f.role=='AWACS' then awacs=f end end
            mock.emit({id=world.event.S_EVENT_EJECTION,initiator=group.units[1]})
            a:observe()
            assert(group.units[2]:isExist() and mock.groups[a.air_groups[awacs.id]]:isExist())
            assert(awacs.status~='COMPLETE' and #c.state.maintenance==0)
        ''')

    def test_cleanup_failure_stops_updates_and_preserves_last_checkpoint(self):
        self.h.run('''
            assert(a:save(c:snapshot()));local before=fs.files[cfg.id]
            mock.emit({id=world.event.S_EVENT_EJECTION,initiator=group.units[1]})
            group.units[1].destroy=function()error('injected retirement failure')end
            mock.advance(2)
            assert(rt.failed and fs.files[cfg.id]==before and #c.state.maintenance==0)
        ''')

    def test_repeated_retirement_does_not_debit_or_credit_again(self):
        self.h.run('''
            mock.land_flight(a,flight)
            local before=mods.json.encode({bases=c.state.bases,maintenance=c.state.maintenance,alive=flight.alive})
            for i=1,3 do a:retire_flight(flight);a:observe() end
            assert(mods.json.encode({bases=c.state.bases,maintenance=c.state.maintenance,alive=flight.alive})==before and #c.state.maintenance==1)
            for _,u in ipairs(group.units)do assert(not a.registry[u.name]) end
        ''')

    def test_short_soak_keeps_runtime_maps_and_command_backlog_bounded(self):
        import sys
        sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'tools'))
        from live_soak import measure
        r=measure(self.config,hours=1)
        self.assertEqual(1800,r['ticks'])
        self.assertEqual(0,r['peaks']['live_lost_aircraft'])
        self.assertLessEqual(r['peaks']['registry'],180)
        self.assertLessEqual(r['peaks']['journal'],128)
        self.assertLessEqual(r['peaks']['log'],80)
        self.assertEqual(0,r['final']['queue'])
        self.assertLess(r['peaks']['save_bytes'],4*1024*1024)
        self.assertLess(r['peaks']['status_bytes'],512*1024)

    def test_twenty_default_profile_resumes_preserve_one_recorded_aircraft_loss(self):
        self.h.run("mock.kill(group.units[1].name)")
        saved=self.h.run('return mods.json.encode(c:snapshot())')
        for cycle in range(20):
            h=Harness(self.config);h.g.saved=saved;h.run('fs.files[cfg.id]=saved');h.start()
            h.run('''
                c.state.next_director=1e9;c.state.next_logistics=1e9;c.state.next_repair=1e9
                c:tick(601)
                assert(c.state.bases.ramat.ready['F-15C']==3 and #c.state.maintenance==0)
                assert(c:validate_save(c:snapshot()))
            ''')
            saved=h.run('return mods.json.encode(c:snapshot())')
