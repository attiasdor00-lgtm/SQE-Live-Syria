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
        self.assertEqual("syria-israel-3", cfg["content_version"])
        self.assertEqual(39, len(cfg["zones"]))
        owners = {z["id"]:z["owner"] for z in cfg["zones"]}
        blue_fields = {f["airport"] for f in cfg["airfields"] if owners[f["zone"]] == "blue"}
        red_fields = {f["airport"] for f in cfg["airfields"] if owners[f["zone"]] == "red"}
        self.assertEqual(FIELDS, blue_fields)
        self.assertEqual({"Naqoura", "Beirut-Rafic Hariri", "Rayak", "Rene Mouawad"}, red_fields)
        self.assertEqual(32, sum(z["owner"] == "red" for z in cfg["zones"]))
        self.assertEqual(12, len(cfg["farps"]))
        self.assertTrue(all(len(z["mission_chain"]) == 4 for z in cfg["zones"] if z["owner"] == "red"))
        bases = [b for b in cfg["bases"] if b["side"] == "blue"]
        self.assertEqual({"ramat", "tel_nof", "hatzor", "nevatim", "hatzerim"}, {b["id"] for b in bases})
        totals = {}
        for b in bases:
            for ac, n in b["aircraft"].items(): totals[ac] = totals.get(ac, 0) + n
        self.assertEqual({"F-16C":14,"F-15C":8,"E-3A":2,"KC-135":2}, totals)
        self.assertLessEqual(self.h.run("return c:active_count()"), cfg["unit_budget"])
        self.assertEqual(111, len(cfg["targets"]))
        self.assertEqual(3, self.h.run('local n=0;for id in pairs(a.ground_groups)do if c.target_defs[id] and c.target_defs[id].side=="red" then n=n+1 end end;return n'))

    def test_red_network_has_32_ordered_chains_and_real_world_inspired_dcs_units(self):
        cfg = self.config
        zones = {z["id"]: z for z in cfg["zones"]}
        red = [z for z in cfg["zones"] if z["owner"] == "red"]
        targets = {t["id"]: t for t in cfg["targets"]}
        self.assertEqual((12, 20),
                         (sum(z["nation"] == "Lebanon" for z in red),
                          sum(z["nation"] == "Syria" for z in red)))
        reached, pending = {cfg["zones"][0]["id"]}, [cfg["zones"][0]["id"]]
        while pending:
            current = pending.pop()
            for neighbor in zones[current]["neighbors"]:
                self.assertIn(current, zones[neighbor]["neighbors"])
                if neighbor not in reached:
                    reached.add(neighbor); pending.append(neighbor)
        self.assertEqual(set(zones), reached)
        for zone in red:
            self.assertEqual(["SEAD", "DEAD", "STRIKE", "CAS"], zone["mission_chain"])
            sam, strike, armor = (targets[zone["objectives"][key]] for key in ("sam", "strike", "armor"))
            self.assertEqual(("SAM", "ARMOR"), (sam["kind"], armor["kind"]))
            self.assertIn(strike["kind"], {"DEPOT", "FUEL", "C2"})
            self.assertTrue(zone["formation"] and sam["formation"] == zone["formation"] == armor["formation"])
        farps = {f["id"]: f for f in cfg["farps"]}
        for target in cfg["targets"]:
            if target.get("farp"):
                farp = farps[target["farp"]]
                self.assertGreater(((target["x"] - farp["x"]) ** 2 +
                                    (target["y"] - farp["y"]) ** 2) ** 0.5, 1000)
        unit_types = {unit for target in cfg["targets"] for unit in target["types"]}
        self.assertTrue({"M-60", "Hummer", "M-2 Bradley", "T-55", "T-72B",
                         "BMP-1", "BMP-2", "BTR-80", "ZSU-23-4 Shilka",
                         "Kub 1S91 str", "Osa 9A33 ln", "SA-11 Buk SR 9S18M1"} <= unit_types)

    def test_miz_warehouses_and_runtime_agree_on_blue_airfield_ownership(self):
        from dcs import lua
        with zipfile.ZipFile(self.bundle / "Missions/SQE_Live_Syria.miz") as z:
            self.assertIsNone(z.testzip())
            warehouses = lua.loads(z.read("warehouses").decode())["warehouses"]
            mission = lua.loads(z.read("mission").decode())["mission"]
        def find_farps(value):
            if isinstance(value, dict):
                return ([value] if value.get("type") == "FARP" else []) + [
                    farp for child in value.values() for farp in find_farps(child)]
            if isinstance(value, (list, tuple)):
                return [farp for child in value for farp in find_farps(child)]
            return []
        farps = find_farps(mission)
        self.assertEqual(12, len(farps))
        self.assertEqual({f["name"] for f in self.config["farps"]}, {f["name"] for f in farps})
        owners = {z["id"]:z["owner"] for z in self.config["zones"]}
        for f in self.config["airfields"]:
            expected = owners[f["zone"]].upper()
            self.assertEqual(expected, warehouses["airports"][f["airport_id"]]["coalition"], f["airport"])
        red = [b for b in self.config["bases"] if b["side"] == "red"]
        self.assertEqual(14, len(red))
        self.assertTrue({"Damascus","Shayrat","Khalkhalah","Marj Ruhayyil","Tiyas","Aleppo","Hama"} <= {b["airport"] for b in red})
        for b in red:
            self.assertEqual("RED", warehouses["airports"][b["airport_id"]]["coalition"], b["airport"])
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
                local side=c.state.zones[f.zone].owner=='blue' and 2 or 1
                assert(mock.bases[f.airport].side==side and mock.bases[f.airport].auto==false)
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

    def test_farps_relay_long_supply_routes_and_follow_sector_capture(self):
        self.h.run('''
            local path=assert(mods.supply.path(c,'red','kuweires','naqoura'))
            assert(#path>cfg.supply_hops)
            for _,state in pairs(c.state.farps) do if state.owner=='red' then state.operational=false end end
            assert(not mods.supply.path(c,'red','kuweires','naqoura'))
            for id,def in pairs(c.farp_defs) do
                c.state.farps[id].owner=c.state.zones[def.zone].owner
                c.state.farps[id].operational=true
            end
            assert(mods.supply.path(c,'red','kuweires','naqoura'))
            c:capture_zone('khalkhalah','blue');a:sync_bases()
            assert(c.state.farps.khalkhalah_farp.owner=='blue')
            assert(mock.bases['Khalkhalah FARP'].side==2)
            assert(c:validate_save(c:snapshot()))
        ''')

    def test_fragmented_front_is_budgeted_without_losing_waiting_progress(self):
        self.h.run('''
            local flip=false
            for _,z in ipairs(cfg.zones) do if z.objectives then
                flip=not flip;c.state.zones[z.id].owner=flip and 'red' or 'blue'
            end end
            for id,def in pairs(c.farp_defs) do
                c.state.farps[id].owner=c.state.zones[def.zone].owner
                c.state.farps[id].operational=true
            end
            c:note('Fragmented-front test fixture')
            local selected,used=c:active_chain_targets()
            assert(used<=cfg.active_front_unit_limit)
            local candidates=0;for _,z in ipairs(cfg.zones) do
                if z.objectives and c.state.zones[z.id].owner=='red' and c:zone_frontline(z.id) then candidates=candidates+1 end
            end
            local active=0;for _ in pairs(selected) do active=active+1 end
            assert(candidates>active and active>0)
            assert(a:sync_zone_targets())
            local reserve=0
            for _,s in ipairs(mods.operations.sectors(c)) do if s.stage=='FRONT_RESERVE' then reserve=reserve+1 end end
            assert(reserve>0 and c:active_count()<=cfg.unit_budget)
            assert(c:validate_save(c:snapshot()))
        ''')

    def test_thirty_nine_sector_native_map_fits_and_lists_controlled_civil_fields(self):
        self.h.g.lua_path = str(LUA)
        self.h.g.ui = self.h.lua.execute((Path(__file__).parent / "ui_mock.lua").read_text())
        self.h.lua.execute((LUA / "hook.lua").read_text())
        self.h.run('''
            local before=mods.json.encode(c:snapshot());local view=rt:view()
            local layout=assert(mods.map.layout(view,368,300));assert(#layout.nodes==39)
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
            for _,id in ipairs(cfg.added_bases) do
                local served=false
                for _,s in pairs(c.state.shipments) do
                    if s.kind=='SUPPLY' and s.base==id then served=true end
                end
                assert(served,id)
            end
            assert(c:validate_save(c:snapshot()))
        ''')

    def test_frontline_pool_and_air_tasking_follow_capture_and_counterattack(self):
        self.h.run('''
            local function task(id) return mods.map.task(rt:view(),id) end
            local function flight(side,role,target)
                for _,f in pairs(c.state.flights) do
                    if f.side==side and f.role==role and (not target or f.target==target) then return f end
                end
            end
            assert(task('south_sam') and task('south_sam').role=='SEAD')
            assert(task('naqoura_sam') and task('bint_jbeil_sam'))
            assert(not task('south_armor') and not task('marj_sam') and not task('damascus_armor'))
            local ok=c:command({id='deep',session=c.session,revision=c.state.revision,action='accept',target='marj_sam'})
            assert(not ok.ok)
            assert(c:command({id='sead',session=c.session,revision=c.state.revision,action='accept',target='south_sam'}).ok)
            mock.kill(a.ground_groups.south_sam..'-1');a:sync_zone_targets()
            assert(c.state.completed==1 and task('south_sam').role=='DEAD')
            assert(c:command({id='dead',session=c.session,revision=c.state.revision,action='accept',target='south_sam'}).ok)
            for i=2,4 do mock.kill(a.ground_groups.south_sam..'-'..i) end
            a:sync_zone_targets()
            assert(c.state.completed==2 and task('south_c2') and not task('south_armor'))
            assert(c:command({id='strike',session=c.session,revision=c.state.revision,action='accept',target='south_c2'}).ok)
            for i=1,3 do mock.kill(a.ground_groups.south_c2..'-'..i) end
            a:sync_zone_targets()
            assert(c.state.completed==3 and task('south_armor'))
            assert(c:command({id='cas',session=c.session,revision=c.state.revision,action='accept',target='south_armor'}).ok)
            for i=1,#c.target_defs.south_armor.types do mock.kill(a.ground_groups.south_armor..'-'..i) end
            a:sync_zone_targets()
            assert(c.state.completed==4 and c:zone_stage('south')==5 and c:defenders('south','blue',false)==0)
            mods.director.air(c,'blue');mods.director.air(c,'red')
            assert(flight('blue','CAP').station_zone=='golan')
            assert(mods.director.dispatch(c,c.base_defs.ramat,'ASSAULT','south','golan'))
            local blue
            for _,s in pairs(c.state.shipments) do if s.side=='blue' then blue=s end end
            mods.director.air(c,'red');assert(flight('red','STRIKE',blue.id))
            mock.deliver(a,blue);a:observe();a:sync_bases()
            assert(c.state.zones.south.owner=='blue')
            assert(not task('south_sam') and task('marj_sam'))
            for _,u in ipairs(mock.groups[a.ship_groups[blue.id]].units) do mock.kill(u.name) end
            assert(mods.director.dispatch(c,c.base_defs.marj_ab,'ASSAULT','south','marj'))
            local counter
            for _,s in pairs(c.state.shipments) do if s.side=='red' and s.zone=='south' then counter=s end end
            mock.deliver(a,counter);a:observe();a:sync_bases()
            assert(c.state.zones.south.owner=='red' and c:zone_stage('south')==1)
            assert(task(counter.id) and task('south_sam') and not task('marj_sam'))
            assert(c:validate_save(c:snapshot()))
        ''')

    def test_previous_checkpoint_migrates_new_bases_without_resetting_the_front(self):
        h = Harness(self.config)
        h.run('''
            local seed=mods.core.new(cfg,nil,nil,'old',mods.targets,mods.supply)
            local s=seed:snapshot();s.content=cfg.previous_content_version
            local old_zones={negev=true,central=true,sharon=true,haifa=true,galilee=true,
                upper_galilee=true,golan=true,south=true,marj=true,damascus=true,shayrat=true}
            local old_targets={blue_armor=true,blue_sam=true,blue_depot=true,blue_fuel=true,
                central_armor=true,central_sam=true,blue_central_depot=true,blue_central_fuel=true,
                negev_armor=true,negev_sam=true,blue_negev_depot=true,blue_negev_fuel=true,
                south_armor=true,south_sam=true,marj_armor=true,marj_sam=true,marj_fuel=true,
                damascus_armor=true,damascus_sam=true,damascus_depot=true,
                shayrat_armor=true,shayrat_sam=true,shayrat_depot=true}
            local old_bases={ramat=true,tel_nof=true,hatzor=true,nevatim=true,hatzerim=true,
                khalkhalah=true,marj_ab=true,tiyas=true,damascus=true,shayrat=true}
            for id in pairs(s.zones) do if not old_zones[id] then s.zones[id]=nil end end
            for id in pairs(s.targets) do if not old_targets[id] then s.targets[id]=nil end end
            for id in pairs(s.bases) do if not old_bases[id] then s.bases[id]=nil end end
            s.farps=nil
            s.zones.south.owner='blue';s.targets.south_sam.alive['1']=false
            s.bases.damascus.resources.ammo=11;s.completed=4
            fs.files[cfg.id]=mods.json.encode(s)
        ''')
        h.start()
        h.run('''
            assert(c.state.completed==4 and c.state.bases.damascus.resources.ammo==11)
            assert(not c.state.targets.south_sam.alive['1'])
            assert(c.state.zones.south.owner=='blue' and mock.bases.Khalkhalah.side==1)
            assert(c.state.bases.khalkhalah.ready['MiG-29S']==3 and c.state.farps.khalkhalah_farp.owner=='red')
        ''')

    def test_unknown_scenario_fails_before_export(self):
        with self.assertRaises(ValueError): content(scenario="missing")

    def test_many_bases_do_not_duplicate_the_same_ground_advance(self):
        self.h.run('''
            for _,id in pairs(c.zone_defs.south.objectives) do
                for key in pairs(c.state.targets[id].alive) do c.state.targets[id].alive[key]=false end
            end
            a:sync_zone_targets()
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
