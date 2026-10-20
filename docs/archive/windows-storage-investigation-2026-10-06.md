# Windows update storage investigation — 2026-10-06

Status: the original failure remains unexplained; it is not a confirmed installer fix.

An independent PC run of `test_three_application_versions_download_fiji_once_and_bound_storage`
retained application versions 1 and 3 instead of 2 and 3. The scratch installation's
`setup-storage.json` and directories confirmed the mismatch, not merely the final test
assertion. The run still shared one Fiji download, retained two applications, reclaimed
storage and preserved the previous setup after the injected completion failure.

Two fresh, instrumented runs with the same repository Python 3.12 interpreter recorded
`1 → 1,2 → 2,3` and the correct `--app` identities at all three collector invocations.
They did not reproduce the earlier mismatch. The first timed-out attempt and the later
failed attempt used different scratch roots. No timestamp sorting is involved: the
collector appends the completed installation to its ledger and keeps the final two entries.

The Windows integration test now checks each completed version's marker identity,
collector argument, ledger order and on-disk application set. A recurrence fails at the
first bad transition with its version, instead of reporting only final booleans. Its
original 60-second timeout and all download/retention assertions remain intact. All three
Windows update-storage tests passed after adding these checks. No production installer
or deletion rule was changed speculatively.

The next Windows release still requires fresh main CI and the actual ZIP's 26-case
installed acceptance. A new retention failure requires investigation; a passing retry
must not be described as a demonstrated cause or repair of the original event.
