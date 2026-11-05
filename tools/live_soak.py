"""Bounded Lua runtime workload; host/stub timings are not DCS frame times."""
from __future__ import annotations
import argparse
import contextlib
import io
import json
import platform
from pathlib import Path
import statistics
import subprocess
import sys
import tempfile
import time

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'tests/live'))
from test_live import Harness
from sqe.live.build import build


def measure(config, hours=6, baseline_ref=None):
    if not 0<hours<=24:
        raise ValueError('hours must be above zero and at most 24')
    h=Harness(config)
    if baseline_ref:
        src=subprocess.check_output(['git','show',baseline_ref+':sqe/live/lua/dcs_adapter.lua'],cwd=ROOT,text=True)
        h.g.mods.adapter=h.lua.execute(src)
    h.start()
    h.run('''
        function size(t)local n=0;for _ in pairs(t or {})do n=n+1 end;return n end
        function metrics()
            local v={time=c.state.time,registry=size(a.registry),air_groups=size(a.air_groups),ship_groups=size(a.ship_groups),
                flights=size(c.state.flights),shipments=size(c.state.shipments),contacts=size(a.contacts),landed=size(a.landed),
                target_returns=size(c.target_returns),journal=#c.journal_order,log=#c.state.log,queue=size(fs.queue),
                save_bytes=#fs.files[cfg.id],status_bytes=#fs.status_text,active_units=c:active_count(),
                diagnostic_history=#rt.diagnostics.history}
            local orphans=0
            for name,r in pairs(a.registry)do if r.kind=='flight' then
                local f=c.state.flights[r.id];local u=Unit.getByName(name)
                if u and u:isExist() and u:getLife()>0 and (not f or f.status=='COMPLETE' or not f.alive[tostring(r.index)]) then orphans=orphans+1 end
            end end
            v.live_lost_aircraft=orphans
            return mods.json.encode(v)
        end
        function workload(minute)
            -- Every fixture arrival/loss is explicit; no AI/combat prediction.
            for _,f in pairs(c.state.flights)do
                if f.status~='COMPLETE' and c.state.time-f.started>=600 then
                    if not ejected and f.side=='blue' and f.count==2 then
                        for _,u in ipairs(mock.groups[a.air_groups[f.id]].units)do
                            mock.emit({id=world.event.S_EVENT_EJECTION,initiator=u})
                        end
                        ejected=true
                    end
                    if f.status~='COMPLETE' then mock.land_flight(a,f) end
                end
            end
            for _,s in pairs(c.state.shipments)do
                if s.kind=='SUPPLY' and s.status=='MOVING' and c.state.time-s.started>=1200 then mock.deliver(a,s) end
            end
            if minute%30==0 then
                for n=1,32 do
                    local id='load-'..minute..'-'..n
                    fs.enqueue(id,mods.json.encode({id=id,session=c.session,revision=c.state.revision,action='brief',target='south_sam'}))
                end
            end
            -- The double keeps historical entities/messages for assertions. They
            -- are excluded from runtime-retention metrics; this is not process RAM.
        end
    ''')
    ticks=int(hours*3600/2);times=[];samples=[];peaks={};started=time.perf_counter()
    for tick in range(1,ticks+1):
        if tick%30==1:
            h.g.minute=(tick-1)//30
            h.run('workload(minute)')
        t=time.perf_counter();h.run('mock.advance(2);assert(not rt.failed,tostring(rt.failed))');times.append((time.perf_counter()-t)*1000)
        row=json.loads(h.run('return metrics()'))
        for k,v in row.items():
            if k!='time':peaks[k]=max(peaks.get(k,0),v)
        if tick%900==0 or tick==ticks:samples.append(row)
        if tick%30==0:h.run('local ok,why=c:validate_save(c:snapshot());assert(ok,why)')
    times.sort()
    return {'boundary':'Actual Lua runtime and two-second callbacks with explicit stub observations; in-memory file bridge. Host timings exclude DCS, Windows filesystem, rendering, flight/AI and FPS; object-double tombstones are not process memory measurements.',
            'metric_cadence_seconds':2,'command_burst':32,'command_period_minutes':30,'hours':hours,'ticks':ticks,'baseline_ref':baseline_ref,'elapsed_host_seconds':round(time.perf_counter()-started,3),
            'update_ms':{'median':round(statistics.median(times),3),'p95':round(times[int(.95*(len(times)-1))],3),'max':round(max(times),3)},
            'peaks':peaks,'samples':samples,'final':json.loads(h.run('return metrics()'))}


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output',required=True,type=Path);p.add_argument('--hours',type=float,default=6)
    p.add_argument('--baseline-ref');a=p.parse_args()
    with tempfile.TemporaryDirectory() as temporary:
        with contextlib.redirect_stdout(io.StringIO()),contextlib.redirect_stderr(io.StringIO()):build(Path(temporary))
        cfg=json.loads((Path(temporary)/'content.json').read_text())
    report={'release':cfg['release'],'python':platform.python_version(),'runtime':'Lupa / Lua 5.1','result':measure(cfg,a.hours,a.baseline_ref)}
    a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(report,indent=2)+'\n');print(a.output)


if __name__=='__main__':main()
