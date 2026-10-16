import {
    COLUMN_DEFS,
    COLUMNS_STORAGE_KEY,
    DEFAULT_VISIBLE_COLUMNS,
    loadVisibleColumns,
    saveVisibleColumns,
} from './columns'

const memoryStorage = (initial: Record<string, string> = {}): Storage => {
    const data = new Map(Object.entries(initial))
    return {
        getItem: (k) => data.get(k) ?? null,
        setItem: (k, v) => void data.set(k, v),
        removeItem: (k) => void data.delete(k),
        clear: () => data.clear(),
        key: (i) => [...data.keys()][i] ?? null,
        get length() {
            return data.size
        },
    }
}

describe('columns', () => {
    it('lists the eleven columns in display order with type and name always visible', () => {
        expect(COLUMN_DEFS.map((c) => c.key)).toEqual([
            'type',
            'name',
            'uid',
            'favorites',
            'publicFavorites',
            'sharedFavorites',
            'privateFavorites',
            'views',
            'percent',
            'percentOfViews',
            'dataSetReports',
        ])
        expect(
            COLUMN_DEFS.filter((c) => c.alwaysVisible).map((c) => c.key)
        ).toEqual(['type', 'name'])
        for (const column of COLUMN_DEFS) {
            expect(column.label()).not.toHaveLength(0)
            if (column.numeric) {
                expect(column.align).toBe('right')
                expect(column.description?.()).not.toHaveLength(0)
            }
        }
    })

    it('has the agreed defaults', () => {
        expect(DEFAULT_VISIBLE_COLUMNS).toEqual([
            'type',
            'name',
            'uid',
            'favorites',
            'views',
            'percent',
            'dataSetReports',
        ])
    })

    it('returns the defaults when nothing is stored or the value is unreadable', () => {
        expect(loadVisibleColumns(memoryStorage())).toEqual(
            DEFAULT_VISIBLE_COLUMNS
        )
        expect(
            loadVisibleColumns(
                memoryStorage({ [COLUMNS_STORAGE_KEY]: 'not json' })
            )
        ).toEqual(DEFAULT_VISIBLE_COLUMNS)
        expect(
            loadVisibleColumns(
                memoryStorage({ [COLUMNS_STORAGE_KEY]: '{"a":1}' })
            )
        ).toEqual(DEFAULT_VISIBLE_COLUMNS)
        const throwing = {
            ...memoryStorage(),
            getItem: () => {
                throw new Error('blocked')
            },
        }
        expect(loadVisibleColumns(throwing)).toEqual(DEFAULT_VISIBLE_COLUMNS)
    })

    it('restores a stored selection, drops unknown keys, forces type and name, keeps display order', () => {
        const storage = memoryStorage({
            [COLUMNS_STORAGE_KEY]: JSON.stringify([
                'views',
                'bogus',
                'privateFavorites',
                'uid',
            ]),
        })
        expect(loadVisibleColumns(storage)).toEqual([
            'type',
            'name',
            'uid',
            'privateFavorites',
            'views',
        ])
    })

    it('round-trips through save and never throws on a failing storage', () => {
        const storage = memoryStorage()
        saveVisibleColumns(['type', 'name', 'views'], storage)
        expect(loadVisibleColumns(storage)).toEqual(['type', 'name', 'views'])
        const throwing = {
            ...storage,
            setItem: () => {
                throw new Error('quota')
            },
        }
        expect(() =>
            saveVisibleColumns(['type', 'name'], throwing)
        ).not.toThrow()
    })
})
