-- Shared, read-only target discovery. Shipment state remains the sole inventory.
local T={}
function T.resolve(c,id,state)
    if type(id)~="string" then return nil end
    state=state or c.state
    local d=c.target_defs[id]
    if d then return d,state.targets[id] end
    local s=state.shipments[id]
    if type(s)~="table" or (s.kind~="ASSAULT" and s.kind~="SUPPLY") then return nil end
    local z=c.zone_defs[s.zone]
    if not z then return nil end
    local name=s.kind=="SUPPLY" and "Supply convoy" or s.status=="ARRIVED" and "Occupying garrison" or "Assault column"
    return {id=id,name=name.." "..id,side=s.side,zone=s.zone,x=z.x,y=z.y,
        kind=s.kind=="ASSAULT" and "ARMOR" or "CONVOY",shipment=true,size=4,
        priority=s.kind=="ASSAULT" and 75 or 45,
        threat="Ground force; enemy fighters and local air defences may be nearby."},s
end
function T.active(c,d,s)
    return d~=nil and s~=nil and (not d.shipment or s.status=="MOVING" or s.status=="ARRIVED")
        and c.count(s.alive)>0 and (d.shipment or c:target_active(d.id))
end
function T.frontline(c,zone)
    return c:zone_frontline(zone)
end
local function strategic_sources(c)
    local sources={}
    local front={}
    for _,z in ipairs(c.config.zones) do
        if c.state.zones[z.id].owner=="red" and T.frontline(c,z.id) then front[#front+1]=z.id end
    end
    for _,b in ipairs(c.config.bases) do
        if b.side=="red" and c.state.zones[b.zone].owner=="red" then
            for _,zone in ipairs(front) do
                if c.supply.path(c,"red",b.zone,zone) then
                    for _,kind in ipairs({"DEPOT","FUEL"}) do
                        for _,offer in ipairs(c.supply.sources(c,b,kind)) do sources[offer.source]=true end
                    end
                    break
                end
            end
        end
    end
    return sources
end
function T.tasks(c)
    local out={}
    local live=c.config.frontline_tasking
    if live and c.state.status~="ACTIVE" then return out end
    local strategic=live and strategic_sources(c)
    local function add(id)
        local d,s=T.resolve(c,id)
        if not d or d.side~="red" or d.taskable==false or not T.active(c,d,s) then return end
        local current=c.state.task and c.state.task.target==id and c.state.task
        local why
        if live then
            if d.shipment then
                why=s.kind=="SUPPLY" and "An enemy convoy still carries supplies."
                    or s.status=="ARRIVED" and "An enemy garrison is holding this sector."
                    or "An enemy ground column is advancing on this sector."
            elseif c.state.zones[d.zone].owner~="red" then return
            elseif current then why="Your current assignment."
            elseif d.chain_objective then
                local stage=c:zone_stage(d.zone)
                why="Ordered sector objective "..stage.."/4. Complete it to unlock the next stage."
            elseif T.frontline(c,d.zone) then why="This target is on the active front."
            elseif strategic[id] then why="This source supplies bases connected to the enemy front."
            else return end
        end
        local remaining=c:target_health(id)
        if not d.shipment and remaining<=0.25 and d.kind~="ARMOR"
            and not (d.kind=="SAM" and not c:suppressed(id)) then return end
        local role=d.kind=="SAM" and (c:suppressed(id) and "DEAD" or "SEAD")
            or d.kind=="ARMOR" and "CAS" or "STRIKE"
        out[#out+1]={id=id,role=live and current and current.role or role,name=d.name,zone=d.zone,x=d.x,y=d.y,why=why,
            health=remaining,priority=d.priority or 1,threat=d.threat or "Enemy fighters and short-range air defences",
            formation=d.formation,
            dynamic=d.shipment==true,survivors=c.count(s.alive),
            force_state=d.shipment and (s.status=="ARRIVED" and "GARRISON"
                or s.corridor and s.corridor.state~="OPEN" and ("SUPPLY_"..s.corridor.state)
                or (s.navigation and s.navigation.state or "MOVING")) or nil,
            objective=d.shipment and "Destroy every remaining vehicle in this force. Arrival or withdrawal does not count as destruction."
                or d.chain_objective and (role=="SEAD" and "Destroy every search/tracking radar to unlock DEAD."
                    or role=="DEAD" and "Reduce the remaining battery to 25% strength or less to unlock STRIKE."
                    or role=="STRIKE" and "Reduce the logistics/command group to 25% strength or less to unlock CAS."
                    or "Destroy every garrison vehicle. A friendly ground column must still arrive to capture the sector.") or nil}
    end
    for _,d in ipairs(c.config.targets) do add(d.id) end
    for id in pairs(c.state.shipments) do add(id) end
    table.sort(out,function(a,b)if a.priority==b.priority then return a.id<b.id end return a.priority>b.priority end)
    return out
end
function T.result(c,task)
    local d,s=T.resolve(c,task.target)
    if not d or not s then return "unavailable","The force is no longer present." end
    if d.shipment then
        if s.outcome=="DESTROYED" and c.count(s.alive)==0 then return "complete" end
        if not T.active(c,d,s) then
            return "unavailable",s.outcome=="DELIVERED" and "The remaining cargo reached its destination."
                or s.outcome=="TIMED_OUT" and "The force was withdrawn after its journey deadline."
                or "The force is no longer an active target."
        end
        return nil
    end
    if task.role=="SEAD" and c:suppressed(task.target)
        or task.role=="CAS" and c:target_health(task.target)==0
        or (task.role=="STRIKE" or task.role=="DEAD") and c:target_health(task.target)<=0.25 then return "complete" end
    if c.config.frontline_tasking and c.state.zones[d.zone].owner~="red" then
        return "unavailable","Friendly forces now control the sector."
    end
end
function T.referenced(c,id)
    if c.state.task and c.state.task.target==id then return true end
    for _,f in pairs(c.state.flights) do if f.target==id then return true end end
    return false
end
return T
