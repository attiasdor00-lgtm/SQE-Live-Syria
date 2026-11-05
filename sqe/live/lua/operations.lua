-- Read-only campaign presentation. Derived from the same state/rules used to act.
-- No saved state, DCS calls, spending, randomness or automatic assignments.
local O={}
O.roles={"CAP","ESCORT","SEAD","STRIKE","AWACS","TANKER"}
local function sources(c,side,kind)
    local n=0
    for _,t in ipairs(c.config.targets) do
        if t.side==side and t.kind==kind and c:target_health(t.id)>0.25
            and c.state.zones[t.zone].owner==side then n=n+1 end
    end
    return n
end
function O.impact(c,id)
    local t,s=c:target(id)
    if not t then return "" end
    if t.shipment then
        local remaining=c.count(s.alive)
        if s.kind=="SUPPLY" then
            return "Destroy all "..remaining.." remaining supply vehicles to stop their undelivered cargo. "
                ..c.count(s.delivered).."/4 vehicles already delivered; existing stock is retained."
                ..(s.corridor and s.corridor.state~="OPEN" and (" "..s.corridor.reason) or "")
        end
        return "Destroy all "..remaining.." remaining vehicles in this "..(s.status=="ARRIVED" and "occupying garrison" or "assault column")
            ..". An arriving column can become a garrison under the same objective. Friendly capture still requires physical ground arrival."
    elseif t.kind=="ARMOR" then
        return "Clear all "..c.count(c.state.targets[id].alive).." remaining vehicles. Ground capture requires no defending armour/garrison survivors AND an arriving friendly column."
    elseif t.kind=="SAM" then
        if not c:suppressed(id) then
            return "Destroy the search/tracking radars to complete SEAD. Surviving battery units can become a DEAD task. This does not capture the sector."
        end
        return "Radars destroyed. Reduce the remaining battery to 25% strength or less for DEAD. Ground capture is a separate objective."
    elseif t.kind=="DEPOT" or t.kind=="FUEL" then
        local active=sources(c,t.side,t.kind)
        local online=c:target_health(id)>0.25 and c.state.zones[t.zone].owner==t.side
        local others=active-(online and 1 or 0)
        local consequence=t.kind=="DEPOT" and "new supply convoys" or "fuel replenishment"
        if online then
            return "Reduce this site to 25% or less. "..(others==0
                and ("It is the last operating source: this stops "..consequence..".")
                or (others.." other source(s) remain; "..consequence.." still requires a controlled corridor to the base."))
                .." Existing base stock is retained."
        end
        return "This source is offline. "..others.." other operating source(s) remain. Existing base stock is retained."
    end
    return "Completes a campaign objective. Destroying this detachment does not reduce enemy dispatch capacity."
end
function O.support(c,target)
    local offers={}
    for _,role in ipairs(O.roles) do offers[role]=c:support_offer(role,target) end
    return offers
end
function O.sectors(c)
    local out={}
    local bases,affordable=0,0
    for _,b in ipairs(c.config.bases) do
        if b.side=="blue" and c.state.zones[b.zone].owner=="blue" then
            bases=bases+1
            if c.state.bases[b.id].resources.supply>=12 then affordable=affordable+1 end
        end
    end
    for _,z in ipairs(c.config.zones) do
        local s={id=z.id,name=z.name,map_label=z.map_label or z.name,x=z.x,y=z.y,neighbors=c.copy(z.neighbors),base_names={},
            owner=c.state.zones[z.id].owner,defenders=c:defenders(z.id,"blue",false),
            resistance=c:defenders(z.id,"blue",true),frontline=false,
            friendly_columns=0,enemy_columns=0,delayed_columns=0,garrison=0,base_effects={}}
        for _,adj in ipairs(z.neighbors) do
            if c.state.zones[adj].owner~=s.owner then s.frontline=true end
        end
        for _,ship in pairs(c.state.shipments) do
            if ship.zone==z.id and ship.kind=="ASSAULT" and c.count(ship.alive)>0 then
                if ship.status=="MOVING" then
                    local key=ship.side=="blue" and "friendly_columns" or "enemy_columns"
                    s[key]=s[key]+1
                    if ship.side=="blue" and ship.navigation and (ship.navigation.state=="STALLED" or ship.navigation.state=="BLOCKED") then
                        s.delayed_columns=s.delayed_columns+1
                    end
                elseif ship.status=="ARRIVED" and ship.side=="red" then
                    s.garrison=s.garrison+c.count(ship.alive)
                end
            end
        end
        for _,b in ipairs(c.config.bases) do
            if b.zone==z.id then
                s.base_names[#s.base_names+1]=b.name
                s.base_effects[#s.base_effects+1]=(b.side=="red" and "Capture blocks enemy launches at " or "Keep friendly launches operating at ")..b.name
                if b.side=="blue" then
                    local _,why=c.supply.offer(c,b)
                    s.base_effects[#s.base_effects+1]=why
                end
            end
        end
        if s.owner=="blue" then
            s.stage=s.enemy_columns>0 and "DEFEND" or "HELD"
            s.instruction=s.enemy_columns>0 and (s.enemy_columns.." enemy ground column(s) inbound. Protect the sector's defenders.")
                or "Sector held. Protect its forces and supply sites."
        elseif not s.frontline then
            s.stage="BEHIND_FRONT";s.instruction="Capture an adjacent sector before a ground advance. Deep strikes remain available."
        elseif s.friendly_columns>0 then
            s.stage=s.defenders>0 and "COVER_ADVANCE" or "AWAIT_ARRIVAL"
            s.instruction=s.friendly_columns.." friendly column(s) en route. "..(s.defenders>0
                and ("Clear "..s.defenders.." remaining defender(s) before capture.")
                or "Defenders cleared; the column must physically arrive.")
        elseif s.resistance>0.5 then
            s.stage="WEAKEN_DEFENDERS";s.instruction="Reduce defending ground forces to enable an automatic advance. "..s.defenders.." defender(s) remain."
        elseif bases==0 then
            s.stage="NO_BASE";s.instruction="Ground advance blocked: no friendly operating base remains."
        elseif affordable==0 then
            s.stage="NO_SUPPLY";s.instruction="Ground advance blocked: an operating base needs 12 supply. Protect replenishment convoys."
        elseif c:active_count()+4>c.config.unit_budget then
            s.stage="UNIT_LIMIT";s.instruction="Ground advance waits for space within the active unit limit."
        else
            local connected=false
            for _,b in ipairs(c.config.bases) do
                if b.side=="blue" and c.state.bases[b.id].resources.supply>=12 then
                    for _,origin in ipairs(z.neighbors) do
                        if c.supply.path(c,b.side,b.zone,origin) then connected=true end
                    end
                end
            end
            if connected then
                s.stage="AWAIT_ADVANCE"
                s.instruction="Ground advance eligible at the next logistics review ("..math.ceil(math.max(0,c.state.next_logistics-c.state.time)/60).." min). "
                    ..(s.defenders>0 and (s.defenders.." defender(s) must still be cleared for capture.") or "Capture still requires physical arrival.")
            else
                s.stage="SUPPLY_ISOLATED";s.instruction="Ground staging sectors have no controlled corridor to a supplied friendly base. Restore the connection."
            end
        end
        if s.delayed_columns>0 then
            s.instruction=s.instruction.." "..s.delayed_columns.." friendly column(s) delayed; bounded road retries are in progress or exhausted. See campaign log."
        end
        out[#out+1]=s
    end
    return out
end
function O.decorate(c,view)
    local sectors=O.sectors(c);local by_id={}
    for _,s in ipairs(sectors) do by_id[s.id]=s end
    for _,t in ipairs(view.tasks) do
        local sector=by_id[t.zone]
        t.sector_name=sector.name;t.sector_stage=sector.stage;t.sector_instruction=sector.instruction
        t.impact=O.impact(c,t.id);t.support=O.support(c,t.id)
        t.rank=t.priority
        if sector.owner=="red" and sector.frontline then
            t.rank=t.rank+(t.role=="CAS" and 120 or t.role=="SEAD" and 100 or 60)
        end
        if c.state.task and t.id==c.state.task.target then t.rank=t.rank+1000 end
    end
    table.sort(view.tasks,function(a,b)if a.rank==b.rank then return a.id<b.id end return a.rank>b.rank end)
    local suggested=c.state.status=="ACTIVE" and view.tasks[1] or nil
    view.front={sectors=sectors,recommended_task=suggested and suggested.id or false,
        recommended_name=suggested and suggested.name or false,
        recommendation=suggested and (c.state.task and "Continue the current assignment."
            or (by_id[suggested.zone].frontline and "Recommended for the active front; choose another task if preferred."
                or "No taskable front target remains. Strategic targets are still available."))
            or "No taskable target remains. Follow sector objectives and ground movements."}
    view.support=O.support(c,nil)
    for _,b in ipairs(view.bases) do
        local d=c.base_defs[b.id]
        b.operational=c.state.zones[d.zone].owner==d.side
        local depots,active,why=c.supply.sources(c,d,"DEPOT")
        local fuel,_,fuel_reason=c.supply.sources(c,d,"FUEL")
        b.depots=#depots;b.fuel_sites=#fuel;b.active_depots=active;b.supply_reason=why
        b.fuel_reason=fuel_reason
        b.inbound=0;b.delayed=0;b.cut_convoys=0
        for _,ship in pairs(c.state.shipments) do
            if ship.base==d.id and ship.kind=="SUPPLY" and ship.status=="MOVING" and c.count(ship.alive)>0 then
                b.inbound=b.inbound+1
                if ship.navigation and (ship.navigation.state=="STALLED" or ship.navigation.state=="BLOCKED") then b.delayed=b.delayed+1 end
                if ship.corridor and ship.corridor.state~="OPEN" then b.cut_convoys=b.cut_convoys+1 end
            end
        end
    end
    return view
end
return O
