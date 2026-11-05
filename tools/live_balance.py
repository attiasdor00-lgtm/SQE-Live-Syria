"""Run deterministic six-hour accounting fixtures; this is not a DCS combat model."""
from __future__ import annotations
import argparse
import contextlib
import io
import json
import subprocess
from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests" / "live"))
from balance_sim import SCENARIOS, simulate
from regional_balance_sim import REGIONAL_SCENARIOS, simulate_regional
from sqe.live.build import build


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--baseline-ref", help="Optional local git ref to compare against")
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--scenario",choices=("israel","legacy"),default="legacy")
    p.add_argument("--regional",action="store_true",help="Israel multi-base attrition/capture/isolation workloads")
    args = p.parse_args()
    if args.regional and args.scenario != "israel":
        p.error("--regional requires --scenario israel")
    cases,runner=(REGIONAL_SCENARIOS,simulate_regional) if args.regional else (SCENARIOS,simulate)
    with tempfile.TemporaryDirectory() as temporary:
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            build(Path(temporary),scenario=args.scenario)
        config = json.loads((Path(temporary) / "content.json").read_text())
    report = {"boundary":"Lua accounting fixtures: twenty-minute convoy travel, twenty-five-minute flight recovery, scripted losses and sector events; no combat/terrain/AI/FPS prediction.",
              "baseline_ref":args.baseline_ref,"scenario_profile":args.scenario,
              "scenario_suite":"regional" if args.regional else "original",
              "workload_note":"Steady/attrition include automatic air. Other regional cases disable automatic air, preserve logistics and script ownership; assault groups receive no injected arrivals; corridor period counters exclude the unaffected Ramat David base." if args.regional else "Original accounting workloads",
              "current":[runner(config, case) for case in cases]}
    if args.baseline_ref:
        report["baseline_tree"] = subprocess.check_output(["git", "rev-parse", args.baseline_ref + "^{tree}"], cwd=ROOT, text=True).strip()
        report["baseline"] = [runner(config, case, args.baseline_ref) for case in cases]
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n")
    print(args.output)


if __name__ == "__main__":
    main()
