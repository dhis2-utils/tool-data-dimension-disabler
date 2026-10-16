import i18n from '@dhis2/d2-i18n'
import { getDimensionType } from '../dimensionTypes'
import { UsageRow } from '../hooks/useUsageData'
import { formatPercent } from './usageTableUtils'

export type ColumnKey =
    | 'type'
    | 'name'
    | 'uid'
    | 'favorites'
    | 'publicFavorites'
    | 'sharedFavorites'
    | 'privateFavorites'
    | 'views'
    | 'percent'
    | 'percentOfViews'
    | 'dataSetReports'

export type ColumnDef = {
    key: ColumnKey
    label: () => string
    /** Shown in the header tooltip; required for numeric columns. */
    description?: () => string
    align: 'left' | 'right'
    numeric: boolean
    alwaysVisible: boolean
    format: (row: UsageRow) => string
    /** Items listed in a tooltip on the cell, when there are any. */
    details?: (row: UsageRow) => readonly string[]
}

// Both helpers take an options object (rather than positional arguments)
// purely to stay under the project's max-params lint rule; the shape of the
// resulting ColumnDef is exactly the interface documented above.
const text = (config: {
    key: 'type' | 'name' | 'uid'
    label: () => string
    format: (row: UsageRow) => string
    alwaysVisible?: boolean
}): ColumnDef => ({
    align: 'left',
    numeric: false,
    alwaysVisible: false,
    ...config,
})

const number = (config: {
    key: Exclude<ColumnKey, 'type' | 'name' | 'uid'>
    label: () => string
    description: () => string
    format: (row: UsageRow) => string
    details?: (row: UsageRow) => readonly string[]
}): ColumnDef => ({
    align: 'right',
    numeric: true,
    alwaysVisible: false,
    ...config,
})

export const COLUMN_DEFS: readonly ColumnDef[] = [
    text({
        key: 'type',
        label: () => i18n.t('Type'),
        format: (row) => getDimensionType(row.type).getLabel(),
        alwaysVisible: true,
    }),
    text({
        key: 'name',
        label: () => i18n.t('Name'),
        format: (row) => row.name,
        alwaysVisible: true,
    }),
    text({
        key: 'uid',
        label: () => i18n.t('UID'),
        format: (row) => row.uid,
    }),
    number({
        key: 'favorites',
        label: () => i18n.t('Favorites'),
        description: () =>
            i18n.t(
                'Number of visualizations, maps and event visualizations that use this dimension, regardless of how often they are viewed.'
            ),
        format: (row) => String(row.favorites),
    }),
    number({
        key: 'publicFavorites',
        label: () => i18n.t('Public'),
        description: () =>
            i18n.t(
                'Favorites using this dimension whose public sharing grants at least metadata read.'
            ),
        format: (row) => String(row.publicFavorites),
    }),
    number({
        key: 'sharedFavorites',
        label: () => i18n.t('Shared'),
        description: () =>
            i18n.t(
                'Favorites using this dimension that are not public but are shared with at least one user or user group.'
            ),
        format: (row) => String(row.sharedFavorites),
    }),
    number({
        key: 'privateFavorites',
        label: () => i18n.t('Private'),
        description: () =>
            i18n.t(
                'Favorites using this dimension that are neither public nor shared with anyone; only their owner can open them.'
            ),
        format: (row) => String(row.privateFavorites),
    }),
    number({
        key: 'views',
        label: () => i18n.t('Views'),
        description: () =>
            i18n.t(
                'How many times favorites using this dimension were opened in the last 12 months.'
            ),
        format: (row) => String(row.views),
    }),
    number({
        key: 'percent',
        label: () => i18n.t('% of dimension views'),
        description: () =>
            i18n.t(
                "This dimension's share of all views counted across every enabled dimension."
            ),
        format: (row) => formatPercent(row.percent),
    }),
    number({
        key: 'percentOfViews',
        label: () => i18n.t('% of favorite views'),
        description: () =>
            i18n.t(
                'The same views compared with every favorite view in the last 12 months, including favorites that use no dimension at all.'
            ),
        format: (row) => formatPercent(row.percentOfViews),
    }),
    number({
        key: 'dataSetReports',
        label: () => i18n.t('Data set reports'),
        description: () =>
            i18n.t(
                'Data sets whose data set report shows sub-totals for this category; disabling it leaves those sub-totals empty. Section and default forms only: custom forms never show sub-totals. Hover a number to see the data sets. Group sets never affect data set reports and show a dash.'
            ),
        format: (row) =>
            row.type === 'CATEGORY' ? String(row.dataSetReports) : '–',
        details: (row) => row.dataSetReportNames,
    }),
]

export const DEFAULT_VISIBLE_COLUMNS: readonly ColumnKey[] = [
    'type',
    'name',
    'uid',
    'favorites',
    'views',
    'percent',
    'dataSetReports',
]

export const COLUMNS_STORAGE_KEY = 'data-dimension-disabler.columns'

const ALL_KEYS: readonly ColumnKey[] = COLUMN_DEFS.map((c) => c.key)

export const isColumnKey = (value: unknown): value is ColumnKey =>
    typeof value === 'string' && (ALL_KEYS as readonly string[]).includes(value)

const defaultStorage = (): Storage | undefined =>
    typeof window === 'undefined' ? undefined : window.localStorage

/** Keys in display order, always including the columns that cannot be hidden. */
const normalise = (keys: readonly ColumnKey[]): ColumnKey[] =>
    ALL_KEYS.filter(
        (key) =>
            keys.includes(key) ||
            COLUMN_DEFS.find((c) => c.key === key)?.alwaysVisible
    )

export const loadVisibleColumns = (
    storage: Storage | undefined = defaultStorage()
): ColumnKey[] => {
    try {
        const raw = storage?.getItem(COLUMNS_STORAGE_KEY)
        if (!raw) {
            return [...DEFAULT_VISIBLE_COLUMNS]
        }
        const parsed: unknown = JSON.parse(raw)
        if (!Array.isArray(parsed)) {
            return [...DEFAULT_VISIBLE_COLUMNS]
        }
        return normalise(parsed.filter(isColumnKey))
    } catch {
        return [...DEFAULT_VISIBLE_COLUMNS]
    }
}

export const saveVisibleColumns = (
    keys: readonly ColumnKey[],
    storage: Storage | undefined = defaultStorage()
): void => {
    try {
        storage?.setItem(COLUMNS_STORAGE_KEY, JSON.stringify(normalise(keys)))
    } catch {
        // Storage unavailable (private mode, quota, blocked): the choice simply is not remembered.
    }
}
