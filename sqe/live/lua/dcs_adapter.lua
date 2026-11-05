-- The only module that creates, tasks or queries DCS units.
local A={}
A.__index=A
local function exists(o) return o and o:isExist() end
local function combo(tasks) return {id="ComboTask",params={tasks=tasks or {}}} end
local function numbered(tasks)
    for i,t in ipairs(tasks) do t.number=i;t.enabled=true;t.auto=false end
    return tasks
end
local function point(x,y,alt,speed,tasks)
    return {x=x,y=y,alt=alt,alt_type="BARO",speed=speed,speed_locked=true,
        ETA=0,ETA_locked=false,type="Turning Point",action="Turning Point",
        task=combo(numbered(tasks or {}))}
end
local function option(name,value)
    return {id="WrappedAction",params={action={id="Option",params={name=name,value=value}}}}
end
function A.new(config,copy)
    return setmetatable({config=config,copy=copy,registry={},ground_groups={},air_groups={},
        ship_groups={},landed={},contacts={},save_status="Not saved yet"},A)
end
function A:attach(core,director,operations,ground) self.core,self.director,self.operations,self.ground=core,director,operations,ground end
function A:cleanup()
    -- Roll back only groups created by this adapter after failed initialization.
    for _,groups in ipairs({self.ground_groups,self.air_groups,self.ship_groups}) do
        for _,name in pairs(groups) do
            pcall(function()local g=Group.getByName(name);if exists(g) then g:destroy() end end)
        end
    end
    self.registry={};self.ground_groups={};self.air_groups={};self.ship_groups={}
end
function A:world_health()
    local expected,observed=0,0
    for name,r in pairs(self.registry) do
        local state=r.kind=="target" and self.core.state.targets[r.id]
            or r.kind=="flight" and self.core.state.flights[r.id] or self.core.state.shipments[r.id]
        if state and state.alive[tostring(r.index)] and state.status~="COMPLETE"
            and state.status~="DELIVERED" and state.status~="LOST" then
            expected=expected+1
            local u=Unit.getByName(name)
            if exists(u) and u:getLife()>0 then observed=observed+1 end
        end
    end
    return expected==observed,tostring(observed).." / "..expected.." registered survivors found in DCS"
end
function A:sync_bases()
    self.base_owners=self.base_owners or {}
    local fields={}
    for _,field in ipairs(self.config.airfields or {}) do fields[#fields+1]=field end
    for _,base in ipairs(self.config.bases) do fields[#fields+1]=base end
    for _,b in ipairs(fields) do
        local owner=self.core.state.zones[b.zone].owner
        if self.base_owners[b.airport]~=owner then
            local airbase=Airbase.getByName(b.airport)
            if airbase then
                airbase:autoCapture(false)
                airbase:setCoalition(owner=="blue" and 2 or 1)
                self.base_owners[b.airport]=owner
            end
        end
    end
end
function A:notify(text,seconds) trigger.action.outText(text,seconds or 15) end
function A:ground_point(x,y,offset)
    local start=offset or 0
    for ring=0,10 do
        for j=0,(ring==0 and 0 or 11) do
            local angle=(j*30+start)*math.pi/180
            local xx,yy=x+ring*150*math.cos(angle),y+ring*150*math.sin(angle)
            local p={x=xx,y=yy}
            local surface=land.getSurfaceType(p)
            local h=land.getHeight(p)
            if surface~=2 and surface~=3 and surface~=5
                and math.abs(land.getHeight({x=xx+15,y=yy})-h)<4
                and math.abs(land.getHeight({x=xx,y=yy+15})-h)<4 then return xx,yy end
        end
    end
    return nil,nil
end
function A:spawn_target(def,state)
    local name="SQEL-G-"..def.id.."-"..state.generation
    local units,records={},{}
    for i,typ in ipairs(def.types) do
        if state.alive[tostring(i)] then
            local saved=(state.positions or {})[tostring(i)]
            local angle=i*2.39996
            local x=(saved and saved.x) or def.x+math.cos(angle)*100*math.sqrt(i)
            local y=(saved and saved.y) or def.y+math.sin(angle)*100*math.sqrt(i)
            x,y=self:ground_point(x,y,i*17)
            if not x then return false,"No safe land position for "..def.name end
            local n=name.."-"..i
            units[#units+1]={name=n,type=typ,x=x,y=y,heading=angle,skill="High",
                playerCanDrive=false}
            records[n]={kind="target",id=def.id,index=i,generation=state.generation}
        end
    end
    if #units==0 then return true end
    local gdata={name=name,visible=false,hidden=false,task="Ground Nothing",
        units=units,x=units[1].x,y=units[1].y,route={points={
            {x=units[1].x,y=units[1].y,type="Turning Point",action="Off Road",speed=0,
             task=combo(numbered({option(0,0),option(9,2)}))}}}}
    local ok,g=pcall(coalition.addGroup,def.side=="blue" and 2 or 0,2,gdata)
    if not ok or not g then return false,tostring(g) end
    self.ground_groups[def.id]=name
    for n,r in pairs(records) do self.registry[n]=r end
    return true
end
function A:rebuild_target(def,replacement)
    local old_name=self.ground_groups[def.id]
    local old=Group.getByName(old_name or "")
    local new_name="SQEL-G-"..def.id.."-"..replacement.generation
    local function rollback()
        local g=Group.getByName(new_name)
        if exists(g) then g:destroy() end
        self.ground_groups[def.id]=old_name
        for name,r in pairs(self.registry) do
            if r.kind=="target" and r.id==def.id and r.generation==replacement.generation then self.registry[name]=nil end
        end
    end
    local called,ok,why=pcall(self.spawn_target,self,def,replacement)
    if not called or not ok then
        local cleaned,err=pcall(rollback)
        if not cleaned then error("Site rebuild rollback failed: "..tostring(err)) end
        return false,tostring(called and why or ok)
    end
    local retired,err=pcall(function()if exists(old) then old:destroy() end end)
    if not retired then
        local cleaned,cleanup_error=pcall(rollback)
        if not cleaned then error("Site rebuild rollback failed: "..tostring(cleanup_error)) end
        return false,"Previous site could not retire: "..tostring(err)
    end
    for name,r in pairs(self.registry) do
        if r.kind=="target" and r.id==def.id and r.generation~=replacement.generation then self.registry[name]=nil end
    end
    return true
end
function A:player()
    local u=Unit.getByName(self.config.player_unit)
    if exists(u) then return u end
    for _,p in ipairs(coalition.getPlayers(2) or {}) do if exists(p) then return p end end
end
function A:destination(f)
    local d=self.core:target(f.target)
    if d then
        local p=self:target_point(d)
        if p then return {x=p.x,y=p.y} end
        -- Area patrols may retain their sector; attack launches require a live anchor.
        return {x=d.x,y=d.y}
    end
    local b=self.core.base_defs[f.base]
    return {x=b.x+20000,y=b.y+20000}
end
function A:target_group(id)
    local d=self.core:target(id)
    if not d then return nil end
    local name=d.shipment and self.ship_groups[id] or self.ground_groups[id]
    return name and Group.getByName(name)
end
function A:route(f,origin)
    local b=self.core.base_defs[f.base]
    local dest=self:destination(f)
    local alt=(f.role=="TANKER" and 6500 or f.role=="AWACS" and 8500 or 6500)
    local tasks={option(0,(f.role=="STRIKE" or f.role=="SEAD") and 3 or 0),option(1,2),option(6,true)}
    local tgt=self:target_group(f.target)
    if f.role=="AWACS" or f.role=="TANKER" then
        -- Support stays behind the friendly front rather than over the selected target.
        dest={x=b.x+8000,y=b.y-22000}
        tasks[#tasks+1]={id=f.role=="AWACS" and "AWACS" or "Tanker",params={}}
    elseif f.role=="CAP" then
        dest={x=(b.x+dest.x)*0.5,y=(b.y+dest.y)*0.5}
        tasks[#tasks+1]={id="EngageTargetsInZone",params={point=dest,zoneRadius=45000,
            targetTypes={"Air"},priority=0}}
    elseif f.role=="ESCORT" then
        local p=self:player()
        if p then tasks[#tasks+1]={id="Escort",params={groupId=p:getGroup():getID(),
            pos={x=-1000,y=500,z=1000},engagementDistMax=30000,targetTypes={"Planes"},
            lastWptIndexFlag=false,lastWptIndexFlagChangedManually=false}} end
    end
    local a=point(origin.x,origin.y,origin.alt or alt,220,tasks)
    local dx,dy=dest.x-b.x,dest.y-b.y
    local distance=math.max(1,math.sqrt(dx*dx+dy*dy))
    local standoff=f.role=="SEAD" and 32000 or 12000
    local attack={}
    if tgt and exists(tgt) and (f.role=="STRIKE" or f.role=="SEAD") then
        -- Transit ROE is return-fire. At the attack point allow assigned targets;
        -- keeping transit ROE here would silently prevent the strike.
        attack[#attack+1]=option(0,2)
        attack[#attack+1]={id="AttackGroup",params={groupId=tgt:getID(),
            weaponType=f.role=="SEAD" and self.config.arm_weapon_type or self.config.auto_weapon_type,
            expend="Auto",attackQty=1,attackQtyLimit=false,groupAttack=true,
            altitudeEnabled=false,altitude=0,directionEnabled=false,direction=0}}
    end
    local ip=point(dest.x-dx/distance*math.min(standoff,distance*0.5),
        dest.y-dy/distance*math.min(standoff,distance*0.5),alt,230,attack)
    local station={}
    if f.role=="CAP" or f.role=="ESCORT" or f.role=="TANKER" or f.role=="AWACS" then
        station[1]={id="ControlledTask",params={task={id="Orbit",params={
            pattern="Circle",point=dest,speed=f.role=="TANKER" and 155 or 190,altitude=alt}},
            stopCondition={time=timer.getTime()+math.max(60,f.expires-self.core.state.time)}}}
        ip=point(dest.x,dest.y,alt,200,station)
    end
    local ret=point(b.x-10000,b.y,4500,210,{option(0,3)})
    local landpt={x=b.x,y=b.y,alt=0,alt_type="BARO",speed=120,speed_locked=true,
        ETA=0,ETA_locked=false,type="Land",action="Landing",airdromeId=b.airport_id,task=combo({})}
    return {points={a,ip,ret,landpt}}
end
function A:spawn_flight(f)
    local d=self.core:target(f.target)
    if (f.role=="STRIKE" or f.role=="SEAD" or (d and d.shipment)) and not self:target_point(d) then
        return false,"Target position unavailable; no aircraft dispatched"
    end
    local spec=self.config.flight_types[f.aircraft]
    if not spec then return false,"Missing aircraft template "..f.aircraft end
    local b=self.core.base_defs[f.base];local name="SQEL-A-"..f.id
    local seq=self.core.state.next_id
    local origin={x=b.x-8000-(seq%4)*2500,y=b.y+(seq%5)*2200,alt=6500+(seq%4)*400}
    origin.alt=math.max(origin.alt,land.getHeight({x=origin.x,y=origin.y})+1500)
    local units={}
    for i=1,f.count do
        local u=self.copy(spec.unit)
        u.name=name.."-"..i;u.unitId=nil;u.skill="High";u.type=spec.type
        u.x,u.y=origin.x-(i-1)*300,origin.y+(i-1)*300;u.alt=origin.alt;u.alt_type="BARO";u.speed=220
        u.heading=0;u.psi=0;u.parking=nil;u.parking_id=nil
        u.payload=self.copy(spec.payloads[f.role] or spec.payloads.STRIKE or spec.unit.payload)
        u.datalinks=nil
        if u.callsign and type(u.callsign)=="table" then u.callsign[2]=(seq%9)+1;u.callsign[3]=i end
        units[i]=u
    end
    local freq=f.role=="AWACS" and 251 or f.role=="TANKER" and 252 or 305
    local gdata={name=name,task=f.role=="SEAD" and "SEAD" or f.role=="STRIKE" and "Ground Attack"
        or f.role=="AWACS" and "AWACS" or f.role=="TANKER" and "Refueling" or "CAP",
        units=units,x=origin.x,y=origin.y,communication=true,frequency=freq,modulation=0,
        uncontrolled=false,lateActivation=false,route=self:route(f,origin)}
    local ok,g=pcall(coalition.addGroup,f.side=="blue" and 2 or 0,0,gdata)
    if not ok or not g then return false,tostring(g) end
    self.air_groups[f.id]=name
    for i,u in ipairs(units) do self.registry[u.name]={kind="flight",id=f.id,index=i} end
    return true
end
function A:control_flight(f,action)
    local d=self.core:target(f.target)
    if action=="push" and (f.role=="STRIKE" or f.role=="SEAD" or (d and d.shipment))
        and not self:target_point(d) then return false end
    local g=Group.getByName(self.air_groups[f.id] or "")
    if not exists(g) then return false end
    local units=g:getUnits();local u=units and units[1]
    if not exists(u) then return false end
    local p=u:getPoint();local ctl=g:getController()
    if action=="hold" then
        ctl:setTask({id="Orbit",params={pattern="Circle",point={x=p.x,y=p.z},speed=190,altitude=p.y}})
    else
        local route=self:route(f,{x=p.x,y=p.z,alt=p.y})
        if action=="rtb" then
            table.remove(route.points,2)
            route.points[1].task=combo(numbered({option(0,3),option(1,2)}))
        end
        ctl:setTask({id="Mission",params={route=route}})
    end
    return true
end
function A:retire_flight(f)
    self.landed[f.id]=nil
    local g=Group.getByName(self.air_groups[f.id] or "")
    if exists(g) then g:destroy() end
    for name,r in pairs(self.registry) do
        if r.kind=="flight" and r.id==f.id then
            self.contacts[name]=nil;self.registry[name]=nil
        end
    end
end
function A:ground_route(origin,destination)
    if type(land.findPathOnRoads)~="function" then return nil,"Road path API unavailable" end
    local ok,path=pcall(land.findPathOnRoads,"roads",origin.x,origin.y,destination.x,destination.y)
    if not ok then return nil,"Road path query failed" end
    local plan,why=self.ground.plan(path,origin,destination)
    if not plan then return nil,why end
    local points={}
    for i,p in ipairs(plan.points) do
        points[i]={x=p.x,y=p.y,speed=11,type="Turning Point",action=p.action,
            task=combo(numbered(i==1 and {option(0,0),option(9,2)} or {}))}
    end
    return {points=points},plan.length
end
function A:spawn_shipment(s,restoring)
    local b=self.core.base_defs[s.base]
    local from=s.kind=="SUPPLY" and self.core.target_defs[s.source] or self.core.zone_defs[s.source]
    local to=s.kind=="SUPPLY" and b or self.core.zone_defs[s.zone]
    if not from or not to then return false,"Invalid ground route" end
    if s.kind=="SUPPLY" and not restoring and not next(s.positions or {}) then
        from=self:target_point(from)
        if not from then return false,"Supply source position unavailable" end
    end
    local name="SQEL-C-"..s.id;local units={}
    local types=s.side=="blue" and (s.kind=="ASSAULT" and {"M-1 Abrams","M-2 Bradley","M-2 Bradley","M 818"} or {"M 818","M 818","M978 HEMTT Tanker","M 818"})
        or (s.kind=="ASSAULT" and {"T-72B","BMP-2","BMP-2","Ural-375"} or {"Ural-375","Ural-375","ATZ-10","Ural-375"})
    for i,typ in ipairs(types) do
        if s.alive[tostring(i)] then
            local saved=(s.positions or {})[tostring(i)]
            local x,y=self:ground_point(saved and saved.x or from.x+i*50,saved and saved.y or from.y)
            if not x then return false,"No safe convoy origin" end
            units[#units+1]={name=name.."-"..i,type=typ,x=x,y=y,heading=0,skill="High",playerCanDrive=false}
        end
    end
    if #units==0 then return true end
    local tx,ty=self:ground_point(s.destination and s.destination.x or to.x,s.destination and s.destination.y or to.y)
    if not tx then return false,"No safe convoy destination" end
    local corridor=self.core.supply.prepare(self.core,s)
    local held=corridor and corridor.state~="OPEN"
    local route,length
    if s.status=="MOVING" and not held then
        route,length=self:ground_route(units[1],{x=tx,y=ty})
        if not route and not restoring and not next(s.positions or {}) then return false,length end
        local nav=self.ground.initialize(s,self.core.state.time,route and length or 0)
        if route then nav.route_length=length
        else nav.state="BLOCKED";nav.last_error=length end
    elseif s.status=="MOVING" then
        self.ground.initialize(s,self.core.state.time,0).state="BLOCKED"
    end
    -- Restored forces remain physically present even when their road query fails.
    -- Occupying garrisons need no route at all.
    route=route or {points={{x=units[1].x,y=units[1].y,speed=0,type="Turning Point",action="Off Road",task=combo({})}}}
    local data={name=name,task="Ground Nothing",units=units,x=units[1].x,y=units[1].y,
        route=route}
    local ok,g=pcall(coalition.addGroup,s.side=="blue" and 2 or 0,2,data)
    if not ok or not g then return false,tostring(g) end
    s.destination={x=tx,y=ty}
    self.ship_groups[s.id]=name
    for _,u in ipairs(units) do
        local key=u.name:match("(%d+)$")
        self.registry[u.name]={kind="shipment",id=s.id,index=tonumber(key)}
        local observed=Unit.getByName(u.name)
        if exists(observed) then
            local p=observed:getPoint();s.positions[key]={x=p.x,y=p.z}
        end
    end
    return true
end
function A:reroute_shipment(s)
    if s.kind=="SUPPLY" then
        local corridor=self.core.supply.prepare(self.core,s)
        if not corridor or corridor.state=="CUT" then return false,"Supply corridor is cut" end
    end
    local g=Group.getByName(self.ship_groups[s.id] or "")
    if not exists(g) then return false,"Convoy group unavailable" end
    local units=g:getUnits();local lead=units and units[1]
    if not exists(lead) then return false,"Convoy has no surviving lead vehicle" end
    local p=lead:getPoint();local route,length=self:ground_route({x=p.x,y=p.z},s.destination)
    if not route then return false,length end
    g:getController():setTask({id="Mission",params={route=route}})
    s.navigation.route_length=length
    return true
end
function A:retire_shipment_units(s,delivered)
    local name=self.ship_groups[s.id]
    if not name then return end
    for k in pairs(delivered) do
        local n=name.."-"..k;self.registry[n]=nil
        local u=Unit.getByName(n);if exists(u) then u:destroy() end
    end
end
function A:hold_shipment(s)
    local g=Group.getByName(self.ship_groups[s.id] or "")
    if exists(g) then g:getController():setTask({id="Hold",params={}});return true end
    return false
end
function A:retire_shipment(s)
    local g=Group.getByName(self.ship_groups[s.id] or "")
    if exists(g) then g:destroy() end
end
function A:lost(name)
    self.contacts[name]=nil
    local r=self.registry[name]
    if not r then return false end
    if r.kind=="target" then
        if self.core.state.targets[r.id].generation~=r.generation then return false end
        return self.core:lose_target(r.id,r.index)
    elseif r.kind=="flight" then return self.core:lose_flight(r.id,r.index)
    else
        local s=self.core.state.shipments[r.id]
        if s and (s.status=="MOVING" or s.status=="ARRIVED") and s.alive[tostring(r.index)] then
            s.alive[tostring(r.index)]=false
            self.core:note("Convoy "..s.id..": vehicle lost.")
            if self.core.count(s.alive)==0 then
                s.status=self.core.count(s.delivered)>0 and "DELIVERED" or "LOST"
                s.outcome="DESTROYED"
            end
            self.core:check_task()
            return true
        end
    end
    return false
end
function A:observe()
    for name,r in pairs(self.registry) do
        local u=Unit.getByName(name)
        local f=r.kind=="flight" and self.core.state.flights[r.id]
        if r.kind=="flight" and (not f or f.status=="COMPLETE" or not f.alive[tostring(r.index)]) then
            -- An ejection/loss notification can precede physical disappearance.
            -- Retire recorded losses on observation, outside the native event
            -- callback, without touching a surviving wingman or crediting stock.
            if exists(u) then u:destroy() end
            self.contacts[name]=nil;self.registry[name]=nil
        elseif not exists(u) or u:getLife()<=0 then
            self:lost(name)
            self.registry[name]=nil
        else
            local p=u:getPoint()
            if r.kind=="target" then
                local t=self.core.state.targets[r.id]
                if t.generation==r.generation then t.positions[tostring(r.index)]={x=p.x,y=p.z} end
            elseif r.kind=="shipment" then
                local s=self.core.state.shipments[r.id]
                if s then s.positions[tostring(r.index)]={x=p.x,y=p.z} end
            end
        end
    end
    for id,s in pairs(self.core.state.shipments) do
        if s.status=="MOVING" and s.destination then
            self.core.supply.update(self.core,s)
            local _,near,total=self.ground.arrivals(s)
            if near>0 and (s.kind=="SUPPLY" or near==total) then self.director.arrived(self.core,id) end
            if s.status=="MOVING" then
                local previous=s.navigation and s.navigation.state
                local nav=self.ground.observe(s,self.core.state.time)
                if nav.state=="BLOCKED" and previous~="BLOCKED" and nav.attempts>=3 then
                    self.core:note("Convoy "..id..": still delayed after three route retries; waiting for physical movement.")
                end
            end
        end
    end
    self:observe_contacts()
    for id in pairs(self.landed) do self:recover_ready(id) end
    for id,name in pairs(self.air_groups) do
        local f=self.core.state.flights[id]
        local g=Group.getByName(name)
        if not f then
            if exists(g) then g:destroy() end
            self.air_groups[id]=nil
        elseif f.status=="COMPLETE" and exists(g) then self:retire_flight(f) end
    end
    for id,name in pairs(self.ship_groups) do if not self.core.state.shipments[id] then self.ship_groups[id]=nil end end
    self:refresh_marks()
end
function A:target_point(d)
    if not d then return nil end
    local _,state=self.core:target(d.id)
    local group=d.shipment and self.ship_groups[d.id] or self.ground_groups[d.id]
    if not self.core.catalog.active(self.core,d,state) or not group then return nil end
    local function observed(i,label)
        if not state.alive[tostring(i)] then return nil end
        local u=Unit.getByName(group.."-"..i)
        if not exists(u) or u:getLife()<=0 then return nil end
        local p=u:getPoint()
        return {x=p.x,y=p.z,alt=land.getHeight({x=p.x,y=p.z}),unit=u:getName(),reference=label}
    end
    -- A SEAD coordinate points to a surviving radar, then to a surviving vehicle
    -- for DEAD. Never use the planned centre or the position of a destroyed unit.
    for _,i in ipairs(d.radars or {}) do local p=observed(i,"Live radar");if p then return p end end
    local label=d.shipment and (state.status=="ARRIVED" and "Live garrison vehicle" or "Live convoy vehicle") or "Live group vehicle"
    for i=1,(d.size or #d.types) do local p=observed(i,label);if p then return p end end
end
function A:coordinates(d,observed)
    local p=observed or self:target_point(d)
    if not p then return nil,nil end
    local lat,lon=coord.LOtoLL({x=p.x,y=p.alt,z=p.y})
    local function dm(v,islat)
        local h=islat and (v>=0 and "N" or "S") or (v>=0 and "E" or "W")
        v=math.abs(v);return string.format("%s %02d %06.3f",h,math.floor(v),(v-math.floor(v))*60)
    end
    return dm(lat,true).."  "..dm(lon,false),math.floor(p.alt*3.28084),p
end
function A:update_mark(d,p,force)
    local id=self.markers and self.markers[d.id]
    if not id then return end
    self.marker_positions=self.marker_positions or {}
    local previous=self.marker_positions[d.id]
    if not force and p and previous and previous.unit==p.unit and previous.reference==p.reference
        and self.core.distance(previous,p)<10 then return end
    if not p and not previous then return end
    trigger.action.removeMark(id)
    -- A failed replacement leaves no mark, even when its position is unchanged.
    self.marker_positions[d.id]=nil
    if p then trigger.action.markToCoalition(id,d.name.." / "..p.reference,{x=p.x,y=p.alt,z=p.y},2,true) end
    self.marker_positions[d.id]=p
end
function A:refresh_marks()
    for id in pairs(self.markers or {}) do
        local ok,err=pcall(function()
            local d,state=self.core:target(id);local p=self:target_point(d)
            self:update_mark(d or {id=id},p)
            if not d or not self.core.catalog.active(self.core,d,state) then
                self.markers[id]=nil
                if self.marker_positions then self.marker_positions[id]=nil end
            end
        end)
        if not ok then env.warning("SQE Live marker update failed: "..tostring(err)) end
    end
end
function A:brief(d,mark)
    local coordinates,elevation,p=self:coordinates(d)
    if not p then return "Target position unavailable; wait for a fresh observation.",false end
    local text=d.name.."\n"..coordinates.."\nElevation: "..elevation.." ft"
        .."\nReference: "..p.reference.."; other group vehicles may be spread out."
        .."\n"..(d.threat or "Enemy air and local air defence possible")
        .."\nAWACS 251.000 AM / Tanker 252.000 AM / Flight 305.000 AM"
    if self.operations then text=text.."\n\nCAMPAIGN EFFECT\n"..self.operations.impact(self.core,d.id) end
    if mark then
        self.markers=self.markers or {}
        if not self.markers[d.id] then
            self.mark_id=(self.mark_id or 870000)+1;self.markers[d.id]=self.mark_id
        end
        local ok,err=pcall(function()self:update_mark(d,p,true)end)
        if not ok then return "Map marker could not be updated: "..tostring(err),false end
    end
    self:notify(text);return text,true
end
-- Touchdown is only a contact notification. The fallback waits for a sustained,
-- slow ground roll; these thresholds are conservative game policy, not DCS rules.
local function finite(n) return type(n)=="number" and n==n and math.abs(n)<math.huge end
function A:at_home(r,u,place,require_runway)
    local f=self.core.state.flights[r.id]
    if not f or f.status=="COMPLETE" or not f.alive[tostring(r.index)] then return false end
    local b=self.core.base_defs[f.base]
    local p=u:getPoint()
    if not b or self.core.state.zones[b.zone].owner~=f.side
        or self.core.distance({x=p.x,y=p.z},b)>6000 then return false end
    if place and place.getID then return place:getID()==b.airport_id end
    if require_runway then
        return land.SurfaceType and land.SurfaceType.RUNWAY and land.getSurfaceType
            and land.getSurfaceType({x=p.x,y=p.z})==land.SurfaceType.RUNWAY
    end
    return true
end
function A:record_landing(name)
    self.contacts[name]=nil
    if name==self.config.player_unit and self.core.state.pilot.airborne then
        self.core.state.pilot.airborne=false
        self.core.state.pilot.landings=self.core.state.pilot.landings+1
        self.core:note("Player landed. Rearm and select another task in this session.")
    end
    local r=self.registry[name]
    if r and r.kind=="flight" then
        self.landed[r.id]=self.landed[r.id] or {}
        self.landed[r.id][tostring(r.index)]=true
        self:recover_ready(r.id)
    end
end
function A:recover_ready(id)
    local f=self.core.state.flights[id]
    if not f or f.status=="COMPLETE" then self.landed[id]=nil;return end
    local landed=self.landed[id]
    if not landed or self.core.count(f.alive)==0 then return end
    for k,alive in pairs(f.alive) do if alive then
        if not landed[k] then return end
        local u=Unit.getByName((self.air_groups[id] or "").."-"..k)
        local r=u and self.registry[u:getName()]
        if not exists(u) or u:getLife()<=0 or not u.inAir or u:inAir()
            or not r or not self:at_home(r,u) then
            landed[k]=nil;return
        end
    end end
    self.core:recover_flight(id);self:retire_flight(f)
end
function A:observe_contacts()
    for name,contact in pairs(self.contacts) do
        local u=Unit.getByName(name)
        local r=self.registry[name]
        if not exists(u) or u:getLife()<=0 or not u.inAir or u:inAir()
            or (r and r.kind=="flight" and not self:at_home(r,u)) then
            self.contacts[name]=nil
        else
            local v=u.getVelocity and u:getVelocity()
            if v and finite(v.x) and finite(v.y) and finite(v.z)
                and v.x*v.x+v.z*v.z<=25 and math.abs(v.y)<=2 then
                contact.since=contact.since or timer.getTime()
                if timer.getTime()-contact.since>=15 then self:record_landing(name) end
            else contact.since=nil end
        end
    end
end
function A:on_event(e)
    if not e.initiator or not e.initiator.getName then return end
    local ok,name=pcall(function()return e.initiator:getName()end);if not ok then return end
    local events=world.event
    if e.id==events.S_EVENT_DEAD or e.id==events.S_EVENT_CRASH or e.id==events.S_EVENT_EJECTION
        or (events.S_EVENT_UNIT_LOST and e.id==events.S_EVENT_UNIT_LOST) then
        self:lost(name)
        if name==self.config.player_unit and not self.player_lost then
            self.player_lost=true;self.core.state.pilot.losses=self.core.state.pilot.losses+1
            self.core.state.pilot.airborne=false;self.core:note("Player aircraft lost. Campaign progress is retained.")
        end
    elseif e.id==events.S_EVENT_TAKEOFF
        or (events.S_EVENT_RUNWAY_TAKEOFF and e.id==events.S_EVENT_RUNWAY_TAKEOFF) then
        self.contacts[name]=nil
        local r=self.registry[name]
        if r and r.kind=="flight" and self.landed[r.id] then self.landed[r.id][tostring(r.index)]=nil end
        if name==self.config.player_unit and not self.core.state.pilot.airborne then
            self.player_lost=false;self.core.state.pilot.airborne=true
            self.core.state.pilot.sorties=self.core.state.pilot.sorties+1;self.core:note("Player sortie airborne.")
        end
    elseif e.id==events.S_EVENT_LAND
        or (events.S_EVENT_RUNWAY_TOUCH and e.id==events.S_EVENT_RUNWAY_TOUCH) then
        local touch=events.S_EVENT_RUNWAY_TOUCH and e.id==events.S_EVENT_RUNWAY_TOUCH
        local r=self.registry[name]
        if r and r.kind=="flight" then
            if not self:at_home(r,e.initiator,e.place,touch) then return end
        elseif name~=self.config.player_unit then return end
        if touch then
            -- Duplicate notifications must not restart the settling interval.
            self.contacts[name]=self.contacts[name] or {}
        elseif e.initiator.inAir and not e.initiator:inAir() then
            self:record_landing(name)
        end
    end
end
return A
