"""Make the install/source archive from a reviewed checkout; does not publish."""
from __future__ import annotations
import argparse
import contextlib
import hashlib
import io
import json
import subprocess
import zipfile
from pathlib import Path
from . import VERSION
from .build import ROOT, build


def package(output: Path, live_log: Path | None = None, upstream_log: Path | None = None,
            balance_report: Path | None = None, soak_report: Path | None = None):
    bundle = output.parent / "SQE-Live-Syria"
    with contextlib.redirect_stdout(io.StringIO()):
        build(bundle)
    tracked = subprocess.check_output(["git", "ls-files", "-z"], cwd=ROOT).decode().split("\0")
    tracked = [name for name in tracked if name]
    if "sqe/live/lua/runtime.lua" not in tracked:
        raise RuntimeError("Stage the reviewed source before packaging; refusing an incomplete source archive")
    source_sha = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for path in sorted(bundle.rglob("*")):
            if path.is_file():
                z.write(path, "SQE-Live-Syria/" + path.relative_to(bundle).as_posix())
        for name in tracked:
            z.write(ROOT/name, "Source/" + name)
        z.writestr("Source/SOURCE_COMMIT.txt", source_sha+"\n")
        for file,name in ((live_log,"live-tests.txt"), (upstream_log,"upstream-smoke.txt")):
            if file:
                z.write(file,"Validation/"+name)
        if balance_report:
            z.write(balance_report,"Validation/solo-balance.json")
        if soak_report:
            z.write(soak_report,"Validation/runtime-soak.json")
        z.writestr("START_HERE.txt",
                   f"SQE Live / Syria {VERSION}\n\n"
                   "Open SQE-Live-Syria/START_HERE_HE.md for Hebrew instructions.\n"
                   "Pilot manual and mission pool: SQE-Live-Syria/MISSION_MANUAL_HE.md.\n"
                   "English: SQE-Live-Syria/START_HERE.md.\n"
                   "Install: extract ALL files, then run SQE-Live-Syria/Install.cmd.\n"
                   "Source/ contains the complete source checkout for continued development.\n"
                   "Validation/ contains automated test logs. Real DCS flight validation is pending.\n")
    with zipfile.ZipFile(output) as z:
        corrupt = z.testzip()
        if corrupt:
            raise RuntimeError("Corrupt archive member: " + corrupt)
    digest = hashlib.sha256(output.read_bytes()).hexdigest()
    output.with_suffix(".zip.sha256").write_text(digest + "  " + output.name + "\n")
    return output


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--output", type=Path, default=ROOT/"dist"/f"SQE-Live-Syria-v{VERSION}.zip")
    p.add_argument("--live-log", type=Path)
    p.add_argument("--upstream-log", type=Path)
    p.add_argument("--balance-report", type=Path)
    p.add_argument("--soak-report", type=Path)
    args=p.parse_args()
    print(package(args.output,args.live_log,args.upstream_log,args.balance_report,args.soak_report))


if __name__ == "__main__":
    main()
