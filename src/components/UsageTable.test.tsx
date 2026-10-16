import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import React from 'react'
import { UsageRow } from '../hooks/useUsageData'
import { renderWithProvider } from '../test-utils/renderWithProvider'
import { UsageTable } from './UsageTable'

const rows: UsageRow[] = [
    {
        type: 'CATEGORY',
        uid: 'a',
        name: 'Gender',
        favorites: 3,
        publicFavorites: 2,
        sharedFavorites: 0,
        privateFavorites: 1,
        views: 5,
        percent: 50,
        percentOfViews: 25,
        dataSetReports: 2,
        dataSetReportNames: ['Child Health', 'Reproductive Health'],
    },
    {
        type: 'ORGUNIT_GROUP_SET',
        uid: 'b',
        name: 'Facility Type',
        favorites: 2,
        publicFavorites: 1,
        sharedFavorites: 1,
        privateFavorites: 0,
        views: 10,
        percent: 40,
        percentOfViews: 20,
        dataSetReports: 0,
        dataSetReportNames: [],
    },
    {
        type: 'CATEGORY',
        uid: 'c',
        name: 'Age',
        favorites: 1,
        publicFavorites: 0,
        sharedFavorites: 1,
        privateFavorites: 0,
        views: 0,
        percent: 0,
        percentOfViews: 0,
        dataSetReports: 0,
        dataSetReportNames: [],
    },
]

const bodyRowNames = () =>
    within(screen.getByTestId('usage-table-body'))
        .getAllByTestId('usage-row')
        .map((row) => within(row).getByTestId('usage-row-name').textContent)

// The chooser tests drive a flyout menu with userEvent and take 4-5 s on
// their own; under a full parallel run they crossed Jest's 5 s default.
jest.setTimeout(20000)

describe('UsageTable', () => {
    beforeEach(() => {
        window.localStorage.clear()
    })

    it('renders rows sorted by views descending by default with type labels and percentages', () => {
        renderWithProvider(<UsageTable rows={rows} onDisable={jest.fn()} />)
        expect(bodyRowNames()).toEqual(['Facility Type', 'Gender', 'Age'])
        expect(
            screen.getByText('Organisation unit group set')
        ).toBeInTheDocument()
        expect(screen.getByText('50.0%')).toBeInTheDocument()
    })

    it('filters by type', async () => {
        const user = userEvent.setup()
        renderWithProvider(<UsageTable rows={rows} onDisable={jest.fn()} />)
        await user.click(
            within(screen.getByTestId('type-filter')).getByTestId(
                'dhis2-uicore-select-input'
            )
        )
        await user.click(
            screen.getByText('Category', {
                selector: '[data-test*="option"] *, [data-test*="option"]',
            })
        )
        expect(bodyRowNames()).toEqual(['Gender', 'Age'])
    })

    it('sorts by name when the header sort icon is clicked', async () => {
        const user = userEvent.setup()
        renderWithProvider(<UsageTable rows={rows} onDisable={jest.fn()} />)
        const nameHeader = screen.getByTestId('usage-header-name')
        await user.click(within(nameHeader).getByRole('button'))
        expect(bodyRowNames()).toEqual(['Age', 'Facility Type', 'Gender'])
        await user.click(within(nameHeader).getByRole('button'))
        expect(bodyRowNames()).toEqual(['Gender', 'Facility Type', 'Age'])
    })

    it('sorts a numeric column descending on the first click (most-viewed first)', async () => {
        const user = userEvent.setup()
        renderWithProvider(<UsageTable rows={rows} onDisable={jest.fn()} />)
        const percentHeader = screen.getByTestId('usage-header-percent')
        await user.click(within(percentHeader).getByRole('button'))
        expect(bodyRowNames()).toEqual(['Gender', 'Facility Type', 'Age'])
    })

    it('calls onDisable with the row', async () => {
        const user = userEvent.setup()
        const onDisable = jest.fn()
        renderWithProvider(<UsageTable rows={rows} onDisable={onDisable} />)
        const genderRow = screen
            .getAllByTestId('usage-row')
            .find(
                (row) =>
                    within(row).getByTestId('usage-row-name').textContent ===
                    'Gender'
            )
        await user.click(
            within(genderRow as HTMLElement).getByRole('button', {
                name: 'Disable',
            })
        )
        expect(onDisable).toHaveBeenCalledWith(rows[0])
    })

    it('shows an empty state', () => {
        renderWithProvider(<UsageTable rows={[]} onDisable={jest.fn()} />)
        expect(
            screen.getByText('No enabled data dimensions found')
        ).toBeInTheDocument()
    })

    it('shows the enabled-dimension count, pluralized correctly', async () => {
        const user = userEvent.setup()
        renderWithProvider(<UsageTable rows={rows} onDisable={jest.fn()} />)
        expect(screen.getByTestId('usage-count').textContent).toBe(
            '3 enabled dimensions'
        )

        await user.click(
            within(screen.getByTestId('type-filter')).getByTestId(
                'dhis2-uicore-select-input'
            )
        )
        await user.click(
            screen.getByText('Category', {
                selector: '[data-test*="option"] *, [data-test*="option"]',
            })
        )
        expect(screen.getByTestId('usage-count').textContent).toBe(
            '2 enabled dimensions'
        )
    })

    it('uses the singular form for a single enabled dimension', () => {
        renderWithProvider(
            <UsageTable rows={[rows[0]]} onDisable={jest.fn()} />
        )
        expect(screen.getByTestId('usage-count').textContent).toBe(
            '1 enabled dimension'
        )
    })

    it('shows the default columns and hides the rest', () => {
        renderWithProvider(<UsageTable rows={rows} onDisable={jest.fn()} />)
        for (const key of [
            'type',
            'name',
            'uid',
            'favorites',
            'views',
            'percent',
            'dataSetReports',
        ]) {
            expect(
                screen.getByTestId(`usage-header-${key}`)
            ).toBeInTheDocument()
        }
        for (const key of [
            'publicFavorites',
            'sharedFavorites',
            'privateFavorites',
            'percentOfViews',
        ]) {
            expect(
                screen.queryByTestId(`usage-header-${key}`)
            ).not.toBeInTheDocument()
        }
    })

    it('adds a column from the chooser and remembers it', async () => {
        const user = userEvent.setup()
        renderWithProvider(<UsageTable rows={rows} onDisable={jest.fn()} />)
        await user.click(screen.getByRole('button', { name: /Manage view/ }))
        await user.click(
            screen.getByRole('menuitemcheckbox', { name: /Private/ })
        )
        expect(
            screen.getByTestId('usage-header-privateFavorites')
        ).toBeInTheDocument()
        expect(
            JSON.parse(
                window.localStorage.getItem(
                    'data-dimension-disabler.columns'
                ) ?? '[]'
            )
        ).toContain('privateFavorites')
    })

    it('renders the favorite counts in the row', async () => {
        const user = userEvent.setup()
        renderWithProvider(<UsageTable rows={rows} onDisable={jest.fn()} />)
        const genderRow = screen
            .getAllByTestId('usage-row')
            .find(
                (row) =>
                    within(row).getByTestId('usage-row-name').textContent ===
                    'Gender'
            ) as HTMLElement
        expect(
            within(genderRow).getByTestId('usage-cell-favorites')
        ).toHaveTextContent(String(rows[0].favorites))
        await user.click(screen.getByRole('button', { name: /Manage view/ }))
        await user.click(
            screen.getByRole('menuitemcheckbox', { name: /Public/ })
        )
        expect(
            within(genderRow).getByTestId('usage-cell-publicFavorites')
        ).toHaveTextContent(String(rows[0].publicFavorites))
    })

    it('sorts by favorites descending on first click', async () => {
        const user = userEvent.setup()
        renderWithProvider(<UsageTable rows={rows} onDisable={jest.fn()} />)
        await user.click(
            within(screen.getByTestId('usage-header-favorites')).getByRole(
                'button'
            )
        )
        const values = screen
            .getAllByTestId('usage-cell-favorites')
            .map((cell) => Number(cell.textContent))
        expect(values).toEqual([...values].sort((a, b) => b - a))
    })

    it('shows an info tooltip icon on numeric headers only', () => {
        renderWithProvider(<UsageTable rows={rows} onDisable={jest.fn()} />)
        expect(screen.getByTestId('column-info-views')).toBeInTheDocument()
        expect(screen.queryByTestId('column-info-name')).not.toBeInTheDocument()
    })

    it('shows the data set report count for categories and a dash for group sets', () => {
        renderWithProvider(<UsageTable rows={rows} onDisable={jest.fn()} />)
        const cellOf = (name: string) =>
            within(
                screen
                    .getAllByTestId('usage-row')
                    .find(
                        (row) =>
                            within(row).getByTestId('usage-row-name')
                                .textContent === name
                    ) as HTMLElement
            ).getByTestId('usage-cell-dataSetReports')
        expect(cellOf('Gender')).toHaveTextContent('2')
        expect(cellOf('Age')).toHaveTextContent('0')
        expect(cellOf('Facility Type')).toHaveTextContent('–')
        // Only a non-empty list gets a tooltip trigger
        expect(
            within(cellOf('Age')).queryByTestId(
                'usage-cell-details-dataSetReports'
            )
        ).not.toBeInTheDocument()
    })

    it('lists the data sets in a tooltip on the count', async () => {
        const user = userEvent.setup()
        renderWithProvider(<UsageTable rows={rows} onDisable={jest.fn()} />)
        await user.hover(
            screen.getByTestId('usage-cell-details-dataSetReports')
        )
        expect(await screen.findByText('Child Health')).toBeInTheDocument()
        expect(screen.getByText('Reproductive Health')).toBeInTheDocument()
    })
})
