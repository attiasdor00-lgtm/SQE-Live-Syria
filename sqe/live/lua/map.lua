-- Pure sector schematic and local browsing state. No DCS or campaign mutations.
local M={MAX_SECTORS=12,MAX_EDGES=24,PAGE_SIZE=4}
local function finite(v)return type(v)=="number" and v==v and math.abs(v)<5000000 end
function M.sector(view,id)
    for _,s in ipairs(view.front and view.front.sectors or {}) do if s.id==id then return s end end
end
function M.tasks(view,zone)
    local out={}
    for _,t in ipairs(view.tasks or {}) do if not zone or t.zone==zone then out[#out+1]=t end end
    return out
end
function M.task(view,id)
    if not id then return nil end
    for _,t in ipairs(view.tasks or {}) do if t.id==id then return t end end
end
function M.select_sector(view,id)
    if not M.sector(view,id) then return nil,"Sector is no longer available" end
    local tasks=M.tasks(view,id)
    return {zone=id,task=tasks[1] and tasks[1].id or false}
end
function M.select_task(view,current,id)
    local t=M.task(view,id)
    if not t or (current.zone and t.zone~=current.zone) then return nil,"Target is no longer in this sector" end
    return {zone=current.zone,task=id}
end
function M.reconcile(view,current)
    local zone=current.zone and M.sector(view,current.zone) and current.zone or false
    local t=M.task(view,current.task)
    -- Never substitute an unrelated target after a kill, removal or sector change.
    if not t or (current.zone and not zone) or (zone and t.zone~=zone) then t=nil end
    return {zone=zone,task=t and t.id or false}
end
function M.step(view,current,delta)
    local tasks=M.tasks(view,current.zone)
    if #tasks==0 then return {zone=current.zone,task=false} end
    local index=delta>0 and 0 or 1
    for i,t in ipairs(tasks) do if t.id==current.task then index=i;break end end
    index=((index-1+delta)%#tasks)+1
    return {zone=current.zone,task=tasks[index].id}
end
function M.page(view,current)
    local tasks=M.tasks(view,current.zone);local index=1
    for i,t in ipairs(tasks) do if t.id==current.task then index=i;break end end
    local first=math.floor((index-1)/M.PAGE_SIZE)*M.PAGE_SIZE+1
    local out={};for i=first,math.min(first+M.PAGE_SIZE-1,#tasks) do out[#out+1]=tasks[i] end
    return out,first,#tasks
end
function M.layout(view,width,height)
    local sectors=view.front and view.front.sectors
    if type(sectors)~="table" or #sectors<1 or #sectors>M.MAX_SECTORS then
        return nil,"Map requires 1-"..M.MAX_SECTORS.." sectors; use Front plan"
    end
    if not finite(width) or not finite(height) or width<340 or height<280 then return nil,"Map area too small" end
    local ordered,by_id={},{}
    local east_min,east_max
    for _,s in ipairs(sectors) do
        if type(s)~="table" or type(s.id)~="string" or by_id[s.id] or type(s.name)~="string"
            or not finite(s.x) or not finite(s.y) or type(s.neighbors)~="table"
            or (s.owner~="blue" and s.owner~="red") then return nil,"Invalid sector map data" end
        by_id[s.id]=s;ordered[#ordered+1]=s
        east_min=math.min(east_min or s.y,s.y);east_max=math.max(east_max or s.y,s.y)
    end
    table.sort(ordered,function(a,b)if a.x==b.x then return a.id<b.id end return a.x>b.x end)
    local nodes,positions={},{}
    local step=(height-16)/#ordered
    for i,s in ipairs(ordered) do
        local east=east_max>east_min and (s.y-east_min)/(east_max-east_min) or 0.5
        local n={id=s.id,name=s.name,caption=s.map_label or s.name,owner=s.owner,
            frontline=s.frontline==true,bases=s.base_names or {},
            x=math.floor(44+east*(width-248)),y=math.floor(8+(i-1)*step),w=160,h=math.min(34,math.floor(step-4))}
        nodes[#nodes+1]=n;positions[s.id]=n
    end
    local edges,seen={},{}
    for _,s in ipairs(ordered) do
        for _,id in ipairs(s.neighbors) do
            if not by_id[id] or id==s.id then return nil,"Invalid sector connection" end
            local key=s.id<id and s.id..":"..id or id..":"..s.id
            if not seen[key] then
                if #edges>=M.MAX_EDGES then return nil,"Too many sector connections; use Front plan" end
                seen[key]=true
                local a,b=positions[s.id],positions[id]
                local left=(a.x+b.x+a.w)<width
                -- Separate lanes keep non-adjacent connections from merging into a bus.
                local lane=left and (6+2*#edges) or (width-8-2*#edges)
                local ax=left and a.x or a.x+a.w;local bx=left and b.x or b.x+b.w
                local ay=a.y+math.floor(a.h/2);local by=b.y+math.floor(b.h/2)
                edges[#edges+1]={from=s.id,to=id,front=s.owner~=by_id[id].owner,segments={
                    {x=math.min(ax,lane),y=ay,w=math.max(2,math.abs(ax-lane)),h=2},
                    {x=lane,y=math.min(ay,by),w=2,h=math.max(2,math.abs(ay-by))},
                    {x=math.min(bx,lane),y=by,w=math.max(2,math.abs(bx-lane)),h=2}}}
            end
        end
    end
    return {nodes=nodes,edges=edges,width=width,height=height}
end
function M.detail(view,current,V)
    if M.task(view,current.task) then return V.task(view,current.task) end
    local s=M.sector(view,current.zone)
    if not s then return "Select a sector, then a target.\n\nClicking the map never assigns a task or spends resources." end
    local lines={s.name,string.upper(s.owner).." / "..s.stage:gsub("_"," "),"",s.instruction,"",
        "No player target selected in this sector."}
    if #M.tasks(view,s.id)==0 then lines[#lines+1]="No current task cards in this sector." end
    if #(s.base_names or {})>0 then lines[#lines+1]="Bases: "..table.concat(s.base_names,", ") end
    if #(s.airfield_names or {})>0 then lines[#lines+1]="Airfields: "..table.concat(s.airfield_names,", ") end
    lines[#lines+1]="Enemy ground defenders: "..s.defenders
    lines[#lines+1]="Friendly / enemy columns: "..s.friendly_columns.." / "..s.enemy_columns
    for _,effect in ipairs(s.base_effects) do lines[#lines+1]=effect end
    return table.concat(lines,"\n")
end
return M
