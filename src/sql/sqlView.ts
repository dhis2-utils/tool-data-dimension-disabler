import { buildQuery } from './buildQuery'

/** Same UID as the original "Category dimension usage" view, so an old install is updated, not duplicated. */
export const SQL_VIEW_ID = 'GOLswS44mh8'
export const SQL_VIEW_NAME = 'Data dimension usage'

export type SqlViewDefinition = {
    id: string
    name: string
    description: string
    type: 'QUERY'
    cacheStrategy: 'NO_CACHE'
    sharing: { public: string }
    sqlQuery: string
}

export const buildSqlViewDefinition = (minor: number): SqlViewDefinition => ({
    id: SQL_VIEW_ID,
    name: SQL_VIEW_NAME,
    description:
        'Installed by the Data Dimension Disabler Tool app. Ranks categories and group sets that are enabled as data dimensions by favorite views in the last 12 months. Safe to delete; the app recreates it on demand.',
    type: 'QUERY',
    cacheStrategy: 'NO_CACHE',
    // Metadata read + data read: /sqlViews/{uid}/data checks data-read access.
    sharing: { public: 'r-r-----' },
    sqlQuery: buildQuery(minor),
})

export const normaliseSql = (sql: string): string =>
    sql.replace(/\s+/g, ' ').trim()

/** True when the installed view's query matches what this app version would generate for this server. */
export const isCurrentSqlQuery = (
    installedSqlQuery: string | undefined,
    minor: number
): boolean =>
    installedSqlQuery !== undefined &&
    normaliseSql(installedSqlQuery) === normaliseSql(buildQuery(minor))
