import i18n from '@dhis2/d2-i18n'
import {
    Button,
    DataTable,
    DataTableBody,
    DataTableCell,
    DataTableColumnHeader,
    DataTableHead,
    DataTableRow,
    Tooltip,
} from '@dhis2/ui'
import React, { useState } from 'react'
import { UsageRow } from '../hooks/useUsageData'
import { ColumnChooser } from './ColumnChooser'
import { ColumnHeaderLabel } from './ColumnHeaderLabel'
import {
    COLUMN_DEFS,
    ColumnDef,
    ColumnKey,
    loadVisibleColumns,
    saveVisibleColumns,
} from './columns'
import { TypeFilter } from './TypeFilter'
import classes from './UsageTable.module.css'
import {
    filterRows,
    SortColumn,
    SortDirection,
    sortRows,
    TypeFilterValue,
} from './usageTableUtils'

type Props = {
    rows: UsageRow[]
    onDisable: (row: UsageRow) => void
}

// Mirrors @dhis2/ui's DataTableSortDirection, which is not re-exported as a type
type HeaderSortDirection = 'asc' | 'desc' | 'default'

// Numeric columns start descending (most-viewed first, this tool's
// purpose); text columns start ascending.
const opposite = (direction: SortDirection): SortDirection =>
    direction === 'asc' ? 'desc' : 'asc'

/** UIDs read as identifiers, figures line up: neither is a column-def concern. */
const cellClass = (column: ColumnDef): string | undefined => {
    if (column.key === 'uid') {
        return classes.uid
    }
    return column.numeric ? classes.number : undefined
}

/** The formatted value, with the column's detail list (if any) in a tooltip. */
const CellContent = ({ column, row }: { column: ColumnDef; row: UsageRow }) => {
    const details = column.details?.(row) ?? []
    if (details.length === 0) {
        return <>{column.format(row)}</>
    }
    return (
        <Tooltip
            maxWidth={360}
            content={
                <ul className={classes.detailList}>
                    {details.map((item) => (
                        <li key={item}>{item}</li>
                    ))}
                </ul>
            }
        >
            <span
                className={classes.hasDetails}
                data-test={`usage-cell-details-${column.key}`}
                tabIndex={0}
            >
                {column.format(row)}
            </span>
        </Tooltip>
    )
}

const defaultDirectionFor = (column: SortColumn): SortDirection =>
    COLUMN_DEFS.find((c) => c.key === column)?.numeric ? 'desc' : 'asc'

export const UsageTable = ({ rows, onDisable }: Props) => {
    const [filter, setFilter] = useState<TypeFilterValue>('ALL')
    const [visibleKeys, setVisibleKeys] = useState<ColumnKey[]>(() =>
        loadVisibleColumns()
    )
    const [sort, setSort] = useState<{
        column: SortColumn
        direction: SortDirection
    }>({
        column: 'views',
        direction: 'desc',
    })

    const visibleColumns = COLUMN_DEFS.filter((c) =>
        visibleKeys.includes(c.key)
    )
    const visibleRows = sortRows(
        filterRows(rows, filter),
        sort.column,
        sort.direction
    )

    const changeColumns = (keys: ColumnKey[]) => {
        setVisibleKeys(keys)
        saveVisibleColumns(keys)
    }

    const sortDirectionFor = (column: SortColumn): HeaderSortDirection =>
        sort.column === column ? sort.direction : 'default'

    const toggleSort = (column: SortColumn) =>
        setSort((current) => ({
            column,
            direction:
                current.column === column
                    ? opposite(current.direction)
                    : defaultDirectionFor(column),
        }))

    const countLabel =
        visibleRows.length === 1
            ? i18n.t('1 enabled dimension')
            : i18n.t('{{n}} enabled dimensions', {
                  n: visibleRows.length,
              })

    return (
        <div>
            <div className={classes.toolbar}>
                <div className={classes.controls}>
                    <TypeFilter value={filter} onChange={setFilter} />
                    <ColumnChooser
                        visible={visibleKeys}
                        onChange={changeColumns}
                    />
                </div>
                <span className={classes.count} data-test="usage-count">
                    {countLabel}
                </span>
            </div>
            <DataTable dataTest="usage-table">
                <DataTableHead>
                    <DataTableRow>
                        {visibleColumns.map((column) => (
                            <DataTableColumnHeader
                                key={column.key}
                                dataTest={`usage-header-${column.key}`}
                                className={
                                    column.numeric
                                        ? classes.numericHeader
                                        : undefined
                                }
                                align={column.align}
                                name={column.key}
                                sortDirection={sortDirectionFor(column.key)}
                                sortIconTitle={i18n.t('Sort by {{column}}', {
                                    column: column.label(),
                                })}
                                onSortIconClick={() => toggleSort(column.key)}
                            >
                                <ColumnHeaderLabel column={column} />
                            </DataTableColumnHeader>
                        ))}
                        <DataTableColumnHeader>
                            {i18n.t('Action')}
                        </DataTableColumnHeader>
                    </DataTableRow>
                </DataTableHead>
                <DataTableBody dataTest="usage-table-body">
                    {visibleRows.length === 0 && (
                        <DataTableRow>
                            <DataTableCell
                                colSpan={String(visibleColumns.length + 1)}
                                align="center"
                            >
                                {i18n.t('No enabled data dimensions found')}
                            </DataTableCell>
                        </DataTableRow>
                    )}
                    {visibleRows.map((row) => (
                        <DataTableRow
                            key={`${row.type}-${row.uid}`}
                            dataTest="usage-row"
                        >
                            {visibleColumns.map((column) => (
                                <DataTableCell
                                    key={column.key}
                                    dataTest={
                                        column.key === 'name'
                                            ? 'usage-row-name'
                                            : `usage-cell-${column.key}`
                                    }
                                    align={column.align}
                                    className={cellClass(column)}
                                >
                                    <CellContent column={column} row={row} />
                                </DataTableCell>
                            ))}
                            <DataTableCell className={classes.actionCell}>
                                <Button
                                    small
                                    destructive
                                    secondary
                                    onClick={() => onDisable(row)}
                                >
                                    {i18n.t('Disable')}
                                </Button>
                            </DataTableCell>
                        </DataTableRow>
                    ))}
                </DataTableBody>
            </DataTable>
        </div>
    )
}
