# Data Dimension Disabler Tool

DHIS2 App Platform app (TypeScript, React 18, @dhis2/app-runtime, @dhis2/ui).
Ranks categories and group sets enabled as data dimensions by favorite views
in the last 12 months and lets an admin disable them.

## Layout

- `src/dimensionTypes.ts` — the single source of truth for the four dimension
  types (API endpoint + SQL names). Add a type here, nowhere else.
- `src/sql/buildQuery.ts` — generates the SQL view query per server minor
  version. `docs/schema-check.md` records the verified table names.
  Its `data_set_report_subtotals` CTE mirrors DHIS2 core's data set report
  sub-total rules (README "Data set reports"); `e2e/data_set_report_oracle.py`
  re-derives the same answer from the metadata API.
- `src/sql/sqlView.ts` — view UID `GOLswS44mh8` (kept from the original
  category-only app so installs upgrade in place), name, sharing, outdated
  check.
- `src/hooks/*` — status (LOADING/MISSING/OUTDATED/READY/ERROR), usage data,
  mutations. Mutations call `engine.mutate` directly (`useEngineMutation`)
  because the resource varies per call; it exposes `run`, `state` and
  `reset` (`reset` clears a stale mutation error when a dialog is opened for
  a different row or cancelled, without clobbering a concurrent call's
  loading state).
- `src/components/columns.ts` — the single source of truth for the usage
  table's columns (key, label, header tooltip, alignment, formatter, whether
  it can be hidden) plus the default visible set. Add or change a column
  here; `UsageTable` and `ColumnChooser` both render from it. Visibility is
  persisted per browser in `localStorage` under
  `data-dimension-disabler.columns` (a JSON array of column keys).
- `src/components/*` — presentational; `UsageView` owns dialogs + mutations.

## Conventions

- pnpm (version pinned in `packageManager`), `pnpm lint` = eslint + prettier + tsc. Tests next to sources,
  `renderWithProvider` from `src/test-utils`. `data-test` is the test id
  attribute.
- Never call `i18n.t` at module scope.
- `src/App.tsx` must render `<CssVariables>` for every token section the
  stylesheets use: the app-platform shell provides none, so an unlisted
  section silently drops every declaration referencing it (`src/cssVariables.test.ts`
  guards this, and the e2e `layout` flow checks it in a browser).
- Two `@dhis2/ui` components look like they do more than they do:
  `MenuItem checkbox` only sets `role`/`aria-checked` and draws nothing (pass
  a visual through its `icon` slot), and `DataTableColumnHeader align` only
  sets `text-align`, which cannot move the label inside the header's flex row
  (`UsageTable.module.css` reverses that row for numeric columns).
- The SQL view text must not contain a protected table name such as `users`
  (also `userinfo`, `oauth2client`): DHIS2 scans the query text with a
  word-boundary match and returns `409 E4310` from
  `/api/sqlViews/{uid}/data`, even when the word is only a JSON key in a
  string literal. Spell such keys by concatenation — `('user'||'s')`.
- Supported servers 2.40–2.43; `minor < 41` is the only SQL version branch
  (the category table was renamed from `dataelementcategory` to `category`
  in 2.41).

## Testing against DHIS2

- Only ever against a throwaway local instance (the app and the e2e suite
  change data). `pnpm start --proxy http://localhost:8080`;
  `scripts/generate-view-events.sh <url> <user:password>` seeds view events
  so the ranking is non-trivial.
- e2e suite: `e2e/run.sh` (shared tool test contract; needs a superuser,
  `APP_ZIP` and `RESULTS_DIR`, no defaults), see `e2e/README.md`. It records
  every change in the dataStore (`e2e-state/tool-data-dimension-disabler`)
  before making it and undoes it at the end. Last multi-version review:
  `docs/review-2026-09-21/`.
- The repo must not reference team-internal dev tooling (instance brokers,
  sandbox variables, agent skills); `docs/superpowers/` holds old plans.
