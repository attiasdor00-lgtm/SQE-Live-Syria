"""Shipped Israel/Syria profile, native mission ownership and legacy isolation."""
import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest
import zipfile

from test_live import Harness, LUA, ROOT
import test_live as live_tests
from sqe.live.build import build, content
from balance_sim import simulate

FIELDS = {"Eyn Shemer", "Haifa", "Kiryat Shmona", "Megiddo", "Ramat David",
          "Rosh Pina", "Nevatim", "Herzliya", "Hatzerim", "Kedem", "Teyman",
          "Tel Nof", "Ben Gurion", "Hatzor", "Palmachim"}


class GeographyCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.bundle = Path(cls.temp.name) / "bundle"
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            build(cls.bundle)
        cls.config = json.loads((cls.bundle / "content.json").read_text())

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def setUp(self):
        self.h = Harness(self.config).start()

    def test_default_covers_all_fifteen_fields_and_keeps_aircraft_finite(self):
        cfg = self.config
        self.assertEqual("syria_israel_solo", cfg["id"])
        self.assertEqual("syria-israel-1", cfg["content_version"])
        self.assertEqual(11, len(cfg["zones"]))
        self.assertEqual(FIELDS, {f["airport"] for f in cfg["airfields"]})
        self.assertEqual(15, len({f["airport_id"] for f in cfg["airfields"]}))
        owners = {z["id"]:z["owner"] for z in cfg["zones"]}
        self.assertTrue(all(owners[f["zone"]] == "blue" for f in cfg["airfields"]))
        bases = [b for b in cfg["bases"] if b["side"] == "blue"]
        self.assertEqual({"ramat", "tel_nof", "hatzor", "nevatim", "hatzerim"}, {b["id"] for b in bases})
        totals = {}
        for b in bases:
            for ac, n in b["aircraft"].items(): totals[ac] = totals.get(ac, 0) + n
        self.assertEqual({"F-16C":14,"F-15C":8,"E-3A":2,"KC-135":2}, totals)
        self.assertEqual(114, self.h.run("return c:active_count()"))
        self.assertEqual(27, len(cfg["targets"]))

    def test_miz_warehouses_and_runtime_agree_on_blue_airfield_ownership(self):
        from dcs import lua
        with zipfile.ZipFile(self.bundle / "Missions/SQE_Live_Syria.miz") as z:
            self.assertIsNone(z.testzip())
            warehouses = lua.loads(z.read("warehouses").decode())["warehouses"]
            mission = lua.loads(z.read("mission").decode())["mission"]
        for f in self.config["airfields"]:
            self.assertEqual("BLUE", warehouses["airports"][f["airport_id"]]["coalition"], f["airport"])
        self.assertEqual("Syria", mission["theatre"])
        flights = [group for country in mission["coalition"]["blue"]["country"].values()
                   for group in country.get("plane", {}).get("group", {}).values()]
        flight = next(group for group in flights if group["name"] == "Viper Live")
        lead, wingman = flight["units"][1], flight["units"][2]
        self.assertEqual((self.config["player_unit"], "Player"), (lead["name"], lead["skill"]))
        self.assertEqual((self.config["wingman_unit"], "High"), (wingman["name"], wingman["skill"]))
        self.assertNotEqual(lead["parking"], wingman["parking"])
        self.assertEqual(lead["payload"], wingman["payload"])
        self.assertEqual(("Viper11", "Viper12"), (lead["callsign"]["name"], wingman["callsign"]["name"]))
        self.h.run('''
            for _,f in ipairs(cfg.airfields)do
                assert(mock.bases[f.airport].side==2 and mock.bases[f.airport].auto==false)
            end
            assert(mock.bases.Damascus.side==1 and mock.bases.Shayrat.side==1)
        ''')

    def test_sector_loss_changes_only_its_airfields_and_surviving_bases_remain_available(self):
        self.h.run('''
            c.state.zones.central.owner='red';a:sync_bases()
            for _,name in ipairs({'Tel Nof','Hatzor','Ben Gurion','Palmachim'})do assert(mock.bases[name].side==1) end
            assert(mock.bases['Ramat David'].side==2 and mock.bases.Nevatim.side==2)
            local offer=c:flight_offer('AWACS','blue')
            assert(offer.available and offer.base=='nevatim')
            assert(c:launch('AWACS','blue',nil,false))
            c.state.zones.central.owner='blue';a:sync_bases()
            assert(mock.bases.Palmachim.side==2 and c:validate_save(c:snapshot()))
        ''')

    def test_supply_paths_use_regional_depots_and_isolation_does_not_cut_every_base(self):
        self.h.run('''
            assert(mods.supply.offer(c,c.base_defs.tel_nof).source=='blue_central_depot')
            assert(mods.supply.offer(c,c.base_defs.hatzerim).source=='blue_negev_depot')
            assert(mods.supply.path(c,'blue','negev','golan'))
            c.state.zones.sharon.owner='red'
            assert(not mods.supply.path(c,'blue','negev','galilee'))
            assert(mods.supply.offer(c,c.base_defs.nevatim).source=='blue_negev_depot')
            assert(mods.supply.offer(c,c.base_defs.ramat).source=='blue_depot')
            assert(c:validate_save(c:snapshot()))
        ''')

    def test_eleven_sector_native_map_fits_and_lists_controlled_civil_fields(self):
        self.h.g.lua_path = str(LUA)
        self.h.g.ui = self.h.lua.execute((Path(__file__).parent / "ui_mock.lua").read_text())
        self.h.lua.execute((LUA / "hook.lua").read_text())
        self.h.run('''
            local before=mods.json.encode(c:snapshot());local view=rt:view()
            local layout=assert(mods.map.layout(view,368,300));assert(#layout.nodes==11)
            for i,p in ipairs(layout.nodes) do
                assert(p.x>=0 and p.y>=0 and p.x+p.w<=368 and p.y+p.h<=300 and p.h>=20)
                for j=i+1,#layout.nodes do local q=layout.nodes[j]
                    assert(not(p.x<q.x+q.w and q.x<p.x+p.w and p.y<q.y+q.h and q.y<p.y+p.h))
                end
            end
            local detail=mods.map.detail(view,{zone='central',task=false},mods.view)
            assert(detail:find('Palmachim',1,true) and detail:find('Ben Gurion',1,true))
            assert(mods.view.front(view):find('Kiryat Shmona',1,true))
            ui.load_mission()
            assert(ui.window and mods.json.encode(c:snapshot())==before)
            ui.hotkeys['Ctrl+Shift+q']()
            assert(ui.window.Overview.text:find('Operation Northern Watch',1,true))
            assert(not ui.window.Accept.visible and not ui.window.CAP.visible)
            ui.window.Recommended.click()
            assert(ui.window.Accept.visible and ui.window.Target.text:find('CAMPAIGN EFFECT',1,true))
            assert(not c.state.task and next(fs.queue)==nil)
        ''')

    def test_native_f10_drawings_follow_campaign_and_keep_task_markers(self):
        self.h.run('''
            local function field(name)
                for _,d in pairs(mock.drawings) do
                    assert(d.side==2)
                    if d.kind=='text' and d.args[6]==name then return d.args[2] end
                end
            end
            local function lines()
                local n=0
                for _,d in pairs(mock.drawings) do if d.kind=='line' then n=n+1 end end
                return n
            end
            local before=mock.draw_calls
            assert(before>0 and lines()>0 and field('[BASE] Tel Nof')[3]==1)
            assert(a:campaign_map(mods.json.encode) and mock.draw_calls==before)
            trigger.action.markToCoalition(870001,'Player task',{x=0,y=0,z=0},2,true)
            c.state.zones.central.owner='red'
            assert(a:campaign_map(mods.json.encode) and mock.draw_calls>before)
            assert(field('[BASE] Tel Nof')[1]==1 and mock.marks[870001])
            for _,t in ipairs(cfg.targets) do
                if t.kind=='DEPOT' then c.state.targets[t.id].alive={} end
            end
            assert(a:campaign_map(mods.json.encode) and lines()==0)
        ''')

    def test_ai_operations_continue_without_an_assignment_if_map_api_fails(self):
        self.h.run('''
            local draw=trigger.action.circleToAll
            trigger.action.circleToAll=function()error('injected map failure')end
            c.state.zones.central.owner='red'
            mock.advance(30)
            assert(not rt.failed and not c.state.task)
            assert(rt.diagnostics.checks.f10_campaign_map.status=='FAIL')
            trigger.action.circleToAll=draw
            mock.advance(300)
            assert(rt.diagnostics.checks.f10_campaign_map.status=='PASS')
            assert(not c.state.task and next(c.state.flights))
        ''')

    def test_new_campaign_does_not_consume_or_reset_legacy_checkpoint(self):
        old = json.loads((ROOT / "sqe/live/syria_legacy.json").read_text())
        self.assertEqual("syria_cedar_current", old["id"])
        with zipfile.ZipFile(self.bundle / "Missions/SQE_Live_Syria_Legacy.miz") as z:
            self.assertIsNone(z.testzip())
            text = z.read("mission").decode()
            self.assertIn("syria_cedar_current", text)
            self.assertIn("syria-1", text)
        h = Harness(self.config)
        h.run("fs.files.syria_cedar_current='existing legacy checkpoint'")
        h.start()
        h.run("assert(fs.files.syria_cedar_current=='existing legacy checkpoint' and c.state.campaign=='syria_israel_solo')")
        self.h.run('''
            local s=c:snapshot();s.campaign='syria_cedar_current';s.content='syria-1'
            assert(not c:validate_save(s))
        ''')

    def test_regional_logistics_and_flights_stay_below_original_unit_budget(self):
        self.h.run('''
            for _,b in pairs(c.state.bases)do b.resources={fuel=50,ammo=50,supply=50} end
            mods.director.logistics(c)
            for i=1,4 do mods.director.air(c,'blue');mods.director.air(c,'red') end
            assert(c:active_count()<=180 and c.count(c.state.flights)<=9)
            assert(c.count(c.state.shipments)==7)
            assert(c:validate_save(c:snapshot()))
        ''')

    def test_unknown_scenario_fails_before_export(self):
        with self.assertRaises(ValueError): content(scenario="missing")

    def test_many_bases_do_not_duplicate_the_same_ground_advance(self):
        self.h.run('''
            for i=1,5 do mock.kill('SQEL-G-south_armor-1-'..i) end
            mods.director.logistics(c)
            local n=0
            for _,s in pairs(c.state.shipments) do if s.side=='blue' and s.kind=='ASSAULT' and s.zone=='south' then n=n+1 end end
            assert(n==1 and c:validate_save(c:snapshot()))
        ''')

    def test_six_hour_expanded_profile_preserves_stock_and_unit_limits(self):
        for case in ('steady','low_stock_depot_loss','attrition'):
            with self.subTest(case=case):
                r=simulate(self.config,case)
                self.assertTrue(r['valid'])
                self.assertLessEqual(r['peak_units'],180)
                self.assertTrue(all(v>=0 for v in r['resources'].values()))


class GeographyInstallerCase(live_tests.InstallerCase):
    """Run the existing installer contracts against the shipped default bundle."""
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            build(cls.bundle)

    def test_installs_and_removes_both_missions_without_touching_other_missions(self):
        self.install()
        self.assertTrue((self.profile / 'Missions/SQE-Live/SQE_Live_Syria_Legacy.miz').exists())
        other=self.profile / 'Missions/SQE-Live/other.miz'
        other.write_bytes(b'unrelated mission')
        self.install('Uninstall-SQE-Live.ps1')
        self.assertFalse((self.profile / 'Missions/SQE-Live/SQE_Live_Syria_Legacy.miz').exists())
        self.assertFalse((self.profile / 'Missions/SQE-Live/SQE_Live_Syria.miz').exists())
        self.assertEqual(b'unrelated mission',other.read_bytes())
