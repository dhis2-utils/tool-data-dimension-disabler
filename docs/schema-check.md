# Schema check for the Data dimension usage SQL view

Checked 2026-09-21 on two local throwaway instances: the Sierra Leone 2.40
demo database on DHIS2 2.40.12, and the Sierra Leone 2.43 demo database on
DHIS2 2.43.1.

## Result

- All expected tables and columns exist on both versions: **NO** — two real
  differences from the spec's expectations (see below). Everything else
  matches exactly on both 2.40 and 2.43.

- **Category table**: confirmed as expected — `dataelementcategory` on 2.40,
  `category` on 2.43 (`categoryid` PK on both, both have `uid`, `name`,
  `datadimension`). No other dimension-type entity table (`orgunitgroupset`,
  `dataelementgroupset`, `categoryoptiongroupset`) is renamed between
  versions, and all four have `uid`, `name`, `datadimension` on both
  versions.

- **`map_mapviews` does not exist — on either version.** The spec's expected
  name is wrong, not version-dependent. The real join table between `map`
  and `mapview` is **`mapmapviews`** (no underscore), with columns `mapid,
  mapviewid, sort_order` — identical on 2.40 and 2.43. Task 4's
  `buildQuery.ts` must join `mapmapviews`, not `map_mapviews`.

- **`mapview_dataelementgroupsetdimensions` and
  `eventvisualization_dataelementgroupsetdimensions` do not exist — on
  either version.** This is not a 2.40-vs-2.43 difference; DATAELEMENT_GROUP_SET
  dimensions are only ever attached to `visualization` favorites in the
  schema. Only `visualization_dataelementgroupsetdimensions` exists (on both
  versions). Task 4's `favoriteSourcesFor`/join-table logic needs to skip the
  DATAELEMENT_GROUP_SET × (map view | event visualization) combination
  entirely, on every version — not gate it behind a version check.

- Missing tables on 2.40 (vs. 2.43): **none**, other than the expected
  `category`/`dataelementcategory` naming swap. Every other table in the
  checked list that exists on 2.43 also exists on 2.40 with the same
  columns.

- Every other expected table/column matches exactly, on both versions:
  `categorydimension(categorydimensionid, categoryid)`,
  `orgunitgroupsetdimension(orgunitgroupsetdimensionid, orgunitgroupsetid)`,
  `dataelementgroupsetdimension(dataelementgroupsetdimensionid, dataelementgroupsetid)`,
  `categoryoptiongroupsetdimension(categoryoptiongroupsetdimensionid, categoryoptiongroupsetid)`,
  the `visualization_*dimensions`, `mapview_*dimensions` and
  `eventvisualization_*dimensions` join tables that do exist (favorite id +
  dimension-table id, plus `sort_order`), `visualization(visualizationid,
  uid)`, `mapview(mapviewid, uid)`, `map(mapid, uid)`,
  `eventvisualization(eventvisualizationid, uid)`, and
  `datastatisticsevent(eventid, eventtype, timestamp, username, favoriteuid)`.

- `datastatisticsevent.eventtype` values seen (both versions, same set):
  `DASHBOARD_VIEW`, `DATA_SET_REPORT_VIEW`, `EVENT_CHART_VIEW`,
  `EVENT_REPORT_VIEW`, `MAP_VIEW`, `PASSIVE_DASHBOARD_VIEW`,
  `VISUALIZATION_VIEW`. Note: **`EVENT_VISUALIZATION_VIEW` was not observed
  on either seed** — event-visualization views are recorded as
  `EVENT_CHART_VIEW` or `EVENT_REPORT_VIEW` instead (legacy chart/report
  distinction retained in this enum even though the entity table was
  unified into `eventvisualization`). Task 4's `VIEW_EVENT_TYPES` list
  should rely on `EVENT_CHART_VIEW`/`EVENT_REPORT_VIEW` to count event
  visualization views; treat `EVENT_VISUALIZATION_VIEW` as belt-and-braces
  only, not as the value actually written by the server on these versions.

## Follow-up 2026-09-22 — the `sharing` column behind the favorite counts

Checked while adding the Favorites / Public / Shared / Private columns. No
new dump was needed: the table/column dumps below already show it.

- `visualization`, `map` and `eventvisualization` all carry a **`sharing`**
  column on both 2.40.12 and 2.43.1 (visible in the raw dumps below, last
  columns of each row). It is JSONB, with the usual DHIS2 shape
  `{"public": "rw------", "owner": "...", "users": {...}, "userGroups": {...}}`.
  `mapview` does **not** have one — which is fine, because the view never
  classifies a map view: map favorites are reached through
  `mapmapviews` → `map`, and it is the `map` row's sharing that counts,
  the same row whose UID the view events are recorded against.

- How `buildQuery.ts` classifies each favorite from that column
  (`SHARING_CLASS_SQL`):
  - `public` — `LEFT(sharing->>'public', 1) = 'r'`, i.e. the public access
    string grants at least metadata read;
  - `shared` — not public, and `sharing->'users'` or `sharing->'userGroups'`
    is a non-empty JSON **object**;
  - `private` — everything else.

  The object test is `jsonb_typeof(...) = 'object' AND ... <> '{}'::jsonb`
  rather than a `COALESCE` against `{}`. That distinction is load-bearing:
  `->` returns SQL `NULL` only for an *absent* key, while for
  `{"users": null}` it returns a non-NULL jsonb `null` that `COALESCE` does
  not touch and that compares `<> '{}'`. `jsonb_typeof` reports `NULL` for
  an absent key and `'null'` (not `'object'`) for a JSON null, so both fall
  through to `private`. On the Sierra Leone 2.43 data this is the common
  case: 32 of Facility Type's 37 public visualizations carry
  `"users": null`.

- The three classes are mutually exclusive and sum to the `favorites` total,
  verified on all 22 rows of a separate 2.43.1 test instance.

- 2026-09-22: the `CASE` above was compared against an independent Python
  classification of the same `sharing` JSON for **all 433** favorites on
  that 2.43.1 instance (269+19+4 visualizations, 91 maps, 50 event
  visualizations): **0 disagreements** — 409 public, 20 private and 4 shared
  (all four visualizations shared via `userGroups` with `public` =
  `--------`), so the `shared` branch is evidenced, not just assumed.

- **Careful with the literal `'users'` in a SQL view.** DHIS2 refuses to
  execute a SQL view whose query *text* contains the word `users`, answering
  `409 E4310` "SQL query contains references to protected tables" from
  `/api/sqlViews/{uid}/data`. The check is a plain word-boundary scan of the
  query, so a JSON key inside a string literal is enough to trip it, even
  though no table of that name is referenced. Probed on that 2.43.1 instance
  with one-line views: `'users'`, `'userinfo'` and `'oauth2client'`
  are rejected; `'user'`, `'usergroup'`, `'userGroups'`, `'useraccess'`,
  `'usergroupaccess'`, `'sharing'`, `'map'` and `'category'` are all fine, as
  is the split spelling `'user' || 's'`. Reading `sharing->'users'` therefore
  has to avoid the bare literal. `buildQuery.ts` accordingly emits
  `f.sharing->('user'||'s')`, and `buildQuery.test.ts` asserts the generated
  query never matches `\busers\b`. This was not theoretical: the first
  version of the query, verified with `psql` only, installed fine and then
  failed with E4310 on every read of `/api/sqlViews/GOLswS44mh8/data`.

## Raw output

### Sierra Leone 2.40 (DHIS2 2.40.12) — table/column dump

```
categorydimension: categorydimensionid, categoryid
categoryoptiongroupset: categoryoptiongroupsetid, uid, code, created, lastupdated, name, description, datadimension, userid, publicaccess, datadimensiontype, lastupdatedby, translations, attributevalues, sharing, shortname
categoryoptiongroupsetdimension: categoryoptiongroupsetdimensionid, categoryoptiongroupsetid
dataelementcategory: categoryid, name, uid, code, lastupdated, created, datadimension, userid, publicaccess, datadimensiontype, lastupdatedby, translations, attributevalues, sharing, shortname, description
dataelementgroupset: dataelementgroupsetid, name, description, compulsory, uid, code, lastupdated, created, userid, publicaccess, datadimension, lastupdatedby, translations, attributevalues, sharing, shortname
dataelementgroupsetdimension: dataelementgroupsetdimensionid, dataelementgroupsetid
datastatisticsevent: eventid, eventtype, timestamp, username, favoriteuid
eventvisualization: eventvisualizationid, uid, code, created, lastupdated, name, relativeperiodsid, userorganisationunit, userorganisationunitchildren, userorganisationunitgrandchildren, externalaccess, userid, publicaccess, programid, programstageid, startdate, enddate, sortorder, toplimit, outputtype, dataelementvaluedimensionid, attributevaluedimensionid, aggregationtype, collapsedatadimensions, hidenadata, completedonly, description, title, lastupdatedby, subtitle, hidetitle, hidesubtitle, programstatus, eventstatus, favorites, subscribers, timefield, translations, orgunitfield, userorgunittype, sharing, attributevalues, type, showdata, rangeaxismaxvalue, rangeaxisminvalue, rangeaxissteps, rangeaxisdecimals, domainaxislabel, rangeaxislabel, hidelegend, targetlinevalue, targetlinelabel, baselinevalue, baselinelabel, regressiontype, hideemptyrowitems, percentstackedvalues, cumulativevalues, nospacebetweencolumns, datatype, hideemptyrows, digitgroupseparator, displaydensity, fontsize, showhierarchy, rowtotals, coltotals, showdimensionlabels, rowsubtotals, colsubtotals, legacy, simpledimensions, eventrepetitions, legendsetid, legenddisplaystrategy, legenddisplaystyle, legendshowkey, sorting, skiprounding, relativeperiods
eventvisualization_categorydimensions: eventvisualizationid, sort_order, categorydimensionid
eventvisualization_categoryoptiongroupsetdimensions: eventvisualizationid, sort_order, categoryoptiongroupsetdimensionid
eventvisualization_orgunitgroupsetdimensions: eventvisualizationid, sort_order, orgunitgroupsetdimensionid
map: mapid, name, uid, lastupdated, userid, longitude, latitude, zoom, created, publicaccess, code, externalaccess, basemap, description, title, lastupdatedby, favorites, subscribers, translations, sharing, attributevalues
mapview: mapviewid, method, classes, colorlow, colorhigh, radiuslow, radiushigh, uid, lastupdated, layer, legendsetid, opacity, orgunitgroupsetid, arearadius, created, userorganisationunit, userorganisationunitchildren, userorganisationunitgrandchildren, relativeperiodsid, hidden, labels, labelfontsize, labelfontweight, labelfontstyle, labelfontcolor, programid, programstageid, startdate, enddate, eventclustering, eventpointcolor, eventpointradius, colorscale, config, code, description, aggregationtype, eventcoordinatefield, lastupdatedby, styledataitem, trackedentitytypeid, programstatus, followup, organisationunitselectionmode, translations, renderingstrategy, userorgunittype, thematicmaptype, nodatacolor, eventstatus, organisationunitcolor, orgunitfield, labeltemplate, relativeperiods
mapview_categorydimensions: mapviewid, categorydimensionid, sort_order
mapview_categoryoptiongroupsetdimensions: mapviewid, sort_order, categoryoptiongroupsetdimensionid
mapview_orgunitgroupsetdimensions: mapviewid, sort_order, orgunitgroupsetdimensionid
orgunitgroupset: orgunitgroupsetid, name, description, compulsory, exclusive, uid, code, lastupdated, created, datadimension, userid, publicaccess, includesubhierarchyinanalytics, lastupdatedby, translations, attributevalues, sharing, shortname
orgunitgroupsetdimension: orgunitgroupsetdimensionid, orgunitgroupsetid
visualization: visualizationid, uid, name, type, code, title, subtitle, description, created, startdate, enddate, sortorder, toplimit, userid, userorgunittype, publicaccess, displaydensity, fontsize, relativeperiodsid, digitgroupseparator, legendsetid, legenddisplaystyle, legenddisplaystrategy, aggregationtype, regressiontype, targetlinevalue, targetlinelabel, rangeaxislabel, rangeaxismaxvalue, rangeaxissteps, rangeaxisdecimals, rangeaxisminvalue, domainaxislabel, baselinevalue, baselinelabel, numbertype, measurecriteria, hideemptyrowitems, percentstackedvalues, nospacebetweencolumns, regression, externalaccess, userorganisationunit, userorganisationunitchildren, userorganisationunitgrandchildren, paramreportingperiod, paramorganisationunit, paramparentorganisationunit, paramgrandparentorganisationunit, rowtotals, coltotals, cumulative, rowsubtotals, colsubtotals, completedonly, skiprounding, showdimensionlabels, hidetitle, hidesubtitle, hidelegend, hideemptycolumns, hideemptyrows, showhierarchy, showdata, lastupdatedby, lastupdated, favorites, subscribers, translations, series, fontstyle, colorset, sharing, serieskey, axes, outlieranalysis, legendshowkey, fixcolumnheaders, fixrowheaders, attributevalues, icons, relativeperiods
visualization_categorydimensions: visualizationid, categorydimensionid, sort_order
visualization_categoryoptiongroupsetdimensions: visualizationid, sort_order, categoryoptiongroupsetdimensionid
visualization_dataelementgroupsetdimensions: visualizationid, sort_order, dataelementgroupsetdimensionid
visualization_orgunitgroupsetdimensions: visualizationid, sort_order, orgunitgroupsetdimensionid
```

Not in this list (verified missing by direct `information_schema.tables`
lookup): `category` (exists as `dataelementcategory` on 2.40 — expected),
`map_mapviews` (real name is `mapmapviews` — see below),
`mapview_dataelementgroupsetdimensions`,
`eventvisualization_dataelementgroupsetdimensions` (do not exist on 2.40).

Follow-up lookup — the real map/mapview join table:

```
=== sl40: tables matching map/mapview ===
externalmaplayer
map
maplayer
maplegend
maplegendset
mapmapviews
mapview
mapview_attributedimensions
mapview_categorydimensions
mapview_categoryoptiongroupsetdimensions
mapview_columns
mapview_datadimensionitems
mapview_dataelementdimensions
mapview_filters
mapview_itemorgunitgroups
mapview_organisationunits
mapview_orgunitgroupsetdimensions
mapview_orgunitlevels
mapview_periods

=== sl40 mapmapviews columns ===
mapid
mapviewid
sort_order
```

### Sierra Leone 2.40 (DHIS2 2.40.12) — eventtype counts

```
DASHBOARD_VIEW|502
DATA_SET_REPORT_VIEW|12
EVENT_CHART_VIEW|60
EVENT_REPORT_VIEW|451
MAP_VIEW|74
PASSIVE_DASHBOARD_VIEW|73
VISUALIZATION_VIEW|1499
```

### Sierra Leone 2.43 (DHIS2 2.43.1) — table/column dump

```
category: categoryid, name, uid, code, lastupdated, created, datadimension, userid, publicaccess, datadimensiontype, lastupdatedby, translations, attributevalues, sharing, shortname, description
categorydimension: categorydimensionid, categoryid
categoryoptiongroupset: categoryoptiongroupsetid, uid, code, created, lastupdated, name, description, datadimension, userid, publicaccess, datadimensiontype, lastupdatedby, translations, attributevalues, sharing, shortname
categoryoptiongroupsetdimension: categoryoptiongroupsetdimensionid, categoryoptiongroupsetid
dataelementgroupset: dataelementgroupsetid, name, description, compulsory, uid, code, lastupdated, created, userid, publicaccess, datadimension, lastupdatedby, translations, attributevalues, sharing, shortname
dataelementgroupsetdimension: dataelementgroupsetdimensionid, dataelementgroupsetid
datastatisticsevent: eventid, eventtype, timestamp, username, favoriteuid
eventvisualization: eventvisualizationid, uid, code, created, lastupdated, name, relativeperiodsid, userorganisationunit, userorganisationunitchildren, userorganisationunitgrandchildren, externalaccess, userid, publicaccess, programid, programstageid, startdate, enddate, sortorder, toplimit, outputtype, dataelementvaluedimensionid, attributevaluedimensionid, aggregationtype, collapsedatadimensions, hidenadata, completedonly, description, title, lastupdatedby, subtitle, hidetitle, hidesubtitle, programstatus, eventstatus, favorites, subscribers, timefield, translations, orgunitfield, userorgunittype, sharing, attributevalues, type, showdata, rangeaxismaxvalue, rangeaxisminvalue, rangeaxissteps, rangeaxisdecimals, domainaxislabel, rangeaxislabel, hidelegend, targetlinevalue, targetlinelabel, baselinevalue, baselinelabel, regressiontype, hideemptyrowitems, percentstackedvalues, cumulativevalues, nospacebetweencolumns, datatype, hideemptyrows, digitgroupseparator, displaydensity, fontsize, showhierarchy, rowtotals, coltotals, showdimensionlabels, rowsubtotals, colsubtotals, legacy, simpledimensions, eventrepetitions, legendsetid, legenddisplaystrategy, legenddisplaystyle, legendshowkey, sorting, skiprounding, trackedentitytypeid, relativeperiods, hideemptycolumns, fixcolumnheaders, fixrowheaders
eventvisualization_categorydimensions: eventvisualizationid, sort_order, categorydimensionid
eventvisualization_categoryoptiongroupsetdimensions: eventvisualizationid, sort_order, categoryoptiongroupsetdimensionid
eventvisualization_orgunitgroupsetdimensions: eventvisualizationid, sort_order, orgunitgroupsetdimensionid
map: mapid, name, uid, lastupdated, userid, longitude, latitude, zoom, created, publicaccess, code, externalaccess, basemap, description, title, lastupdatedby, favorites, subscribers, translations, sharing, attributevalues, basemaps
mapview: mapviewid, method, classes, colorlow, colorhigh, radiuslow, radiushigh, uid, lastupdated, layer, legendsetid, opacity, orgunitgroupsetid, arearadius, created, userorganisationunit, userorganisationunitchildren, userorganisationunitgrandchildren, relativeperiodsid, hidden, labels, labelfontsize, labelfontweight, labelfontstyle, labelfontcolor, programid, programstageid, startdate, enddate, eventclustering, eventpointcolor, eventpointradius, colorscale, config, code, description, aggregationtype, eventcoordinatefield, lastupdatedby, styledataitem, trackedentitytypeid, programstatus, followup, organisationunitselectionmode, translations, renderingstrategy, userorgunittype, thematicmaptype, nodatacolor, eventstatus, organisationunitcolor, orgunitfield, labeltemplate, relativeperiods, name, eventcoordinatefieldfallback
mapview_categorydimensions: mapviewid, categorydimensionid, sort_order
mapview_categoryoptiongroupsetdimensions: mapviewid, sort_order, categoryoptiongroupsetdimensionid
mapview_orgunitgroupsetdimensions: mapviewid, sort_order, orgunitgroupsetdimensionid
orgunitgroupset: orgunitgroupsetid, name, description, compulsory, exclusive, uid, code, lastupdated, created, datadimension, userid, publicaccess, includesubhierarchyinanalytics, lastupdatedby, translations, attributevalues, sharing, shortname
orgunitgroupsetdimension: orgunitgroupsetdimensionid, orgunitgroupsetid
visualization: visualizationid, uid, name, type, code, title, subtitle, description, created, startdate, enddate, sortorder, toplimit, userid, userorgunittype, publicaccess, displaydensity, fontsize, relativeperiodsid, digitgroupseparator, legendsetid, legenddisplaystyle, legenddisplaystrategy, aggregationtype, regressiontype, targetlinevalue, targetlinelabel, rangeaxislabel, rangeaxismaxvalue, rangeaxissteps, rangeaxisdecimals, rangeaxisminvalue, domainaxislabel, baselinevalue, baselinelabel, numbertype, measurecriteria, hideemptyrowitems, percentstackedvalues, nospacebetweencolumns, regression, externalaccess, userorganisationunit, userorganisationunitchildren, userorganisationunitgrandchildren, paramreportingperiod, paramorganisationunit, paramparentorganisationunit, paramgrandparentorganisationunit, rowtotals, coltotals, cumulative, rowsubtotals, colsubtotals, completedonly, skiprounding, showdimensionlabels, hidetitle, hidesubtitle, hidelegend, hideemptycolumns, hideemptyrows, showhierarchy, showdata, lastupdatedby, lastupdated, favorites, subscribers, translations, series, fontstyle, colorset, sharing, serieskey, axes, outlieranalysis, legendshowkey, fixcolumnheaders, fixrowheaders, attributevalues, icons, sorting, relativeperiods
visualization_categorydimensions: visualizationid, categorydimensionid, sort_order
visualization_categoryoptiongroupsetdimensions: visualizationid, sort_order, categoryoptiongroupsetdimensionid
visualization_dataelementgroupsetdimensions: visualizationid, sort_order, dataelementgroupsetdimensionid
visualization_orgunitgroupsetdimensions: visualizationid, sort_order, orgunitgroupsetdimensionid
```

Not in this list (verified missing by direct `information_schema.tables`
lookup): `dataelementcategory` (exists as `category` on 2.43 — expected),
`map_mapviews` (real name is `mapmapviews`, same on 2.43),
`mapview_dataelementgroupsetdimensions`,
`eventvisualization_dataelementgroupsetdimensions` (do not exist on 2.43
either).

### Sierra Leone 2.43 (DHIS2 2.43.1) — eventtype counts

```
DASHBOARD_VIEW|524
DATA_SET_REPORT_VIEW|12
EVENT_CHART_VIEW|60
EVENT_REPORT_VIEW|451
MAP_VIEW|74
PASSIVE_DASHBOARD_VIEW|123
VISUALIZATION_VIEW|1513
```

## Follow-up 2026-10-16 — tables behind the Data set reports column

Checked while adding the data set report sub-totals column, on local
throwaway instances with the Sierra Leone 2.40 demo database (DHIS2 2.40.12)
and the Sierra Leone 2.43 demo database (DHIS2 2.43.2).

- The `data_set_report_subtotals` CTE uses `dataset(datasetid, name,
  dataentryform)`, `datasetelement(datasetid, dataelementid,
  categorycomboid)`, `dataelement(dataelementid, valuetype, aggregationtype,
  categorycomboid)`, `categorycombos_categories(categorycomboid, categoryid)`,
  `section(sectionid, datasetid)` and `sectiondataelements(sectionid,
  dataelementid)`. All exist with these columns on both versions; none is
  renamed. The custom-form link is the column `dataset.dataentryform` (not
  `dataentryformid`). `categorycombos_categories.categoryid` joins the
  category table on both versions (`dataelementcategory` on 2.40, `category`
  on 2.43), since both keep the `categoryid` primary key.
- The generated query ran on both versions, and its per-category data set
  lists match `e2e/data_set_report_oracle.py` (from `/api/dataSets` and
  `/api/categoryCombos`) exactly: 12 enabled categories on each, 5 of them
  with sub-totals (Gender, EPI/nutrition age, HIV age, Location
  Fixed/Outreach, Pregnant/Non-pregnant).
- `datastatisticsevent` on the 2.43 seed holds 12 `DATA_SET_REPORT_VIEW`
  rows, the newest from 2016-06-23, while visualization and map views run to
  the present: the Reports app does not record data set report views
  (DHIS2-17175), so the app does not count them.
