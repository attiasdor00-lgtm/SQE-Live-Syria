-- Bounded road-plan validation and convoy progress. No DCS calls or spending.
local G={ARRIVAL=1200,STALL=300,RETRIES=3,MAX_PATH=20000,ROAD_WAYPOINTS=16}
local function distance(a,b)return math.sqrt((a.x-b.x)^2+(a.y-b.y)^2)end
local function point(p)
    return type(p)=="table" and type(p.x)=="number" and type(p.y)=="number"
        and p.x==p.x and p.y==p.y and math.abs(p.x)<5000000 and math.abs(p.y)<5000000
end
function G.plan(path,origin,destination)
    if not point(origin) or not point(destination) then return nil,"Invalid route endpoint" end
    if type(path)~="table" or #path<2 or #path>G.MAX_PATH then return nil,"Road path unavailable or outside size limit" end
    local length=0
    for i=1,#path do
        local p=path[i]
        if not point(p) then return nil,"Invalid road path point" end
        if i>1 then length=length+distance(path[i-1],p) end
    end
    local start,finish=distance(origin,path[1]),distance(destination,path[#path])
    if start>2500 or finish>2500 then return nil,"Road endpoint too far from convoy or destination" end
    length=length+start+finish
    if length>300000 or length>math.max(5000,distance(origin,destination)*8+5000) then
        return nil,"Road detour exceeds route limit"
    end
    local points={{x=origin.x,y=origin.y,action="Off Road"}}
    local function add(p,action)
        if distance(points[#points],p)<1 then
            if action=="On Road" then points[#points].action=action end
        else points[#points+1]={x=p.x,y=p.y,action=action} end
    end
    local n=math.min(G.ROAD_WAYPOINTS,#path)
    for j=1,n do
        local p=path[math.floor((j-1)*(#path-1)/(n-1))+1]
        add(p,"On Road")
    end
    add(destination,"Off Road")
    return {points=points,length=length}
end
function G.initialize(ship,now,length)
    ship.navigation=ship.navigation or {state="MOVING",attempts=0,next_retry=now+G.STALL,
        deadline=ship.started+math.max(10800,math.min(21600,math.ceil((length or 0)/5+1800))),
        route_length=length or 0,last_error=false,watch={}}
    return ship.navigation
end
function G.arrivals(ship)
    local near,n,total={},0,0
    for k,alive in pairs(ship.alive) do if alive then
        total=total+1;local p=ship.positions[k]
        if p and ship.destination and distance(p,ship.destination)<G.ARRIVAL then near[k]=true;n=n+1 end
    end end
    return near,n,total
end
function G.observe(ship,now)
    local nav=G.initialize(ship,now);local near,n,total=G.arrivals(ship)
    if ship.corridor and ship.corridor.state~="OPEN" then nav.state="BLOCKED";return nav end
    local stalled,moved=false,false
    for k in pairs(nav.watch) do if not ship.alive[k] or near[k] then nav.watch[k]=nil end end
    for k,alive in pairs(ship.alive) do if alive and not near[k] then
        local p=ship.positions[k];local old=nav.watch[k]
        if p then
            if not old or distance(old,p)>=50 then
                moved=moved or old~=nil;nav.watch[k]={x=p.x,y=p.y,at=now}
            elseif now-old.at>=G.STALL then stalled=true end
        end
    end end
    if total>0 and n==total then nav.state="WAITING"
    elseif stalled then nav.state=nav.attempts>=G.RETRIES and "BLOCKED" or "STALLED"
    elseif nav.last_error and not moved then nav.state="BLOCKED"
    else nav.state="MOVING" end
    if moved then nav.last_error=false end
    return nav
end
return G
