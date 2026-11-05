-- Continuous tasking and logistics. All battles are settled by DCS observations.
local Director={}
local function enemy(side) return side=="blue" and "red" or "blue" end
local function active_flights(c,side)
    local n=0;for _,f in pairs(c.state.flights) do if f.side==side and f.status~="COMPLETE" then n=n+1 end end;return n
end
function Director.air(c,side)
    if active_flights(c,side)>=3 then return end
    local candidates={}
    for _,d in ipairs(c.config.targets) do
        if d.side==enemy(side) and c:target_health(d.id)>0.25 and d.taskable~=false then
            local priority=d.priority or 1
            if d.kind=="SAM" and not c:suppressed(d.id) then priority=priority+20 end
            candidates[#candidates+1]={d=d,score=priority}
        end
    end
    table.sort(candidates,function(a,b)if a.score==b.score then return a.d.id<b.d.id end return a.score>b.score end)
    local cap=false
    for _,f in pairs(c.state.flights) do if f.side==side and f.role=="CAP" and f.status~="COMPLETE" then cap=true end end
    if not cap then
        local target=candidates[1] and candidates[1].d.id
        c:launch("CAP",side,target,true)
        return
    end
    for _,entry in ipairs(candidates) do
        local d=entry.d
        local role=d.kind=="SAM" and not c:suppressed(d.id) and "SEAD" or "STRIKE"
        if c:launch(role,side,d.id,true) then break end
    end
end
local function shipment_active(c,base,kind,zone)
    for _,s in pairs(c.state.shipments) do
        if s.status=="MOVING" and s.base==base and s.kind==kind and s.zone==zone then return true end
    end
    return false
end
function Director.dispatch(c,b,kind,zone,source)
    local base=c.state.bases[b.id]
    if shipment_active(c,b.id,kind,zone) or c:active_count()+4>c.config.unit_budget then return false end
    local corridor
    if kind=="SUPPLY" then
        if zone~=b.zone then return false,"Supply destination must match its base" end
        local offer,why=c.supply.offer(c,b,source)
        if not offer then return false,why end
        source=offer.source;corridor={path=offer.path,state="OPEN",reason=false}
    elseif kind=="ASSAULT" and not c.supply.path(c,b.side,b.zone,source) then
        return false,"Ground staging sector is isolated from its base"
    end
    local price=kind=="ASSAULT" and 12 or 0
    if base.resources.supply<price then return false end
    local id=c:id("ground-")
    local s={id=id,side=b.side,base=b.id,kind=kind,zone=zone,source=source,
        status="MOVING",outcome=false,corridor=corridor,started=c.state.time,alive={["1"]=true,["2"]=true,["3"]=true,["4"]=true},positions={}}
    local ok,err=c.adapter:spawn_shipment(s)
    if not ok then c:note("Ground dispatch delayed: "..tostring(err)); return false end
    base.resources.supply=base.resources.supply-price
    c.state.shipments[id]=s
    c:note(b.side.." "..(kind=="ASSAULT" and "ground advance" or "supply convoy").." dispatched toward "..c.zone_defs[zone].name..".")
    return true
end
function Director.logistics(c)
    for _,b in ipairs(c.config.bases) do
        if c.state.zones[b.zone].owner==b.side then
            local source=c.supply.offer(c,b)
            local r=c.state.bases[b.id].resources
            if source and (r.fuel<90 or r.ammo<90 or r.supply<90) then Director.dispatch(c,b,"SUPPLY",b.zone,source.source) end
            -- Ground forces can advance only across a connected front. No remote capture.
            for _,z in ipairs(c.config.zones) do
                if c.state.zones[z.id].owner==b.side then
                    for _,adj in ipairs(z.neighbors) do
                        if c.state.zones[adj].owner~=b.side then
                            local resistance=c:defenders(adj,b.side,true)
                            if resistance<=0.5 then
                                if Director.dispatch(c,b,"ASSAULT",adj,z.id) then break end
                            end
                        end
                    end
                end
            end
        end
    end
end
function Director.arrived(c,id)
    local s=c.state.shipments[id]
    if not s or s.status~="MOVING" then return false end
    local n=c.count(s.alive)
    if n==0 then s.status="LOST";return false end
    local near,arrived=c.adapter.ground.arrivals(s)
    if arrived==0 or (s.kind=="ASSAULT" and arrived~=n) then return false end
    if s.kind=="SUPPLY" then
        local b=c.state.bases[s.base]
        if c.state.zones[s.zone].owner~=s.side then
            s.status="LOST";s.outcome="DESTINATION_LOST";c.adapter:retire_shipment(s);c:check_task()
            c:note("Supply convoy reached a captured destination; cargo lost.");return false
        end
        if not c.supply.open(c,s) then c.supply.update(c,s);return false end
        local fuel_available=#c.supply.sources(c,c.base_defs[s.base],"FUEL")>0
        s.delivered=s.delivered or {}
        for k in pairs(near) do
            s.delivered[k]=true;s.alive[k]=false
        end
        for _,r in ipairs({"supply","fuel","ammo"}) do
            if r~="fuel" or fuel_available then b.resources[r]=math.min(100,b.resources[r]+20*arrived/4) end
        end
        if c.count(s.alive)==0 then s.status="DELIVERED";s.outcome="DELIVERED" end
        c:note("Supply delivered at "..c.base_defs[s.base].name..": "..arrived.." now, "..c.count(s.delivered).."/4 total.")
        c.adapter:retire_shipment_units(s,near)
    else
        if c:defenders(s.zone,s.side,false)>0 then return false end
        c.state.zones[s.zone].owner=s.side
        s.status="ARRIVED"
        c:note(c.zone_defs[s.zone].name.." captured by "..s.side.." ground forces.")
        -- Keep the assault group as the occupying garrison until it is destroyed.
        c.adapter:hold_shipment(s)
    end
    if s.kind=="SUPPLY" and s.status=="DELIVERED" then c.adapter:retire_shipment(s) end
    c:check_task()
    local red=0;local blue=0
    for _,z in pairs(c.state.zones) do if z.owner=="red" then red=red+1 else blue=blue+1 end end
    if red==0 then c.state.status="VICTORY"; c:note("Campaign victory: all sectors are held by blue forces.")
    elseif blue==0 then c.state.status="DEFEAT"; c:note("Campaign lost: all sectors are held by red forces.") end
    return true
end
function Director.repair(c)
    for _,d in ipairs(c.config.targets) do
        local t=c.state.targets[d.id]
        if c:target_health(d.id)==0 and t.destroyed_at and c.state.time-t.destroyed_at>=14400
            and c.state.zones[d.zone].owner==d.side and d.kind~="ARMOR" then
            for _,b in ipairs(c.config.bases) do
                local r=c.state.bases[b.id].resources
                if b.side==d.side and c.supply.path(c,b.side,b.zone,d.zone) and r.supply>=25 and r.ammo>=10 then
                    local replacement=c.copy(t)
                    replacement.generation=replacement.generation+1;replacement.positions={}
                    for k in pairs(replacement.alive) do replacement.alive[k]=true end
                    replacement.destroyed_at=false
                    local ok=false
                    if c:active_count()+#d.types<=c.config.unit_budget then ok=c.adapter:spawn_target(d,replacement) end
                    if ok then c.state.targets[d.id]=replacement;r.supply=r.supply-25;r.ammo=r.ammo-10;c:note(d.name.." rebuilt after resupply.") end
                    break
                end
            end
        end
    end
end
function Director.tick(c)
    local s=c.state
    if s.status~="ACTIVE" then return end
    if s.time>=s.next_director then
        s.next_director=s.time+180
        Director.air(c,"red");Director.air(c,"blue")
    end
    if s.time>=s.next_logistics then s.next_logistics=s.time+900;Director.logistics(c) end
    if s.time>=s.next_repair then s.next_repair=s.time+1800;Director.repair(c) end
    for id,ship in pairs(s.shipments) do
        c.supply.update(c,ship)
        local nav=ship.navigation
        if ship.status=="MOVING" and nav and (nav.state=="STALLED" or nav.state=="BLOCKED")
            and (not ship.corridor or ship.corridor.state~="CUT")
            and nav.attempts<c.adapter.ground.RETRIES and s.time>=nav.next_retry and s.time<=nav.deadline
            and s.time>=(c.next_ground_retry or 0) then
            c.next_ground_retry=s.time+10
            nav.attempts=nav.attempts+1;nav.next_retry=s.time+c.adapter.ground.STALL
            local called,ok,why=pcall(function()return c.adapter:reroute_shipment(ship)end)
            if called and ok then
                nav.watch={};nav.state="MOVING";nav.last_error=false
                c.supply.resumed(c,ship)
                c:note("Convoy "..id..": route refreshed from its current position ("..nav.attempts.."/3).")
            else
                nav.state=nav.attempts>=3 and "BLOCKED" or "STALLED"
                nav.last_error=tostring(called and why or ok):sub(1,300)
                c:note("Convoy "..id..": route retry "..nav.attempts.."/3 failed: "..nav.last_error)
            end
        end
        local deadline=nav and nav.deadline or ship.started+10800
        if ship.status=="MOVING" and s.time>deadline and not (ship.kind=="ASSAULT" and nav and nav.state=="WAITING") then
            local delivered=c.count(ship.delivered)
            ship.status=delivered>0 and "DELIVERED" or "LOST"
            ship.outcome="TIMED_OUT"
            c.adapter:retire_shipment(ship)
            c:note("Convoy "..id.." timed out: "..delivered.."/4 delivered; remaining cargo not credited.")
            c:check_task()
        elseif ship.status~="MOVING" and ship.status~="ARRIVED" and s.time>deadline+600
            and not c.catalog.referenced(c,id) then s.shipments[id]=nil end
    end
    c.supply.cleanup(c)
end
return Director
