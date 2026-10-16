import { FetchError } from '@dhis2/app-runtime'
import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import React from 'react'
import { UsageRow } from '../hooks/useUsageData'
import { renderWithProvider } from '../test-utils/renderWithProvider'
import { DisableDialog } from './DisableDialog'

const row: UsageRow = {
    type: 'CATEGORYOPTION_GROUP_SET',
    uid: 'x1',
    name: 'Funding source',
    favorites: 2,
    publicFavorites: 1,
    sharedFavorites: 0,
    privateFavorites: 1,
    views: 3,
    percent: 1,
    percentOfViews: 1,
    dataSetReports: 0,
    dataSetReportNames: [],
}

describe('DisableDialog', () => {
    it('names the object and its type and calls onConfirm', async () => {
        const user = userEvent.setup()
        const onConfirm = jest.fn()
        renderWithProvider(
            <DisableDialog
                row={row}
                loading={false}
                onConfirm={onConfirm}
                onCancel={jest.fn()}
            />
        )
        expect(screen.getByText(/Funding source/)).toBeInTheDocument()
        expect(
            screen.getByText(/category option group set/i)
        ).toBeInTheDocument()
        await user.click(screen.getByRole('button', { name: 'Disable' }))
        expect(onConfirm).toHaveBeenCalled()
    })

    it('calls onCancel', async () => {
        const user = userEvent.setup()
        const onCancel = jest.fn()
        renderWithProvider(
            <DisableDialog
                row={row}
                loading={false}
                onConfirm={jest.fn()}
                onCancel={onCancel}
            />
        )
        await user.click(screen.getByRole('button', { name: 'Cancel' }))
        expect(onCancel).toHaveBeenCalled()
    })

    it('shows the server error and stays open', () => {
        const error = new FetchError({
            type: 'access',
            message: 'You do not have the authority to update this object',
        })
        renderWithProvider(
            <DisableDialog
                row={row}
                loading={false}
                error={error}
                onConfirm={jest.fn()}
                onCancel={jest.fn()}
            />
        )
        expect(
            screen.getByText(/do not have the authority/)
        ).toBeInTheDocument()
        expect(screen.getByRole('button', { name: 'Disable' })).toBeEnabled()
    })

    it('disables both buttons while loading', () => {
        renderWithProvider(
            <DisableDialog
                row={row}
                loading={true}
                onConfirm={jest.fn()}
                onCancel={jest.fn()}
            />
        )
        expect(screen.getByRole('button', { name: 'Disable' })).toBeDisabled()
        expect(screen.getByRole('button', { name: 'Cancel' })).toBeDisabled()
    })

    it('lists the data sets whose report loses its sub-totals', () => {
        renderWithProvider(
            <DisableDialog
                row={{
                    ...row,
                    type: 'CATEGORY',
                    dataSetReports: 2,
                    dataSetReportNames: ['Child Health', 'Reproductive Health'],
                }}
                loading={false}
                onConfirm={jest.fn()}
                onCancel={jest.fn()}
            />
        )
        expect(
            screen.getByTestId('disable-dialog-data-sets')
        ).toHaveTextContent('Child HealthReproductive Health')
    })

    it('does not mention data set reports when no report is affected', () => {
        renderWithProvider(
            <DisableDialog
                row={row}
                loading={false}
                onConfirm={jest.fn()}
                onCancel={jest.fn()}
            />
        )
        expect(
            screen.queryByTestId('disable-dialog-data-sets')
        ).not.toBeInTheDocument()
    })
})
