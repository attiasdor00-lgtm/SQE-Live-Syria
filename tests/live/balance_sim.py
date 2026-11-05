"""Repeatable campaign accounting scenarios. Events are fixtures, not combat predictions."""
from __future__ import annotations
import copy
import subprocess

from test_live import Harness, ROOT

SCENARIOS = ("steady", "low_stock_depot_loss", "quarter_strength_depot",
             "fuel_loss", "corridor_cut", "attrition", "empty_legacy_stock")


def simulate(config, scenario, baseline_ref=None):
    if scenario not in SCENARIOS:
        raise ValueError("Unknown scenario: " + scenario)
    config = copy.deepcopy(config)
    if scenario == "corridor_cut":
        south = next(z for z in config["zones"] if z["id"] == "south")
        south["owner"] = "blue"
        for t in config["targets"]:
            if t["id"] == "blue_depot":
                t.update(zone="south", x=south["x"] + 5000, y=south["y"] + 5000)
            if t["id"] == "south_armor": t["side"] = "blue"
            if t["id"] == "blue_front": t["side"] = "red"
    h = Harness(config)
    if baseline_ref:
        for name, file in {"core":"core", "director":"director", "adapter":"dcs_adapter",
                           "operations":"operations", "view":"view"}.items():
            text = subprocess.check_output(["git", "show", baseline_ref + ":sqe/live/lua/" + file + ".lua"], cwd=ROOT, text=True)
            h.g.mods[name] = h.lua.execute(text)
    h.start()
    h.g.scenario = scenario
    result = h.run('''
        local low=scenario~='steady' and scenario~='attrition'
        c.state.bases.ramat.resources=low and {fuel=30,ammo=30,supply=30} or {fuel=100,ammo=100,supply=100}
        if scenario=='empty_legacy_stock' then c.state.bases.ramat.resources={fuel=0,ammo=0,supply=0} end
        local depot_loss=scenario=='low_stock_depot_loss' or scenario=='quarter_strength_depot' or scenario=='empty_legacy_stock'
        if depot_loss then
            local n=scenario=='quarter_strength_depot' and 3 or 4
            for i=1,n do mock.kill('SQEL-G-blue_depot-1-'..i) end
        end
        if scenario=='low_stock_depot_loss' then
            for i=1,5 do mock.kill('SQEL-G-south_armor-1-'..i) end
        end
        if scenario=='fuel_loss' then for i=1,3 do mock.kill('SQEL-G-blue_fuel-1-'..i) end end
        if scenario=='corridor_cut' then c.state.zones.golan.owner='red' end
        local seen,seen_ship={},{}
        local south_was_blue=c.state.zones.south.owner=='blue'
        local report={scenario=scenario,minutes=360,blue_automatic_launches=0,requested=0,accepted=0,
            aircraft_losses=0,cargo_losses=0,supply_convoys=0,first_rebuild_minute=false,first_supply_minute=false,
            first_south_capture_minute=false,peak_units=c:active_count(),samples={}}
        for minute=1,360 do
            c:tick(60)
            if scenario=='corridor_cut' and minute==120 then
                for i=1,#c.target_defs.blue_front.types do mock.kill(a.ground_groups.blue_front..'-'..i) end
                c.state.zones.golan.owner='blue'
            end
            if (scenario=='steady' or scenario=='attrition') and (minute==90 or minute==180 or minute==270) then
                local target=minute==90 and 'south_armor' or minute==180 and 'marj_armor' or 'damascus_armor'
                for i=1,#c.target_defs[target].types do
                    local name=a.ground_groups[target]..'-'..i
                    if mock.units[name].alive then mock.kill(name) end
                end
            end
            for id,f in pairs(c.state.flights) do
                if not seen[id] then
                    seen[id]=true
                    if f.side=='blue' and f.automatic then report.blue_automatic_launches=report.blue_automatic_launches+1 end
                end
                if f.status~='COMPLETE' and c.state.time-f.started>=1500 then
                    if scenario=='attrition' and f.side=='blue' and tonumber(id:match('(%d+)$'))%2==0 then
                        for _,u in ipairs(mock.groups[a.air_groups[id]].units)do
                            if u.alive then mock.kill(u.name);report.aircraft_losses=report.aircraft_losses+1;break end
                        end
                    end
                    mock.land_flight(a,f)
                end
            end
            for id,s in pairs(c.state.shipments)do
                if not seen_ship[id] then
                    seen_ship[id]=true
                    if s.side=='blue' and s.kind=='SUPPLY' then report.supply_convoys=report.supply_convoys+1 end
                end
                if s.status=='MOVING' and c.state.time-s.started>=1200 then
                    if scenario=='attrition' and s.side=='blue' and s.kind=='SUPPLY' then
                        local u=mock.units[a.ship_groups[id]..'-1']
                        if u.alive then mock.kill(u.name);report.cargo_losses=report.cargo_losses+1 end
                    end
                    mock.deliver(a,s)
                end
            end
            a:observe();mods.director.tick(c)
            if not report.first_rebuild_minute and c.state.targets.blue_depot.generation>1 then report.first_rebuild_minute=minute end
            if not south_was_blue and not report.first_south_capture_minute and c.state.zones.south.owner=='blue' then report.first_south_capture_minute=minute end
            for _,s in pairs(c.state.shipments) do
                if not report.first_supply_minute and s.side=='blue' and s.kind=='SUPPLY' and c.count(s.delivered)>0 then report.first_supply_minute=minute end
            end
            if (scenario=='steady' or scenario=='attrition') and minute%45==0 then
                report.requested=report.requested+1
                local ok=c:launch('STRIKE','blue','south_sam',false)
                if ok then report.accepted=report.accepted+1 end
            end
            for id,f in pairs(c.state.flights) do
                if not seen[id] then
                    seen[id]=true
                    if f.side=='blue' and f.automatic then report.blue_automatic_launches=report.blue_automatic_launches+1 end
                end
            end
            for id,s in pairs(c.state.shipments) do
                if not seen_ship[id] then seen_ship[id]=true;if s.side=='blue' and s.kind=='SUPPLY' then report.supply_convoys=report.supply_convoys+1 end end
            end
            local valid,why=c:validate_save(c:snapshot());assert(valid,why)
            assert(c:active_count()<=cfg.unit_budget)
            report.peak_units=math.max(report.peak_units,c:active_count())
            if minute%60==0 then
                report.samples[#report.samples+1]={minute=minute,resources=c.copy(c.state.bases.ramat.resources),depot_generation=c.state.targets.blue_depot.generation}
            end
        end
        report.bases={}
        for _,b in ipairs(cfg.bases)do if b.side=='blue' then
            report.bases[b.id]={ready=c.copy(c.state.bases[b.id].ready),resources=c.copy(c.state.bases[b.id].resources),
                operational=c.state.zones[b.zone].owner==b.side}
        end end
        report.resources=c.copy(c.state.bases.ramat.resources)
        report.depot_health=c:target_health('blue_depot');report.depot_generation=c.state.targets.blue_depot.generation
        report.fuel_health=c:target_health('blue_fuel');report.fuel_generation=c.state.targets.blue_fuel.generation
        report.blue_sectors=0
        for _,z in pairs(c.state.zones)do if z.owner=='blue' then report.blue_sectors=report.blue_sectors+1 end end
        report.status=c.state.status;report.valid=c:validate_save(c:snapshot())
        local offer=c:flight_offer('STRIKE','blue','south_sam')
        report.final_strike_offer={available=offer.available,code=offer.code,reason=offer.reason}
        return mods.json.encode(report)
    ''')
    import json
    return json.loads(result)
