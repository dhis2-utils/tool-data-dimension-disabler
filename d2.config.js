/** @type {import('@dhis2/cli-app-scripts').D2Config} */
const config = {
    type: 'app',
    name: 'tool-data-dimension-disabler',
    title: 'Data Dimension Disabler Tool',
    description:
        'Rank categories and group sets that are enabled as data dimensions by how often favorites using them are viewed, and disable the unused ones',
    minDHIS2Version: '2.40',

    entryPoints: {
        app: './src/App.tsx',
    },

    viteConfigExtensions: './viteConfigExtensions.mts',
}

module.exports = config
