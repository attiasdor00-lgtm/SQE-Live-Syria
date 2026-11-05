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
python -m sqe.live.package --output dist/SQE-Live-Syria-v0.1.6.zip --live-log live-tests.txt --upstream-log upstream-smoke.txt
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
