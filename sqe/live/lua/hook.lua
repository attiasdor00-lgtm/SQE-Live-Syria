-- Native DCS GUI. Window lifetime/hotkey pattern adapted from dcs-scratchpad
-- (MIT, Markus Ast); see licenses/scratchpad-MIT.txt.
local function start()
    package.path=package.path..";.\\Scripts\\?.lua;.\\Scripts\\UI\\?.lua;"
    local lfs=require("lfs")
    local DialogLoader=require("DialogLoader")
    local Skin=require("Skin")
    local dxgui=require("dxgui")
    local base=lfs.writedir().."Scripts/SQE-Live/"
    local json=dofile(base.."json.lua")
    local V=dofile(base.."view.lua")
    local M=dofile(base.."map.lua")
    local MapUI=dofile(base.."map_ui.lua")
    -- The UI Lua environment has filesystem access, independently of mission Lua.
    local fs=dofile(base.."storage.lua").new(lfs.writedir().."SQE-Live/")
    local window,normal_skin,hidden_skin
    local tab="map"
    local visible,in_mission=false,false
    local latest,selected,pending,message=nil,nil,nil,"Waiting for SQE Live..."
    local selected_zone,map_ui,map_error=false,nil,false
    local row_ids={}
    local mission_started,serial,last_poll,last_attempt=0,0,-1,-10
    local last_report,creation_error,poll_error=-1000,false,false
    local widgets={"Overview","Target","Journal","Status","Previous","Next","Accept","Brief","Mark","Abort",
        "CAP","ESCORT","SEAD","STRIKE","AWACS","TANKER","Hold","Push","Save","Close",
        "MapTab","FrontTab","ResourcesTab","SupportTab","Recommended",
        "MapCanvas","MapLegend","MapFilter","AllSectors","MapTask1","MapTask2","MapTask3","MapTask4"}
    local actions={"Accept","Brief","Mark","Abort","CAP","ESCORT","SEAD","STRIKE","AWACS","TANKER","Hold","Push","Save"}
    local function connected()
        return in_mission and latest and latest.protocol==1 and latest.running==true
            and type(latest.session)=="string" and latest.started_at>=mission_started
            and os.time()-latest.heartbeat>=0 and os.time()-latest.heartbeat<=10 and true or false
    end
    local function report(force)
        local now=os.time()
        if not force and now-last_report<5 then return end
        last_report=now
        if type(fs.report)~="function" then return end
        local current=latest and latest.started_at>=mission_started
        local ok,written,why=pcall(function()
            return fs.report("ui",json.encode({protocol=1,session=current and latest.session or false,
                heartbeat=now,in_mission=in_mission,window_created=window~=nil,
                status_connected=connected() and true or false,visible=visible,
                error=creation_error or poll_error or map_error}))
        end)
        if not ok or not written then net.log("[SQE Live] UI diagnostic write failed: "..tostring(ok and why or written)) end
    end
    local render
    local function show(on)
        visible=on and in_mission
        if not window then return end
        window:setVisible(true)
        window:setSkin(visible and normal_skin or hidden_skin)
        window:setHasCursor(visible)
        for _,name in ipairs(widgets) do window[name]:setVisible(visible) end
        if not visible then
            for _,name in ipairs({"Overview","Target","Journal","Status"}) do window[name]:setFocused(false) end
        end
        if render then render() end
    end
    local function selection()return {zone=selected_zone,task=selected} end
    local function choose(value)
        if value then selected_zone=value.zone;selected=value.task end
    end
    render=function()
        if not window then return end
        local online=connected()
        for _,name in ipairs(actions) do window[name]:setEnabled(online and not pending) end
        local layout,map_reason
        if latest and latest.protocol==1 and latest.tasks then
            choose(M.reconcile(latest,selection()))
            window.Overview:setText((tab=="front" or tab=="map") and V.front(latest)
                or tab=="support" and V.support(latest,selected) or V.overview(latest))
            window.Target:setText(M.detail(latest,selection(),V))
            window.Journal:setText(V.log(latest))
            layout,map_reason=M.layout(latest,368,300)
            local rows,first,total=M.page(latest,selection())
            local sector=M.sector(latest,selected_zone)
            window.MapFilter:setText((sector and sector.name or "All sectors").." | "
                ..(total>0 and (first.."-"..(first+#rows-1).." / "..total) or "no targets"))
            for i=1,M.PAGE_SIZE do
                local t=rows[i];row_ids[i]=t and t.id or false
                window["MapTask"..i]:setText(t and ((selected==t.id and "> " or "")..t.role.." / "..t.name) or "")
            end
            local offers=V.offers(latest,selected)
            for _,role in ipairs({"CAP","ESCORT","SEAD","STRIKE","AWACS","TANKER"}) do
                if offers[role] then window[role]:setEnabled(online and not pending and offers[role].available==true) end
            end
        else
            row_ids={};window.MapFilter:setText("Waiting for campaign...")
            window.Overview:setText("Waiting for campaign...");window.Target:setText("Waiting for campaign...")
            window.Journal:setText("")
        end
        local map_visible=visible and tab=="map"
        if map_ui then
            local ok,err=pcall(function()map_ui:render(layout,online,selected_zone,map_visible and layout~=nil)end)
            map_error=not ok and tostring(err) or map_reason or false
            if not ok then window.MapCanvas:setVisible(false) end
        end
        local map_ok=map_ui~=nil and not map_error
        window.MapCanvas:setVisible(map_visible and map_ok)
        window.MapLegend:setVisible(map_visible and map_ok)
        window.Overview:setVisible(visible and (tab~="map" or not map_ok))
        if tab=="map" and not map_ok then
            window.Overview:setText("Map unavailable: "..tostring(map_error or "waiting for campaign").."\n\nUse Front plan or F10.")
        end
        window.MapLegend:setText((online and "LIVE / sector schematic" or "STALE / last known state")
            .."\nBLUE friendly / RED enemy / * front / [B] base\nLinks are sector connections, not roads.")
        window.Target:setBounds(392,map_visible and 216 or 52,524,map_visible and 196 or 360)
        window.MapFilter:setVisible(map_visible);window.AllSectors:setVisible(map_visible)
        window.AllSectors:setEnabled(online)
        for i=1,M.PAGE_SIZE do
            window["MapTask"..i]:setVisible(map_visible and row_ids[i] and true or false)
            window["MapTask"..i]:setEnabled(online and row_ids[i] and true or false)
        end
        local has_target=latest and M.task(latest,selected)~=nil or false
        for _,name in ipairs({"Accept","Brief","Mark"}) do window[name]:setEnabled(online and not pending and has_target) end
        local has_tasks=latest and #M.tasks(latest,selected_zone)>0 or false
        window.Previous:setEnabled(online and has_tasks);window.Next:setEnabled(online and has_tasks)
        window.Recommended:setEnabled(online and latest.front and latest.front.recommended_task and true or false)
        local status=online and (latest.save_status or "Save status unknown")
            or (latest and latest.error and tostring(latest.error) or "No live connection. Start SQE_Live_Syria; check the bridge installation.")
        if pending then message="Command queued. Waiting for the mission (unpause if paused)..." end
        local summary=latest and latest.diagnostic_summary or "Automatic checks pending."
        window.Status:setText((online and "LIVE | " or "OFFLINE | ")..status.."\n"..message.."\n"..summary
            ..(map_error and ("\nMap: "..map_error) or ""))
    end
    local function send(action,role)
        if not connected() or pending then return end
        if (action=="accept" or action=="brief" or action=="mark") and not M.task(latest,selected) then return end
        serial=serial+1
        local id="ui-"..tostring(os.time()).."-"..tostring(math.floor(os.clock()*1000000)).."-"..serial
        local cmd={id=id,session=latest.session,revision=latest.revision,action=action,target=selected,role=role}
        local ok,err=fs.enqueue(id,json.encode(cmd))
        if ok then pending={id=id,sent=os.time(),session=latest.session}
        else message="Command could not be sent: "..tostring(err) end
        render()
    end
    local function step(delta)
        if not connected() then return end
        choose(M.step(latest,selection(),delta));render()
    end
    local function create()
        window=DialogLoader.spawnDialogFromFile(base.."Operations.dlg")
        normal_skin=window:getSkin();hidden_skin=Skin.windowSkinChatMin()
        local sw,sh=dxgui.GetScreenSize()
        window:setBounds(math.max(0,math.floor((sw-940)/2)),math.max(0,math.floor((sh-710)/2)),940,710)
        local ok,value=pcall(function()
            return MapUI.new(window.MapCanvas,window.Accept:getSkin(),require("Panel"),require("Button"),M,function(id)
                if connected() then choose(M.select_sector(latest,id));render() end
            end)
        end)
        map_ui=ok and value or nil;map_error=not ok and tostring(value) or false
        window.Previous:addMouseUpCallback(function()step(-1)end)
        window.Next:addMouseUpCallback(function()step(1)end)
        window.Close:addMouseUpCallback(function()show(false)end)
        for name,value in pairs({MapTab="map",FrontTab="front",ResourcesTab="resources",SupportTab="support"}) do
            local page=value;window[name]:addMouseUpCallback(function()tab=page;render()end)
        end
        window.Recommended:addMouseUpCallback(function()
            if connected() and latest.front and latest.front.recommended_task then
                local t=M.task(latest,latest.front.recommended_task)
                if t then selected=t.id;selected_zone=t.zone;tab="map";render() end
            end
        end)
        window.AllSectors:addMouseUpCallback(function()
            if connected() then selected_zone=false;render() end
        end)
        for i=1,M.PAGE_SIZE do
            local row=i;window["MapTask"..i]:addMouseUpCallback(function()
                if connected() then choose(M.select_task(latest,selection(),row_ids[row]));render() end
            end)
        end
        for name,action in pairs({Accept="accept",Brief="brief",Mark="mark",Abort="abort",Hold="hold",Push="push",Save="save"}) do
            local a=action;window[name]:addMouseUpCallback(function()send(a)end)
        end
        for _,role in ipairs({"CAP","ESCORT","SEAD","STRIKE","AWACS","TANKER"}) do
            local r=role;window[role]:addMouseUpCallback(function()send("support",r)end)
        end
        window:addHotKeyCallback("Ctrl+Shift+q",function()show(not visible)end)
        show(false)
    end
    local function poll()
        local raw=fs.status()
        if raw then
            local ok,s=pcall(json.decode,raw)
            if ok and type(s)=="table" and type(s.heartbeat)=="number" and type(s.started_at)=="number" then
                if not latest or s.session~=latest.session then
                    selected_zone=false;selected=(s.tasks or {})[1] and s.tasks[1].id or false
                    if not pending and s.running==true then message="Select a sector or target; Accept assigns it." end
                end
                latest=s
            end
        end
        if pending and latest then
            local result=(latest.results or {})[pending.id]
            if not result and latest.last_result and latest.last_result.id==pending.id then result=latest.last_result end
            if result then message=(result.ok and "OK: " or "Not applied: ")..tostring(result.message);pending=nil
            elseif latest.session~=pending.session or os.time()-pending.sent>20 then
                message="No acknowledgement yet. Check the current state before retrying."
                pending=nil
            end
        end
        render()
    end
    local handler={}
    function handler.onMissionLoadBegin()
        message="Waiting for SQE Live..."
        in_mission=false;mission_started=os.time();latest=nil;pending=nil;selected=false;selected_zone=false;tab="map";show(false)
    end
    function handler.onMissionLoadEnd()
        in_mission=true
        -- LoadBegin is the freshness boundary; long terrain loads are supported.
        if mission_started==0 then mission_started=os.time() end
    end
    function handler.onSimulationStop()
        in_mission=false;pending=nil;show(false);report(true);latest=nil
    end
    function handler.onSimulationFrame()
        local now=os.clock()
        if not window and now-last_attempt>=5 then
            last_attempt=now
            local ok,err=pcall(create)
            creation_error=not ok and tostring(err) or false
            if not ok then
                if window then pcall(function()window:setVisible(false)end) end
                window=nil;net.log("[SQE Live] UI creation failed: "..tostring(err))
            end
        end
        if now-last_poll>=0.3 then
            last_poll=now
            local ok,err=pcall(poll)
            poll_error=not ok and tostring(err) or false
            if not ok then net.log("[SQE Live] UI update failed: "..tostring(err)) end
        end
        report(false)
    end
    DCS.setUserCallbacks(handler)
    net.log("[SQE Live] Operations hook loaded; Ctrl+Shift+Q")
end
local ok,err=pcall(start)
if not ok then net.log("[SQE Live] Hook failed: "..tostring(err)) end
