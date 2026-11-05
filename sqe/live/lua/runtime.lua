local Runtime={}
function Runtime.start(config,modules,storage)
    local json,Core,Director,Adapter=modules.json,modules.core,modules.director,modules.adapter
    local adapter=Adapter.new(config,Core.copy)
    local session=storage and storage.session() or ("volatile-"..tostring(math.random(1,2000000000)))
    local runtime={last_clock=timer.getTime(),last_save=-999,last_save_revision=-1,
        started_at=storage and storage.now() or 0,failed=false,storage=storage,next_diagnostics=60}
    local diagnostics=modules.diagnostics.new(config,json,storage,session)
    runtime.diagnostics=diagnostics
    function runtime:checked(stage,fn)
        return diagnostics:call(stage,fn,self.core and self.core.state.time or 0)
    end
    function runtime:fail(reason)
        if self.failed then return end
        self.failed=tostring(reason)
        diagnostics:set("campaign_updates","FAIL",self.failed,self.core and self.core.state.time or 0)
        pcall(env.error,"SQE Live stopped campaign updates: "..self.failed)
        pcall(function()adapter:notify("SQE Live campaign updates stopped: "..self.failed.."\nExisting saves retained.")end)
    end
    local restored,errors
    if storage then
        for _,previous in ipairs({false,true}) do
            local raw,err=storage.load(config.id,previous)
            if raw then
                local ok,value=pcall(json.decode,raw)
                if ok then
                    local probe=Core.new(config,adapter,nil,session,modules.targets,modules.supply)
                    local valid,why=probe:validate_save(value)
                    if valid then
                        if previous then
                            local recovered,why_recovery=storage.restore_previous(config.id,raw)
                            if not recovered then error("Valid backup retained, but recovery write failed: "..tostring(why_recovery)) end
                        end
                        restored=value;runtime.used_backup=previous;break
                    end
                    err=why
                else err=value end
            end
            if err and err~="missing" then errors=(errors or "")..tostring(err).."; " end
        end
    end
    if errors and not restored then
        error("Existing SQE Live save could not be loaded; it has NOT been reset. "..errors)
    end
    local core=Core.new(config,adapter,restored,session,modules.targets,modules.supply)
    runtime.core=core
    adapter:attach(core,Director,modules.operations,modules.ground)
    if runtime.used_backup then core:note("Recovered the previous valid checkpoint; the primary save was unreadable.") end
    function adapter:save(snapshot)
        if runtime.failed then return false,"Campaign stopped; last valid checkpoint retained" end
        if not storage then
            self.save_status="DISABLED: storage bridge not installed"
            diagnostics:set("checkpoint_write","WARN",self.save_status,core.state.time)
            return false,self.save_status
        end
        local checked,valid,reason=pcall(function()return core:validate_save(snapshot)end)
        if not checked or not valid then
            self.save_status="SAVE ERROR: invalid campaign state; previous checkpoint retained"
            runtime:fail(checked and reason or valid)
            return false,self.save_status
        end
        local ok,encoded=pcall(json.encode,snapshot)
        if not ok then
            self.save_status="SAVE ERROR: "..tostring(encoded)
            diagnostics:set("checkpoint_write","FAIL",self.save_status,core.state.time)
            return false,self.save_status
        end
        local called,saved,err=pcall(storage.save,config.id,encoded)
        if not called then err=saved;saved=false end
        if saved then
            runtime.last_save=snapshot.time;runtime.last_save_revision=snapshot.revision
            self.save_status="Saved at campaign "..math.floor(core.state.time/60).." min"
        else self.save_status="SAVE ERROR: "..tostring(err) end
        diagnostics:set("checkpoint_write",saved and "PASS" or "FAIL",self.save_status,core.state.time)
        return saved,self.save_status
    end
    function runtime:view() return modules.operations.decorate(core,core:view()) end
    function runtime:publish()
        if not storage then return end
        return self:checked("status_channel",function()
            local view=self:view()
            for _,t in ipairs(view.tasks) do
                local coordinates,elevation,p=adapter:coordinates((core:target(t.id)))
                t.coordinates=coordinates or "Position unavailable; wait for a fresh observation."
                t.elevation_ft=elevation or "?";t.position_reference=p and p.reference or "Unavailable"
                t.x=p and p.x or false;t.y=p and p.y or false
            end
            view.heartbeat=storage.now();view.started_at=self.started_at
            view.save_status=adapter.save_status;view.last_save=self.last_save
            view.running=not self.failed;view.error=self.failed or false
            view.diagnostic_summary=diagnostics:summary()
            return storage.publish(json.encode(view))
        end)
    end
    function runtime:invoke(action,target,role)
        if self.failed then adapter:notify("Campaign updates stopped: "..tostring(self.failed));return end
        local res=core:command({id=core:id("f10-"),session=session,revision=core.state.revision,
            action=action,target=target,role=role})
        self:checked("notifications",function()adapter:notify(res.message)end)
        self:publish()
    end
    function runtime:menus()
        local p=adapter:player()
        if not p then return end
        local gid=p:getGroup():getID()
        local tasks=core:tasks();local signature=tostring(gid)..":"..tostring(core.state.task and core.state.task.target)
        for _,t in ipairs(tasks) do signature=signature..":"..t.id..":"..t.role..":"..t.name end
        if self.menu_signature==signature then return end
        if self.menu then pcall(missionCommands.removeItemForGroup,self.menu_gid,self.menu) end
        self.menu_gid=gid
        local root=missionCommands.addSubMenuForGroup(gid,"SQE Live")
        self.menu=root
        local function add(label,path,fn) missionCommands.addCommandForGroup(gid,label,path,fn) end
        local page
        for i,t in ipairs(tasks) do
            if (i-1)%6==0 then page=missionCommands.addSubMenuForGroup(gid,"Tasks "..(math.floor((i-1)/6)+1),root) end
            local target=t.id
            local sub=missionCommands.addSubMenuForGroup(gid,t.role.." / "..t.name,page)
            add("Accept",sub,function()self:invoke("accept",target)end)
            add("Brief / coordinates",sub,function()self:invoke("brief",target)end)
            add("Mark on map",sub,function()self:invoke("mark",target)end)
        end
        add("Current task briefing",root,function()self:invoke("brief")end)
        add("Abort current task",root,function()self:invoke("abort")end)
        local support=missionCommands.addSubMenuForGroup(gid,"Request support",root)
        for _,r in ipairs({"CAP","ESCORT","SEAD","STRIKE","AWACS","TANKER"}) do
            local role=r;add(role,support,function()self:invoke("support",nil,role)end)
        end
        add("Hold supporting flights",support,function()self:invoke("hold")end)
        add("Push supporting flights",support,function()self:invoke("push")end)
        add("Save campaign",root,function()self:invoke("save")end)
        add("Front and sector objectives",root,function()adapter:notify(modules.view.front(self:view()),30)end)
        add("Suggested task briefing",root,function()
            local v=self:view()
            if v.front.recommended_task then self:invoke("brief",v.front.recommended_task)
            else adapter:notify(modules.view.front(v)) end
        end)
        add("Support availability",root,function()
            local v=self:view();adapter:notify(modules.view.support(v,false),30)
        end)
        add("Campaign status",root,function()
            adapter:notify(config.name.."\nElapsed "..math.floor(core.state.time/60).." minutes / tasks completed "..core.state.completed
                .."\n"..adapter.save_status.."\nOperations window: Ctrl+Shift+Q\n\n"..modules.view.overview(self:view()),30)
        end)
        add("Automatic diagnostics",root,function()
            self:checked("diagnostic_checks",function()diagnostics:inspect(self)end)
            diagnostics:write(self,true)
            adapter:notify(diagnostics:brief())
        end)
        self.menu_signature=signature
    end
    function runtime:process_commands()
        if not storage then return end
        local read,items=self:checked("command_read",function()
            local items,why=storage.commands()
            if type(items)~="table" then return false,why or "Command list unavailable" end
            return items
        end)
        if not read then return end
        for _,item in ipairs(items) do
            if self.failed then break end
            if item.text then
                local ok,cmd=pcall(json.decode,item.text)
                if ok and type(cmd)=="table" and cmd.id==item.id then
                    local result=core:command(cmd)
                    if result.ok and cmd.action~="brief" and cmd.action~="mark" then adapter:save(core:snapshot()) end
                else env.warning("SQE Live: malformed UI command discarded") end
            end
            self:checked("command_ack",function()
                local ok,why=storage.ack(item.id)
                if not ok then return false,why or "Command acknowledgement could not be written" end
                return true
            end)
        end
    end
    local initialized,initialization_error=pcall(function()
        for _,d in ipairs(config.targets) do
            local ok,err=adapter:spawn_target(d,core.state.targets[d.id])
            if not ok then error("World initialization failed: "..tostring(err)) end
        end
        for _,s in pairs(core.state.shipments) do
            if s.status=="MOVING" or s.status=="ARRIVED" then
                local ok,err=adapter:spawn_shipment(s,true)
                if not ok then error("Convoy restore failed: "..tostring(err)) end
                if s.status=="ARRIVED" then adapter:hold_shipment(s) end
            end
        end
        adapter:sync_bases()
        local registered,why=adapter:world_health()
        if not registered then error("Spawned force registration mismatch: "..why) end
    end)
    if not initialized then
        adapter:cleanup()
        runtime.failed=tostring(initialization_error)
        diagnostics:set("startup","FAIL",initialization_error,core.state.time)
        diagnostics:write(runtime,true)
        error(initialization_error)
    end
    diagnostics:set("startup","PASS","Ground groups and bases initialized",core.state.time)
    local handler={}
    function handler:onEvent(event)
        if runtime.failed then return end
        local ok,err=pcall(function()adapter:on_event(event)end)
        if not ok then runtime:fail("Event handler: "..tostring(err)) end
        if event.id==world.event.S_EVENT_MISSION_END then adapter:save(core:snapshot()) end
        if runtime.failed or event.id==world.event.S_EVENT_MISSION_END then diagnostics:write(runtime,true) end
    end
    world.addEventHandler(handler)
    adapter:save(core:snapshot())
    runtime:checked("f10_menu",function()runtime:menus()end)
    runtime:checked("diagnostic_checks",function()diagnostics:inspect(runtime)end)
    runtime:publish();diagnostics:write(runtime,true)
    local warning=storage and "" or "\nStorage bridge absent: this session will NOT be saved; install the package for persistence/UI."
    runtime:checked("notifications",function()
        adapter:notify("SQE LIVE / SYRIA\nCampaign running. Use F10 > SQE Live or Ctrl+Shift+Q."..warning)
    end)
    timer.scheduleFunction(function(_,now)
        if not runtime.failed then
            local ok,err=pcall(function()
                local dt=math.max(0,now-runtime.last_clock);runtime.last_clock=now
                core:tick(dt)
                adapter:observe()
                Director.tick(core)
                core:check_task()
                adapter:sync_bases()
                runtime:process_commands()
                runtime:checked("f10_menu",function()runtime:menus()end)
                if core.state.time-runtime.last_save>=30 or core.state.revision~=runtime.last_save_revision then adapter:save(core:snapshot()) end
            end)
            if not ok then
                runtime:fail(err)
            end
        end
        runtime:publish()
        if core.state.time>=runtime.next_diagnostics then
            runtime.next_diagnostics=core.state.time+60
            runtime:checked("diagnostic_checks",function()diagnostics:inspect(runtime)end)
        end
        diagnostics:write(runtime)
        return now+2
    end,nil,timer.getTime()+2)
    return runtime
end
return Runtime
