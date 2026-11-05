-- SQE Live. Pure campaign logic; no DCS globals or filesystem calls.
-- MIT; see the project LICENSE. Distances are metres, time is simulation seconds.
local Core = {}
Core.__index = Core
local function copy(v)
    if type(v) ~= "table" then return v end
    local out = {}; for k, x in pairs(v) do out[k] = copy(x) end; return out
end
local function count(t)
    local n = 0; for _, v in pairs(t or {}) do if v then n = n + 1 end end; return n
end
local function dist(a, b)
    return math.sqrt((a.x-b.x)^2 + (a.y-b.y)^2)
end
local function finite(n) return type(n) == "number" and n == n and math.abs(n) < 1e12 end
local function integer(n,lo,hi) return finite(n) and n%1==0 and n>=lo and n<=hi end
local function position(p)
    return type(p)=="table" and finite(p.x) and finite(p.y) and math.abs(p.x)<5000000 and math.abs(p.y)<5000000
end
local function sequence(t,limit)
    if type(t)~="table" or #t>limit then return false end
    for k in pairs(t) do if not integer(k,1,#t) then return false end end
    return true
end
local function units(alive,positions,n)
    if type(alive)~="table" or type(positions)~="table" then return false end
    for i=1,n do if type(alive[tostring(i)])~="boolean" then return false end end
    for k in pairs(alive) do
        if type(k)~="string" or not integer(tonumber(k),1,n) or tostring(tonumber(k))~=k then return false end
    end
    for k,p in pairs(positions) do if alive[k]==nil or not position(p) then return false end end
    return true
end
Core.copy, Core.count, Core.distance = copy, count, dist

function Core.new(config, adapter, restored, session, targets, supply)
    assert(type(config) == "table" and config.id and config.content_version, "invalid content")
    local self = setmetatable({config=config, adapter=adapter, session=session,catalog=assert(targets,"target catalog required"),
        supply=assert(supply,"supply coordinator required"),
        target_defs={}, base_defs={}, zone_defs={}, journal={}, journal_order={}}, Core)
    for _, t in ipairs(config.targets) do self.target_defs[t.id] = t end
    for _, b in ipairs(config.bases) do self.base_defs[b.id] = b end
    for _, z in ipairs(config.zones) do self.zone_defs[z.id] = z end
    self.state = {schema=1, campaign=config.id, content=config.content_version, time=0,
        revision=1, next_id=0, rng=config.seed or 71, targets={}, bases={}, zones={},
        flights={}, shipments={}, maintenance={}, task=false, completed=0,
        pilot={sorties=0, landings=0, losses=0, airborne=false}, log={}, status="ACTIVE",
        next_director=180, next_logistics=900, next_repair=1800}
    for _, b in ipairs(config.bases) do
        self.state.bases[b.id] = {ready=copy(b.aircraft), resources=copy(b.resources)}
    end
    for _, t in ipairs(config.targets) do
        local alive = {}; for i=1,#t.types do alive[tostring(i)]=true end
        self.state.targets[t.id] = {alive=alive, generation=1, positions={}, destroyed_at=false,disabled_at=false}
    end
    for _, z in ipairs(config.zones) do self.state.zones[z.id]={owner=z.owner} end
    if restored then
        local ok, err = self:validate_save(restored)
        if not ok then error("Campaign save rejected: "..err) end
        self.state = copy(restored)
        for _,d in ipairs(config.targets) do
            local t=self.state.targets[d.id]
            if (d.kind=="DEPOT" or d.kind=="FUEL") and count(t.alive)/#d.types<=0.25 and not t.disabled_at then
                -- Legacy partial sites have no known outage time: start their repair wait at load.
                t.disabled_at=t.destroyed_at or self.state.time
            end
        end
        -- DCS cannot resume the exact aircraft, fuel and weapons states. Bring surviving
        -- interrupted AI flights back through maintenance, keeping losses and costs.
        for _, f in pairs(self.state.flights) do
            if f.status ~= "COMPLETE" then
                local survivors=count(f.alive)
                if survivors>0 then
                    self.state.maintenance[#self.state.maintenance+1] =
                        {base=f.base, aircraft=f.aircraft, count=survivors, due=self.state.time+600}
                end
            end
        end
        self.state.flights = {}
        self.state.pilot.airborne = false
        self:note("Campaign resumed. Interrupted surviving AI flights enter 10-minute maintenance.")
    else self:note("Operation Cedar Current begins. The campaign clock follows this session.") end
    return self
end

function Core:validate_save(s)
    if type(s)~="table" or s.schema~=1 or s.campaign~=self.config.id or s.content~=self.config.content_version then
        return false, "schema, campaign or content does not match"
    end
    for _, key in ipairs({"targets","bases","zones","flights","shipments","maintenance","pilot","log"}) do
        if type(s[key])~="table" then return false, "missing "..key end
    end
    for _, key in ipairs({"time","revision","next_id","rng","next_director","next_logistics","next_repair","completed"}) do
        if not finite(s[key]) or s[key]<0 then return false, "invalid "..key end
    end
    if not integer(s.rng,1,2147483646) or not integer(s.next_id,0,1e10) or not integer(s.revision,1,1e10)
        or not integer(s.completed,0,1e9) then return false,"invalid counters" end
    if s.status~="ACTIVE" and s.status~="VICTORY" and s.status~="DEFEAT" then return false,"invalid campaign status" end
    for id in pairs(s.targets) do if not self.target_defs[id] then return false,"unknown saved target" end end
    for id in pairs(s.bases) do if not self.base_defs[id] then return false,"unknown saved base" end end
    for id in pairs(s.zones) do if not self.zone_defs[id] then return false,"unknown saved zone" end end
    for id, def in pairs(self.target_defs) do
        local t=s.targets[id]
        if type(t)~="table" or not units(t.alive,t.positions,#def.types) or not integer(t.generation,1,1e8) then
            return false, "invalid target "..id
        end
        if t.destroyed_at~=false and (not finite(t.destroyed_at) or t.destroyed_at<0 or t.destroyed_at>s.time) then return false,"invalid destruction time" end
        if t.disabled_at~=nil and t.disabled_at~=false
            and (not finite(t.disabled_at) or t.disabled_at<0 or t.disabled_at>s.time) then return false,"invalid site outage time" end
    end
    for id, def in pairs(self.base_defs) do
        local b=s.bases[id]
        if type(b)~="table" or type(b.ready)~="table" or type(b.resources)~="table" then return false,"invalid base "..id end
        for ac, _ in pairs(def.aircraft) do
            if not integer(b.ready[ac],0,def.aircraft[ac]) then return false,"invalid inventory "..id end
        end
        for ac in pairs(b.ready) do if not def.aircraft[ac] then return false,"unknown aircraft stock" end end
        for _, r in ipairs({"fuel","ammo","supply"}) do
            if not finite(b.resources[r]) or b.resources[r]<0 or b.resources[r]>200 then return false,"invalid resources "..id end
        end
    end
    for id in pairs(self.zone_defs) do
        if type(s.zones[id])~="table" or (s.zones[id].owner~="blue" and s.zones[id].owner~="red") then return false,"invalid zone "..id end
    end
    local stock={}
    for id,b in pairs(s.bases) do stock[id]=copy(b.ready) end
    local roles={CAP=true,ESCORT=true,SEAD=true,STRIKE=true,AWACS=true,TANKER=true}
    local statuses={ENROUTE=true,HOLD=true,RTB=true,COMPLETE=true}
    for id, f in pairs(s.flights) do
        if type(f)~="table" or type(id)~="string" or id~=f.id or #id>80 or not self.base_defs[f.base]
            or not self.config.flight_types[f.aircraft] or not self.base_defs[f.base].aircraft[f.aircraft]
            or not integer(f.count,1,2) or not units(f.alive,{},f.count)
            or not roles[f.role] or not statuses[f.status] or f.side~=self.base_defs[f.base].side
            or type(f.label)~="string" or #f.label>120 or type(f.automatic)~="boolean"
            or not finite(f.expires) or not finite(f.started) or f.started<0 or f.started>s.time
            or (f.target~=false and not self:target(f.target,s)) then return false,"invalid flight" end
        if f.status~="COMPLETE" then stock[f.base][f.aircraft]=stock[f.base][f.aircraft]+count(f.alive)
        elseif not finite(f.finished) or f.finished>s.time then return false,"invalid recovery time" end
    end
    if not sequence(s.maintenance,200) then return false,"invalid maintenance list" end
    for _,m in pairs(s.maintenance) do
        if type(m)~="table" or not self.base_defs[m.base] or not self.base_defs[m.base].aircraft[m.aircraft]
            or not integer(m.count,1,2) or not finite(m.due) or m.due<0 then return false,"invalid maintenance" end
        stock[m.base][m.aircraft]=stock[m.base][m.aircraft]+m.count
    end
    for id,types in pairs(stock) do for ac,n in pairs(types) do
        if n>self.base_defs[id].aircraft[ac] then return false,"aircraft conservation violated" end
    end end
    for id,c in pairs(s.shipments) do
        if type(c)~="table" or type(id)~="string" or id~=c.id or #id>80 or self.target_defs[id] or not self.base_defs[c.base]
            or c.side~=self.base_defs[c.base].side or not self.zone_defs[c.zone] or not units(c.alive,c.positions,4)
            or not finite(c.started) or c.started<0 or c.started>s.time
            or (c.status~="MOVING" and c.status~="ARRIVED" and c.status~="DELIVERED" and c.status~="LOST")
            or (c.destination~=nil and not position(c.destination)) then return false,"invalid convoy" end
        if c.kind=="SUPPLY" then
            if not self.target_defs[c.source] or self.target_defs[c.source].kind~="DEPOT"
                or self.target_defs[c.source].side~=c.side or c.zone~=self.base_defs[c.base].zone then return false,"invalid supply source" end
        elseif c.kind=="ASSAULT" then
            if not self.zone_defs[c.source] then return false,"invalid assault source" end
        else return false,"invalid convoy kind" end
        if c.status=="ARRIVED" and c.kind~="ASSAULT" then return false,"invalid garrison kind" end
        if c.outcome~=nil and c.outcome~=false then
            local outcomes={DESTROYED=true,DELIVERED=true,TIMED_OUT=true,DESTINATION_LOST=true}
            if not outcomes[c.outcome] or c.status=="MOVING" or c.status=="ARRIVED"
                or (c.outcome=="DESTROYED" and count(c.alive)>0)
                or (c.outcome=="DELIVERED" and (c.kind~="SUPPLY" or c.status~="DELIVERED" or count(c.alive)>0))
                or (c.outcome=="DESTINATION_LOST" and c.kind~="SUPPLY") then return false,"invalid convoy outcome" end
        end
        if c.delivered~=nil then
            if c.kind~="SUPPLY" or type(c.delivered)~="table" then return false,"invalid delivered cargo" end
            for k,v in pairs(c.delivered) do
                if c.alive[k]==nil or type(v)~="boolean" or (v and c.alive[k]) then return false,"invalid delivered cargo" end
            end
        end
        if c.corridor~=nil then
            local r=c.corridor
            if c.kind~="SUPPLY" or type(r)~="table" or not ({OPEN=true,CUT=true,RESUME=true,BLOCKED=true})[r.state]
                or not sequence(r.path,self.supply.MAX_SECTORS)
                or (r.state=="OPEN" and r.reason~=false)
                or (r.state~="OPEN" and (type(r.reason)~="string" or #r.reason==0 or #r.reason>300)) then return false,"invalid supply corridor" end
            if #r.path==0 then
                if r.state~="CUT" or self.supply.path(self,c.side,self.target_defs[c.source].zone,c.zone,true) then
                    return false,"invalid empty corridor"
                end
            elseif r.path[1]~=self.target_defs[c.source].zone or r.path[#r.path]~=c.zone then
                return false,"invalid corridor endpoints"
            end
            local seen={}
            for i,id in ipairs(r.path) do
                if not self.zone_defs[id] or seen[id] then return false,"invalid corridor sector" end
                seen[id]=true
                if i>1 then
                    local adjacent=false
                    for _,neighbor in ipairs(self.zone_defs[r.path[i-1]].neighbors)do if neighbor==id then adjacent=true end end
                    if not adjacent then return false,"invalid corridor connection" end
                end
            end
        end
        local nav=c.navigation
        if nav~=nil then
            if type(nav)~="table" or not ({MOVING=true,WAITING=true,STALLED=true,BLOCKED=true})[nav.state]
                or not integer(nav.attempts,0,3) or not finite(nav.next_retry) or nav.next_retry<0
                or not finite(nav.deadline) or nav.deadline<c.started or nav.deadline>c.started+21600
                or not finite(nav.route_length) or nav.route_length<0 or nav.route_length>300000
                or (nav.last_error~=false and (type(nav.last_error)~="string" or #nav.last_error>300))
                or type(nav.watch)~="table" then return false,"invalid convoy navigation" end
            for k,p in pairs(nav.watch) do
                if c.alive[k]==nil or not position(p) or not finite(p.at) or p.at<0 or p.at>s.time then
                    return false,"invalid convoy progress observation"
                end
            end
        end
    end
    if s.task~=false then
        if type(s.task)~="table" then return false,"invalid player task" end
        local d,t=self:target(s.task.target,s)
        if not d or d.side~="red" or not finite(s.task.accepted) or s.task.accepted<0 or s.task.accepted>s.time
            or (s.task.role~="SEAD" and s.task.role~="DEAD" and s.task.role~="CAS" and s.task.role~="STRIKE")
            or (d.shipment and s.task.role~=(t.kind=="ASSAULT" and "CAS" or "STRIKE")) then return false,"invalid player task" end
    end
    for _,k in ipairs({"sorties","landings","losses"}) do
        if not integer(s.pilot[k],0,1e8) then return false,"invalid pilot record" end
    end
    if type(s.pilot.airborne)~="boolean" or not sequence(s.log,80) then return false,"invalid pilot/log" end
    for _,l in pairs(s.log) do
        if type(l)~="table" or not finite(l.time) or l.time<0 or l.time>s.time or type(l.text)~="string" or #l.text>1024 then return false,"invalid log" end
    end
    local active=self.config.player_slots or 1
    local flights=0
    for _,t in pairs(s.targets) do active=active+count(t.alive) end
    for _,f in pairs(s.flights) do
        if f.status~="COMPLETE" then active=active+count(f.alive);flights=flights+1 end
    end
    for _,ship in pairs(s.shipments) do
        if ship.status=="MOVING" or ship.status=="ARRIVED" then active=active+count(ship.alive) end
    end
    if active>self.config.unit_budget or flights>self.config.max_flights then return false,"saved force exceeds active limits" end
    return true
end

function Core:note(text)
    local s=self.state; s.log[#s.log+1]={time=s.time,text=text}
    while #s.log>80 do table.remove(s.log,1) end
    s.revision=s.revision+1
end
function Core:random()
    self.state.rng=(self.state.rng*16807)%2147483647
    return self.state.rng/2147483647
end
function Core:id(prefix)
    self.state.next_id=self.state.next_id+1
    return prefix..tostring(self.state.next_id)
end
function Core:target(id,state) return self.catalog.resolve(self,id,state) end
function Core:target_health(id)
    local d,s=self:target(id)
    return d and s and count(s.alive)/(d.size or #d.types) or 0
end
function Core:suppressed(id)
    local d,s=self:target(id)
    if not d or not d.radars or #d.radars==0 then return self:target_health(id)==0 end
    for _, i in ipairs(d.radars) do if s.alive[tostring(i)] then return false end end
    return true
end
function Core:task_done(task)
    return self.catalog.result(self,task)=="complete"
end
function Core:defenders(zone,side,health)
    local n=0
    for _,t in ipairs(self.config.targets) do
        if t.zone==zone and t.side~=side and t.kind=="ARMOR" then
            n=n+(health and self:target_health(t.id) or count(self.state.targets[t.id].alive))
        end
    end
    for _,s in pairs(self.state.shipments) do
        if s.zone==zone and s.side~=side and s.status=="ARRIVED" then
            n=n+(health and count(s.alive)/4 or count(s.alive))
        end
    end
    return n
end
function Core:tasks()
    return self.catalog.tasks(self)
end
function Core:active_count()
    local n=self.config.player_slots or 1
    for _, t in pairs(self.state.targets) do n=n+count(t.alive) end
    for _, f in pairs(self.state.flights) do if f.status~="COMPLETE" then n=n+count(f.alive) end end
    for _, c in pairs(self.state.shipments) do if c.status=="MOVING" or c.status=="ARRIVED" then n=n+count(c.alive) end end
    return n
end
function Core:check_task()
    local t=self.state.task
    if not t then return end
    local result,why=self.catalog.result(self,t)
    if not result then return end
    local d=self:target(t.target);local name=d and d.name or t.target
    self.state.task=false
    if result=="complete" then
        self.state.completed=self.state.completed+1
        self:note("Objective complete: "..name..". Select another task whenever ready.")
        if self.adapter.notify then pcall(self.adapter.notify,self.adapter,"SQE: objective complete. Another task is available.") end
    else
        self:note("Objective unavailable: "..name..". "..why.." No completion credited.")
    end
end
function Core:lose_target(id, index)
    local t=self.state.targets[id]; local key=tostring(index)
    if not t or not t.alive[key] then return false end
    t.alive[key]=false
    local d=self.target_defs[id]
    if (d.kind=="DEPOT" or d.kind=="FUEL") and count(t.alive)/#d.types<=0.25 and not t.disabled_at then
        t.disabled_at=self.state.time
    end
    if count(t.alive)==0 then t.destroyed_at=self.state.time end
    self:note(self.target_defs[id].name..": unit lost ("..count(t.alive).."/"..#self.target_defs[id].types.." remaining).")
    self:check_task()
    return true
end
function Core:lose_flight(id,index)
    local f=self.state.flights[id]; local key=tostring(index)
    if not f or f.status=="COMPLETE" or not f.alive[key] then return false end
    f.alive[key]=false
    self:note(f.label..": aircraft lost.")
    if count(f.alive)==0 then f.status="COMPLETE"; f.finished=self.state.time end
    return true
end
function Core:recover_flight(id)
    local f=self.state.flights[id]
    if not f or f.status=="COMPLETE" then return false end
    local n=count(f.alive)
    f.status="COMPLETE"; f.finished=self.state.time
    if n>0 then
        self.state.maintenance[#self.state.maintenance+1]={base=f.base,aircraft=f.aircraft,count=n,due=self.state.time+600}
        self:note(f.label..": "..n.." aircraft recovered; maintenance 10 minutes.")
    end
    return true
end

local COST={CAP={fuel=8,ammo=8,supply=0},ESCORT={fuel=8,ammo=8,supply=0},
    SEAD={fuel=8,ammo=12,supply=0},STRIKE={fuel=8,ammo=12,supply=0},
    AWACS={fuel=10,ammo=0,supply=0},TANKER={fuel=15,ammo=0,supply=0}}
function Core:automation_reserve(base)
    -- Solo tuning: one requested strike (8/12) plus one site's repair (0/10/25).
    return base.side=="blue" and {fuel=8,ammo=22,supply=25} or {fuel=0,ammo=0,supply=0}
end
function Core:ground_funding(base)
    local reserve=self:automation_reserve(base)
    local stock=self.state.bases[base.id].resources
    if base.side=="blue" and #self.supply.sources(self,base,"DEPOT")==0 then
        local repairable=false
        for _,d in ipairs(self.config.targets) do
            if d.side==base.side and d.kind=="DEPOT" and self:target_health(d.id)<=0.25
                and stock.supply>=25 and stock.ammo>=10 and self.supply.path(self,base.side,base.zone,d.zone) then repairable=true end
        end
        -- With no depot or affordable depot repair, spend finite stock on last advances.
        if not repairable then reserve.supply=0 end
    end
    return stock.supply>=12+reserve.supply,12+reserve.supply
end
function Core:flight_offer(role,side,target,automatic)
    -- A read-only dispatch quote. Launch rechecks this same function before spending.
    local cost=COST[role]
    local out={available=false,role=role,side=side,target=target or false,cost=copy(cost or {})}
    local function blocked(code,reason)out.code=code;out.reason=reason;return out end
    if not cost or not self.config.role_aircraft[side] then return blocked("ROLE","Unknown support role or side") end
    if role=="AWACS" or role=="TANKER" then target=nil;out.target=false end
    local d,t=self:target(target)
    if target and not d then return blocked("TARGET","Target is no longer available") end
    if (role=="STRIKE" or role=="SEAD") and (not d or d.side==side or not self.catalog.active(self,d,t)) then
        return blocked("TARGET","A living enemy target is required")
    end
    if d and d.shipment and (d.side==side or not self.catalog.active(self,d,t)) then
        return blocked("TARGET","Ground force is no longer an enemy target")
    end
    if role=="SEAD" and (d.kind~="SAM" or self:suppressed(target)) then return blocked("TARGET","No operating radar at this target") end
    local n=(role=="AWACS" or role=="TANKER") and 1 or 2
    -- Project policy: explicit blue requests may use a surviving single only
    -- after every funded pair has been considered. Automatic/red flights keep
    -- their normal size; a single still pays the full sortie resource cost.
    local sizes=(n==2 and side=="blue" and not automatic) and {2,1} or {n}
    local selected,aircraft
    local reasons,resource_shortage,reserve_shortage
    for _,size in ipairs(sizes) do
        n=size;out.count=n
        reasons={};resource_shortage=false;reserve_shortage=false
        for _, b in ipairs(self.config.bases) do
            if b.side==side and self.state.zones[b.zone].owner==side then
                local ready
                for _, ac in ipairs(self.config.role_aircraft[side][role] or {}) do
                    if (self.state.bases[b.id].ready[ac] or 0)>=n then ready=ac;break end
                end
                if ready then
                    local missing={};local protected={};local reserve=self:automation_reserve(b)
                    for _,r in ipairs({"fuel","ammo","supply"}) do
                        local remaining=self.state.bases[b.id].resources[r]-cost[r]
                        if remaining<0 then missing[#missing+1]=r
                        elseif automatic and cost[r]>0 and remaining<reserve[r] then protected[#protected+1]=r end
                    end
                    if #missing==0 and #protected==0 then selected,aircraft=b,ready;break end
                    if #missing>0 then
                        resource_shortage=true;reasons[#reasons+1]=b.name..": insufficient "..table.concat(missing," / ")
                    else
                        reserve_shortage=true;reasons[#reasons+1]=b.name..": automatic dispatch preserves solo reserve ("..table.concat(protected," / ")..")"
                    end
                else
                    local compatible={};local maintenance=0
                    for _,ac in ipairs(self.config.role_aircraft[side][role] or {}) do compatible[ac]=true end
                    for _,m in ipairs(self.state.maintenance) do
                        if m.base==b.id and compatible[m.aircraft] then maintenance=maintenance+m.count end
                    end
                    reasons[#reasons+1]=b.name..": needs "..n.." ready aircraft for "..role
                        ..(maintenance>0 and ("; "..maintenance.." in maintenance") or "")
                end
            end
        end
        if selected then break end
    end
    if not selected then
        if #reasons==0 then return blocked("BASE_LOST","No friendly operating base remains") end
        return blocked(resource_shortage and "RESOURCES" or reserve_shortage and "RESERVE" or "AIRCRAFT",table.concat(reasons,"; "))
    end
    if self:active_count()+n>self.config.unit_budget then return blocked("UNIT_LIMIT","Active unit budget reached; wait for a flight to recover") end
    local active=0
    for _, f in pairs(self.state.flights) do
        if f.status~="COMPLETE" then
            active=active+1
            if f.side==side and f.role==role and (role=="AWACS" or role=="TANKER" or f.target==out.target) then
                return blocked("ASSIGNED",role.." already assigned")
            end
        end
    end
    if active>=self.config.max_flights then return blocked("FLIGHT_LIMIT","Airspace is at its flight limit") end
    out.available=true;out.code="READY";out.base=selected.id;out.base_name=selected.name;out.aircraft=aircraft
    out.reason=n.." "..aircraft.." ready at "..selected.name
        ..((n==1 and role~="AWACS" and role~="TANKER") and "; single-aircraft support, no funded pair available; full sortie cost" or "")
    return out
end
function Core:support_offer(role,selected)
    if role=="AWACS" or role=="TANKER" then return self:flight_offer(role,"blue",nil) end
    local target=self.state.task and self.state.task.target or selected
    local function blocked(reason)return {available=false,role=role,code="TARGET",reason=reason}end
    local d,t=self:target(target)
    if target and (not d or not self.catalog.active(self,d,t)) then return blocked("Support target is no longer available") end
    if (role=="SEAD" or role=="STRIKE") and not target then return blocked("Select a target first") end
    if target and d.side~="red" then return blocked("Support cannot attack friendly targets") end
    if role=="SEAD" and d and d.shipment then return blocked("This ground force has no radar objective. Select a SAM for SEAD.") end
    if role=="SEAD" and target and d.kind~="SAM" then
        local origin=d;local nearest,range
        for _,d in ipairs(self.config.targets) do
            local r=dist(origin,d)
            if d.kind=="SAM" and d.side=="red" and not self:suppressed(d.id) and (not range or r<range) then
                nearest,range=d.id,r
            end
        end
        target=nearest
    end
    if role=="SEAD" and (not target or self:suppressed(target)) then return blocked("No active enemy radar at the selected support target") end
    if role=="STRIKE" and self:target_health(target)==0 then return blocked("Target already destroyed") end
    return self:flight_offer(role,"blue",target)
end
function Core:launch(role,side,target,automatic)
    local offer=self:flight_offer(role,side,target,automatic)
    if not offer.available then return false,offer.reason end
    local selected=self.base_defs[offer.base]
    local aircraft,n,cost=offer.aircraft,offer.count,offer.cost
    local b=self.state.bases[selected.id]
    local alive={}; for i=1,n do alive[tostring(i)]=true end
    local f={id=self:id("flight-"),side=side,role=role,base=selected.id,aircraft=aircraft,
        target=offer.target,count=n,alive=alive,status="ENROUTE",started=self.state.time,
        expires=self.state.time+((role=="AWACS" or role=="TANKER") and 5400 or 2100),
        automatic=automatic or false,label=side.." "..role.." "..self.state.next_id}
    -- A failed spawn has no inventory effect. ID gaps are intentionally harmless.
    local ok,err=self.adapter:spawn_flight(f)
    if not ok then return false,"Flight could not launch: "..tostring(err) end
    b.ready[aircraft]=b.ready[aircraft]-n
    for r,v in pairs(cost) do b.resources[r]=b.resources[r]-v end
    self.state.flights[f.id]=f
    self:note(f.label.." launched from "..selected.name..".")
    return true,f.label.." dispatched ("..n.." aircraft)"
end

function Core:command(cmd)
    if type(cmd)~="table" or type(cmd.id)~="string" or #cmd.id>100 then return {ok=false,message="Invalid command"} end
    if cmd.session~=self.session then return {ok=false,message="This command belongs to another session"} end
    if self.journal[cmd.id] then return copy(self.journal[cmd.id]) end
    local ok,message=false,"Unknown command"
    if cmd.action~="save" and cmd.action~="brief" and cmd.action~="mark" and cmd.revision~=self.state.revision then
        message="Campaign changed. Refresh and try again."
    elseif cmd.action=="accept" then
        if self.state.task then message="Finish or abort your current task first."
        elseif not self:target(cmd.target) or self:target(cmd.target).side~="red" then message="Invalid target."
        else
            for _, t in ipairs(self:tasks()) do
                if t.id==cmd.target then
                    self.state.task={target=t.id,role=t.role,accepted=self.state.time}
                    self:note("Assigned: "..t.role.." / "..t.name)
                    ok,message=true,"Task assigned. Coordinates are in Brief / F10."
                    break
                end
            end
            if not ok then message="Target is no longer available." end
        end
    elseif cmd.action=="abort" then
        if self.state.task then self:note("Player task aborted; world state and losses are retained."); self.state.task=false; ok=true; message="Task aborted."
        else message="No active player task." end
    elseif cmd.action=="support" then
        local offer=self:support_offer(cmd.role,cmd.target)
        if offer.available then ok,message=self:launch(cmd.role,"blue",offer.target,false)
        else message=offer.reason end
    elseif cmd.action=="hold" or cmd.action=="push" then
        local n=0
        for _,f in pairs(self.state.flights) do
            if f.side=="blue" and not f.automatic and f.status~="COMPLETE" and f.status~="RTB" and f.role~="AWACS" and f.role~="TANKER" then
                if self.adapter:control_flight(f,cmd.action) then f.status=cmd.action=="hold" and "HOLD" or "ENROUTE"; n=n+1 end
            end
        end
        ok=n>0; message=n>0 and (cmd.action.." sent to "..n.." supporting flights.") or "No supporting flight available."
        if ok then self:note(message) end
    elseif cmd.action=="save" then
        ok,message=self.adapter:save(self:snapshot())
    elseif cmd.action=="brief" or cmd.action=="mark" then
        local id=cmd.target or (self.state.task and self.state.task.target)
        local d=self:target(id)
        if d then message,ok=self.adapter:brief(d,cmd.action=="mark")
        else message="Select a target first." end
    end
    local result={id=cmd.id,ok=ok,message=message,revision=self.state.revision}
    self.journal[cmd.id]=copy(result); self.journal_order[#self.journal_order+1]=cmd.id
    if #self.journal_order>128 then self.journal[table.remove(self.journal_order,1)]=nil end
    self.last_result=result
    return result
end

function Core:tick(dt)
    if not finite(dt) or dt<0 then error("Invalid simulation delta") end
    self.state.time=self.state.time+dt
    for i=#self.state.maintenance,1,-1 do
        local m=self.state.maintenance[i]
        if m.due<=self.state.time then
            local b=self.state.bases[m.base]; local def=self.base_defs[m.base]
            if self.state.zones[def.zone].owner==def.side then
                b.ready[m.aircraft]=math.min(def.aircraft[m.aircraft],(b.ready[m.aircraft] or 0)+m.count)
                self:note(m.count.." "..m.aircraft.." returned to service at "..def.name..".")
            else self:note("Maintenance aircraft lost at captured base "..def.name..".") end
            table.remove(self.state.maintenance,i)
        end
    end
    for id,f in pairs(self.state.flights) do
        if f.status~="COMPLETE" and self.state.time>=f.expires and f.status~="RTB" then
            self:request_return(f,"returning to base.",false)
        end
        if f.status~="COMPLETE" and self.state.time>f.expires+1800 then
            self.adapter:retire_flight(f)
            f.status="COMPLETE"; f.finished=self.state.time
            self:note(f.label.." overdue: remaining airframes recorded missing, not returned to inventory.")
        elseif f.status=="COMPLETE" and self.state.time-(f.finished or 0)>300 then self.state.flights[id]=nil end
    end
    self:check_task()
    self:reconcile_support()
end
function Core:request_return(f,reason,release_target)
    self.target_returns=self.target_returns or {}
    if f.status=="RTB" then
        if release_target then f.target=false end
        self.target_returns[f.id]=nil;return true
    end
    local retry=self.target_returns[f.id]
    if retry and self.state.time<retry then return false end
    local called,ok=pcall(self.adapter.control_flight,self.adapter,f,"rtb")
    if called and ok then
        self:note(f.label..": "..reason)
        f.status="RTB"
        if release_target then f.target=false end
        self.target_returns[f.id]=nil;return true
    end
    if not retry then self:note(f.label..": return-to-base command delayed; will retry.") end
    self.target_returns[f.id]=self.state.time+10
    return false
end
function Core:reconcile_support()
    self.target_returns=self.target_returns or {}
    for id in pairs(self.target_returns) do
        if not self.state.flights[id] or self.state.flights[id].status=="COMPLETE" then self.target_returns[id]=nil end
    end
    for id,f in pairs(self.state.flights) do
        if f.target and f.status~="COMPLETE" then
            local d,t=self:target(f.target)
            if not d or ((d.shipment or f.role=="STRIKE" or f.role=="SEAD") and not self.catalog.active(self,d,t)) then
                self:request_return(f,"target "..f.target.." unavailable; returning to base.",true)
            end
        end
    end
end
function Core:snapshot() return copy(self.state) end
function Core:view()
    local s=self.state; local flights={}
    for _, f in pairs(s.flights) do
        if f.side=="blue" and f.status~="COMPLETE" then
            flights[#flights+1]={id=f.id,label=f.label,role=f.role,status=f.status,survivors=count(f.alive),target=f.target}
        end
    end
    table.sort(flights,function(a,b)return a.id<b.id end)
    local zones={}; for _,z in ipairs(self.config.zones) do zones[#zones+1]={name=z.name,owner=s.zones[z.id].owner} end
    local bases={};for _,b in ipairs(self.config.bases) do if b.side=="blue" then
        bases[#bases+1]={id=b.id,name=b.name,ready=copy(s.bases[b.id].ready),resources=copy(s.bases[b.id].resources)}
    end end
    return {protocol=1,campaign=s.campaign,session=self.session,title=self.config.name,
        time=s.time,revision=s.revision,status=s.status,task=copy(s.task),tasks=self:tasks(),
        completed=s.completed,pilot=copy(s.pilot),flights=flights,zones=zones,bases=bases,
        unit_count=self:active_count(),unit_budget=self.config.unit_budget,
        log=copy(s.log),last_result=copy(self.last_result or false),results=copy(self.journal)}
end
return Core
