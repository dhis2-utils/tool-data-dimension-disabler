# UI test results: Data Dimension Disabler 1.0.0

Tested: 2026-09-21 · Driven as the **installed production bundle**
(`build/bundle/data-dimension-disabler-1.0.0.zip` at
`<base>/api/apps/data-dimension-disabler/index.html`), not the dev server ·
Suite: `e2e/run_suite.py` (Python Playwright, Chromium 153)

Every row below is one step of that suite. The suite asserts against the Web
API as well as the DOM, so "PASS" means the screen and the server agree.
All five instances have now been tested: 2.40.12 and 2.43.1 (Sierra Leone
seeds) in pass A, 2.41.10 (EMIS) in pass B, 2.42.6 (EHR) in pass C, and
2.43.1 Laos in the final pass D (2026-09-21) against the `lao_hmis_demo v43`
seed — the largest instance in the review (120 enabled dimensions, 2,942
favorites). Only functional checks 1, 3, 4, 6, 7, 8 and 9 were run on
2.42.6 and on the Laos instance — checks 2 (outdated-view detection) and 5
(limited-user permission error) do not apply to either instance (check 2
was covered on 2.41.10, check 5 on 2.43.1 Sierra Leone, per the review
plan); see "2.42.6-specific notes" and "2.43.1 Laos-specific notes" below.

Only the main table screenshot per instance is kept in the repository; the
full set (51 files) was delivered to the maintainer separately.

## Instances

All instances were local throwaway instances, one per database.

| Label | DHIS2 version | Database |
|---|---|---|
| 2.40.12 | 2.40.12 (rev 82b6022) | Sierra Leone 2.40 demo database |
| 2.41.10 | 2.41.10 (rev 1a3484f) | DHIS2 for Education (EMIS) metadata snapshot, July 2026 |
| 2.42.6 | 2.42.6 (rev dd8bdbb) | EHR metadata snapshot, July 2026 |
| 2.43.1 | 2.43.1 (rev 9cbfbf3) | Sierra Leone 2.43 demo database |
| 2.43 Laos | 2.43.1 (rev 9cbfbf3) | Laos HMIS demo database (large) |

Test data on both Sierra Leone instances: 23 objects with `dataDimension =
true` (12 categories, 4 org unit group sets, 5 data element group sets, 2
category option group sets), plus favorite-view events recorded through
`POST /api/dataStatistics` — including 7 `MAP_VIEW` events on map
`X7x2WOLhCA8`, whose map views carry org-unit-group-set dimensions, so the
`mapmapviews` correction is actually exercised (see "Counts verified against
SQL" below).

**2.41.10 (EMIS seed) test data is different in kind, not just size**: the
seed enables 70 objects as data dimensions (62 categories, 7 org unit group
sets, 1 data element group set, **0 category option group sets — the seed
defines none at all**, confirmed by `GET /api/categoryOptionGroupSets`
returning `pager.total: 0`). The seed also has **no `visualizations` and no
`maps`** (`pager.total: 0` for both), only `eventVisualizations` (125 of
them). `scripts/generate-view-events.sh` therefore only ever records
`EVENT_VISUALIZATION_VIEW` events here; see "M2 live check" below. These are
data limitations of the seed, not app defects — recorded per-row below.

**2.43.1 Laos (`lao_hmis_demo v43`) is the largest instance in the review,
by a wide margin.** The seed enables 120 objects as data dimensions (60
categories, 20 org unit group sets, **0 data element group sets — the seed
defines none at all**, confirmed by `GET /api/dataElementGroupSets` →
`pager.total: 0`, and 40 category option group sets) and carries 2,392
`visualizations`, 497 `maps` and 53 `eventVisualizations` — none of the
other four seeds combined comes close. `scripts/generate-view-events.sh`
recorded events against all three favorite kinds here for the first time
in the review (5/4/3/2/1 `VISUALIZATION_VIEW`, 3/2/1 `MAP_VIEW`, 0
`EVENT_VISUALIZATION_VIEW` — this seed's event visualizations happen to
carry no dimensions). The installed view already carried a substantial
amount of pre-existing `datastatisticsevent` history from the seed itself
(the 12-month window totals 55 views across 7 non-zero rows, not just the
21 added by this pass's script run), which is a property of the seed's
data, not a defect.

## Results

| Step | 2.40.12 | 2.41.10 | 2.42.6 | 2.43.1 | 2.43 Laos | Notes |
|---|---|---|---|---|---|---|
| Fresh load shows the "SQL view not installed" notice | PASS | PASS | PASS | PASS | PASS | |
| Exactly one header bar renders | PASS | PASS | PASS | PASS | PASS | 2.40/2.41 top level; 2.42/2.43 (both seeds) inside the global-shell iframe, the app's own header hidden by the shell — no double header |
| Create SQL view yields the usage table | PASS | PASS | PASS | PASS | PASS | `*-02-table.png` |
| Created view has the expected name and `r-r-----` sharing | PASS | PASS | PASS | PASS | PASS | `name='Data dimension usage'` |
| `/sqlViews/{id}/data` responds | PASS (23 rows) | PASS (70 rows) | PASS (118 rows) | PASS (23 rows) | PASS (120 rows) | Laos is now the largest table in the review |
| Response time of `/sqlViews/{id}/data` | 106 ms | 98 ms | 132 ms | 116 ms | 220/112/107 ms (3 runs) | INFO; measured three times with `curl -w '%{time_total}'` on Laos per the review plan — first run 220 ms (cold), then 112 ms and 107 ms; 120 rows, the largest table in the review, still well under 250 ms |
| Table row count matches the payload | PASS (23/23) | PASS (70/70) | PASS (118/118) | PASS (23/23) | PASS (120/120) | `paging=false` is sent and honoured |
| Row count label matches the rows shown | PASS | PASS | PASS | PASS | PASS | "23 enabled dimensions" on 2.40/2.43; "70" on 2.41; "118" on 2.42; "120 enabled dimensions" on 2.43 Laos |
| Every row shows the view count the server returned | PASS | PASS | PASS | PASS | PASS | |
| All four dimension types appear | PASS | **FAIL** | **FAIL** | PASS | **FAIL** | 2.41: only 3 types shown (Category, Org unit group set, Data element group set) — **not an app bug**: the EMIS seed defines **zero** `categoryOptionGroupSets` at all (`GET /api/categoryOptionGroupSets` → `pager.total: 0`), so that type can never have a row here. Filter dropdown still offers it (next row) and correctly shows 0 rows. 2.42: only **2** types shown (Category, Org unit group set) — the EHR seed defines **zero** `dataElementGroupSets` **and** zero `categoryOptionGroupSets` at all (`pager.total: 0` for both). 2.43 Laos: only **3** types shown (Category, Org unit group set, Category option group set) — this seed defines **zero** `dataElementGroupSets` at all (`pager.total: 0`) |
| Filter "Category" | PASS (12) | PASS (62) | PASS (110) | PASS (12) | PASS (60) | |
| Filter "Organisation unit group set" | PASS (4) | PASS (7) | PASS (8) | PASS (4) | PASS (20) | |
| Filter "Data element group set" | PASS (5) | PASS (1) | PASS (0) | PASS (5) | PASS (0) | Laos: 0 rows shown, 0 expected — correct, seed has no objects of this type |
| Filter "Category option group set" | PASS (2) | PASS (0) | PASS (0) | PASS (2) | PASS (40) | 2.41/2.42: 0 rows shown, 0 expected — correct, neither seed has any object of this type |
| Sort by name, ascending / descending | PASS | PASS | **FAIL** | PASS | **FAIL** | 2.42 and 2.43 Laos: finding **L10** — the on-screen order is the correct `localeCompare` order; the suite's Python `sorted(key=str.lower)` oracle disagrees on a handful of rows whose names contain `<`, `(`, `,` and digits (2.42: 14/118 rows; Laos: 6/120 rows, e.g. `"Age (0-59,60+)"` vs `"Age (<1- 30+ years)"`), confirmed by reproducing the same comparison in Node (same engine Chromium uses) — 0 mismatches once the two orderings are compared with a locale-aware comparator |
| Sort by views, ascending / descending | PASS | PASS | PASS | PASS | PASS | 2.40 top: 15/8/7; 2.41 top: 13/11/9; 2.42 top: 15/12/6; 2.43 top: 30/20/7; 2.43 Laos top: 42/6/2 |
| Disable dialog names the object and its type (all four types) | PASS | PASS (3 of 4) | PASS (2 of 2) | PASS | PASS (3 of 3) | 2.41: Category option group set **SKIPPED** (no enabled object of that type exists to disable); 2.42: Data element group set and Category option group set **SKIPPED** (neither type has any object at all on this seed); 2.43 Laos: Data element group set **SKIPPED** (no objects of that type exist at all on this seed) |
| Row disappears after confirming (all four types) | PASS | PASS (3 of 4) | PASS (2 of 2) | PASS | PASS (3 of 3) | 2.41/2.42/Laos: same skips as above |
| Server reports `dataDimension=false` (all four types) | PASS | PASS (3 of 4) | PASS (2 of 2) | PASS | PASS (3 of 3) | verified per type via `GET /api/<resource>/<uid>?fields=dataDimension`; 2.41/2.42/Laos: same skips as above |
| Success alert names the disabled object | **FAIL (2 of 4)** | **PASS (3 of 3 disabled)** | **PASS (2 of 2 disabled)** | **FAIL (2 of 4)** | **PASS (3 of 3 disabled)** | finding **M1**, fixed in `2c997df`. 2.41 disabled Category, Org unit group set, and Data element group set in succession — all three toasts appeared. 2.42 disabled Category then Organisation unit group set — both toasts appeared. 2.43 Laos disabled Category ("AFI - Screening form age group"), Organisation unit group set ("50 Districts of EPI (P-DLI8)") and Category option group set ("Age (0-59,60+)") in succession — **all three toasts appeared**, re-confirming the fix on the fifth and final instance |
| Re-enable each disabled dimension (cleanup) | PASS | PASS | PASS | PASS | PASS | JSON Patch `value: true`, verified by read-back |
| Remove SQL view returns to the create notice | PASS | PASS | PASS | PASS | PASS | view really deleted (`404`) |
| Creating the view again restores the table | PASS | PASS | PASS | PASS | PASS | |
| Data-read error (409 E4312) shows the server message | PASS | **FAIL** | **FAIL** | PASS | **FAIL** | 2.42/Laos screenshots instead show the table — the error state is never reached. **Not an app bug — instance limitation**: on this EMIS seed, `admin` (and the separate superuser account) both hold the `Superuser` role with `ALL`, and `admin` is also the SQL view's owner; DHIS2 grants owners/superusers full access regardless of `sharing.public`, so setting `public: r-------` has no effect when driven as either account and `/data` keeps answering 200. Unlike the Sierra Leone seeds' limited demo `admin`, no standard account on this instance can be denied data read. Confirmed by `GET /api/me` as both accounts: both report `authorities: ["ALL"]`. 2.42/Laos: same root cause — `admin` rejects Basic auth outright on both seeds (401), and the only usable account, a separate superuser, also holds `ALL`. Because the flow raised an exception before its own cleanup step, it left the view's sharing at `r-------` on all three; restored to `r-r-----` by hand and verified on each (see STATE-CHANGES.md) |
| "Remove SQL view" stays available in the error state | PASS | N/A | N/A | PASS | N/A | not reached — the error state above never occurs on this instance |
| Retry loads the table once access is restored | PASS | N/A | N/A | PASS | N/A | not reached, same reason |
| Legacy category-only view detected as outdated | PASS | PASS | N/A | PASS | N/A | 2.41 verified with **two** legacy definitions: the suite's synthetic one (`legacy_sql_view.py`) during the automated run, and separately, by hand, the actual historical `sql_view_41` object from `git show 7b8c7e1:src/app.js` (Task 14 step 4). 2.42/Laos: check 2 not run per review plan (already covered on 2.41.10 and, in pass A, on 2.43.1 Sierra Leone) |
| Update renames the view in place (same UID) | PASS | PASS | N/A | PASS | N/A | `Category dimension usage` → `Data dimension usage`, UID `GOLswS44mh8` kept |
| Update sets public sharing to `r-r-----` | PASS | PASS | N/A | PASS | N/A | PUT does change sharing on all versions tested (was `rwrw----`) |
| User without the SQL view authority: server message shown | PASS | SKIPPED | SKIPPED | PASS | SKIPPED | check 5 skipped on 2.41, 2.42 and Laos per review plan — already verified on 2.43.1 Sierra Leone |
| …and the "Add/Update SQL view" authority is named | PASS | SKIPPED | SKIPPED | PASS | SKIPPED | |
| …and the app does not crash | PASS | SKIPPED | SKIPPED | PASS | SKIPPED | no page errors |
| SQL view left installed at the end | PASS | PASS | PASS | PASS | PASS | 2.41/2.42/Laos: the suite's own `restore-view` step raised an exception (finding **L9**; see notes below the table) but the view's actual state was verified directly via `GET /api/sqlViews/GOLswS44mh8?fields=name,sharing` → installed, correct name and `r-r-----` sharing on all three |
| No unexpected console errors | PASS | PASS | PASS | PASS | PASS | |
| No React duplicate-key warnings | PASS | PASS | PASS | PASS | PASS | |
| No unexpected HTTP error responses | PASS | PASS | PASS | PASS | PASS | |

Totals per instance: **46 PASS / 2 FAIL / 2 INFO** on 2.40.12 and on 2.43.1
(pass A, before the M1/M2 fixes). **2.41.10 (pass B, after the fixes, 36
doc rows): 28 PASS / 2 FAIL / 3 SKIPPED / 2 N/A / 1 INFO** — see
"2.41.10-specific notes" below; both FAILs are instance/seed limitations, not
app defects, and the step that failed under pass A (M1) now passes (3 of 3
toasts shown, disabling three dimension types in succession). **2.42.6
(pass C, same fix-wave bundle, 36 doc rows, checks 2 and 5 out of scope):
24 PASS / 3 FAIL / 5 N/A / 3 SKIPPED / 1 INFO** — see "2.42.6-specific
notes" below; all three FAILs are instance/seed limitations, not app
defects, and M1 is confirmed fixed again live (2 of 2 toasts shown,
disabling two dimension types in succession — this seed only has enabled
objects of two of the four types). Raw suite tallies (finer-grained than the
doc rows, and including the steps a flow-level exception short-circuits) are
`{'PASS': 27, 'INFO': 1, 'FAIL': 5, 'SKIP': 2}` for 2.42.6, in
`e2e/results/results-2.42.6.json` (gitignored, not committed). **2.43.1 Laos
(pass D, final pass, same fix-wave bundle, 36 doc rows, checks 2 and 5 out
of scope): 24 PASS / 3 FAIL / 5 N/A / 3 SKIPPED / 1 INFO** — see "2.43.1
Laos-specific notes" below; all three FAILs are instance/seed limitations,
not app defects, and M1 is confirmed fixed again live (3 of 3 toasts shown,
disabling three dimension types in succession — this seed only has enabled
objects of three of the four types). Raw suite tally for Laos:
`{'PASS': 31, 'INFO': 1, 'FAIL': 5, 'SKIP': 1}`, in
`e2e/results/results-2.43-lao.json` (gitignored, not committed).

## Version-specific failures

None in the app itself across 2.40.12, 2.41.10, 2.42.6, 2.43.1 and 2.43.1
Laos — all five instances tested in this review. Every difference observed
is in the platform or the seed data:

- **App hosting**: 2.40/2.41 serve `/api/apps/…/index.html` at top level;
  from **2.42** the instance wraps the app in the global-shell iframe (2.43
  does the same). The app renders its own `@dhis2/header-bar` in all cases;
  from 2.42 the shell hides it (`display: none`), so exactly one header bar
  is visible everywhere. **2.42.6 is the first instance in this review where
  the global shell is confirmed live** (it was previously verified only on
  2.43.1, one version past the boundary) — `page.frames` reports more than
  one frame and exactly one `<header>` is visible across all of them, same
  mechanism and same result as 2.43.1.
- **SQL**: the view installed on 2.40 uses `dataelementcategory`, 2.41/2.42/
  2.43 use `category`, as the version branch intends. All execute.
- **Writes**: JSON Patch `dataDimension` and `PUT /api/sqlViews/{id}` behave
  identically on both sides of the 2.42 boundary.

M1 (pass A finding, fixed in `2c997df`) reproduced identically on 2.40.12 and
2.43.1 and is confirmed fixed live on 2.41.10 (three disables in a row, three
toasts), on 2.42.6 (two disables in a row, two toasts — this seed only has
enabled objects of two of the four types), and on 2.43.1 Laos (three
disables in a row, three toasts — this seed only has enabled objects of
three of the four types), the fifth and final instance in this review.

## 2.41.10-specific notes (review pass B)

Two rows differ from the "all versions behave the same" pattern above, and
both are properties of the **EMIS ("edu-meta") seed**, not the app or the
DHIS2 version:

1. **No `categoryOptionGroupSets` exist in this seed at all**
   (`GET /api/categoryOptionGroupSets` → `pager.total: 0`), so that dimension
   type never has a row, is skipped wherever the suite would otherwise
   disable/re-enable an object of that type, and "all four types appear"
   fails by construction. The filter for that type still works correctly
   (shows 0 rows, as expected).
2. **The data-read-error scenario cannot be reproduced on this instance
   with any standard account.** Both `admin` and the separate superuser
   account hold the `Superuser` role with the `ALL` authority here (unlike the
   Sierra Leone seeds, whose demo `admin` has neither `ALL` nor
   `F_SQLVIEW_EXECUTE`), and `admin` is also the SQL view's owner. DHIS2
   grants owners and `ALL`-holders full access regardless of an object's
   `sharing.public`, so setting the view's sharing to `r-------` has no
   effect when driven as either account — `/sqlViews/{id}/data` keeps
   returning 200 with the full grid. This was confirmed directly: `GET
   /api/me` as `admin` returns `{"id":"M5zQapPyTZI", ...,
   "userRoles":[{"name":"Superuser","authorities":["...","ALL",...]}]}`,
   and the SQL view's `sharing.owner` is the same `M5zQapPyTZI`; `GET
   /api/me` as the superuser account returns `authorities: ["ALL"]` too. The two
   downstream steps that depend on reaching the error state ("Remove SQL
   view stays available" and "Retry recovers") were consequently not
   reached and are marked N/A rather than FAIL.
3. A related, harmless artifact: because check 5 (limited user) was
   intentionally skipped on this instance (already covered on 2.43.1), the
   suite's own `restore-view` step — which normally relies on the preceding
   `limited-user` step having deleted the view first — found the view
   already installed and `READY` (table rendered, no notice box to click
   through) and raised a "waiting for noticebox" exception. This is a gap in
   how the suite's flows compose when `limited-user` is excluded via
   `E2E_FLOWS`, not an app defect: the view's actual end state was verified
   directly via the API (installed, correct name, `r-r-----` sharing) and is
   fine.

## 2.42.6-specific notes (review pass C)

Checks 2 (outdated-view detection) and 5 (limited-user permission error)
were out of scope for this instance per the review plan (check 2 was
exercised on 2.41.10, check 5 on 2.43.1) — Task 14 step 4 (installing the
legacy view) was correspondingly not run on the 2.42.6 instance, and the
`outdated-update` and `limited-user` suite flows were excluded via
`E2E_FLOWS`. All corresponding doc rows are N/A/SKIPPED, not FAIL. Four
things differ from the "all versions behave the same" pattern above, three
of them properties of the **EHR ("ehr-meta") seed**:

1. **Neither `dataElementGroupSets` nor `categoryOptionGroupSets` exist on
   this seed at all** (`GET /api/dataElementGroupSets` and
   `GET /api/categoryOptionGroupSets` both → `pager.total: 0`). Unlike
   2.41.10 (which was missing only category option group sets), this seed
   has enabled objects of only **two** of the four types (110/111 categories,
   8/8 organisation unit group sets). "All four dimension types appear"
   fails by construction, both empty-type filters correctly show 0 rows, and
   the disable/re-enable/toast checks only exercise Category and
   Organisation unit group set (2 of 2, not 2 of 4).
2. **The data-read-error scenario is unreachable here too, for a related but
   distinct reason.** This seed's `admin` account rejects Basic auth
   outright (`401`) — it cannot be used at all, unlike the EMIS seed's
   `admin`. The only usable account, a separate superuser, holds `ALL`
   (`GET /api/me` → `authorities: ["ALL"]`), so — same mechanism as
   2.41.10 — setting the view's sharing to `r-------` has no effect and
   `/sqlViews/{id}/data` keeps answering 200. Because `flow_data_error`
   raises its "waiting for the error notice" exception *before* its own
   `_set_view_sharing(ctx.client, READABLE_SHARING)` restore call, the view
   was left with `sharing.public = r-------` when the suite finished. This
   was caught and fixed by hand: `PUT /api/sharing?type=sqlView&id=…` with
   `publicAccess: "r-r-----"` → `200 "Access control set"`, verified by
   `GET /api/sqlViews/GOLswS44mh8?fields=sharing` afterwards. On 2.41.10
   this didn't need a manual fix because the (there, in-scope) `outdated-
   update` flow ran immediately afterwards and starts by deleting and
   recreating the view unconditionally, incidentally clearing the bad
   sharing; excluding that flow here removed that safety net.
3. Same `restore-view` artifact as 2.41.10 (finding **L9**): with
   `limited-user` excluded, the view is already `READY` when `restore-view`
   opens the app, so it never finds a notice box and raises an exception.
   The view's real end state (installed, correct name, `r-r-----` sharing)
   was verified directly via the API and is fine.
4. **New finding, this instance only: the "sort by name" doc rows FAIL, but
   the app is correct** (finding **L10**, `docs/review-2026-09-21/
   REVIEW-FINDINGS.md`). The suite's Python oracle (`sorted(names,
   key=str.lower)`) is not locale-aware, unlike the app's own
   `a.localeCompare(b, undefined, { sensitivity: 'base' })`. The EHR seed's
   category names — heavy on `<`, `(`, `,` and embedded digits — are the
   first in this review to make the two orderings disagree (14 of 118
   rows). Spot-checked directly in Node (the same V8/ICU engine Chromium
   uses): `"Age(<1 Yr, 50+Yrs)".localeCompare("Age(0-4Yrs,25-49Yrs,50+Yrs)",
   undefined, {sensitivity: "base"})` returns `-1` — exactly the order the
   app displayed and the suite marked wrong.

## 2.43.1 Laos-specific notes (review pass D, final pass)

Checks 2 (outdated-view detection) and 5 (limited-user permission error)
were out of scope for this instance per the review plan (check 2 was
exercised on 2.41.10, check 5 on 2.43.1 Sierra Leone) — Task 14 step 4 was
correspondingly not run on the Laos instance, and the `outdated-update` and
`limited-user` suite flows were excluded via `E2E_FLOWS`. All corresponding
doc rows are N/A/SKIPPED, not FAIL. Three things differ from the "all
versions behave the same" pattern above, all of them properties of the
**Laos HMIS demo seed**:

1. **`dataElementGroupSets` does not exist on this seed at all**
   (`GET /api/dataElementGroupSets` → `pager.total: 0`). Unlike 2.41.10
   (missing category option group sets) and 2.42.6 (missing both data
   element group sets and category option group sets), this seed has
   enabled objects of **three** of the four types (60/161 categories,
   20/32 organisation unit group sets, 40/40 category option group sets).
   "All four dimension types appear" fails by construction; the empty-type
   filter correctly shows 0 rows; the disable/re-enable/toast checks
   exercise Category, Organisation unit group set and Category option
   group set (3 of 3, not 3 of 4).
2. **The data-read-error scenario is unreachable here too, same mechanism
   as 2.41.10 and 2.42.6.** This seed's `admin` account rejects Basic auth
   outright (`401`); the only usable account, a separate superuser,
   holds `ALL` (`GET /api/me` → `authorities: ["ALL"]`), so setting the
   view's sharing to `r-------` has no effect and `/sqlViews/{id}/data`
   keeps answering 200. `flow_data_error` again raised its "waiting for the
   error notice" exception before its own sharing-restore cleanup ran,
   leaving the view at `sharing.public = r-------`. Fixed by hand:
   `PUT /api/sharing?type=sqlView&id=GOLswS44mh8` with
   `publicAccess: "r-r-----"` → `200 "Access control set"`, verified by
   `GET /api/sqlViews/GOLswS44mh8?fields=sharing` afterwards.
3. Same `restore-view` artifact as 2.41.10 and 2.42.6 (finding **L9**):
   with `limited-user` excluded, the view is already `READY` when
   `restore-view` opens the app, so it never finds a notice box and raises
   an exception. The view's real end state (installed, correct name,
   `r-r-----` sharing after the manual fix above) was verified directly via
   the API and is fine.
4. **The "sort by name" doc rows FAIL for the same reason as 2.42.6
   (finding L10), reproduced on a fourth seed.** Fetching the installed
   view's 120 rows directly from the API and sorting them both with
   Python's `sorted(names, key=str.lower)` and with Node's
   `a.localeCompare(b, undefined, {sensitivity: "base"})` (same V8/ICU
   engine Chromium uses) finds exactly 6 of 120 rows where the two
   orderings disagree, all involving names with `<`, `(`, `,` and digits —
   e.g. `sorted()` places `"Age (0-59,60+)"` before `"Age (<1- 30+
   years)"`, while `localeCompare` places `"Age (<1- 30+ years)"` first.
   This is the app's displayed (correct) order; the suite's Python oracle
   is simply the wrong comparator for this seed's names, same root cause as
   L10, not a new finding.

Additionally, this instance is the largest seed in the review by a wide
margin: 2,392 `visualizations`, 497 `maps` and 53 `eventVisualizations`
(2,942 favorites total), and `generate-view-events.sh` recorded events
against both `VISUALIZATION_VIEW` and `MAP_VIEW` favorites in the same run
for the first time in this review (5/4/3/2/1 and 3/2/1 respectively; this
seed's event visualizations happen to carry no dimensions at all, so
`EVENT_VISUALIZATION_VIEW` recorded nothing here).

## Counts verified against SQL

The numbers the app shows were checked against the database, not only against
the API. For each instance the installed `sqlQuery` was read back from
`GET /api/sqlViews/GOLswS44mh8?fields=sqlQuery` and executed directly with
`psql`; the result was compared row by row with
`GET /api/sqlViews/GOLswS44mh8/data?paging=false` and with the rendered table.

- 2.43.1 — 23 rows, identical in all three places. Top rows: Location
  Fixed/Outreach 30 (49.2 % / 44.1 %), Facility Type 20, Facility Ownership 7,
  Implementing Partner 4.
- 2.40.12 — 23 rows, identical in all three places. Top rows: Facility Type 15
  (31.25 % / 32.6 %), Implementing Partner 8, Facility Ownership 7, Location
  Fixed/Outreach 6, Diagnosis 5.
- Denominators check out by hand: on 2.40, 46 favorite-view events were
  recorded in the window and Facility Type's 15 views give 15/46 = 32.6 %
  ("% of favorite views") and 15/48 = 31.25 % of the 48 dimension views
  (a favorite using two dimensions counts once for each).
- **The map-view correction is confirmed empirically.** Facility Ownership's 7
  views are exactly the 7 `MAP_VIEW` events recorded against map
  `X7x2WOLhCA8`. All `MAP_VIEW` rows in `datastatisticsevent` carry a **map**
  UID (`SELECT` against `mapview.uid` matches none of them), so the previous
  app's `mapview.uid` join would have counted 0 here.
- 2.41.10 — 70 rows, identical in all three places (`psql` direct execution
  of the installed `sqlQuery`, `GET /sqlViews/GOLswS44mh8/data?paging=false`,
  and the rendered table). Only 7 rows are non-zero, all `ORGUNIT_GROUP_SET`:
  School Type 13 (20.6% / 100.0%), Implementation 11, Location Rural/Urban 9,
  Ownership Public/Private 9, Geo-Political Zone 7, School Level 7, UNICEF
  Field Office 7. The 13-view denominator (`percent_of_views`) matches
  exactly the 7+4+2 = 13 raw `datastatisticsevent` rows recorded against the
  three `EVENT_VISUALIZATION_VIEW` favorites by `generate-view-events.sh`
  (see "M2 live check" below) — confirmed directly against
  `datastatisticsevent` with `psql`. No `CATEGORY`,
  `DATAELEMENT_GROUP_SET` or `CATEGORYOPTION_GROUP_SET` row is non-zero,
  because none of those three favorites carries a category or
  data-element-group-set dimension on this seed (and there are no
  category-option group sets to carry one at all).
- 2.42.6 — 118 rows, identical in all three places (`psql` direct execution
  of the installed `sqlQuery`, `GET /sqlViews/GOLswS44mh8/data?paging=false`,
  and the rendered table). Only 8 rows are non-zero: Sex (Category) 15
  (31.25% / 71.4%), OPD Age(0-28days+) (Category) 12 (25.0% / 57.1%),
  Reporting Status (Organisation unit group set) 6 (12.5% / 28.6%), then five
  rows tied at 3 views each (6.25% / 14.3%): 1.3.28 Nutrition Services (Age
  Groups), Authority, Nutrition Pregnancy Status, Operational Status,
  Ownership. The 21-view denominator (15 + 6, i.e.
  `percent_of_favorite_views` for Sex = 15/21 = 71.4%) matches exactly the
  raw `datastatisticsevent` rows recorded by `generate-view-events.sh`: 5+4+3
  +2+1 = 15 `VISUALIZATION_VIEW` and 3+2+1 = 6 `EVENT_VISUALIZATION_VIEW`,
  confirmed directly with `psql`
  (`SELECT favoriteuid, eventtype, count(*) FROM datastatisticsevent GROUP
  BY favoriteuid, eventtype`). No `DATAELEMENT_GROUP_SET` or
  `CATEGORYOPTION_GROUP_SET` row exists at all, because this seed defines no
  objects of either type.
- 2.43.1 Laos — 120 rows, **0 mismatches** between the API payload and a
  direct `psql` execution of the installed `sqlQuery` against the
  instance's database (compared uid-by-uid and views-by-views, not
  just row counts), and identical to the rendered table. Only 7 rows are
  non-zero: Sex (Male/Female) (Category option group set) 42 (76.4% of
  dimension views, 16.6% of favorite views), ENTO - Reporting institution
  (Category) 6, Gender (Category option group set) 2, PEP/OAMT/PrEP Age
  (Category option group set) 2, then three rows tied at 1 view each. The
  55-view total (across all favorite-view events in the 12-month window) is
  larger than the 21 events this pass's `generate-view-events.sh` run added
  (15 `VISUALIZATION_VIEW` + 6 `MAP_VIEW`), because this large seed ships
  with substantial pre-existing `datastatisticsevent` history of its own —
  a property of the seed's data, not a discrepancy. No `DATAELEMENT_GROUP_SET`
  row exists at all, because this seed defines no objects of that type.
  Response time of `/sqlViews/{id}/data`, measured three times with
  `curl -w '%{time_total}'`: **0.220577s, 0.112248s, 0.107094s** (first run
  cold; 120 rows, the largest table measured in this review).

## Console/network hygiene

No console errors, page errors, React key warnings or unexpected HTTP errors
from the app on 2.40.12, 2.41.10, 2.42.6, 2.43.1 or 2.43.1 Laos. Filtered as
platform noise, not app defects:

- `Error: This window is not a secure context … PWA features will not work` —
  the App Platform's offline/PWA layer on a plain-http test instance. Logged
  from the app's own bundle on 2.40 and from the shell on 2.43.
- `404 /api/<v>/staticContent/logo_banner` and
  `404 /api/<v>/dataStore/custom-translations/controller` — header-bar/shell
  probes for optional resources.
- `404 /api/<v>/sqlViews/GOLswS44mh8?fields=id,sqlQuery` — the expected probe
  while the view is not installed; it is how the app detects `MISSING`.

## Screenshots

In `screenshots/`, named `<version>-<step>.png` (2.41.10 uses a short `2.41-`
prefix; 2.42.6 uses a short `2.42-` prefix; 2.43.1 Laos uses a `2.43-lao-`
prefix). Only the usage-table screenshot per instance is kept in the
repository; the full set (51 files) was delivered to the maintainer
separately.

| Step | 2.40.12 | 2.41.10 | 2.42.6 | 2.43.1 | 2.43.1 Laos |
|---|---|---|---|---|---|
| Create notice | not kept in repo | not kept in repo | not kept in repo | not kept in repo | not kept in repo |
| Usage table | `2.40.12-02-table.png` | `2.41-02-table.png` | `2.42-02-table.png` | `2.43-columns.png` (see 2026-09-22 below) | `2.43-lao-02-table.png` |
| Filtered to one type | not kept in repo | not kept in repo | not kept in repo | not kept in repo | not kept in repo |
| Sorted | not kept in repo | not kept in repo | not kept in repo | not kept in repo | not kept in repo |
| Disable dialog | not kept in repo | not kept in repo | not kept in repo | not kept in repo | not kept in repo |
| After disabling objects | not kept in repo | not kept in repo (3 objects, not 4 — see notes) | not kept in repo (2 objects, not 4 — see notes) | not kept in repo | not kept in repo (3 objects, not 4 — see notes) |
| View removed | not kept in repo | not kept in repo | not kept in repo | not kept in repo | not kept in repo |
| Outdated (legacy) view notice | not kept in repo | not kept in repo (suite's synthetic legacy view, and separately the actual historical `sql_view_41` from `git show 7b8c7e1:src/app.js`) | not captured (check 2 out of scope on this instance) | not kept in repo | not captured (check 2 out of scope on this instance) |
| After update | not kept in repo | not kept in repo (both the suite's synthetic legacy view and the actual historical `sql_view_41`) | not captured (check 2 out of scope on this instance) | not kept in repo | not captured (check 2 out of scope on this instance) |
| Limited user, create refused | not kept in repo | not captured (check 5 skipped on this instance) | not captured (check 5 out of scope on this instance) | not kept in repo | not captured (check 5 out of scope on this instance) |
| Data-read error state | not kept in repo | not captured (scenario unreachable on this instance — see notes) | not kept in repo (shows the table, not an error — the scenario is unreachable on this instance, see notes) | not kept in repo | not kept in repo (shows the table, not an error — the scenario is unreachable on this instance, see notes) |
| `restore-view` exception (L9 artifact) | n/a | n/a | not kept in repo (shows the table, not a notice box — see notes) | n/a | not kept in repo (shows the table, not a notice box — see notes) |

## 2026-09-22 — favorite-count columns re-check (2.43.1)

The table's columns changed on 2026-09-22 (favorite counts split by sharing,
a column chooser, header tooltips, no in-app title), so the 2.43.1 usage-table
screenshot from this review no longer shows the current UI. The table above now
points at **`2.43-columns.png`**, taken on a separate 2.43.1 instance
with Public, Shared and Private enabled through the Columns chooser;
`2.43.1-02-table.png` is kept as the record of what this review actually saw.
The other versions' screenshots are from the 2026-09-21 run and likewise still
show the older column set.

Re-run of the e2e suite on that 2.43.1 instance, all flows including
the new `columns-chooser` one: **56 PASS, 2 INFO, 0 FAIL**.

Favorite counts shown in the table, cross-checked against a second,
independently written SQL count of the same favorites (run through a
throwaway SQL view, then deleted):

| Dimension | Type | Favorites | Public | Shared | Private | SQL |
|---|---|---|---|---|---|---|
| Facility Type (`J5jldMd8OHv`) | Organisation unit group set | 42 | 37 | 0 | 5 | identical |
| Facility Ownership (`Bpx0589u8y0`) | Organisation unit group set | 12 | 11 | 0 | 1 | identical |
| Location Fixed/Outreach (`fMZEcRHuamy`) | Category | 14 | 14 | 0 | 0 | identical |

Two test-oracle updates were needed in the suite itself, neither an app
defect: the app frame is now found by the intro block rather than an `<h1>`
(the app no longer renders one), and numeric columns sort descending on the
first click, which the suite still expected to be ascending.
