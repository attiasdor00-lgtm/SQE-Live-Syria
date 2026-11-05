-- Campaign corridor eligibility and convoy pause/resume coordination.
-- Sector connectivity is an abstract permission, not a physical road boundary.
local S={MAX_SECTORS=32}
function S.path(c,side,from,to,unrestricted)
    if #c.config.zones>S.MAX_SECTORS or not c.zone_defs[from] or not c.zone_defs[to] then return nil end
    local function allowed(id)return c.zone_defs[id] and (unrestricted or c.state.zones[id].owner==side)end
    if not allowed(from) or not allowed(to) then return nil end
    local queue,parents={from},{[from]=false};local head=1
    while head<=#queue do
        local id=queue[head];head=head+1
        if id==to then
            local path={};while id do table.insert(path,1,id);id=parents[id] end
            return path
        end
        local neighbors=c.copy(c.zone_defs[id].neighbors);table.sort(neighbors)
        for _,next_id in ipairs(neighbors) do
            if parents[next_id]==nil and allowed(next_id) then parents[next_id]=id;queue[#queue+1]=next_id end
        end
    end
end
function S.path_open(c,side,path)
    if not path or #path==0 then return false end
    for _,id in ipairs(path) do if not c.state.zones[id] or c.state.zones[id].owner~=side then return false end end
    return true
end
function S.cut_reason(c,side,from,to)
    local path=S.path(c,side,from,to,true)
    if not path then return "No sector connection between source and destination." end
    local blocked={}
    for _,id in ipairs(path) do if c.state.zones[id].owner~=side then blocked[#blocked+1]=c.zone_defs[id].name end end
    return ("No controlled supply corridor. Blocked sector(s): "..table.concat(blocked,", ")):sub(1,300)
end
function S.sources(c,b,kind)
    local out={};local active=0;local reason="No operating "..(kind=="FUEL" and "fuel site" or "supply depot").." remains."
    for _,d in ipairs(c.config.targets) do
        if d.side==b.side and d.kind==kind and c:target_health(d.id)>0.25 and c.state.zones[d.zone].owner==b.side then
            active=active+1
            local path=S.path(c,b.side,d.zone,b.zone)
            if path then out[#out+1]={source=d.id,path=path}
            else reason=S.cut_reason(c,b.side,d.zone,b.zone) end
        end
    end
    table.sort(out,function(a,b)if #a.path==#b.path then return a.source<b.source end return #a.path<#b.path end)
    if #out>0 then reason="Controlled supply corridor available." end
    return out,active,reason
end
function S.offer(c,b,source)
    if not b or c.state.zones[b.zone].owner~=b.side then return nil,"Destination base is not controlled." end
    if not source then
        local choices,_,reason=S.sources(c,b,"DEPOT")
        return choices[1],reason
    end
    local d=c.target_defs[source]
    if not d or d.kind~="DEPOT" or d.side~=b.side or c:target_health(source)<=0.25
        or c.state.zones[d.zone].owner~=b.side then return nil,"Supply source is not operating or controlled." end
    local path=S.path(c,b.side,d.zone,b.zone)
    if not path then return nil,S.cut_reason(c,b.side,d.zone,b.zone) end
    return {source=source,path=path},"Controlled supply corridor available."
end
function S.prepare(c,ship)
    if ship.kind~="SUPPLY" or ship.status~="MOVING" then return nil end
    local from=c.target_defs[ship.source].zone
    local current=ship.corridor
    if current and S.path_open(c,ship.side,current.path) then return current end
    local path=S.path(c,ship.side,from,ship.zone)
    if not current then
        ship.corridor={path=path or S.path(c,ship.side,from,ship.zone,true) or {},
            state=path and "OPEN" or "CUT",reason=path and false or S.cut_reason(c,ship.side,from,ship.zone)}
    elseif path then
        current.path=path;current.state="RESUME";current.reason="Controlled corridor changed; road refresh pending."
    else
        current.state="CUT";current.reason=S.cut_reason(c,ship.side,from,ship.zone)
    end
    return ship.corridor
end
function S.open(c,ship)
    if ship.kind~="SUPPLY" then return true end
    local route=S.prepare(c,ship)
    return route and route.state=="OPEN" and S.path_open(c,ship.side,route.path)
end
function S.hold(c,ship)
    c.supply_holds=c.supply_holds or {}
    local hold=c.supply_holds[ship.id]
    if hold==true or (type(hold)=="number" and c.state.time<hold) then return end
    local called,ok=pcall(c.adapter.hold_shipment,c.adapter,ship)
    if called and ok then c.supply_holds[ship.id]=true
    else
        if not hold then c:note("Convoy "..ship.id..": hold command delayed; delivery remains blocked.") end
        c.supply_holds[ship.id]=c.state.time+10
    end
end
function S.update(c,ship)
    local previous=ship.corridor and ship.corridor.state
    local route=S.prepare(c,ship)
    if not route then return end
    if route.state=="OPEN" then return end
    if route.state=="CUT" and S.path_open(c,ship.side,route.path) then
        route.state="RESUME";route.reason="Corridor restored; road refresh pending."
    end
    if route.state~=previous then c:note("Convoy "..ship.id..": "..route.reason) end
    local nav=ship.navigation
    if not nav then return end
    nav.state="BLOCKED"
    S.hold(c,ship)
    if route.state~="CUT" and nav.attempts>=c.adapter.ground.RETRIES then
        route.state="BLOCKED";route.reason="Corridor open, but all three road refresh attempts are used."
    end
end
function S.resumed(c,ship)
    if ship.corridor then ship.corridor.state="OPEN";ship.corridor.reason=false end
    if c.supply_holds then c.supply_holds[ship.id]=nil end
end
function S.cleanup(c)
    for id in pairs(c.supply_holds or {}) do
        local s=c.state.shipments[id]
        if not s or s.status~="MOVING" then c.supply_holds[id]=nil end
    end
end
return S
