# Changelog

All notable changes to this project will be documented in this file.

## [1.1.0] - 2026-10-16

### Upgrading

- The app key changes from `data-dimension-disabler` to
  `tool-data-dimension-disabler`, and the name to "Data Dimension Disabler
  Tool". DHIS2 treats this as a different app:
    - Install the new version, then uninstall the old "Data Dimension Disabler"
      in App Management right away. Otherwise two entries remain in the menu,
      and the two apps keep offering to "update" the shared SQL view to their
      own version; the old app's update removes the Data set reports column.
    - Add the new app to every user role that gave access to the old one. Until
      then, users without the ALL authority cannot open it.
    - Bookmarks to the old app URL stop working.
- The SQL view needs an update, which the app offers on startup. It keeps
  its UID, so no usage data is lost.

### Added

- **Data set reports** column: for each category, the data sets whose data
  set report shows sub-totals for it (section and default forms with a
  category combination of more than one category), listed in a tooltip.
  Disabling such a category leaves those sub-totals empty; the disable
  dialog now lists the affected data sets.
- Known limitations section in the README.

### Changed

- App key `tool-data-dimension-disabler` and name "Data Dimension Disabler
  Tool", following the shared tool naming conventions.
- The end-to-end suite follows the shared tool test contract: `e2e/run.sh`
  installs the bundle, records every change it makes in the dataStore
  (`e2e-state`) before making it, leaves the instance as it found it,
  uninstalls the app and writes `results.json`. It needs a superuser and has
  no default instance or account.

## [1.0.0] - 2026-09-21

### Changed

- Rewritten on the DHIS2 App Platform (React, TypeScript, @dhis2/ui).
  Replaces the webpack build, jQuery/DataTables and the conditional legacy
  header bar.
- Renamed to **Data Dimension Disabler** (app key `data-dimension-disabler`).
  Uninstall the old "Category dimension disabler" after installing this one.
- The SQL view keeps its UID and is renamed "Data dimension usage"; an old
  install is detected and updated in place from the app. Sharing tightened
  to public read-only (`r-r-----`: metadata read plus data read, since the
  view's data endpoint requires data read).
- Map views are now counted correctly, through the `mapmapviews` join table
  (the view previously joined the map view UID instead of the map UID that
  view events are recorded against).
- Event types counted: VISUALIZATION_VIEW, MAP_VIEW, EVENT_VISUALIZATION_VIEW,
  EVENT_CHART_VIEW, EVENT_REPORT_VIEW.
- The app no longer renders a title of its own — the DHIS2 header bar already
  names it — and the introduction is shorter and runs the full width of the
  page, with tighter spacing above the table.

### Added

- Organisation unit group sets, data element group sets and category option
  group sets, in addition to categories. Data element group set dimensions
  are ranked from visualizations only, since no map view or event
  visualization join table exists for them.
- Type filter, sortable columns, confirmation dialogs, in-app error messages.
- Favorite counts per dimension: how many visualizations, maps and event
  visualizations use it, split into public, shared and private by each
  favorite's sharing.
- A **Manage view** chooser above the table. Type and Name are always shown; the
  choice is remembered per browser in `localStorage`
  (`data-dimension-disabler.columns`).
- An ⓘ tooltip in every numeric column header explaining what it counts.
- Support for DHIS2 2.40 to 2.43.

### Fixed

- The app now renders `<CssVariables>`. The app-platform shell does not
  provide the DHIS2 design tokens, so every `var(--spacers-*)` and
  `var(--colors-*)` declaration in the app's own stylesheets was dropped and
  the page rendered with no padding, margins or spacing at all.
- The **Manage view** chooser draws a checkbox per entry. `MenuItem`'s `checkbox`
  prop only sets `role` and `aria-checked`, so the current selection was
  invisible behind the open dropdown.
- Numeric column headers are right-aligned above their numbers, with the sort
  icon after the label as in every other column.
  `DataTableColumnHeader` applies its `align` prop as `text-align` only, which
  cannot move the label inside its flex row, so the header sat 89px to the
  left of the figures it named.

## [0.1.0]

### Added

- Initial release.
- Updated automation to release zip artifact.

## [0.1.1]

### Added

- Include DHIS2 header bar

### Fixed

- Fixed webpack config to properly load project
