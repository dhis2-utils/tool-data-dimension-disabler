import { CustomDataProvider, Provider } from '@dhis2/app-runtime'
import { act, renderHook } from '@testing-library/react'
import React from 'react'
import { defaultConfig } from '../test-utils/renderWithProvider'
import { useDisableDimension } from './useDisableDimension'
import { UsageRow } from './useUsageData'

const row: UsageRow = {
    type: 'ORGUNIT_GROUP_SET',
    uid: 'J5jldMd8OHv',
    name: 'Facility Type',
    favorites: 1,
    publicFavorites: 0,
    sharedFavorites: 1,
    privateFavorites: 0,
    views: 0,
    percent: 0,
    percentOfViews: 0,
    dataSetReports: 0,
    dataSetReportNames: [],
}

const wrapperWith =
    (data: Record<string, jest.Mock>) =>
    ({ children }: { children: React.ReactNode }) => (
        <Provider
            config={defaultConfig}
            userInfo={undefined}
            plugin={false}
            parentAlertsAdd={() => undefined}
            showAlertsInPlugin={true}
        >
            <CustomDataProvider data={data} options={{ failOnMiss: true }}>
                {children}
            </CustomDataProvider>
        </Provider>
    )

describe('useDisableDimension', () => {
    it('sends a JSON Patch setting dataDimension=false to the endpoint of the row type', async () => {
        const organisationUnitGroupSets = jest.fn(() => ({ status: 'OK' }))
        const { result } = renderHook(() => useDisableDimension(), {
            wrapper: wrapperWith({ organisationUnitGroupSets }),
        })
        let ok = false
        await act(async () => {
            ok = await result.current.disable(row)
        })
        expect(ok).toBe(true)
        expect(organisationUnitGroupSets).toHaveBeenCalledWith(
            'json-patch',
            expect.objectContaining({
                resource: 'organisationUnitGroupSets',
                id: 'J5jldMd8OHv',
                data: [{ op: 'add', path: '/dataDimension', value: false }],
            }),
            expect.anything()
        )
    })

    it('resolves false and exposes the error when the server rejects', async () => {
        const organisationUnitGroupSets = jest.fn(() => {
            throw new Error('409 Conflict')
        })
        const { result } = renderHook(() => useDisableDimension(), {
            wrapper: wrapperWith({ organisationUnitGroupSets }),
        })
        let ok = true
        await act(async () => {
            ok = await result.current.disable(row)
        })
        expect(ok).toBe(false)
        expect(result.current.state.error?.message).toContain('409')
    })
})
