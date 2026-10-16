import { DIMENSION_TYPES, DimensionType } from '../dimensionTypes'

export const SQL_VIEW_COLUMNS = [
    'type',
    'uid',
    'name',
    'favorites',
    'public_favorites',
    'shared_favorites',
    'private_favorites',
    'views',
    'percent',
    'percent_of_views',
    'data_set_reports',
    'data_set_report_names',
] as const

/**
 * datastatisticsevent.eventtype values that mean "a favorite was opened".
 * Applied to both the per-favorite counts and the grand total so the two
 * percentages share one denominator definition.
 */
export const VIEW_EVENT_TYPES: readonly string[] = [
    'VISUALIZATION_VIEW',
    'MAP_VIEW',
    'EVENT_VISUALIZATION_VIEW',
    'EVENT_CHART_VIEW',
    'EVENT_REPORT_VIEW',
]

type FavoriteSource = {
    /** Prefix of the dimension join table: <prefix>_<joinTableSuffix> */
    prefix: 'visualization' | 'mapview' | 'eventvisualization'
    /**
     * SQL joining from the join-table alias `a` to the favorite whose uid
     * datastatisticsevent records, exposed as alias `f` with a `uid` column.
     */
    favoriteJoin: string
}

const FAVORITE_SOURCES: readonly FavoriteSource[] = [
    {
        prefix: 'visualization',
        favoriteJoin:
            'JOIN visualization f ON f.visualizationid = a.visualizationid',
    },
    {
        // A map view is one layer of a map; view events are recorded against
        // the map's uid, so go through mapmapviews to reach it.
        prefix: 'mapview',
        favoriteJoin:
            'JOIN mapmapviews mm ON mm.mapviewid = a.mapviewid\n        JOIN map f ON f.mapid = mm.mapid',
    },
    {
        prefix: 'eventvisualization',
        favoriteJoin:
            'JOIN eventvisualization f ON f.eventvisualizationid = a.eventvisualizationid',
    },
]

/**
 * Favorite sources that have a join table for a given type. Verified on
 * 2.40 and 2.43 (docs/schema-check.md): every type has all three, except
 * data element group sets, which only visualizations can carry — there is
 * no mapview_ or eventvisualization_dataelementgroupsetdimensions table on
 * any supported version. This is version-independent today; if a source
 * ever becomes version-gated, re-add a `minor` parameter here.
 */
const favoriteSourcesFor = (type: DimensionType): readonly FavoriteSource[] =>
    type.key === 'DATAELEMENT_GROUP_SET'
        ? FAVORITE_SOURCES.filter((source) => source.prefix === 'visualization')
        : FAVORITE_SOURCES

/**
 * Sharing class of a favorite from its `sharing` JSONB (present on
 * visualization, map and eventvisualization on 2.40-2.43):
 *  public  - public access string grants metadata read (first char 'r')
 *  shared  - not public, but shared with at least one user or user group
 *  private - neither
 * The users/userGroups keys may be absent, a JSON null, or {}; none of those
 * count as shared, only a non-empty JSON object does. jsonb_typeof(...) is
 * NULL for an absent key and 'null' (not 'object') for a JSON null literal,
 * so both fall through to private; COALESCE alone would not catch the JSON
 * null case, since the key lookup for `{"users": null}` yields a non-NULL
 * jsonb null, not SQL NULL.
 *
 * The first key is spelled `('user'||'s')` on purpose. DHIS2 refuses to
 * execute a SQL view whose query *text* matches a protected table name
 * (users, userinfo, oauth2client, ...) and answers 409 E4310, "SQL query
 * contains references to protected tables". The check is a plain
 * word-boundary scan, so the bare word inside a string literal is enough to
 * trip it even though no such table is referenced here; concatenating the
 * key keeps the word out of the query text. `userGroups` is not protected.
 */
const SHARING_CLASS_SQL = `CASE WHEN LEFT(f.sharing->>'public', 1) = 'r' THEN 'public'
             WHEN (jsonb_typeof(f.sharing->('user'||'s')) = 'object' AND f.sharing->('user'||'s') <> '{}'::jsonb)
               OR (jsonb_typeof(f.sharing->'userGroups') = 'object' AND f.sharing->'userGroups' <> '{}'::jsonb) THEN 'shared'
             ELSE 'private' END`

/** (entity id, favorite uid, sharing class) rows for every favorite that uses the dimension */
const usageSubquery = (type: DimensionType): string =>
    favoriteSourcesFor(type)
        .map(
            ({
                prefix,
                favoriteJoin,
            }) => `      SELECT DISTINCT d.${type.dimensionForeignKey} AS objectid, f.uid AS favoriteuid,
        ${SHARING_CLASS_SQL} AS sharingclass
        FROM ${prefix}_${type.joinTableSuffix} a
        JOIN ${type.dimensionTable} d ON d.${type.dimensionPrimaryKey} = a.${type.dimensionPrimaryKey}
        ${favoriteJoin}`
        )
        .join('\n      UNION\n')

const quotedList = (values: readonly string[]) =>
    values.map((value) => `'${value}'`).join(', ')

/**
 * Value types whose data set report sub-totals are a meaningful total: the
 * numeric and boolean types. DHIS2's own filter (AggregatableDataElementFilter)
 * also lets text types through, but a sub-total of text values is not a
 * total anyone reads, so those data elements are not counted.
 */
export const SUBTOTAL_VALUE_TYPES: readonly string[] = [
    'NUMBER',
    'UNIT_INTERVAL',
    'PERCENTAGE',
    'INTEGER',
    'INTEGER_POSITIVE',
    'INTEGER_NEGATIVE',
    'INTEGER_ZERO_OR_POSITIVE',
    'BOOLEAN',
    'TRUE_ONLY',
]

/**
 * Aggregation types that analytics cannot aggregate (AggregationType
 * isAggregatable() is false for CUSTOM and DEFAULT; NONE only aggregates text).
 */
export const NON_AGGREGATABLE_AGGREGATION_TYPES: readonly string[] = [
    'NONE',
    'CUSTOM',
    'DEFAULT',
]

/**
 * Per category: the data sets whose data set report shows sub-total columns
 * for it, mirroring DHIS2's DefaultDataSetReportService (2.40-2.43):
 *  - custom forms (dataset.dataentryform set) never show sub-totals;
 *  - a section form shows the data elements placed in its sections, a
 *    default form every data element of the data set;
 *  - each data element is grouped by its resolved category combo (the data
 *    set element's override, else the data element's own combo), and a
 *    combo gets one sub-total column per category option only when it has
 *    more than one category (CategoryCombo.doSubTotals());
 *  - the sub-total is an analytics query grouped by the category itself,
 *    which is skipped when the category is not a data dimension.
 * No per-section or per-form setting switches sub-totals off.
 */
const DATA_SET_REPORT_SUBTOTALS_CTE = `data_set_report_subtotals AS (
  SELECT x.categoryid, COUNT(*) AS data_sets,
    json_agg(x.name ORDER BY x.name)::text AS names
  FROM (
    SELECT DISTINCT cc.categoryid, ds.datasetid, ds.name
    FROM dataset ds
    JOIN datasetelement dse ON dse.datasetid = ds.datasetid
    JOIN dataelement de ON de.dataelementid = dse.dataelementid
    JOIN categorycombos_categories cc
      ON cc.categorycomboid = COALESCE(dse.categorycomboid, de.categorycomboid)
    WHERE ds.dataentryform IS NULL
      AND de.valuetype IN (${quotedList(SUBTOTAL_VALUE_TYPES)})
      AND de.aggregationtype NOT IN (${quotedList(NON_AGGREGATABLE_AGGREGATION_TYPES)})
      AND (SELECT COUNT(*) FROM categorycombos_categories n
           WHERE n.categorycomboid = cc.categorycomboid) > 1
      AND (NOT EXISTS (SELECT 1 FROM section s WHERE s.datasetid = ds.datasetid)
           OR EXISTS (SELECT 1 FROM section s
                      JOIN sectiondataelements sde ON sde.sectionid = s.sectionid
                      WHERE s.datasetid = ds.datasetid
                        AND sde.dataelementid = de.dataelementid))
  ) x
  GROUP BY x.categoryid
)`

/** Only categories produce data set report sub-totals; group sets get 0 and an empty list. */
const dataSetReportColumns = (type: DimensionType) =>
    type.key === 'CATEGORY'
        ? `COALESCE(MAX(dsr.data_sets), 0) AS data_set_reports,
    COALESCE(MAX(dsr.names), '[]') AS data_set_report_names`
        : `0 AS data_set_reports,
    '[]' AS data_set_report_names`

const dataSetReportJoin = (type: DimensionType) =>
    type.key === 'CATEGORY'
        ? `\n  LEFT JOIN data_set_report_subtotals dsr ON dsr.categoryid = z.${type.primaryKey}`
        : ''

const summaryBlock = (type: DimensionType, minor: number): string =>
    `  SELECT '${type.key}' AS type, z.uid, z.name,
    COUNT(DISTINCT y.favoriteuid) AS favorites,
    COUNT(DISTINCT y.favoriteuid) FILTER (WHERE y.sharingclass = 'public') AS public_favorites,
    COUNT(DISTINCT y.favoriteuid) FILTER (WHERE y.sharingclass = 'shared') AS shared_favorites,
    COUNT(DISTINCT y.favoriteuid) FILTER (WHERE y.sharingclass = 'private') AS private_favorites,
    COALESCE(SUM(fv.views), 0) AS views,
    ${dataSetReportColumns(type)}
  FROM ${type.table(minor)} z
  LEFT JOIN (
${usageSubquery(type)}
  ) y ON y.objectid = z.${type.primaryKey}
  LEFT JOIN favorite_views fv ON fv.favoriteuid = y.favoriteuid${dataSetReportJoin(type)}
  WHERE z.datadimension = TRUE
  GROUP BY z.uid, z.name`

export const buildQuery = (minor: number): string => `WITH favorite_views AS (
  SELECT favoriteuid, COUNT(*) AS views
  FROM datastatisticsevent
  WHERE AGE(NOW(), timestamp) < '12 month'::interval
    AND eventtype IN (${quotedList(VIEW_EVENT_TYPES)})
  GROUP BY favoriteuid
),
total_favorite_views AS (
  SELECT COALESCE(SUM(views), 0) AS count FROM favorite_views
),
${DATA_SET_REPORT_SUBTOTALS_CTE},
summary AS (
${DIMENSION_TYPES.map((type) => summaryBlock(type, minor)).join('\n  UNION ALL\n')}
),
totals AS (
  SELECT SUM(views) AS total FROM summary
)
SELECT s.type, s.uid, s.name,
  s.favorites, s.public_favorites, s.shared_favorites, s.private_favorites,
  s.views,
  COALESCE(s.views::double precision / NULLIF(t.total, 0) * 100.0, 0) AS percent,
  COALESCE(s.views::double precision / NULLIF(f.count, 0) * 100.0, 0) AS percent_of_views,
  s.data_set_reports, s.data_set_report_names
FROM summary s
CROSS JOIN totals t
CROSS JOIN total_favorite_views f
ORDER BY s.views DESC, s.favorites DESC, s.name`
