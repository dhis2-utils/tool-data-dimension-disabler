import i18n from '@dhis2/d2-i18n'
import React from 'react'
import classes from './Intro.module.css'

export const Intro = () => (
    <details className={classes.intro} open>
        <summary>{i18n.t('About this tool')}</summary>
        <p>
            {i18n.t(
                'Every metadata type enabled as a data dimension adds a column to the analytics tables. This tool ranks them by how many favorites use them and how often those favorites were opened in the last 12 months, so rarely used dimensions can be disabled. Hover the info icon in the column headers for definitions.'
            )}
        </p>
        <p>
            {i18n.t(
                'Favorites that use a disabled dimension stop working, and data set reports show empty sub-totals for a disabled category (the Data set reports column lists which), so check before disabling. A dimension can be re-enabled at any time in the Maintenance app.'
            )}
        </p>
    </details>
)
