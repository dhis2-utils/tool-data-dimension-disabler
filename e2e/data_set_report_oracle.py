"""An independent second answer to "which data set reports show sub-totals
for this category?".

The app's SQL view answers it from the database tables. This oracle answers
it from the metadata Web API instead (`/api/dataSets`, `/api/categoryCombos`)
and applies DHIS2's data set report rules in Python, so a wrong join, a
missed combo override or a mis-read form type in the SQL shows up as a
mismatch rather than being copied.

The rules are spelled out here from DHIS2 core (DefaultDataSetReportService,
AnalyticsDataSetReportStore, CategoryCombo.doSubTotals, 2.40-2.43), not
derived from `src/`: an oracle built from the code under test proves nothing.

- A data set with a custom form (`dataEntryForm`) never shows sub-totals.
- A section form shows the data elements placed in its sections; a default
  form shows every data element of the data set.
- Each data element is grouped by its resolved category combo: the data set
  element's own `categoryCombo` when set, else the data element's.
- A combo shows one sub-total column per category option only when it has
  more than one category.
- Only numeric and boolean data elements with an aggregation type analytics
  can aggregate are counted (the app's chosen definition, see README).
"""

SUBTOTAL_VALUE_TYPES = {
    "NUMBER",
    "UNIT_INTERVAL",
    "PERCENTAGE",
    "INTEGER",
    "INTEGER_POSITIVE",
    "INTEGER_NEGATIVE",
    "INTEGER_ZERO_OR_POSITIVE",
    "BOOLEAN",
    "TRUE_ONLY",
}
NON_AGGREGATABLE = {"NONE", "CUSTOM", "DEFAULT"}

DATA_SET_FIELDS = (
    "id,name,dataEntryForm[id],sections[dataElements[id]],"
    "dataSetElements[categoryCombo[id],"
    "dataElement[id,valueType,aggregationType,categoryCombo[id]]]"
)


class UnreadableMetadata(Exception):
    """The account cannot list data sets or category combos."""


def _get_all(client, endpoint, fields):
    status, body = client.get(f"/api/{endpoint}?paging=false&fields={fields}")
    if status != 200:
        raise UnreadableMetadata(f"GET /api/{endpoint} answered {status}")
    return body.get(endpoint) or []


def _counts(element):
    data_element = element.get("dataElement") or {}
    return (
        data_element.get("valueType") in SUBTOTAL_VALUE_TYPES
        and data_element.get("aggregationType") not in NON_AGGREGATABLE
    )


def _resolved_combo(element):
    own = (element.get("categoryCombo") or {}).get("id")
    return own or ((element.get("dataElement") or {}).get("categoryCombo") or {}).get(
        "id"
    )


def _shown_data_elements(data_set):
    """Data element ids the report shows, or None for every element."""
    sections = data_set.get("sections") or []
    if not sections:
        return None
    return {
        data_element["id"]
        for section in sections
        for data_element in section.get("dataElements") or []
    }


def data_set_report_names(client):
    """{category uid: sorted data set names whose report shows its sub-totals}."""
    combo_categories = {
        combo["id"]: [category["id"] for category in combo.get("categories") or []]
        for combo in _get_all(client, "categoryCombos", "id,categories[id]")
    }
    names = {}
    for data_set in _get_all(client, "dataSets", DATA_SET_FIELDS):
        if data_set.get("dataEntryForm"):
            continue
        shown = _shown_data_elements(data_set)
        for element in data_set.get("dataSetElements") or []:
            data_element_id = (element.get("dataElement") or {}).get("id")
            if shown is not None and data_element_id not in shown:
                continue
            if not _counts(element):
                continue
            categories = combo_categories.get(_resolved_combo(element), [])
            if len(categories) < 2:
                continue
            for category in categories:
                names.setdefault(category, set()).add(data_set["name"])
    return {category: sorted(found) for category, found in names.items()}
