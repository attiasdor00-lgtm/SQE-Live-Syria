-- A contract double, not a DCS emulator. No ballistics, AI or terrain claims.
local M={clock=0,groups={},units={},messages={},marks={},menus={},handlers={},next_id=100,
    callbacks={},bases={},fail_spawn=false}
local function make_group(data,category,country)
    assert(type(data.name)=="string" and #data.units>0,"invalid group")
    assert(not M.groups[data.name] or not M.groups[data.name].alive,"live group name collision: "..data.name)
    M.next_id=M.next_id+1
    local g={id=M.next_id,name=data.name,data=data,category=category,country=country,alive=true,units={}}
    local controller={task={id="Mission",params={route=data.route}}}
    function controller:setTask(task) self.task=task end
    function controller:setCommand(command) self.command=command end
    function g:isExist() return self.alive end
    function g:getID() return self.id end
    function g:getName() return self.name end
    function g:getUnits()
        local out={};for _,u in ipairs(self.units) do if u.alive then out[#out+1]=u end end;return out
    end
    function g:getController() return controller end
    function g:destroy() self.alive=false;for _,u in ipairs(self.units) do u.alive=false end end
    for _,d in ipairs(data.units) do
        assert(not M.units[d.name] or not M.units[d.name].alive,"live unit name collision: "..d.name)
        assert(type(d.type)=="string" and type(d.x)=="number" and type(d.y)=="number","invalid unit")
        local u={name=d.name,group=g,alive=true,life=100,point={x=d.x,y=d.alt or 100,z=d.y},data=d}
        function u:isExist() return self.alive end
        function u:getName() return self.name end
        function u:getGroup() return self.group end
        function u:getLife() return self.life end
        function u:getPoint() return self.point end
        function u:inAir() return self.point.y>110 end
        function u:destroy() self.alive=false end
        M.units[d.name]=u;g.units[#g.units+1]=u
    end
    M.groups[g.name]=g
    return g
end
Unit={getByName=function(n)return M.units[n]end}
Group={getByName=function(n)return M.groups[n]end}
coalition={
    addGroup=function(country,category,data)
        if M.fail_spawn then return nil end
        return make_group(data,category,country)
    end,
    getPlayers=function(side)return M.player and {M.player} or {} end
}
land={getHeight=function()return 100 end,getSurfaceType=function()return 1 end,
    findPathOnRoads=function(kind,x,y,tx,ty)
        assert(kind=="roads")
        M.road_queries=(M.road_queries or 0)+1
        if M.road_error then error('injected road API failure') end
        if M.no_road then return nil end
        return {{x=x,y=y},{x=(x+tx)/2,y=(y+ty)/2},{x=tx,y=ty}}
    end}
coord={LOtoLL=function(p)return 33+p.x/111000,36+p.z/100000 end}
trigger={action={
    outText=function(t,seconds)M.messages[#M.messages+1]=t end,
    markToCoalition=function(id,text,p,side,readonly)M.marks[id]={text=text,point=p}end,
    removeMark=function(id)M.marks[id]=nil end
}}
timer={
    getTime=function()return M.clock end,
    scheduleFunction=function(fn,arg,at)M.callbacks[#M.callbacks+1]={fn=fn,arg=arg,at=at};return #M.callbacks end
}
world={
    event={S_EVENT_DEAD=8,S_EVENT_CRASH=5,S_EVENT_EJECTION=6,S_EVENT_UNIT_LOST=30,
        S_EVENT_TAKEOFF=3,S_EVENT_LAND=4,S_EVENT_MISSION_END=12},
    addEventHandler=function(h)M.handlers[#M.handlers+1]=h end
}
env={error=function(t)M.error=t end,warning=function(t)M.warning=t end}
missionCommands={
    addSubMenuForGroup=function(gid,name,parent)local t={gid=gid,name=name,parent=parent};M.menus[#M.menus+1]=t;return t end,
    addCommandForGroup=function(gid,name,parent,fn)local t={gid=gid,name=name,parent=parent,fn=fn};M.menus[#M.menus+1]=t;return t end,
    removeItemForGroup=function(gid,item)item.removed=true end
}
Airbase={getByName=function(name)
    if not M.bases[name] then
        local b={};function b:autoCapture(v)self.auto=v end;function b:setCoalition(v)self.side=v end
        M.bases[name]=b
    end
    return M.bases[name]
end}
function M.add_player(config)
    local b=config.bases[1]
    local g=make_group({name="player",units={{name=config.player_unit,type="F-16C_50",x=b.x,y=b.y,alt=100}}},0,2)
    M.player=g.units[1]
end
function M.emit(event)
    for _,h in ipairs(M.handlers) do h:onEvent(event) end
end
function M.kill(name)
    local u=M.units[name];assert(u,name);u.life=0;u.alive=false
    M.emit({id=world.event.S_EVENT_DEAD,initiator=u})
    M.emit({id=world.event.S_EVENT_UNIT_LOST,initiator=u})
end
function M.advance(seconds)
    local target=M.clock+seconds
    while M.clock<target do
        M.clock=math.min(target,M.clock+2)
        for _,cb in ipairs(M.callbacks) do
            if cb.at and cb.at<=M.clock then cb.at=cb.fn(cb.arg,M.clock) end
        end
    end
end
function M.land_flight(adapter,f)
    local b=adapter.core.base_defs[f.base]
    local g=M.groups[adapter.air_groups[f.id]]
    for _,u in ipairs(g.units) do if u.alive then
        u.point={x=b.x,y=100,z=b.y}
        M.emit({id=world.event.S_EVENT_LAND,initiator=u,place={getID=function()return b.airport_id end}})
    end end
end
function M.deliver(adapter,s)
    for _,u in ipairs(M.groups[adapter.ship_groups[s.id]].units) do
        if u.alive then u.point={x=s.destination.x,y=100,z=s.destination.y} end
    end
end
function M.memory_storage()
    local f={files={},queue={},reports={},writes=0,status_text=nil,session_count=0}
    function f.now()return 100000+math.floor(M.clock) end
    function f.session()f.session_count=f.session_count+1;return "test-session-"..f.session_count end
    function f.load(id,previous)
        local s=f.files[id..(previous and ".prev" or "")]
        if not s then return nil,"missing" end;return s
    end
    function f.save(id,text)
        if f.fail_save then return false,"injected disk failure" end
        f.files[id..".prev"]=f.files[id];f.files[id]=text;f.writes=f.writes+1;return true
    end
    function f.restore_previous(id,text)f.files[id]=text;return true end
    function f.publish(text)f.status_text=text;return true end
    function f.status()return f.status_text end
    function f.report(kind,text)f.reports[kind]=text;return true end
    function f.read_report(kind)return f.reports[kind] end
    function f.enqueue(id,text)f.queue[id]=text;return true end
    function f.commands()
        local out={};for id,text in pairs(f.queue) do out[#out+1]={id=id,text=text} end;return out
    end
    function f.ack(id)f.queue[id]=nil;return true end
    return f
end
return M
