# V01.1 — first native persistence failure and candidate fix (0.1.13)

## Native observations received on 2026-11-06

The user reports that Operations opens and all SQE Live radio commands appear.
The supplied diagnostic archive records an installed 0.1.12 package, a loaded
Operations hook, repeated UI diagnostic write failures, SAVE ERROR: nil, and
failed status/diagnostic publication. Neither runtime nor UI report files were
present in that collection. The installed bridge reached the save call; this is
not merely an absent UI hook or proof that the mission never started.

The original archive and local paths are private diagnostic inputs and are not
copied into this repository. The filtered log does not identify the DCS build
or the exact native IO call/return that failed. A root-cause attribution to
file:close, permissions, antivirus or an engine change would be premature.

## Reproduced code behavior

The 0.1.12 writer checks write/close truthiness and can return false with no
reason if either returns nil without an error string. An open failure without a
reason has the same outward result. The same writer serves checkpoints, status,
commands and diagnostic reports, so this code path can explain simultaneous
channel failures. Synthetic IO reproduces that outward signature; it does not
establish that the user's DCS has this exact return convention.

The [Lua 5.1 reference manual](https://www.lua.org/manual/5.1/manual.html#5.7)
specifies non-nil success for ordinary IO functions. The earlier tests covered
that conventional behavior. Compatibility with an ambiguous embedded return is
now based on independent file content verification, not treating nil as success.

## Candidate implementation

The bridge always attempts close, including after a write exception. Explicit
false/error returns and exceptions fail with an operation-specific nonempty
reason. A nil/no-detail write/close return proceeds only to verification: the
closed temporary file must reopen as a bounded regular file and match the full
intended byte string. Every write is verified, including conventional success.
Only then does the existing rotation/promotion occur. A failed verification
removes the temporary output before touching the previous primary/backup.

Read/open/close failures also receive explicit reasons. An unreadable existing
file is not silently treated as an absent checkpoint. Empty existing files are
read as empty content, so invalid checkpoint data follows normal validation and
backup handling. Directory and path limits, standard DCS sanitization and the
narrow bridge scope remain unchanged. This is not an fsync/power-loss guarantee.

Six new cases cover both/mixed nil return conventions, exact-byte verification,
partial output, explicit errors/false returns/exceptions, silent read-open failure,
and an end-to-end pipeline. The pipeline runs the actual compiled mission Lua
and filesystem bridge, presents status to fake native widgets and sends a Save
command back through real temporary command files. It reaches LIVE/Saved under
the synthetic convention. It does not execute DCS or render native widgets.

## Applying and verifying

The bridge is captured at DCS startup; an existing running instance continues to
use its old closures. Close DCS, extract the complete 0.1.13 archive and rerun
Install.cmd using the same installation/profile, then launch the installed mission.
Existing checkpoint files are preserved by installation. The failed native save
was not acknowledged; current-session progress may be absent on exit. No rescue
or hot-reload of that volatile session is claimed.

After the update, Operations should receive current state and a Save command
should acknowledge Saved. If the write is genuinely blocked or another IO
operation fails, the new stage-specific error should replace the unhelpful nil;
Collect-Diagnostics.cmd remains the collection route. These expected outcomes
still require an updated native observation. V01 remains IN PROGRESS.

Sector geometry is currently in the Operations schematic. Native DCS F10 supports
requested target marks; sector polygons are not implemented by this fix.
The L12 workload/timing artifacts are historical 0.1.12 memory-bridge measurements;
they do not measure the added filesystem readback cost or actual DCS frame time.
