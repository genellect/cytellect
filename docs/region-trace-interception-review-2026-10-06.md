# Region-source browser acceptance: interception lifecycle

Date: 2026-10-06

The `fiji-browser` job for commit `510db71` failed in `region-trace.spec.ts`
after a delayed field-adoption response. `Add` remained disabled, then the
editor's parent remained inert. The same failure was reproduced against the
Docker application without changing application code.

Request-category diagnostics showed four concurrent navigation refresh reads.
In one reproduction, workspace, fields and revisions completed while jobs
remained pending; in another, jobs completed in about 15 ms while revisions
remained pending. The application aborted the remaining read at its existing
15-second deadline and displayed its recovery message. An independent API
client could read jobs successfully. Thus the disabled editor was the intended
fail-closed recovery state, not evidence that its guard should be removed.

The test removed its final Playwright route immediately after fulfilling the
adoption request, while that response was starting the concurrent refresh.
The correction retains interception until the refresh and editor transition
settle, then removes the routes. This removes the interception-teardown race
without changing application requests, navigation deadlines, masks or metrics.
The observations localize the race to the browser test's route lifecycle;
Chromium-internal protocol ordering was not independently captured.

The corrected case also deliberately holds the jobs refresh and verifies that
editing remains disabled until it is released. Existing checks for exact
historical masks/channels, draft preservation, failed adoption, and an actual
refresh deadline followed by a late response remain in place. There is no
forced click, increased timeout or acceptance based solely on a rerun.

Validation: TypeScript and focused ESLint pass. The corrected browser case
passed three consecutive runs (`--repeat-each=3`, 3.6 minutes total) against
the real local Docker API and unchanged application build. The fixtures are registered public
BBBC013 pixels and artificial navigation rectangles, not private research data
or a biological segmentation benchmark.
