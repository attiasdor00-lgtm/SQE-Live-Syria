# Working on SQE Live

Start with [the Hebrew roadmap](LIVE_ROADMAP_HE.md) and
[the validation boundary](LIVE_VALIDATION.md). The conversion lives under
`sqe/live`; the original SQE mission generator remains in the rest of `sqe`.

## Browse and build

- Runtime and campaign rules: `sqe/live/lua/`.
- Syria scenario: `sqe/live/syria.json`.
- Mission authoring and install bundle: `sqe/live/build.py`.
- Windows installer and diagnostics: `sqe/live/install/`.
- Tests using Lua 5.1 and fake DCS/native widgets: `tests/live/`.
- Release version: `sqe/live/__init__.py`. Upstream version is separate.

From a checkout, install Python 3.12 or 3.13 and Git, then create a virtual
environment and install `requirements.txt` plus `requirements-live-test.txt`.
Activate that environment before running:

```sh
python -m sqe.live.build
python -m unittest discover -s tests/live -v
python tools/smoke_test.py
```

The build writes `dist/SQE-Live-Syria/`, including the reusable Syria mission and
installer. Tests do not require DCS. Installer/collector fixtures require `pwsh`;
set `SQE_TEST_PWSH` to its executable path if it is not on PATH. A skipped
installation test is not an installation pass. Real DCS behavior remains pending.

## Release a reviewed checkout

Commit the reviewed source and retain successful live/upstream test logs. Then:

```sh
python -m sqe.live.package --output dist/SQE-Live-Syria-v0.1.10.zip --live-log live-tests.txt --upstream-log upstream-smoke.txt --balance-report docs/LIVE_BALANCE_RESULTS.json
```

The archive includes the install bundle, all tracked source and the logs, plus a
source commit and install-file checksums. The packaging command does not publish.
Do not include a virtual environment, campaign saves, credentials or personal
logs in source control. GitHub's **Code → Download ZIP** supplies source; the
generated release ZIP also includes the ready-to-install mission.

The inherited `.github/workflows/release.yml` builds the original SQE executable
and uses the upstream version. It is not a Live release workflow. Use the Live
commands above for this conversion. Future work should preserve unrelated
remote edits and publish each completed feature as its own reviewed commit.

## Repeat the solo accounting scenarios

```sh
python tools/live_balance.py --baseline-ref 08102d69f82c4c86679149d4f0cb0df9afc772f0 --output balance-results.json
```

The baseline ref is the public 0.1.6 import and must be available in local Git
history (use a full clone). Omit `--baseline-ref` to measure the current rules
only. The report uses scripted travel, returns and losses, not a DCS combat model.
See LIVE_BALANCE.md for the fixtures and limits.

## Scenario profiles

`python -m sqe.live.build` defaults to the Israel profile and includes a separate
Legacy mission. `--scenario legacy` builds the previous campaign only. Existing
regression fixtures use that legacy profile; `test_geography.py` checks the
shipped default, ownership, multi-base logistics and both installed missions.

Use `python tools/live_balance.py --scenario israel --output israel-results.json`
for new-profile accounting fixtures. The tool defaults to legacy so historical
0.1.7 comparisons remain reproducible. The regional profile has larger starting
stocks and additional depots; historical balance results are not its playtest.
