"""Native map contracts under Lua 5.1; not a dxgui rendering or flight test."""
import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from test_live import Harness, LUA, build


class MapCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temporary = tempfile.TemporaryDirectory()
        cls.bundle = Path(cls.temporary.name) / "bundle"
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            build(cls.bundle)
        cls.config = json.loads((cls.bundle / "content.json").read_text())

    @classmethod
    def tearDownClass(cls):
        cls.temporary.cleanup()

    def setUp(self):
        self.h = Harness(self.config).start()

    def ui(self, fail_panel=False):
        self.h.g.lua_path = str(LUA)
        self.h.g.ui = self.h.lua.execute((Path(__file__).parent / "ui_mock.lua").read_text())
        self.h.g.ui.fail_panel = fail_panel
        self.h.lua.execute((LUA / "hook.lua").read_text())
        self.h.run('''
            assert(ui.handler,ui.last_log)
            ui.load_mission()
            ui.hotkeys['Ctrl+Shift+q']()
            ui.window.MapTab.click()
        ''')

    def test_map_geometry_identity_and_connections_match_campaign(self):
        self.h.run('''
            local view=rt:view();local m=assert(mods.map.layout(view,368,300))
            assert(#m.nodes==6 and #m.edges==5)
            local function contained(p)
                assert(p.x>=0 and p.y>=0 and p.w>0 and p.h>0)
                assert(p.x+p.w<=m.width and p.y+p.h<=m.height)
            end
            local nodes,edges={},{}
            for i,n in ipairs(m.nodes) do
                contained(n);assert(not nodes[n.id]);nodes[n.id]=n
                assert(n.owner==c.state.zones[n.id].owner)
                for j=i+1,#m.nodes do local q=m.nodes[j]
                    assert(not(n.x<q.x+q.w and q.x<n.x+n.w and n.y<q.y+q.h and q.y<n.y+n.h))
                end
            end
            assert(nodes.galilee.bases[1]=='Ramat David' and nodes.damascus.bases[1]=='Damascus')
            assert(#nodes.south.bases==0)
            local front=0
            for _,e in ipairs(m.edges) do
                assert(nodes[e.from] and nodes[e.to]);assert(#e.segments==3)
                local key=e.from<e.to and e.from..':'..e.to or e.to..':'..e.from
                assert(not edges[key]);edges[key]=true
                for _,p in ipairs(e.segments) do contained(p) end
                assert(e.front==(nodes[e.from].owner~=nodes[e.to].owner))
                if e.front then front=front+1 end
            end
            assert(front==1 and edges['golan:south'])
            for _,s in ipairs(view.front.sectors) do
                for _,id in ipairs(s.neighbors) do
                    assert(edges[s.id<id and s.id..':'..id or id..':'..s.id])
                end
            end
        ''')

    def test_map_rejects_invalid_graph_and_separates_coincident_sectors(self):
        self.h.run('''
            local v=rt:view();local m=mods.map
            for _,s in ipairs(v.front.sectors) do s.x=-100;s.y=-200 end
            local layout=assert(m.layout(v,368,300))
            for i=2,#layout.nodes do assert(layout.nodes[i].y>=layout.nodes[i-1].y+layout.nodes[i-1].h) end
            assert(not m.layout(v,100,100))
            v.front.sectors[1].neighbors={'unknown'};assert(not m.layout(v,368,300))
            v=rt:view();v.front.sectors[1].neighbors={v.front.sectors[1].id};assert(not m.layout(v,368,300))
            v=rt:view();v.front.sectors[1].x=0/0;assert(not m.layout(v,368,300))
            v=rt:view();v.front.sectors[2].id=v.front.sectors[1].id;assert(not m.layout(v,368,300))
            v=rt:view();for i=1,mods.map.MAX_SECTORS do v.front.sectors[#v.front.sectors+1]=v.front.sectors[1] end
            assert(not m.layout(v,368,300))
            v=rt:view();v.front.sectors={}
            for i=1,15 do v.front.sectors[i]={id=tostring(i),name=tostring(i),x=i,y=i,owner='red',neighbors={}} end
            for i,s in ipairs(v.front.sectors) do for j=1,15 do if i~=j then s.neighbors[#s.neighbors+1]=tostring(j) end end end
            assert(not m.layout(v,368,300))
        ''')

    def test_map_browsing_is_read_only_filters_targets_and_preserves_empty_selection(self):
        self.h.run('''
            local before=mods.json.encode(c:snapshot());local view=rt:view();local m=mods.map
            local s=assert(m.select_sector(view,'south'));assert(s.task=='south_armor')
            assert(#m.tasks(view,s.zone)==2)
            local next_task=m.step(view,s,1);assert(next_task.task=='south_sam')
            assert(m.step(view,next_task,1).task=='south_armor')
            assert(not m.select_task(view,s,'marj_sam'))
            s=assert(m.select_sector(view,'galilee'));assert(s.task==false)
            assert(not mods.view.selected(view,s.task) and not m.step(view,s,1).task)
            assert(m.detail(view,s,mods.view):find('No current task cards',1,true))
            assert(not m.select_sector(view,'unknown'))
            assert(mods.json.encode(c:snapshot())==before and next(fs.queue)==nil)
        ''')

    def test_map_capture_changes_ownership_and_front_without_moving_nodes(self):
        self.h.run('''
            local old=assert(mods.map.layout(rt:view(),368,300))
            for i=1,5 do mock.kill('SQEL-G-south_armor-1-'..i) end
            mods.director.logistics(c)
            local arrival
            for _,s in pairs(c.state.shipments) do
                if s.kind=='ASSAULT' and s.side=='blue' and s.zone=='south' then arrival=s end
            end
            assert(arrival);mock.deliver(a,arrival);a:observe()
            assert(c.state.zones.south.owner=='blue')
            local now=assert(mods.map.layout(rt:view(),368,300));local fronts={}
            for i,n in ipairs(now.nodes) do
                assert(n.id==old.nodes[i].id and n.x==old.nodes[i].x and n.y==old.nodes[i].y)
                if n.id=='south' then assert(n.owner=='blue' and n.frontline) end
            end
            for _,e in ipairs(now.edges) do if e.front then fronts[e.from..':'..e.to]=true end end
            assert(fronts['marj:south'] or fronts['south:marj'])
            assert(not fronts['golan:south'] and not fronts['south:golan'])
        ''')

    def test_native_map_selects_same_brief_and_target_as_f10(self):
        self.ui()
        self.h.run('''
            local before=mods.json.encode(c:snapshot())
            ui.sector('South').click();ui.window.MapTask2.click()
            assert(ui.window.Target.text:find('Southern SA-6',1,true))
            assert(next(fs.queue)==nil and mods.json.encode(c:snapshot())==before)
            local target=mods.map.task(mods.json.decode(fs.status_text),'south_sam')
            assert(ui.window.Target.text:find(target.coordinates,1,true))
            ui.window.Brief.click();mock.advance(2);ui.handler.onSimulationFrame()
            local ui_brief=mock.messages[#mock.messages]
            local f10_brief
            for _,item in ipairs(mock.menus) do
                if item.name=='Brief / coordinates' and item.parent.name=='SEAD / Southern SA-6 battery' then f10_brief=item.fn end
            end
            assert(f10_brief);f10_brief();assert(mock.messages[#mock.messages]==ui_brief)
            ui.window.Accept.click();mock.advance(2);ui.handler.onSimulationFrame()
            assert(c.state.task.target=='south_sam' and c.state.task.role=='SEAD')
        ''')

    def test_native_empty_sector_and_removed_target_cannot_accept_unrelated_task(self):
        self.ui()
        self.h.run('''
            ui.sector('Ramat D.').click()
            assert(ui.window.Target.text:find('No current task cards',1,true))
            assert(not ui.window.Accept.enabled and not ui.window.Brief.enabled and not ui.window.Mark.enabled)
            ui.window.Accept.click();ui.window.Brief.click();ui.window.Mark.click()
            assert(next(fs.queue)==nil and not c.state.task)
            ui.sector('South').click();assert(ui.window.Accept.enabled)
            for i=1,5 do mock.kill('SQEL-G-south_armor-1-'..i) end
            mock.advance(2);ui.handler.onSimulationFrame()
            assert(not ui.window.Accept.enabled and ui.window.MapFilter.text:find('Southern corridor',1,true))
            assert(ui.window.Target.text:find('No player target selected',1,true))
            ui.window.Accept.click();assert(next(fs.queue)==nil)
            ui.window.Next.click();assert(ui.window.Target.text:find('Southern SA-6',1,true))
        ''')

    def test_native_stale_map_disables_actions_and_recovers_with_fresh_data(self):
        self.ui()
        self.h.run('''
            ui.sector('South').click();local red=ui.sector('South'):getSkin()
            mock.clock=mock.clock+20;ui.handler.onSimulationFrame()
            assert(ui.window.MapLegend.text:find('STALE',1,true))
            assert(not ui.sector('South').enabled and ui.sector('South'):getSkin()~=red)
            assert(not ui.window.Accept.enabled and not ui.window.MapTask1.enabled and not ui.window.Next.enabled)
            ui.window.Accept.click();ui.window.MapTask2.click();ui.sector('Marj').click()
            assert(next(fs.queue)==nil and ui.window.MapFilter.text:find('Southern corridor',1,true))
            rt:publish();mock.clock=mock.clock+1;ui.handler.onSimulationFrame()
            assert(ui.window.MapLegend.text:find('LIVE',1,true) and ui.sector('South').enabled and ui.window.Accept.enabled)
        ''')

    def test_native_map_updates_capture_colour_and_resets_selection_for_new_session(self):
        self.ui()
        self.h.run('''
            ui.sector('South').click();local red=ui.sector('South'):getSkin()
            c.state.zones.south.owner='blue';c:note('Capture fixture');rt:publish()
            mock.clock=mock.clock+1;ui.handler.onSimulationFrame()
            assert(ui.sector('BLUE South'):getSkin()~=red)
            ui.window.Accept.click();assert(next(fs.queue))
            local view=mods.json.decode(fs.status_text);view.session='new-map-session';view.heartbeat=fs.now()
            fs.status_text=mods.json.encode(view);mock.clock=mock.clock+1;ui.handler.onSimulationFrame()
            assert(ui.window.MapFilter.text:find('All sectors',1,true))
            assert(ui.window.Status.text:find('No acknowledgement',1,true))
            ui.handler.onMissionLoadBegin()
            assert(not ui.window.MapCanvas.visible and not ui.window.cursor)
        ''')

    def test_native_map_pagination_and_sector_filter_never_cross_silently(self):
        self.ui()
        self.h.run('''
            assert(ui.window.MapFilter.text:find('1-4 /',1,true))
            for i=1,4 do ui.window.Next.click() end
            assert(ui.window.MapFilter.text:find('5-8 /',1,true))
            ui.window.MapTask2.click();local selected=ui.window.Target.text
            ui.window.Previous.click();ui.window.Next.click();assert(ui.window.Target.text==selected)
            ui.sector('Marj').click();assert(ui.window.MapFilter.text:find('1-3 / 3',1,true))
            for i=1,8 do ui.window.Next.click();assert(ui.window.Target.text:find('Sector: Marj',1,true)) end
            ui.window.AllSectors.click();assert(ui.window.MapFilter.text:find('All sectors',1,true))
            assert(next(fs.queue)==nil)
        ''')

    def test_native_map_tabs_fit_window_and_pool_does_not_grow(self):
        self.ui()
        self.h.run('''
            local function layout_check()
                local seen={}
                for _,w in ipairs(ui.window.children) do if w.visible then
                    local p=w.bounds;assert(p[1]>=0 and p[2]>=0 and p[1]+p[3]<=940 and p[2]+p[4]<=680,w.name)
                    for _,q in ipairs(seen) do
                        assert(not(p[1]<q[1]+q[3] and q[1]<p[1]+p[3] and p[2]<q[2]+q[4] and q[2]<p[2]+p[4]),w.name)
                    end
                    seen[#seen+1]=p
                end end
            end
            assert(ui.window.MapCanvas.visible and not ui.window.Overview.visible);layout_check()
            for _,tab in ipairs({'FrontTab','SupportTab','ResourcesTab'}) do
                ui.window[tab].click();layout_check()
                assert(not ui.window.MapCanvas.visible and ui.window.Overview.visible and not ui.window.MapTask1.visible)
            end
            ui.window.MapTab.click();layout_check()
            local count=#ui.widgets
            for i=1,100 do mock.clock=mock.clock+1;rt:publish();ui.handler.onSimulationFrame() end
            assert(#ui.widgets==count and #ui.window.MapCanvas.children==mods.map.MAX_SECTORS+mods.map.MAX_EDGES*3)
            ui.window.Close.click();assert(not ui.window.cursor)
            for _,w in ipairs(ui.window.children) do assert(not w.visible,w.name) end
            for _,w in ipairs(ui.window.MapCanvas.children) do assert(not w.visible) end
            ui.hotkeys['Ctrl+Shift+q']();assert(ui.window.cursor and ui.window.MapCanvas.visible)
        ''')

    def test_native_map_invalid_layout_falls_back_and_recovers(self):
        self.ui()
        self.h.run('''
            local v=mods.json.decode(fs.status_text);v.front.sectors[1].neighbors={'not-a-sector'}
            fs.status_text=mods.json.encode(v);mock.clock=mock.clock+1;ui.handler.onSimulationFrame()
            assert(not ui.window.MapCanvas.visible and ui.window.Overview.visible)
            assert(ui.window.Overview.text:find('Invalid sector connection',1,true))
            ui.window.FrontTab.click();assert(ui.window.Overview.text:find('CAMPAIGN OBJECTIVE',1,true))
            rt:publish();mock.clock=mock.clock+1;ui.handler.onSimulationFrame();ui.window.MapTab.click()
            assert(ui.window.MapCanvas.visible and not ui.window.Overview.visible and not rt.failed)
        ''')

    def test_native_map_widget_failure_leaves_front_and_commands_available(self):
        self.ui(fail_panel=True)
        self.h.run('''
            assert(ui.window.Overview.visible and ui.window.Overview.text:find('Panel failure',1,true))
            assert(not ui.window.MapCanvas.visible)
            ui.window.FrontTab.click();assert(ui.window.Overview.text:find('CAMPAIGN OBJECTIVE',1,true))
            ui.window.MapTab.click()
            ui.window.Accept.click();mock.advance(2);ui.handler.onSimulationFrame()
            assert(c.state.task.target=='south_armor' and not rt.failed)
        ''')

    def test_packaged_map_sources_match_tested_files(self):
        for name in ("map.lua", "map_ui.lua", "view.lua", "Operations.dlg"):
            self.assertEqual((LUA / name).read_bytes(), (self.bundle / "Scripts/SQE-Live" / name).read_bytes())
