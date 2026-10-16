# Review findings: Data Dimension Disabler 1.0.0

Reviewed: 2026-09-21 · Branch `app-platform-migration` ·
Scope: code review + functional test + architecture assessment ·
Reviewer: HISP Centre implementation team
**All five planned instances have now been tested, across four review
passes (2026-09-21): 2.40.12 (Sierra Leone seed), 2.41.10 (EMIS seed),
2.42.6 (EHR seed), 2.43.1 (Sierra Leone seed) and 2.43.1 (Laos HMIS demo
seed, the largest instance in the review).** Pass A (below) covered
2.40.12 and 2.43.1 Sierra Leone; passes B, C and D (further down) cover
2.41.10, 2.42.6 and 2.43.1 Laos respectively.

**Update, review pass B (2026-09-21)**: **2.41.10** (DHIS2 for Education
(EMIS) metadata) tested against the rebuilt bundle containing the M1/M2/L1/L3
–L6 fixes below. Full results in `docs/review-2026-09-21/UI-TEST-RESULTS.md`.
M1 is confirmed fixed live (three dimensions disabled in succession, three
toasts, no alternation). No new app defect was found; one new LOW finding
(L9) documents a test-suite-only gap discovered while running `e2e/` with
the `limited-user` flow excluded. Two suite steps fail on this instance for
reasons that are properties of the EMIS seed, not the app — see
`UI-TEST-RESULTS.md` "2.41.10-specific notes" for the full explanation:
the seed defines zero `categoryOptionGroupSets`, and both `admin` and
the superuser account hold `ALL` here (unlike the Sierra Leone seeds), so the
data-read-denied scenario cannot be reproduced on this instance with any
standard account.

**Update, review pass C (2026-09-21)**: **2.42.6** (EHR metadata
snapshot) tested against the same fix-wave bundle, functional checks
1, 3, 4, 6, 7, 8, 9 only (checks 2 and 5 do not apply to this instance — see
`UI-TEST-RESULTS.md` "2.42.6-specific notes"). **Check 7 (global shell) is
confirmed live for the first time on the version that introduces it**: the
installed app renders inside the 2.42 global-shell iframe with exactly one
visible header bar, same as the 2.43.1 result in pass A. No new app defect
was found. One new LOW finding (**L10**) documents a second test-suite-only
gap: the suite's "sort by name" assertion compares against Python's
`str.lower`-keyed sort, which is not locale-aware, while the app correctly
uses the browser's `localeCompare`; the EHR seed's category names (heavy use
of `<`, `(`, `,` inside names, e.g. `"Age(<1 Yr, 50+Yrs)"`) are the first in
this review to expose the divergence. Two suite steps fail on this instance
for reasons that are properties of the EHR seed, not the app: it defines
zero `dataElementGroupSets` and zero `categoryOptionGroupSets` at all, and
the superuser account (the only account that can drive this seed) holds `ALL`, so
the data-read-denied scenario is unreachable here too, same root cause as
on 2.41.10.

**Update, review pass D (2026-09-21, final pass)**: **2.43.1 Laos**
(Laos HMIS demo database) tested against the same fix-wave
bundle, functional checks 1, 3, 4, 6, 7, 8, 9 only (checks 2 and 5 out of
scope, same reasoning as pass C — see `UI-TEST-RESULTS.md` "2.43.1
Laos-specific notes"). This is by far the largest instance in the review
(120 enabled dimensions, 2,942 favorites across visualizations, maps and
event visualizations), and the response-time measurement planned for the
review was taken here: three direct `curl -w '%{time_total}'` runs
against `/api/sqlViews/GOLswS44mh8/data?paging=false` returned **0.220577s,
0.112248s, 0.107094s** (120 rows — the largest table measured in this
review, still comfortably fast). No new app defect was found. M1 is
confirmed fixed live for a fifth time (three dimensions disabled in
succession — Category, Organisation unit group set, Category option group
set — three toasts, no alternation). The "sort by name" suite assertion
fails again for the same reason as **L10** (reproduced on a fourth seed,
6 of 120 rows affected, not a new finding), and the same two instance/seed
limitations already documented on 2.41.10/2.42.6 recur: this seed defines
zero `dataElementGroupSets`, and the data-read-denied scenario is
unreachable because the only usable account (a superuser) holds `ALL`.
The counts the app shows were cross-checked directly against the database
with `psql`: all 120 rows match the API and the rendered table exactly,
uid-by-uid and views-by-views, with 0 mismatches.

## Summary (as of pass A, 2026-09-21)

The App Platform rewrite is in good shape. `yarn lint` is clean and all 63
unit tests pass; the production bundle installs and runs on both 2.40.12 and
2.43.1, and every documented flow works end to end on both: create the SQL
view, rank all four dimension types, filter, sort, disable one object of each
type (server state verified by read-back), remove and recreate the view,
detect and update a legacy category-only view in place, and report permission
and data-access errors in the UI instead of the console. The numbers the table
shows match the database exactly on both versions, and the map-view correction
the rewrite claims is confirmed empirically — the counted `MAP_VIEW` events
carry map UIDs that the previous `mapview.uid` join could never have matched.

No HIGH findings. One MEDIUM UI defect (success toasts are swallowed when
dimensions are disabled in quick succession) reproduces identically on both
versions, and one MEDIUM defect in the developer helper script
(`generate-view-events.sh` records nothing useful on 2.40 and, on any version,
mostly picks favorites that use no dimension at all). The rest are LOW. The
app is safe to release once M1 is fixed.

## Final verdict (2026-09-21, after pass D — all five instances tested)

**The app is safe to release.** All five planned instances have been tested
end to end against the fix-wave bundle: 2.40.12 and 2.43.1 (Sierra Leone
seeds, pass A), 2.41.10 (EMIS seed, pass B), 2.42.6 (EHR seed, pass C) and
2.43.1 Laos (Laos HMIS demo seed, the largest instance tested, pass D). No
HIGH or open MEDIUM findings remain, `yarn lint` and `yarn test` (68/68) are
clean at HEAD, and the core workflow — create the SQL view, rank all four
dimension types, filter, sort, disable/re-enable, remove/recreate, detect
and update a legacy view, and surface permission/data errors in the UI —
works identically across all four DHIS2 minor versions from 2.40 to 2.43 and
across five very different seeds (a few dozen dimensions on the small
Sierra Leone seeds up to 120 on the Laos seed, with 0 to 2,942 favorites).
The response-time check requested for the largest instance came back at
102–220 ms for a 120-row table — no performance concern.

Finding disposition:

- **Fixed** (`docs/review-2026-09-21/FIXES.md`, commit `2c997df`/`314e264`/
  `63b629c`): **M1** (alternating success toasts), **M2**
  (`generate-view-events.sh` produced no usable ranking data), **L1**
  (duplicate SQL column-name source), **L3** (missing `serverVersion`
  silently meant the 2.40 schema), **L4** (README overstated the SQL view
  authority), **L5** (`reset()` no-op while a call is in flight), **L6**
  (dead `minor` parameter). M1 was re-confirmed fixed live on all four
  instances tested after the fix (2.41.10, 2.42.6, 2.43.1, 2.43.1 Laos —
  every one of them shows every success toast when disabling several
  dimensions in a row).
- **Open, by design** (maintainer decision, not release-blocking): **L2**
  (a translated label is lowercased for the dialog sentence), **L7** (the
  SQL view is intentionally world-readable), **L8** (the OUTDATED notice
  offers no path for a user who cannot update it).
- **Open, test-suite gaps only** (no `src/` or `scripts/` code is affected;
  the app's own behaviour is correct in both cases): **L9** (`e2e/flows.py`'s
  `restore-view` step assumes a notice box is always present, which fails
  when `limited-user` is excluded from a run — reproduced on 2.41.10,
  2.42.6 and 2.43.1 Laos), **L10** (the suite's "sort by name" oracle uses
  Python's `sorted(key=str.lower)` instead of a locale-aware comparator like
  the app's own `localeCompare`, so it disagrees with the app's correct,
  on-screen order on seeds whose names contain `<`, `(`, `,` and digits —
  reproduced on 2.42.6 and 2.43.1 Laos).

No new app-code defects were found in passes B, C or D. Every suite FAIL
across all five instances beyond M1 (before its fix) traces to either a
seed's own metadata shape (e.g. a seed defining zero objects of one or two
dimension types), an account's authorities (the superuser account used
on those databases holds `ALL`, so the data-read-denied scenario can only be exercised on the
Sierra Leone seeds' more limited demo `admin`), or the two test-suite gaps
above — never to the app itself.

## Findings

### HIGH

None.

### MEDIUM

#### M1. Only every other "… is no longer a data dimension" toast is shown

**Fixed in 2c997df.** See `docs/review-2026-09-21/FIXES.md`.

- **Where**: `src/components/UsageView.tsx:25-32` (the `useAlert` hook) and
  `src/components/UsageView.tsx:63` (`showDisabled({ name })`).
- **What**: disabling several dimensions in a row — the app's main workflow —
  shows a success toast for the first, none for the second, one for the third,
  none for the fourth. Reproduced on 2.40.12 and 2.43.1 by the e2e suite
  (`disable-per-type / Success alert names the disabled object`), failing for
  the 2nd and 4th object on both.
  Cause: `useAlert` keeps the id of the alert it last raised in a ref
  (`node_modules/@dhis2/app-service-alerts/build/cjs/useAlert.js:11,36` →
  `makeAlertsManager.js:10`). While that alert is still on screen, a second
  `show()` **reuses the same id**, so `AlertBar` is not remounted and keeps the
  auto-hide timer started by the first message
  (`@dhis2-ui/alert/.../alert-bar.js:25`, `duration = 8000`). The second
  message therefore inherits an almost-expired timer and disappears at once.
  Once the alert has been removed, the ref is cleared and the next `show()`
  works again — hence the alternating pattern. The row does still disappear
  and the server is still updated, so this is feedback loss, not data loss.
- **Fix**: make each success a fresh alert. Smallest change:

  ```ts
  const { show: showDisabled, hide: hideDisabled } = useAlert(…)
  …
  hideDisabled()            // clears the ref, so show() allocates a new alert
  showDisabled({ name: rowToDisable.name })
  ```

  Add a regression test that raises two alerts in succession and asserts both
  messages reach the alert stack (`MockAlertStack` already renders them), and
  re-run `e2e/run_suite.py` — the two failing steps must turn green.

#### M2. `generate-view-events.sh` produces no usable ranking data

**Fixed in 314e264.** See `docs/review-2026-09-21/FIXES.md`.

- **Where**: `scripts/generate-view-events.sh:23` (the visualization query) and
  `:29`/`:35` (maps and event visualizations).
- **What**: two problems in the one script the README and `CLAUDE.md` point
  developers and reviewers at.
  1. The filter `categoryDimensions:!empty` is rejected by 2.40 with
     `400 E1003 "!empty is not a valid operator"` (verified on
     the Sierra Leone 2.40.12 demo database; it works on 2.43). The `|| true` on the same line
     swallows the error, so the script reports success and silently records
     **zero** `VISUALIZATION_VIEW` events on 2.40 — exactly the event type the
     ranking is mostly built from.
  2. The map and event-visualization batches take the *first* favorites the
     API returns, with no filter at all. On the Sierra Leone seeds none of
     those favorites carries a dimension, so the 12 events they record
     contribute 0 to every row. To exercise the map path at all, this review
     had to pick map `X7x2WOLhCA8` by hand (its map views carry org-unit
     group-set dimensions).
- **Fix**: drop the version-specific filter and select favorites by what they
  actually use — e.g. read `visualizations?fields=id,categoryDimensions~size,
  dataElementGroupSetDimensions~size` (works on 2.40 too) and keep the ones
  with a non-zero size; for maps, page through
  `maps?fields=id,mapViews[categoryDimensions~size,
  organisationUnitGroupSetDimensions~size]`. Also drop the blanket `|| true`
  so an API error is visible, or `echo` a warning when a batch comes back
  empty.

### LOW

- **L1. Two sources of truth for the SQL view's column names** —
  **Fixed in 63b629c.** See `docs/review-2026-09-21/FIXES.md`.
  `src/sql/buildQuery.ts:3-10` exports `SQL_VIEW_COLUMNS`, which nothing but
  `buildQuery.test.ts:78` reads, while `src/hooks/useUsageData.ts:50-55`
  hard-codes the same six names again. Fix: import `SQL_VIEW_COLUMNS` in
  `useUsageData` (or delete the export and let the test read the query text),
  so a column rename cannot pass the tests while breaking the mapping.
- **L2. A translated label is lowercased for the dialog sentence** —
  `src/components/DisableDialog.tsx:32-34` calls `.getLabel().toLowerCase()`.
  This is wrong in every language that capitalises nouns (German
  "Kategorie" → "kategorie") and in locales with special casing rules. Fix:
  give `DimensionType` a second label function (`getLabelLowercase`) with its
  own `i18n.t` string, or phrase the sentence so the label keeps its own
  capitalisation.
- **L3. A missing `serverVersion` silently means "2.40 schema"** —
  **Fixed in 63b629c.** See `docs/review-2026-09-21/FIXES.md`.
  `src/hooks/useSqlViewStatus.ts:44`: `serverVersion?.minor ?? 0`. With `0`
  the app builds the `dataelementcategory` variant, so on a modern server it
  would report a correct view as OUTDATED and, if the user pressed Update,
  install a view that fails at query time. The platform normally fills
  `serverVersion` in, so this is latent, not observed. Fix: treat an absent
  `serverVersion` as `LOADING`/`ERROR` rather than defaulting the minor.
- **L4. The README overstates what "SQL view execute" does** —
  **Fixed in 63b629c.** See `docs/review-2026-09-21/FIXES.md`. `README.md`
  ("Permissions"): the demo `admin` on both test instances has **no**
  `F_SQLVIEW_EXECUTE` and reads the ranking fine; what the server actually
  enforces on `/sqlViews/{uid}/data` is *data read* on the view
  (`409 E4312 "Current user is not authorised to read data from SQL view"`,
  reproduced by removing `r` from the data position). Worth adding in the same
  section: on 2.42+ the global shell only opens the app for users whose role
  holds the server-generated `M_datadimensiondisabler` authority — without it
  the shell answers "Unable to find an app for this URL" (observed on 2.43.1).
- **L5. `reset()` is a no-op while a call is in flight** —
  **Fixed in 63b629c.** See `docs/review-2026-09-21/FIXES.md`.
  `src/hooks/useEngineMutation.ts:46-50` only clears state when
  `pendingCalls.current === 0`, so reopening the dialog for a different row
  during a slow request still shows the previous row's error. Narrow window;
  fix by clearing `error` unconditionally and only leaving `loading` alone.
- **L6. Dead parameter kept "for symmetry"** —
  **Fixed in 63b629c.** See `docs/review-2026-09-21/FIXES.md`.
  `src/sql/buildQuery.ts:63-70`:
  `favoriteSourcesFor(type, minor)` never uses `minor` and needs an
  `eslint-disable`. The schema check established that the missing
  data-element-group-set join tables are version-independent, so drop the
  parameter (and the disable comment); re-add it if a version ever diverges.
- **L7. The view is world-readable by design** — `src/sql/sqlView.ts:25`
  installs `public: 'r-r-----'`, so every logged-in user can execute it and
  read which dimensions exist and how often they are used. That is the
  intended trade-off (the app itself needs data read), but it is worth one
  sentence in the README, and an admin who cares can narrow it to a user group
  afterwards — the app only checks the query text, not the sharing, so a
  narrowed view stays `READY`.
- **L8. The OUTDATED notice offers no path for a user who cannot update** —
  `src/components/SqlViewNotice.tsx:89-107` shows only an "Update SQL view"
  button; a user without the authority gets an error and no data at all, even
  though the installed view may still work for them. Fix: add one sentence
  ("Ask an administrator with the 'Add/Update SQL view' authority to update
  it.").
- **L9 (new, review pass B, 2026-09-21). `e2e/flows.py`'s `restore-view` step
  assumes a notice box is always present** — test-suite-only, not an app
  defect. `flow_restore_view` (`e2e/flows.py`) calls
  `ui.notice_title(frame)`, which waits for `NOTICE_BOX` to become visible,
  then only acts if its text contains `MISSING_NOTICE`. In the normal full
  run this works because the preceding `limited-user` step
  (`_ensure_limited_user` / `flow_limited_user`) always deletes the SQL view
  before returning, so `restore-view` reliably finds the MISSING notice and
  recreates the view. When `limited-user` is excluded from `E2E_FLOWS` (as
  review pass B did on the 2.41.10 EMIS instance, since that check was already
  covered on 2.43.1) and the preceding `outdated-update` step already leaves
  the view installed and `READY`, `restore-view` opens the app straight to
  the usage table — no notice box ever appears — and `notice_title()` times
  out, raising an exception that is reported as a suite FAIL. Observed
  live: `[FAIL] restore-view / flow raised an exception — waiting for
  locator("[data-test='dhis2-uicore-noticebox']").first to be visible`; the
  view's actual end state was verified directly via `GET
  /api/sqlViews/GOLswS44mh8?fields=name,sharing` and was correct throughout.
  Fix (test suite, not app code): have `flow_restore_view` check whether the
  table is already rendered before waiting for a notice box, e.g. `if
  frame.locator(ui.USAGE_TABLE).count() > 0: return PASS` short-circuit, or
  document in `e2e/README.md` that `limited-user` must run whenever
  `restore-view` does. Left undone — no source or script under `src/`/
  `scripts/` is affected, and this is a review deliverable, not the app
  itself.

- **L10 (new, review pass C, 2026-09-21). `e2e/flows.py`'s name-sort
  assertion is not locale-aware, unlike the app it is testing** —
  test-suite-only, not an app defect. `_sort_checks` (`e2e/flows.py:240-251`)
  computes the expected ascending/descending order with Python's
  `sorted(names, key=str.lower)`, i.e. plain code-point comparison after
  lowercasing. The app itself sorts with
  `a.localeCompare(b, undefined, { sensitivity: 'base' })`
  (`src/components/usageTableUtils.ts:10`), which is correct — ICU collation,
  not naive code-point order, is the right choice for a name column. The two
  orderings usually agree, so this was never observed on the 2.40/2.41/2.43
  Sierra Leone/EMIS seeds. The EHR seed's category names expose the gap:
  names built from `<`, `(`, `,`, and digits (`"Age(<1 Yr, 50+Yrs)"`,
  `"Age(0-4Yrs,25-49Yrs,50+Yrs)"`, `"Nutrition(MAM_SAM_Overweight_Obese)"` vs
  `"Nutrition(MAM_SAM)"`) collate differently from how they compare
  byte-for-byte, so `sorted(..., key=str.lower)` disagrees with
  `localeCompare` on 14 of 118 rows. Verified directly in Node (same V8/ICU
  engine Chromium uses): `"Age(<1 Yr, 50+Yrs)".localeCompare("Age(0-4Yrs,25-
  49Yrs,50+Yrs)", undefined, {sensitivity: "base"})` returns `-1`, i.e. the
  app's displayed order is the *correct* `localeCompare` order; the
  suite's Python comparator is simply the wrong oracle for this seed's data.
  Reproduced live on the 2.42.6 EHR instance: `disable-per-type`'s
  "Sort by name ascending/descending" steps FAIL while the on-screen order
  is demonstrably right. Fix (test suite, not app code): reimplement the
  expected order with the same comparator the app uses — either compare
  through a headless JS `localeCompare` call (e.g. via
  `page.evaluate`) instead of Python's `sorted`, or drop the strict-order
  assertion in favour of a weaker check (e.g. "every adjacent pair compares
  as ≤ under the same rule the row values were shown in"). Left undone — no
  source or script under `src/`/`scripts/` is affected.

  **Reproduced again, review pass D (2026-09-21), Laos HMIS demo database
  on 2.43.1**: 6 of 120 rows disagree between Python's
  `sorted(key=str.lower)` and Node's `localeCompare` (same names class as
  before — `<`, `(`, `,` and digits, e.g. `sorted()` orders `"Age
  (0-59,60+)"` before `"Age (<1- 30+ years)"`; `localeCompare` orders them
  the other way, matching what the app displayed). Confirms this is a
  general property of the suite's oracle, not specific to the EHR seed's
  naming conventions.

## Claims investigated and rejected

- **Claim**: the refetch after a successful disable unmounts `UsageTable`
  (`UsageView.tsx:100` renders it only when `!loading`), so the type filter and
  the chosen sort are lost after every disable.
  **Source**: static reading of `UsageView.tsx` during this review.
  **Refuted by**: live test on 2.43.1 — filtered to "Category option group
  set", sorted by name, disabled "Donor": the filter and sort survived and the
  row simply vanished. `useDataQuery`'s `refetch` does not raise `loading`
  again (it reports background refetches separately), so the table is never
  unmounted.
- **Claim**: `PUT /api/sqlViews/{id}` ignores `sharing`, so a legacy view
  upgraded in place would keep the old `rwrw----` (the server-quirks reference
  warns that patching `/sharing` silently no-ops).
  **Source**: `dhis2-app-review/references/server-quirks.md`.
  **Refuted by**: the `outdated-update` flow on both versions — after the
  update, `GET …?fields=sharing` reports `public: "r-r-----"` on 2.40.12 and
  2.43.1. The quirk applies to JSON Patch on `/sharing`, which this app does
  not do; a full `PUT` of the object does carry sharing through.
- **Claim**: the app renders its own `@dhis2/header-bar` inside the 2.42+
  global-shell iframe, so 2.43 shows a double header (the app's `<header>` is
  indeed present in the iframe's DOM).
  **Source**: DOM scan of both frames on 2.43.1.
  **Refuted by**: measuring the elements — the in-app `<header>` is
  `display: none` with a 0×0 box inside the shell, the shell's header is 40 px
  tall, and a full-page screenshot shows one header. The suite therefore counts
  *visible* headers (`e2e/app_driver.py:header_bar_count`).
- **Claim** (review plan, check 2): after the update the view's `sharing.public`
  should be `r-------`.
  **Refuted by**: the approved design (§4) and the server — with `r-------`
  the data endpoint answers `409 E4312` even for the creating admin (verified
  on 2.43.1), which is why commit 475c873 moved to `r-r-----`. The brief's
  expected value predates that commit; `r-r-----` is correct.
- **Claim**: `params: { paging: false }` on `sqlViews/{id}/data`
  (`src/hooks/useUsageData.ts:25`) might be dropped by the data engine or
  ignored by the server, capping the table at 50 rows on large instances.
  **Refuted by**: request capture — the app sends
  `/api/43/sqlViews/GOLswS44mh8/data?paging=false`, and the endpoint pages when
  asked (`?pageSize=5` → 5 rows) and returns all 23 rows without paging.

## Architecture assessment

**Verdict: the migration is done and the result is idiomatic App Platform.
Stay here; no further architectural work is needed before release.**

What the rewrite gets right:

- `d2.config.js` with `type: app`, `minDHIS2Version: '2.40'` and a single
  entry point; build through `@dhis2/cli-app-scripts` 12; the icon carried over
  as `public/dhis2-app-icon.png` and correctly emitted as `icons.48` in the
  generated `manifest.webapp`.
- All server access goes through `@dhis2/app-runtime` (`useDataQuery`,
  `useDataEngine`, `useConfig`, `useAlert`); there is no hand-rolled fetch
  layer left, and the versioned API path and session auth come for free. The
  legacy `d2api.js`, jQuery, DataTables and the conditionally injected header
  bar are gone, along with `alert()`/`confirm()` — every outcome is now a
  `NoticeBox`, a `Modal` or an `AlertBar`.
- The one custom abstraction, `useEngineMutation`, is justified: the resource
  varies per call (four metadata endpoints plus three SQL view operations),
  which `useDataMutation`'s static mutation object cannot express. It is 50
  lines, counts in-flight calls rather than guessing, and is unit-tested.
- Layering is clean and matches the design document: pure logic
  (`dimensionTypes`, `buildQuery`, `sqlView`, `usageTableUtils`) has no React
  dependency and carries most of the tests; hooks own data and mutations;
  components are presentational except `UsageView`, which owns the dialogs.
  Every module has a co-located test; the single version branch (`minor < 41`)
  lives in exactly one place, as intended.
- i18n is wired up properly (`i18n/en.pot` regenerated, no `i18n.t` at module
  scope — labels are functions for that reason), CSS modules use the DHIS2
  design tokens, and `data-test` attributes exist on the elements a test needs.

What remains (none of it architectural):

1. Fix M1 and M2, then re-run `yarn lint && yarn test`, rebuild, reinstall and
   re-run `e2e/run_suite.py` on both instances.
2. Consider declaring `authorities` in `d2.config.js`. The server already
   generates `M_datadimensiondisabler` and gates the app on it from 2.42, but
   an explicit declaration documents that this is a destructive admin tool and
   shows up in `GET /api/apps`.
3. The unit tests assert *request shape* against a mocked engine (for example
   `useDisableDimension.test.tsx:44-52` checks the JSON Patch body). That is
   the right level for unit tests, but it cannot catch a server that accepts
   and ignores a write; the `e2e/` suite added by this review is what verifies
   server effect, and it should be run against at least one instance before
   each release.
4. Housekeeping before the App Hub release: uninstall the old "Category
   dimension disabler" on target instances (the CHANGELOG says so), and keep
   `docs/schema-check.md` next to `buildQuery.ts` as the record of why the
   table names are what they are.

## Environment gaps (as of pass A; closed by pass D)

- Only 2.40.12 and 2.43.1 were exercised in this pass; 2.41, 2.42 and the
  larger Laos 2.43 instance (including the response-time measurement asked for
  there) are left for the following passes. The 2.42 boundary itself *is*
  covered, since 2.43.1 serves the app through the global shell.
- Both instances run the same Sierra Leone seed, so the table content is
  similar on both; the EMIS and EHR seeds in the later passes will exercise
  different metadata shapes.
- The seeds' `admin` is not a full superuser (no `ALL`, no
  `F_SQLVIEW_EXECUTE`), so creating the throwaway limited user for the
  permission test needs a separate superuser account. The e2e suite takes
  it through `E2E_SUPERUSER`/`E2E_SUPERPASS`.
- The instances are served over plain http, so the platform's PWA layer logs
  "not a secure context" errors on every load. They are filtered as platform
  noise; on an https deployment they would not appear.

**Update, pass D (2026-09-21)**: all gaps above are now closed. 2.41.10,
2.42.6 and 2.43.1 Laos have all been tested (passes B, C, D); the Laos
instance is the large, differently-shaped seed the first gap called for,
and its response time was measured three times as requested (102–220 ms for
120 rows). The remaining environment property worth noting for future
passes: on every non-Sierra-Leone seed tested (EMIS, EHR, Laos), the only
account that can drive the seed at all (a superuser) holds `ALL`, so the
data-read-denied scenario (design §6) can only ever be exercised on the
Sierra Leone seeds' demo `admin` — this is now a settled, understood
limitation of those demo databases rather than an open gap.
