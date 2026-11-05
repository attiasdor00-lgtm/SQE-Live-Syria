"""Regression cases found while reviewing the 0.1.4 runtime boundaries."""
import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from test_live import Harness, build


class DebugCase(unittest.TestCase):
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

    def test_missing_explicit_selection_never_displays_another_target(self):
        self.h.run('''
            local view=rt:view();assert(#view.tasks>1)
            assert(mods.view.selected(view,nil))
            assert(not mods.view.selected(view,'expired-convoy'))
            view.task={target='expired-convoy',role='CAS'}
            local text=mods.view.task(view,view.tasks[1].id)
            assert(text:find('CAS / expired-convoy',1,true))
        ''')

    def test_completion_notification_error_does_not_stop_or_duplicate_campaign(self):
        self.assertTrue(self.h.command("accept", target="south_armor").ok)
        self.h.run('''
            local out=trigger.action.outText
            trigger.action.outText=function()error('injected notification failure')end
            for i=1,5 do mock.kill('SQEL-G-south_armor-1-'..i) end
            assert(not rt.failed,tostring(rt.failed))
            assert(c.state.completed==1 and not c.state.task)
            trigger.action.outText=out;mock.advance(4)
            assert(c.state.completed==1 and c.state.time==4 and not rt.failed)
        ''')

    def test_save_immediately_after_dispatch_restores_when_road_query_fails(self):
        self.h.run('''
            assert(mods.director.dispatch(c,c.base_defs.ramat,'SUPPLY','galilee','blue_depot'))
            for _,s in pairs(c.state.shipments)do ship=s end
            assert(a:save(c:snapshot()))
        ''')
        saved = self.h.run("return fs.files[cfg.id]")
        resumed = Harness(self.config)
        resumed.g.saved = saved
        resumed.run("fs.files[cfg.id]=saved;mock.road_error=true")
        resumed.start()
        resumed.run('''
            local n=0
            for _,s in pairs(c.state.shipments)do
                n=n+1;assert(s.status=='MOVING' and s.navigation.state=='BLOCKED')
                assert(c.count(s.alive)==4 and next(s.positions))
            end
            assert(n==1 and not rt.failed)
        ''')

    def test_legacy_convoy_without_positions_can_restore_after_source_destruction(self):
        self.h.run('''
            assert(mods.director.dispatch(c,c.base_defs.ramat,'SUPPLY','galilee','blue_depot'))
            for _,s in pairs(c.state.shipments)do s.positions={} end
            for i=1,#c.target_defs.blue_depot.types do mock.kill(a.ground_groups.blue_depot..'-'..i) end
        ''')
        saved = self.h.run("return mods.json.encode(c:snapshot())")
        resumed = Harness(self.config)
        resumed.g.saved = saved
        resumed.run("fs.files[cfg.id]=saved;mock.road_error=true")
        resumed.start()
        resumed.run('''
            for _,s in pairs(c.state.shipments)do
                assert(s.navigation.state=='BLOCKED' and next(s.positions) and c.count(s.alive)==4)
            end
            assert(c:target_health('blue_depot')==0 and not rt.failed)
            assert(c:validate_save(c:snapshot()))
        ''')
