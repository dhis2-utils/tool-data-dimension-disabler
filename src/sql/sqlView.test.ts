import { buildQuery } from './buildQuery'
import {
    buildSqlViewDefinition,
    isCurrentSqlQuery,
    normaliseSql,
    SQL_VIEW_ID,
    SQL_VIEW_NAME,
} from './sqlView'

describe('sqlView', () => {
    it('keeps the UID of the original category-only view so installs upgrade in place', () => {
        expect(SQL_VIEW_ID).toBe('GOLswS44mh8')
    })

    it('builds a complete QUERY view definition with public metadata+data read sharing', () => {
        const definition = buildSqlViewDefinition(43)
        expect(definition).toMatchObject({
            id: SQL_VIEW_ID,
            name: SQL_VIEW_NAME,
            type: 'QUERY',
            cacheStrategy: 'NO_CACHE',
            sharing: { public: 'r-r-----' },
        })
        expect(definition.sqlQuery).toBe(buildQuery(43))
        expect(definition.description).toContain('Data Dimension Disabler Tool')
    })

    it('normalises whitespace before comparing', () => {
        expect(normaliseSql('  SELECT  1\n\n FROM   x ')).toBe(
            'SELECT 1 FROM x'
        )
    })

    it('treats the exact or whitespace-different query as current', () => {
        expect(isCurrentSqlQuery(buildQuery(42), 42)).toBe(true)
        expect(
            isCurrentSqlQuery(buildQuery(42).replace(/\n/g, '   \n'), 42)
        ).toBe(true)
    })

    it('treats another version, a legacy query or nothing as outdated', () => {
        expect(isCurrentSqlQuery(buildQuery(40), 41)).toBe(false)
        expect(isCurrentSqlQuery('SELECT z.uid FROM category z', 43)).toBe(
            false
        )
        expect(isCurrentSqlQuery(undefined, 43)).toBe(false)
    })
})
