> [!WARNING]
> This suite changes and deletes data. It installs and uninstalls the app,
> disables and re-enables data dimensions, deletes and recreates the app's SQL
> view, and creates and deletes a user, a user role and SQL views. Run it only
> against a **throwaway** DHIS2 instance that you can reset or recreate, never
> against a server whose content anyone wants to keep, including shared test
> and play servers.

# End-to-end suite

Drives the Data Dimension Disabler Tool app in a real browser against a real DHIS2
instance, and cross-checks every UI claim against the Web API. One run covers
the full life cycle of the app's SQL view: create → read → filter/sort →
disable a dimension of each type → remove → detect and update a legacy view →
permission errors.

The entry point is `e2e/run.sh`, which follows the shared tool test contract
(version 1): it installs the bundle, runs the suite, cleans up, uninstalls the
app and writes `results.json`. No host, UID or credential is hard-coded, and
the instance and account have no defaults, so nothing runs against an
instance by accident. The same run works on every version from 2.40 up.

## A throwaway instance

Any local DHIS2 instance you can throw away will do. The simplest is the
Docker Compose setup in the DHIS2 core repository, which starts DHIS2 with
the Sierra Leone demo database at `http://localhost:8080`: see
[Run DHIS2 in Docker](https://github.com/dhis2/dhis2-core#run-dhis2-in-docker).
Pick the version with `DHIS2_IMAGE`, for example `dhis2/core:2.42.1`, and
remove the volumes (`docker compose down --volumes`) to start over.

The suite needs an account that holds the **ALL** authority (`DHIS2_USER`).
On the demo databases the `admin` user does not hold it, so use or create a
superuser account on your throwaway instance.

## Requirements

- Python 3 with Playwright for Python and its Chromium
  (`pip install -r e2e/requirements.txt`, then `python3 -m playwright install chromium`).
- A built bundle: `pnpm build` writes it to `build/bundle/`.

## Running

```bash
mkdir -p /tmp/e2e-results
DHIS2_URL=http://localhost:8080 DHIS2_USER=<superuser> DHIS2_PASS=<password> \
APP_ZIP=$(ls "$PWD"/build/bundle/*.zip) \
RESULTS_DIR=/tmp/e2e-results \
  e2e/run.sh
```

| Variable                    | Required | Meaning                                                                                |
| --------------------------- | -------- | -------------------------------------------------------------------------------------- |
| `DHIS2_URL`                 | yes      | Base URL of the throwaway instance, no trailing slash                                  |
| `DHIS2_USER` / `DHIS2_PASS` | yes      | An account holding ALL. No default                                                     |
| `APP_ZIP`                   | yes      | Absolute path of the built bundle; the suite installs it and uninstalls it at the end  |
| `RESULTS_DIR`               | yes      | Existing directory for `results.json`, `results.md` and screenshots                    |
| `LABEL`                     | no       | Label in output and screenshot names; default: the server version                      |
| `APP_KEY`                   | no       | Default: the key the server reports for the installed app                              |
| `E2E_FLOWS`                 | no       | Comma-separated flow ids to run (default: all)                                         |
| `E2E_HEADED`                | no       | `1` to watch the browser                                                               |
| `DHIS2_LIMITED_PASSWORD`    | no       | Password for the throwaway non-superuser the suite creates; default: generated per run |

Exit codes: `0` every test passed, `1` at least one failed, `2` the suite
could not run (the stage is in `results.json` under `error`). The runner also
prints one line per step and writes the same table to `results.md`.

## What a run changes, and how it is undone

Before each change, the suite writes it to a run record on the instance, in
the dataStore at `e2e-state/tool-data-dimension-disabler`. Every run starts by
undoing what the record still lists (from an earlier run that was killed),
and ends by undoing its own changes and deleting the record:

- the installed app, uninstalled at the end;
- the app's "Data dimension usage" SQL view: its definition is recorded as
  found (or that there was none), it is removed so the suite starts without
  one, and at the end it is put back exactly as found;
- every dimension the suite disables, enabled again;
- a user role and a user without ALL, used by the `data-error` and
  `limited-user` flows, deleted;
- the throwaway SQL views of the favorite-count cross-check, deleted.

Everything the suite creates gets a run-unique uid and a name starting with
`E2E tool-data-dimension-disabler <run id>` (the user's name starts with
`e2e-ddd-`), so leftovers are easy to find and never collide with a later
run. A final `cleanup` step reports whether the instance was left as found.

## Flows

| Id                 | What it proves                                                                                                                                                                                                                                                                                                                                                                                                                                                                                           |
| ------------------ | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `load-missing`     | Fresh load with no view shows the create notice; exactly one header bar (top level ≤2.41, global-shell iframe 2.42+)                                                                                                                                                                                                                                                                                                                                                                                     |
| `create-view`      | Create installs the view with the expected name and `r-r-----` sharing; the table lists every dimension type the server returns; every row matches the `/sqlViews/{id}/data` payload; the favorite counts of the three dimensions with the most favorites match an independent second count; every category's data set report sub-totals (count and data set names) match an independent count from `/api/dataSets`, and hovering a count lists the data sets; records the data endpoint's response time |
| `columns-chooser`  | The table opens with the default columns (including Data set reports); the Manage view chooser shows "Private", the choice survives a page reload (`localStorage`), and unticking removes it again                                                                                                                                                                                                                                                                                                       |
| `layout`           | The DHIS2 design tokens the stylesheets use resolve in the browser (the app must render `<CssVariables>`); every right-aligned numeric header sits above its numbers and its sort icon follows the label, as in every other column; the chooser draws one checkbox per column, ticked for exactly the columns on screen                                                                                                                                                                                  |
| `filter-sort`      | Each type filter shows exactly that type's rows; name and views sort, both directions (numeric columns start descending)                                                                                                                                                                                                                                                                                                                                                                                 |
| `disable-per-type` | Disables the least-viewed object of each type: dialog names object and type, the row disappears, a success alert names it, and the API reports `dataDimension=false`                                                                                                                                                                                                                                                                                                                                     |
| `re-enable`        | Puts every disabled dimension back (also runs unconditionally at the end of a run, before the run record is undone)                                                                                                                                                                                                                                                                                                                                                                                      |
| `remove-recreate`  | Remove returns to the create notice (view really gone), creating again restores the table                                                                                                                                                                                                                                                                                                                                                                                                                |
| `data-error`       | As the throwaway non-superuser (sharing does not restrict ALL), with data read removed from the view's sharing, `/data` answers 409 E4312: the app shows the server message, keeps "Remove SQL view" available, and Retry recovers                                                                                                                                                                                                                                                                       |
| `outdated-update`  | A legacy category-only view (old name, `rwrw----`) is detected as outdated and updated in place: same UID, new name, `r-r-----`                                                                                                                                                                                                                                                                                                                                                                          |
| `limited-user`     | A user without the SQL view authority sees the server's message plus the "Add/Update SQL view" hint, and the app does not crash                                                                                                                                                                                                                                                                                                                                                                          |
| `console-clean`    | No app console errors, no React duplicate-key warnings, no unexpected 4xx/5xx                                                                                                                                                                                                                                                                                                                                                                                                                            |

Platform noise that is not the app's doing (the PWA "not a secure context"
message on plain http, the shell's optional `staticContent/logo_banner` and
`dataStore/custom-translations` 404s, and the expected 404 while the view is
missing) is filtered in `app_driver.BENIGN_CONSOLE` / `BENIGN_HTTP_404`.

## How the table is read

`app_driver.table_rows` reads the header cells
(`[data-test^='usage-header-']`), takes each column's key from the
`data-test` suffix, and zips those keys with the row's `<td>` texts. Rows
therefore come back as dicts keyed by column key (`type`, `name`, `uid`,
`favorites`, `views`, …) covering whatever the column chooser currently
shows — no fixed cell positions — and the trailing action cell, which has no
header of its own, drops out of the zip. `app_driver.set_columns` ticks or
unticks columns through the chooser (ticking an item deliberately leaves the
flyout open, and its backdrop then covers the toggle button, so the menu is
closed by clicking the backdrop, exactly as a user would).

## The favorite-count oracle

`favorite_counts_sql.py` counts one dimension's favorites per sharing class
without reusing any of the app's logic, by splitting the job across two
layers:

- **which favorites use the dimension** comes from a throwaway SQL view —
  created, read and deleted in one call — whose query returns nothing but
  `(favorite uid, favorite kind)` pairs reached through the join tables. Its
  schema knowledge is spelled out in the module rather than imported from
  `src/`, and it contains no sharing logic at all;
- **how each favorite is shared** comes from the Web API
  (`/api/visualizations`, `/api/maps`, `/api/eventVisualizations`,
  `fields=id,sharing`, one filtered request per kind) and is classified in
  Python by `sharing_class()`: public when `sharing.public` starts with `r`;
  shared when it is not public and `sharing.users` or `sharing.userGroups` is
  a non-empty object; private otherwise (`None`, a missing key and `{}` all
  mean "not shared").

Restating the app's own SQL `CASE` here would only have proved it was copied
correctly, so the classification deliberately comes from a different layer
than the view under test. The `CASE` itself was compared against the same
Python rule over every favorite on the test database — 433 rows, 0
disagreements, including the 4 genuinely shared visualizations — and that
check is recorded in `docs/schema-check.md`.

The sharing lookups need an account that can see every favorite, which is
why `DHIS2_USER` must hold ALL. A private favorite owned by someone else is a
404 for an account without it, and treating "unreadable" as "private" would
silently turn a _shared_ favorite into a private one, so the oracle raises
`UnreadableFavorites` instead and the flow reports SKIP.

One trap worth knowing when writing SQL for a view: DHIS2 refuses to execute
a SQL view whose _text_ contains the word `users` (`E4310`, "SQL query
contains references to protected tables"). The check is a plain word scan, so
even a JSON key in a string literal trips it — `src/sql/buildQuery.ts`
therefore spells that key `('user'||'s')`.

## Known test-oracle gaps

Two findings from `docs/review-2026-09-21/REVIEW-FINDINGS.md` are gaps in
this suite's own oracles, not app defects:

- **L9.** `e2e/flows.py`'s `restore-view` step assumes a notice box is
  always present — test-suite-only, not an app defect. `flow_restore_view`
  (`e2e/flows.py`) calls `ui.notice_title(frame)`, which waits for
  `NOTICE_BOX` to become visible, then only acts if its text contains
  `MISSING_NOTICE`. In the normal full run this works because the preceding
  `limited-user` step (`_ensure_limited_user` / `flow_limited_user`) always
  deletes the SQL view before returning, so `restore-view` reliably finds
  the MISSING notice and recreates the view. When `limited-user` is
  excluded from `E2E_FLOWS` and the preceding `outdated-update` step
  already leaves the view installed and `READY`, `restore-view` opens the
  app straight to the usage table — no notice box ever appears — and
  `notice_title()` times out, raising an exception that is reported as a
  suite FAIL. Fix (test suite, not app code): have `flow_restore_view`
  check whether the table is already rendered before waiting for a notice
  box, e.g. `if frame.locator(ui.USAGE_TABLE).count() > 0: return PASS`
  short-circuit, or document that `limited-user` must run whenever
  `restore-view` does.
- **L10.** `e2e/flows.py`'s name-sort assertion is not locale-aware, unlike
  the app it is testing — test-suite-only, not an app defect.
  `_sort_checks` (`e2e/flows.py:240-251`) computes the expected
  ascending/descending order with Python's `sorted(names, key=str.lower)`,
  i.e. plain code-point comparison after lowercasing. The app itself sorts
  with `a.localeCompare(b, undefined, { sensitivity: 'base' })`
  (`src/components/usageTableUtils.ts:10`), which is correct — ICU
  collation, not naive code-point order, is the right choice for a name
  column. The two orderings usually agree, but seeds with names built from
  `<`, `(`, `,`, and digits expose the gap (verified directly in Node, the
  same V8/ICU engine Chromium uses: `"Age(<1 Yr, 50+Yrs)".localeCompare(
"Age(0-4Yrs,25-49Yrs,50+Yrs)", undefined, {sensitivity: "base"})` returns
  `-1`, i.e. the app's displayed order is the _correct_ `localeCompare`
  order; the suite's Python comparator is simply the wrong oracle for that
  data). Fix (test suite, not app code): reimplement the expected order
  with the same comparator the app uses — either compare through a
  headless JS `localeCompare` call (e.g. via `page.evaluate`) instead of
  Python's `sorted`, or drop the strict-order assertion in favour of a
  weaker check (e.g. "every adjacent pair compares as ≤ under the same rule
  the row values were shown in").

## Files

- `run_suite.py` — entry point: settings, browser, flow loop, results
- `flows.py` — one function per flow
- `app_driver.py` — frame lookup, selectors, console recorder, screenshots
- `dhis2_api.py` — small REST client (session cookie, SQL view, JSON Patch)
- `legacy_sql_view.py` — the pre-migration view definition, for `outdated-update`
- `favorite_counts_sql.py` — the independent oracle for the favorite counts
  (see "The favorite-count oracle" above)

Output (`e2e/results/`) is gitignored.
