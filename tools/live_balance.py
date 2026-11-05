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
from sqe.live.build import build


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--baseline-ref", help="Optional local git ref to compare against")
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--scenario",choices=("israel","legacy"),default="legacy")
    args = p.parse_args()
    with tempfile.TemporaryDirectory() as temporary:
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            build(Path(temporary),scenario=args.scenario)
        config = json.loads((Path(temporary) / "content.json").read_text())
    report = {"boundary":"Lua accounting fixtures: twenty-minute convoy travel, twenty-five-minute flight recovery, scripted losses and sector events; no combat/terrain/AI/FPS prediction.",
              "baseline_ref":args.baseline_ref,"scenario_profile":args.scenario,
              "current":[simulate(config, case) for case in SCENARIOS]}
    if args.baseline_ref:
        report["baseline_tree"] = subprocess.check_output(["git", "rev-parse", args.baseline_ref + "^{tree}"], cwd=ROOT, text=True).strip()
        report["baseline"] = [simulate(config, case, args.baseline_ref) for case in SCENARIOS]
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n")
    print(args.output)


if __name__ == "__main__":
    main()
