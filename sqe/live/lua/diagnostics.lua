-- Observational checks. Never fly test sorties or change campaign state.
-- PASS applies only to the named API/data check, never to actual DCS flight QA.
local D={}
D.__index=D
local function short(v) return tostring(v or ""):sub(1,700) end
function D.new(config,json,storage,session)
    return setmetatable({config=config,json=json,storage=storage,session=session,
        checks={},history={},last_write=-1000,dirty=true},D)
end
function D:set(id,status,detail,time)
    local previous=self.checks[id]
    detail=short(detail)
    if not previous or previous.status~=status or previous.detail~=detail then
        self.checks[id]={id=id,status=status,detail=detail,time=time or 0}
        self.history[#self.history+1]={id=id,status=status,detail=detail,time=time or 0}
        while #self.history>32 do table.remove(self.history,1) end
        self.dirty=true
        if status=="FAIL" and env and env.warning then
            pcall(env.warning,"SQE Live diagnostic ["..id.."]: "..detail)
        end
    end
end
function D:call(id,fn,time)
    local ok,a,b=pcall(fn)
    if not ok or a==false then
        local reason=ok and b or a
        self:set(id,"FAIL",reason,time);return false,nil,reason
    end
    self:set(id,"PASS","Call completed",time)
    return true,a,b
end
function D:summary()
    local fail,warn,pending=0,0,0
    for _,c in pairs(self.checks) do
        if c.status=="FAIL" then fail=fail+1 elseif c.status=="WARN" then warn=warn+1
        elseif c.status=="UNOBSERVED" then pending=pending+1 end
    end
    if fail>0 then return "Automatic checks: "..fail.." issue(s); see F10 Diagnostics." end
    if warn>0 then return "Automatic checks: "..warn.." warning(s); see F10 Diagnostics." end
    return "Automatic checks recorded; "..pending.." observation(s) pending. Flight QA pending."
end
function D:view(runtime)
    local checks={};for _,c in pairs(self.checks) do checks[#checks+1]=c end
    table.sort(checks,function(a,b)return a.id<b.id end)
    return {protocol=1,release=self.config.release or "unknown",campaign=self.config.id,
        session=self.session,time=runtime and runtime.core and runtime.core.state.time or 0,
        stopped=runtime and runtime.failed or false,summary=self:summary(),
        checks=checks,history=self.history,
        flight_validation="UNOBSERVED: this report does not validate rendering, AI tactics or performance"}
end
function D:write(runtime,force)
    local t=runtime and runtime.core and runtime.core.state.time or 0
    if not force and not self.dirty and t-self.last_write<60 then return end
    if not self.storage or type(self.storage.report)~="function" then return end
    local ok,result,why=pcall(function()
        return self.storage.report("runtime",self.json.encode(self:view(runtime)))
    end)
    self.last_write=t
    if not ok or not result then
        self:set("diagnostic_file","FAIL",ok and why or result,t)
    else
        if self.checks.diagnostic_file and self.checks.diagnostic_file.status=="FAIL" then
            self:set("diagnostic_file","PASS","Diagnostic file writes recovered",t)
        else self.dirty=false end
    end
end
function D:inspect(runtime)
    local c=runtime.core;local t=c.state.time
    local valid,why=c:validate_save(c:snapshot())
    self:set("campaign_state",valid and "PASS" or "FAIL",valid and "Inventory and saved-state constraints hold" or why,t)
    self:set("unit_budget",c:active_count()<=c.config.unit_budget and "PASS" or "FAIL",
        tostring(c:active_count()).." / "..c.config.unit_budget.." active units",t)
    self:set("mission_clock",t>0 and "PASS" or "UNOBSERVED",
        t>0 and "Campaign updates observed" or "Waiting for first update",t)
    self:set("campaign_updates",runtime.failed and "FAIL" or "PASS",
        runtime.failed or "Campaign updates enabled",t)
    local healthy,world_detail=c.adapter:world_health()
    self:set("world_registration",healthy and "PASS" or "FAIL",world_detail,t)
    self:set("player_sorties",c.state.pilot.sorties>0 and "PASS" or "UNOBSERVED",
        c.state.pilot.sorties.." takeoff event(s), "..c.state.pilot.landings.." landing event(s)",t)
    self:set("combat_results",c.state.completed>0 and "PASS" or "UNOBSERVED",
        c.state.completed.." objective completion(s) observed",t)
    if not self.storage then
        self:set("save_readback","WARN","Storage bridge absent; session is not persistent",t)
        self:set("ui_hook","UNOBSERVED","Storage bridge absent; use F10",t)
        return
    end
    if runtime.last_save>=0 then
        local ok,raw,err=pcall(self.storage.load,self.config.id,false)
        local decoded,value=pcall(self.json.decode,ok and raw or "")
        local saved_valid,saved_why=false,"Primary checkpoint could not be read"
        if decoded then saved_valid,saved_why=c:validate_save(value) end
        if saved_valid and (value.revision~=runtime.last_save_revision or value.time~=runtime.last_save) then
            saved_valid=false;saved_why="Checkpoint does not match last acknowledged save"
        end
        self:set("save_readback",saved_valid and "PASS" or "FAIL",
            saved_valid and "Primary checkpoint read back and validated" or saved_why or err,t)
    else self:set("save_readback","UNOBSERVED","No successful save yet",t) end
    if type(self.storage.read_report)~="function" then
        self:set("ui_hook","WARN","Installed bridge is older than the mission; reinstall package",t)
        return
    end
    local ok,raw=pcall(self.storage.read_report,"ui")
    local decoded,ui=pcall(self.json.decode,ok and raw or "")
    if decoded and type(ui)=="table" and ui.session==self.session and type(ui.heartbeat)=="number" then
        if ui.error then self:set("ui_hook","FAIL",ui.error,t)
        elseif ui.window_created==true and ui.status_connected==true
            and self.storage.now()-ui.heartbeat>=0 and self.storage.now()-ui.heartbeat<=90 then
            self:set("ui_hook","PASS","UI hook and status channel responsive; rendering not verified",t)
        else self:set("ui_hook","WARN","UI hook heartbeat stale or window not created; F10 remains available",t) end
    else self:set("ui_hook","UNOBSERVED","No UI heartbeat for this session yet; F10 remains available",t) end
end
function D:brief()
    local lines={"SQE LIVE / AUTOMATIC DIAGNOSTICS",self:summary()}
    local report=self:view()
    for _,c in ipairs(report.checks) do lines[#lines+1]=c.status.." / "..c.id..": "..c.detail end
    lines[#lines+1]="Local reports: SQE-Live/diagnostics-runtime.json and diagnostics-ui.json"
    return table.concat(lines,"\n")
end
return D
