-- Presentation only: used by the native DCS operations window.
local V={}
function V.time(seconds)
    local m=math.floor((seconds or 0)/60)
    return string.format("%02d:%02d",math.floor(m/60),m%60)
end
function V.selected(s,id)
    if id==false then return nil end
    for _,t in ipairs(s.tasks or {}) do if t.id==id then return t end end
    if id==nil then return (s.tasks or {})[1] end
end
function V.front(s)
    local front=s.front
    if not front then return "Front plan unavailable. Update the mission and Operations hook together." end
    local lines={"FRONT PLAN / "..(s.status or "?"),""}
    if front.recommended_name then
        lines[#lines+1]=(s.task and "ASSIGNED: " or "SUGGESTED: ")..front.recommended_name
    end
    lines[#lines+1]=front.recommendation
    for _,z in ipairs(front.sectors) do
        lines[#lines+1]="";lines[#lines+1]=string.upper(z.owner).." / "..z.name
        lines[#lines+1]=z.stage:gsub("_"," ")
        if #(z.airfield_names or {})>0 then lines[#lines+1]="Airfields: "..table.concat(z.airfield_names,", ") end
        if z.frontline or z.friendly_columns>0 or z.enemy_columns>0 or #(z.base_names or {})>0 then
            lines[#lines+1]=z.instruction
            if z.garrison>0 then lines[#lines+1]=z.garrison.." occupying garrison vehicle(s) included in the capture requirement." end
            for _,effect in ipairs(z.base_effects) do lines[#lines+1]=effect end
        end
    end
    return table.concat(lines,"\n")
end
function V.offers(s,id)
    if id==false then return s.support or {} end
    local t=V.selected(s,id)
    return t and t.support or s.support or {}
end
function V.support(s,id)
    local lines={"SUPPORT AVAILABILITY",s.task and "Requests support your current assignment."
        or id and "Requests support the selected target." or "Accept a task for SEAD / strike requests."}
    local offers=V.offers(s,id)
    for _,role in ipairs({"CAP","ESCORT","SEAD","STRIKE","AWACS","TANKER"}) do
        local o=offers[role]
        lines[#lines+1]=""
        if o then
            lines[#lines+1]=role.." / "..(o.available and "READY" or "UNAVAILABLE")
            lines[#lines+1]=o.reason
            if o.available then lines[#lines+1]="Cost: "..o.cost.fuel.." fuel / "..o.cost.ammo.." ammo" end
        else lines[#lines+1]=role.." / availability not supplied by this mission" end
    end
    lines[#lines+1]="";lines[#lines+1]="Availability is checked again when you send the request."
    return table.concat(lines,"\n")
end
function V.overview(s)
    local lines={s.title or "SQE LIVE", "",
        "CAMPAIGN "..(s.status or "?").."     "..V.time(s.time),
        "Completed objectives: "..(s.completed or 0),
        "Sorties: "..((s.pilot or {}).sorties or 0).."   Landings: "..((s.pilot or {}).landings or 0),
        "Player losses: "..((s.pilot or {}).losses or 0),
        "Active units: "..(s.unit_count or 0).." / "..(s.unit_budget or 0), "",
        "BASES AND RESOURCES"}
    for _,b in ipairs(s.bases or {}) do
        lines[#lines+1]="";lines[#lines+1]=string.upper(b.name)
        if b.operational==false then lines[#lines+1]="BASE CAPTURED: launches unavailable" end
        local r=b.resources
        lines[#lines+1]=string.format("Fuel %.0f  Ammo %.0f  Supply %.0f",r.fuel,r.ammo,r.supply)
        local types={};for k in pairs(b.ready) do types[#types+1]=k end;table.sort(types)
        for _,k in ipairs(types) do lines[#lines+1]=k..": "..b.ready[k].." ready" end
        if b.automation_reserve then
            local r=b.automation_reserve
            lines[#lines+1]="Automatic dispatch reserve: "..r.fuel.." fuel / "..r.ammo.." ammo / "..r.supply.." supply. Requested support may use reserved fuel/ammo."
            if not b.ground_funded then lines[#lines+1]="Ground advance waits for "..b.ground_required.." supply (12 cost + "..r.supply.." recovery reserve)." end
            if r.supply==0 then lines[#lines+1]="Recovery reserve released: no connected depot or affordable depot repair. Last advances use existing stock." end
            for _,reason in ipairs(b.site_recovery or {}) do lines[#lines+1]="Recovery: "..reason end
        end
        if b.depots then
            lines[#lines+1]="Connected depots: "..b.depots.." / fuel sources: "..b.fuel_sites
            if b.supply_reason then lines[#lines+1]=b.supply_reason end
            lines[#lines+1]="Supply convoys inbound: "..b.inbound
            if (b.delayed or 0)>0 then lines[#lines+1]="Delayed convoys: "..b.delayed.." (see campaign log)" end
            if (b.cut_convoys or 0)>0 then lines[#lines+1]="Convoys awaiting a corridor/road refresh: "..b.cut_convoys end
            if b.depots==0 then lines[#lines+1]="No new supply convoys: no connected operating depot." end
            if b.fuel_sites==0 then
                lines[#lines+1]="Fuel replenishment stopped: no connected operating fuel site."
                if b.fuel_reason then lines[#lines+1]=b.fuel_reason end
            end
        end
    end
    lines[#lines+1]="";lines[#lines+1]="SUPPORT IN FLIGHT"
    for _,f in ipairs(s.flights or {}) do lines[#lines+1]=f.label.." / "..f.status.." / "..f.survivors end
    if #(s.flights or {})==0 then lines[#lines+1]="No friendly AI flights active." end
    return table.concat(lines,"\n")
end
function V.task(s,id)
    local t=V.selected(s,id)
    if not t then return "No remaining taskable targets. Watch the front and ground advances." end
    local lines={t.role.." / "..t.name, "", "Surviving strength: "..math.floor(t.health*100).."%", "Sector: "..(t.sector_name or t.zone),
        "", t.threat or "", "", "COORDINATES", t.coordinates or "Use Brief / coordinates or Mark on F10 map.",
        "Elevation: "..tostring(t.elevation_ft or "?").." ft", "Reference: "..(t.position_reference or "Live group vehicle"), "",
        t.objective and ("Objective: "..t.objective) or t.role=="SEAD" and "Objective: destroy the site's search/tracking radars."
            or t.role=="CAS" and "Objective: eliminate every vehicle in this defending group."
            or "Objective: reduce this group to 25% strength or less.",
        "", "CAMPAIGN EFFECT",t.impact or "Effect not supplied by this mission.",
        "", "SECTOR OBJECTIVE",t.sector_instruction or "See Front plan.","", "CURRENT ASSIGNMENT"}
    if s.task then
        local active=V.selected(s,s.task.target)
        lines[#lines+1]=s.task.role.." / "..(active and active.name or s.task.target)
        lines[#lines+1]="Finish or abort it before accepting another."
    else lines[#lines+1]="None. Select a target and press Accept." end
    lines[#lines+1]="";lines[#lines+1]="Support tab: availability, cost and reasons."
    if t.dynamic then
        lines[#lines+1]="Force: "..(t.force_state or "?").." / "..t.survivors.." surviving vehicles."
        lines[#lines+1]="Coordinates follow an observed survivor. Select a SAM separately for SEAD."
    else lines[#lines+1]="SEAD uses this battery or the nearest active SAM." end
    lines[#lines+1]="AWACS 251.000 AM / Tanker 252.000 AM"
    return table.concat(lines,"\n")
end
function V.log(s)
    local lines={};local items=s.log or {}
    for i=#items,math.max(1,#items-14),-1 do
        lines[#lines+1]=V.time(items[i].time).."  "..items[i].text
    end
    return table.concat(lines,"\n")
end
return V
