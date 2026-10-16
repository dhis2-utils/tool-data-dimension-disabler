# Fixes for review findings (2026-09-21)

Tracks what changed for each finding fixed under Task 15d, where, and how it
was verified. `REVIEW-FINDINGS.md` marks each of these "Fixed in <commit>"
without deleting the original finding text. L2, L7 and L8 are left as-is
(design/copy decisions for the maintainer) and are not covered here.

## M1. Only every other "… is no longer a data dimension" toast is shown

**Commit**: `2c997df`

**What changed**: `src/components/UsageView.tsx` — destructured `hide` from
the `useAlert()` result alongside `show`, and call `hideDisabled()`
immediately before `showDisabled({ name: ... })` in `confirmDisable`.

**Why this is the right fix**: read
`node_modules/@dhis2/app-service-alerts/build/es/useAlert.js` and
`makeAlertsManager.js`. `useAlert`'s `show()` reuses `alertRef.current?.id`
if the ref is still set (`add()` in `makeAlertsManager.js`: `alertId =
alertRef.current?.id ?? ++id`), and only `hide()` (which calls
`alertRef.current.remove()`) sets `alertRef.current = null`. So calling
`hide()` before every `show()` guarantees the next `show()` always
allocates a fresh id via `++id`, whether or not a previous alert is still
on screen (calling `hide()` when nothing is showing is a safe no-op, since
`remove` is called only if `alertRef.current` is non-null). This matches
the reviewer's proposed fix exactly; no alternative was needed.

**Side note for the maintainer**: this fixes the id-reuse root cause, but
it changes the observable behaviour slightly from "both toasts theoretically
visible" to "the previous toast is replaced immediately by the next one" -
`hide()` removes the current alert as part of the fix, rather than letting
it run its own 8s timer. Both messages still reach the user, just not
simultaneously; this is the smallest fix and matches what the finding
proposed.

**Test**: `src/components/UsageView.test.tsx` — new test "shows a fresh
success alert for each of two disables done in quick succession". It
disables two rows back to back (each against a grid that shrinks by one row)
and asserts:
  - the second success message is present and the first is not (MockAlertStack
    can't reproduce the real AlertBar's auto-hide-timer artifact - it has no
    timer at all - so both the bug and the fix converge on this same final
    message state; see the in-file comment for the full explanation), and
  - critically, the second alert's `data-alert-id` differs from the first
    alert's `data-alert-id` - i.e. a *new* alert was raised, not the first
    alert's id reused with its message overwritten in place (the actual root
    cause M1 reports).

  `src/test-utils/MockAlertStack.tsx` now renders each alert's id as
  `data-alert-id` (previously only used as the React `key`, invisible to
  assertions) so this distinction is testable at all.

**Verified**:
  - `yarn test --testPathPattern UsageView` → all pass with the fix.
  - Sanity check: reverted just `UsageView.tsx` (`git stash -- src/components/UsageView.tsx`)
    and re-ran the same test - it fails with `secondAlertId` equal to
    `firstAlertId` (both `"1"`), confirming the test is a genuine regression
    guard and not a false positive.
  - Full suite: `yarn test` → 68/68 pass (63 original + this + the L3/L5
    tests below).

## M2. `generate-view-events.sh` produces no usable ranking data

**Commit**: `314e264`

**What changed**: `scripts/generate-view-events.sh`, all three favorite
selection batches (visualizations, maps, event visualizations) plus a new
`fetch` helper.
  - Replaced `filter=categoryDimensions:!empty` (rejected by 2.40 with
    `400 E1003`) with the `~size` field transformer, e.g.
    `categoryDimensions~size`, requested for every dimension type at once
    (`categoryDimensions~size,organisationUnitGroupSetDimensions~size,
    dataElementGroupSetDimensions~size,categoryOptionGroupSetDimensions~size`
    for visualizations; the map fields nest under `mapViews[...]`; event
    visualizations get the three types that have an
    `eventvisualization_*dimensions` join table per `buildQuery.ts`, i.e. no
    `dataElementGroupSetDimensions`).
  - Added a `select_with_dimensions` jq helper that keeps only the favorites
    whose dimension-size fields sum to more than 0, takes the first N of
    those (5 visualizations, 3 maps, 3 event visualizations, matching the
    script's original batch sizes), and prints a one-line
    `<kind>: <withDimensions>/<total> favorites carry a dimension` summary to
    stderr.
  - Replaced the blanket `... || true` with a `fetch` helper that captures
    the HTTP status via `curl -sS -w '\n%{http_code}'`, prints
    `warning: GET <path> -> HTTP <status>: <body>` to stderr and falls back
    to `{}` on any non-2xx response, instead of silently treating a server
    error as "no favorites found". Added `--globoff` to `fetch`'s curl call
    since the map query's `fields=...[...]` brackets are otherwise
    interpreted by curl's own URL-globbing and fail with a local "malformed
    URL" error (exit 3) before any request is even sent.
  - `set -euo pipefail` remains safe: `fetch` never lets a failed request
    propagate an unhandled non-zero exit, and empty `ids` lists just make
    the `for uid in $(...)` loops not iterate.

**Verified**:
  - `bash -n scripts/generate-view-events.sh` and `shellcheck
    scripts/generate-view-events.sh` → clean.
  - jq logic dry-run against saved sample JSON (a real 125-row
    `eventVisualizations` response, and a hand-built 3-map sample covering
    an empty `mapViews`, a view with a non-zero size, and an all-zero view) -
    correctly picked only the favorites with a non-zero dimension sum in
    both cases.
  - `fetch`'s warning path tested directly against a nonexistent endpoint on
    the live instance below - printed the expected `warning: GET ... -> HTTP
    404: ...` to stderr and returned `{}`.
  - **Live run** against a 2.41.10 instance with the DHIS2 for Education
    (EMIS) metadata, at `http://localhost:8080` (the Sierra Leone 2.43.1
    instance was not used for this run):

    ```
    $ ./scripts/generate-view-events.sh http://localhost:8080 admin:district
    visualizations: 0/0 favorites carry a dimension
    maps: 0/0 favorites carry a dimension
    event_visualizations: 17/125 favorites carry a dimension
    EVENT_VISUALIZATION_VIEW aD7taFe4Z3E x3
    EVENT_VISUALIZATION_VIEW AjGJkwuKf9y x2
    EVENT_VISUALIZATION_VIEW QcykbZCcmmz x1
    ```

    This seed has no visualizations or maps at all (confirmed separately via
    `GET /api/visualizations?pageSize=1` and `GET /api/maps?pageSize=1`,
    both `pager.total: 0`), so 0/0 for those two is correct, not a bug. The
    `~size` transformer itself was confirmed working on 2.41.10 before
    wiring it into the script (raw `curl` calls returned e.g.
    `{"dataElementGroupSetDimensions":0,"categoryDimensions":0,"id":"..."}`
    per row). The three recorded events were read back via
    `GET /api/dataStatistics/favorites?eventType=EVENT_VISUALIZATION_VIEW`,
    which reported `views: 3, 2, 1` for the three uids in the same order -
    an exact match. The live run is therefore complete, not pending.

## L1. Two sources of truth for the SQL view's column names

**Commit**: `63b629c`

**What changed**: `src/hooks/useUsageData.ts` now imports `SQL_VIEW_COLUMNS`
from `src/sql/buildQuery.ts` and destructures it into named constants
(`TYPE, UID, NAME, VIEWS, PERCENT, PERCENT_OF_VIEWS`) used everywhere the
six column-name string literals were previously repeated. `column()`'s
`name` parameter is now typed as `(typeof SQL_VIEW_COLUMNS)[number]` instead
of a bare `string`, so a typo or a renamed column is a compile error at the
call site, not just a silent mismatch at runtime.

**Verified**: `yarn test --testPathPattern useUsageData` and the full suite
both pass unchanged (`parseUsageRows` behaviour is identical); `tsc --noEmit`
(part of `yarn lint`) passes.

## L3. A missing `serverVersion` silently means "2.40 schema"

**Commit**: `63b629c`

**What changed**: `src/hooks/useSqlViewStatus.ts` no longer defaults
`serverVersion?.minor` to `0`. `classifyStatus`'s `minor` parameter is now
optional (`minor?: number`); when it's `undefined` (and there's no loading
or query error to report instead), `classifyStatus` returns `'ERROR'`
rather than falling through to `isCurrentSqlQuery(sqlQuery, 0)`. When that
happens, `useSqlViewStatus` also synthesizes a `FetchError` with a clear,
translated message ("Could not determine the DHIS2 server version, so the
SQL view cannot be checked.") so `SqlViewNotice`'s existing ERROR branch has
something specific to show instead of its generic "Unknown error" fallback.
The hook's returned `minor` still falls back to `0` for callers that need a
plain `number` (`useSqlViewMutations`, `UsageView`), but those are only ever
invoked once `status` is READY/OUTDATED/MISSING, none of which are reachable
with an undefined minor and no query error - see the comment at the return
site.

**Test**: two new tests in `src/hooks/useSqlViewStatus.test.tsx`:
  - `classifyStatus` unit test: `minor: undefined` with a *current* (2.43)
    `sqlQuery` returns `'ERROR'`, not `'READY'`/`'OUTDATED'` - directly
    exercising the exact old bug (misclassifying a correct view because the
    version was unknown).
  - `useSqlViewStatus` integration test: renders with
    `{ ...defaultConfig, serverVersion: undefined }` and asserts the hook
    reports `status: 'ERROR'` with the exact synthesized message above.

**Verified**:
  - `yarn test --testPathPattern useSqlViewStatus` → both new tests pass
    with the fix.
  - Sanity check: reverted just `useSqlViewStatus.ts` and re-ran - both new
    tests fail (the unit test reports `Received: "READY"`; the integration
    test can't find the ERROR text and shows `OUTDATED` in the rendered
    DOM instead), confirming they're genuine regression guards.
  - Full suite: `yarn test` → 68/68 pass.

## L4. The README overstates what "SQL view execute" does

**Commit**: `63b629c`

**What changed**: `README.md`, "Permissions" section. Replaced the
"**SQL view execute** authority — required to read the view's data..."
bullet with one describing what the server actually checks: **data read**
on the SQL view, already granted to every logged-in user by its
`r-r-----` sharing, with the SQL view execute authority explicitly called
out as not being what's enforced (a demo admin without it still reads the
ranking fine; removing data read from the sharing is what produces the
`409 E4312` error). Also added the second sentence the finding suggested
for the same section: on 2.42+, the global app shell requires the
server-generated `M_datadimensiondisabler` authority to open the app at
all.

**Verified**: `npx prettier -c README.md` (part of `yarn lint`) passes;
proofread the corrected text against the finding's own reproduction steps
(no live re-verification needed - this is a documentation-only change and
the underlying server behaviour it describes was already verified by the
review itself).

## L5. `reset()` is a no-op while a call is in flight

**Commit**: `63b629c`

**What changed**: `src/hooks/useEngineMutation.ts` — `reset()` now always
calls `setState({ loading: pendingCalls.current > 0 })`, instead of only
doing anything when `pendingCalls.current === 0`. `error` is dropped
unconditionally (since `setState` replaces the whole state object rather
than merging), while `loading` is still derived from the in-flight
counter rather than hard-coded, so a still-pending call's loading state is
never clobbered. Comment updated to match.

**Test**: new file `src/hooks/useEngineMutation.test.tsx`. The regression
test starts two overlapping `run()` calls against two different mocked
resources, lets the first reject with an error while the second is still
pending (so the current state genuinely has a stale error *and* a call
still in flight - the exact race the finding describes), calls `reset()`,
and asserts `error` is cleared while `loading` stays `true`; it then
resolves the second call and asserts the state settles to
`{ loading: false, error: undefined }`.

Note: a *single* `run()` call already clears `error` at its own start
(`setState({ loading: true, error: undefined })`), so a test with only one
in-flight call at a time cannot observe the bug - reset()'s effect on
`error` would be masked by the call's own reset of it. Two genuinely
overlapping calls are needed to have a stale error and an in-flight call
at the same time, which is why the test manufactures that with two
resources rather than one.

**Verified**:
  - `yarn test --testPathPattern useEngineMutation` → passes with the fix.
  - Sanity check: reverted just `useEngineMutation.ts` and re-ran - fails
    with `expect(received).toBeUndefined() / Received: [Error: 409
    Conflict]` at the `reset()` assertion, confirming the test is a
    genuine regression guard.
  - Full suite: `yarn test` → 68/68 pass.

## L6. Dead parameter kept "for symmetry"

**Commit**: `63b629c`

**What changed**: `src/sql/buildQuery.ts` — dropped the unused `minor`
parameter (and its `eslint-disable-next-line @typescript-eslint/no-unused-vars`)
from `favoriteSourcesFor`, and updated its one caller, `usageSubquery`,
which itself lost the now-unused `minor` parameter it was only forwarding.
`summaryBlock` still takes `minor` (it uses it for `type.table(minor)`) and
its call to `usageSubquery` was updated to the new one-argument signature.
Comment reworded to say the sources are version-independent today and to
re-add the parameter if that ever changes, rather than claiming symmetry.

**Verified**: `yarn test --testPathPattern buildQuery` and the full suite
pass unchanged (query text is byte-for-byte the same, since the removed
parameter was never read); `tsc --noEmit` and `eslint` (both part of
`yarn lint`) pass with no unused-vars warning and no disable comment left
behind.

## Not fixed (left for the maintainer)

L2 (lowercased translated label in `DisableDialog.tsx`), L7 (the SQL
view's world-readable-by-design sharing) and L8 (no fallback message on
the OUTDATED notice for a user who can't update) are unchanged - each is a
design or copy decision the finding itself frames as something for the
maintainer to weigh in on, not a code defect. Their entries in
`REVIEW-FINDINGS.md` are untouched (no "Fixed in" marker).

## Overall verification

  - `yarn lint` (eslint + prettier + tsc) → clean.
  - `yarn test` → 68/68 pass (the original 63, plus 1 for M1, 2 for L3, 1
    for L5 - L1, L4 and L6 are covered by existing tests continuing to pass
    unchanged).
  - `yarn build` → succeeds, produces
    `build/bundle/data-dimension-disabler-1.0.0.zip`.
  - `git status` is clean after committing; nothing under
    `docs/review-2026-09-21/screenshots` was touched.

One incidental, out-of-scope fix: `e2e/README.md` had a pre-existing
Prettier violation (from the commit that added the e2e suite, before this
task started) that made `yarn lint` fail regardless of anything above; it
was reformatted in its own commit (`7ac0818`) so the lint gate is green.
It corresponds to no finding in `REVIEW-FINDINGS.md`.
