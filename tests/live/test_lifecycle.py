"""Mission/UI boundaries under Lua 5.1; no native rendering or DCS execution."""
import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from test_live import Harness, LUA
from sqe.live.build import build


class LifecycleCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            build(Path(cls.temp.name))
        cls.config = json.loads((Path(cls.temp.name)/"content.json").read_text())

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def setUp(self):
        self.h = Harness(self.config).start()
        self.h.g.lua_path = str(LUA)
        self.h.g.ui = self.h.lua.execute((Path(__file__).parent/"ui_mock.lua").read_text())
        self.h.lua.execute((LUA/"hook.lua").read_text())

    def test_cold_start_rejects_same_second_status_already_on_disk(self):
        self.h.run('''
            ui.handler.onMissionLoadBegin();ui.handler.onMissionLoadEnd();ui.handler.onSimulationFrame()
            ui.hotkeys['Ctrl+Shift+q']()
            assert(not ui.window.Accept.enabled and not mods.json.decode(fs.reports.ui).status_connected)
            ui.window.Accept.click();assert(next(fs.queue)==nil)
            local v=mods.json.decode(fs.status_text);v.session='new-same-second'
            fs.status_text=mods.json.encode(v);mock.clock=mock.clock+1;ui.handler.onSimulationFrame()
            assert(ui.window.Accept.enabled and mods.json.decode(fs.reports.ui).in_mission)
        ''')

    def test_transition_rejects_old_session_even_after_long_terrain_load(self):
        self.h.run('''
            ui.load_mission();ui.hotkeys['Ctrl+Shift+q']();ui.window.Accept.click()
            local old=mods.json.decode(fs.status_text)
            ui.handler.onMissionLoadBegin()
            mock.clock=mock.clock+30;old.heartbeat=fs.now();fs.status_text=mods.json.encode(old)
            ui.handler.onSimulationFrame();assert(not ui.window.Accept.enabled)
            ui.handler.onMissionLoadEnd();ui.handler.onSimulationFrame()
            assert(not ui.window.Accept.enabled and not mods.json.decode(fs.reports.ui).status_connected)
            local new=mods.json.decode(fs.status_text);new.session='next';new.started_at=old.started_at
            fs.status_text=mods.json.encode(new);mock.clock=mock.clock+1;ui.handler.onSimulationFrame()
            assert(ui.window.Accept.enabled and not ui.window.Status.text:find('Command queued',1,true))
        ''')

    def test_stop_cleans_state_and_cursor_even_when_widget_hiding_fails(self):
        self.h.run('''
            ui.load_mission();ui.hotkeys['Ctrl+Shift+q']();ui.window.Accept.click()
            local hide=ui.window.Target.setVisible
            ui.window.Target.setVisible=function()error('injected hide failure')end
            assert(select('#',ui.handler.onSimulationStop())==0)
            local report=mods.json.decode(fs.reports.ui)
            assert(not report.in_mission and not report.visible and not report.status_connected and report.session==c.session)
            assert(not ui.window.cursor and not ui.window.Target.focus)
            ui.window.Target.setVisible=hide;ui.hotkeys['Ctrl+Shift+q']()
            assert(not ui.window.Accept.enabled and not ui.window.cursor)
            mock.clock=mock.clock+1;ui.handler.onSimulationFrame()
            assert(not ui.window.Accept.enabled)
        ''')

    def test_load_begin_cleans_pending_despite_widget_failure(self):
        self.h.run('''
            ui.load_mission();ui.hotkeys['Ctrl+Shift+q']();ui.window.Accept.click()
            local hide=ui.window.Target.setVisible
            ui.window.Target.setVisible=function()error('injected load hide failure')end
            assert(select('#',ui.handler.onMissionLoadBegin())==0)
            ui.window.Target.setVisible=hide
            local v=mods.json.decode(fs.status_text);v.session='fresh-after-error'
            fs.status_text=mods.json.encode(v)
            ui.handler.onMissionLoadEnd();mock.clock=mock.clock+1;ui.handler.onSimulationFrame()
            ui.hotkeys['Ctrl+Shift+q']()
            assert(ui.window.Accept.enabled and not ui.window.Status.text:find('Command queued',1,true))
        ''')

    def test_frame_diagnostic_and_logging_failure_never_escapes_callback(self):
        self.h.run('''
            ui.load_mission()
            fs.report=function()error('report failure')end
            net.log=function()error('log failure')end
            mock.clock=mock.clock+6
            assert(select('#',ui.handler.onSimulationFrame())==0)
            assert(select('#',ui.handler.onSimulationStop())==0)
            assert(not ui.window.cursor)
        ''')

    def test_bad_status_timestamp_does_not_replace_last_valid_view(self):
        self.h.run('''
            ui.load_mission();ui.hotkeys['Ctrl+Shift+q']()
            local v=mods.json.decode(fs.status_text)
            -- Lua's JSON decoder accepts a numeric exponent that overflows.
            v.session='overflow-session'
            local raw=mods.json.encode(v):gsub('"started_at":100000','"started_at":1e999')
            assert(raw~=fs.status_text);fs.status_text=raw
            mock.clock=mock.clock+6;ui.handler.onSimulationFrame()
            assert(ui.window.Accept.enabled)
            local report=mods.json.decode(fs.reports.ui)
            assert(report.session==c.session)
        ''')

    def test_input_callback_error_is_contained_and_later_toggle_works(self):
        self.h.run('''
            ui.load_mission();local skin=ui.window.setSkin
            ui.window.setSkin=function()error('injected skin failure')end
            assert(select('#',ui.hotkeys['Ctrl+Shift+q']())==0)
            ui.window.setSkin=skin
            assert(select('#',ui.hotkeys['Ctrl+Shift+q']())==0)
            assert(not ui.window.cursor)
            ui.hotkeys['Ctrl+Shift+q']();assert(ui.window.cursor and ui.window.Accept.enabled)
        ''')
