import { UsageRow } from '../hooks/useUsageData'
import { filterRows, formatPercent, sortRows } from './usageTableUtils'

const rows: UsageRow[] = [
    {
        type: 'CATEGORY',
        uid: 'a',
        name: 'Gender',
        favorites: 3,
        publicFavorites: 1,
        sharedFavorites: 1,
        privateFavorites: 1,
        views: 5,
        percent: 50,
        percentOfViews: 25,
        dataSetReports: 0,
        dataSetReportNames: [],
    },
    {
        type: 'ORGUNIT_GROUP_SET',
        uid: 'b',
        name: 'Area',
        favorites: 2,
        publicFavorites: 1,
        sharedFavorites: 0,
        privateFavorites: 1,
        views: 10,
        percent: 40,
        percentOfViews: 20,
        dataSetReports: 0,
        dataSetReportNames: [],
    },
    {
        type: 'CATEGORY',
        uid: 'c',
        name: 'age',
        favorites: 0,
        publicFavorites: 0,
        sharedFavorites: 0,
        privateFavorites: 0,
        views: 0,
        percent: 0,
        percentOfViews: 0,
        dataSetReports: 0,
        dataSetReportNames: [],
    },
]

describe('sortRows', () => {
    it('sorts numerically', () => {
        expect(sortRows(rows, 'views', 'desc').map((r) => r.uid)).toEqual([
            'b',
            'a',
            'c',
        ])
        expect(sortRows(rows, 'views', 'asc').map((r) => r.uid)).toEqual([
            'c',
            'a',
            'b',
        ])
    })
    it('sorts favorites and publicFavorites numerically', () => {
        expect(sortRows(rows, 'favorites', 'desc').map((r) => r.uid)).toEqual([
            'a',
            'b',
            'c',
        ])
        expect(
            sortRows(rows, 'publicFavorites', 'desc').map((r) => r.uid)
        ).toEqual(['b', 'a', 'c'])
    })
    it('sorts names case-insensitively', () => {
        expect(sortRows(rows, 'name', 'asc').map((r) => r.name)).toEqual([
            'age',
            'Area',
            'Gender',
        ])
    })
    it('sorts by type label order and does not mutate the input', () => {
        const copy = [...rows]
        sortRows(rows, 'type', 'asc')
        expect(rows).toEqual(copy)
    })
})

describe('filterRows', () => {
    it('returns everything for ALL and only the chosen type otherwise', () => {
        expect(filterRows(rows, 'ALL')).toHaveLength(3)
        expect(filterRows(rows, 'CATEGORY').map((r) => r.uid)).toEqual([
            'a',
            'c',
        ])
        expect(filterRows(rows, 'DATAELEMENT_GROUP_SET')).toEqual([])
    })
})

describe('formatPercent', () => {
    it('renders one decimal with a percent sign', () => {
        expect(formatPercent(33.333)).toBe('33.3%')
        expect(formatPercent(0)).toBe('0.0%')
        expect(formatPercent(100)).toBe('100.0%')
    })
})
