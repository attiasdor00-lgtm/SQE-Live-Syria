"""Israel accounting workloads. Every loss, arrival and ownership change is scripted."""
from __future__ import annotations
import copy
import json
import subprocess

from test_live import Harness, ROOT
from balance_sim import simulate

REGIONAL_SCENARIOS = ('steady', 'attrition', 'fragmented_survivors', 'ramat_captured',
                      'central_captured', 'corridor_isolation', 'exhausted_aircraft', 'all_bases_lost')


def simulate_regional(config, scenario, baseline_ref=None):
    if scenario not in REGIONAL_SCENARIOS:
        raise ValueError(scenario)
    if config['id'] != 'syria_israel_solo':
        raise ValueError('Regional workloads require the Israel profile')
    if scenario in ('steady', 'attrition'):
        return simulate(config, scenario, baseline_ref)
    h=Harness(copy.deepcopy(config))
    if baseline_ref:
        for name in ('core', 'director', 'operations', 'view'):
            text=subprocess.check_output(['git','show',baseline_ref+':sqe/live/lua/'+name+'.lua'],cwd=ROOT,text=True)
            h.g.mods[name]=h.lua.execute(text)
        text=subprocess.check_output(['git','show',baseline_ref+':sqe/live/lua/dcs_adapter.lua'],cwd=ROOT,text=True)
        h.g.mods.adapter=h.lua.execute(text)
    h.start();h.g.scenario=scenario
    return json.loads(h.run('''
        c.state.next_director=1e9 -- Isolate player access; steady/attrition include automatic flights.
        local function aircraft_stock()
            local n=0
            for _,b in ipairs(cfg.bases)do if b.side=='blue' then
                for _,v in pairs(c.state.bases[b.id].ready)do n=n+v end
            end end
            for _,f in pairs(c.state.flights)do if f.side=='blue' and f.status~='COMPLETE' then n=n+c.count(f.alive) end end
            for _,m in ipairs(c.state.maintenance)do if c.base_defs[m.base].side=='blue' then n=n+m.count end end
            return n
        end
        local report={scenario=scenario,minutes=360,requested=0,accepted=0,aircraft_losses=0,
            automatic_air=false,peak_units=c:active_count(),requests={},samples={},initial_aircraft=aircraft_stock(),deliveries_during_cut=0,
            deliveries_after_reconnect=0,deliveries_before_cut=0,single_requests=0,delivered={}}
        if scenario=='fragmented_survivors' or scenario=='exhausted_aircraft' then
            for _,b in ipairs(cfg.bases)do if b.side=='blue' and c.state.bases[b.id].ready['F-16C'] then
                c.state.bases[b.id].ready['F-16C']=scenario=='fragmented_survivors' and 1 or 0
            end end
        end
        if scenario=='corridor_isolation' then
            c.state.bases.ramat.ready['F-16C']=0
            for _,id in ipairs({'blue_central_depot','blue_negev_depot'})do
                for i=1,#c.target_defs[id].types do mock.kill(a.ground_groups[id]..'-'..i) end
            end
            for _,id in ipairs({'hatzor','tel_nof','nevatim','hatzerim'})do
                c.state.bases[id].resources={fuel=40,ammo=40,supply=40}
            end
        end
        local previous=aircraft_stock();report.seeded_aircraft_losses=report.initial_aircraft-previous
        local delivered={}
        for minute=1,360 do
            if minute==60 then
                if scenario=='ramat_captured' then c.state.zones.galilee.owner='red'
                elseif scenario=='central_captured' then c.state.zones.central.owner='red'
                elseif scenario=='corridor_isolation' then c.state.zones.sharon.owner='red'
                elseif scenario=='all_bases_lost' then
                    for _,id in ipairs({'galilee','central','negev'})do c.state.zones[id].owner='red' end
                end
            end
            if minute==180 and scenario=='corridor_isolation' then c.state.zones.sharon.owner='blue' end
            c:tick(60)
            for _,f in pairs(c.state.flights)do if f.status~='COMPLETE' and c.state.time-f.started>=1500 then
                local home=c.base_defs[f.base]
                local lose=c.state.zones[home.zone].owner~=f.side
                    or (scenario=='fragmented_survivors' and (f.fixture_request==1 or f.fixture_request==3))
                if lose then
                    for _,u in ipairs(mock.groups[a.air_groups[f.id]].units)do if u.alive then
                        mock.kill(u.name);report.aircraft_losses=report.aircraft_losses+1
                    end end
                else mock.land_flight(a,f) end
            end end
            for _,s in pairs(c.state.shipments)do
                if s.kind=='SUPPLY' and s.status=='MOVING' and c.state.time-s.started>=1200 then mock.deliver(a,s) end
            end
            a:observe();mods.director.tick(c)
            for id,s in pairs(c.state.shipments)do if s.side=='blue' and s.kind=='SUPPLY' then
                local n=c.count(s.delivered);local added=n-(delivered[id] or 0);delivered[id]=n
                if added>0 then
                    local period=minute<60 and 'deliveries_before_cut' or minute<180 and 'deliveries_during_cut' or 'deliveries_after_reconnect'
                    if scenario~='corridor_isolation' or s.base~='ramat' then report[period]=report[period]+added end
                    report.delivered[s.base]=(report.delivered[s.base] or 0)+added
                end
            end end
            if minute%45==0 then
                report.requested=report.requested+1
                local q=c:flight_offer('STRIKE','blue','south_sam',false)
                local ok=c:launch('STRIKE','blue','south_sam',false)
                report.requests[#report.requests+1]={minute=minute,accepted=ok,code=q.code,base=q.base or false,count=q.count or 0}
                if ok then
                    report.accepted=report.accepted+1
                    if q.count==1 then report.single_requests=report.single_requests+1 end
                    for _,f in pairs(c.state.flights)do if f.status~='COMPLETE' and not f.fixture_request then f.fixture_request=report.requested end end
                end
            end
            local stock=aircraft_stock();assert(stock<=previous,'Aircraft were manufactured by the accounting workload')
            previous=stock
            local valid,why=c:validate_save(c:snapshot());assert(valid,why)
            assert(c:active_count()<=cfg.unit_budget)
            report.peak_units=math.max(report.peak_units,c:active_count())
            if minute%60==0 then
                local sample={minute=minute,aircraft_stock=stock,bases={}}
                for _,b in ipairs(cfg.bases)do if b.side=='blue' then
                    sample.bases[b.id]={ready=c.copy(c.state.bases[b.id].ready),resources=c.copy(c.state.bases[b.id].resources),
                        operational=c.state.zones[b.zone].owner==b.side}
                end end
                report.samples[#report.samples+1]=sample
            end
        end
        report.final_aircraft=aircraft_stock();report.status=c.state.status;report.valid=c:validate_save(c:snapshot())
        report.bases=report.samples[#report.samples].bases
        return mods.json.encode(report)
    '''))
