"""One function per tested flow. Each returns a list of (step, status, detail).

Flows are ordered: the suite starts with no SQL view installed and ends with
the view installed again and every dimension re-enabled.
"""

import json
import os
import re
import secrets
import string
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import app_driver as ui
import state as run_state
from dhis2_api import (
    SQL_VIEW_ID,
    SQL_VIEW_PATH,
    Dhis2Client,
    grid_rows,
    hostname_of,
)
from data_set_report_oracle import UnreadableMetadata, data_set_report_names
from favorite_counts_sql import favorite_counts, UnreadableFavorites
from legacy_sql_view import LEGACY_NAME, legacy_definition

PASS = "PASS"
FAIL = "FAIL"
INFO = "INFO"
SKIP = "SKIP"

SQL_VIEW_NAME = "Data dimension usage"
READABLE_SHARING = "r-r-----"
METADATA_READ_ONLY_SHARING = "r-------"
MISSING_NOTICE = "SQL view not installed"
OUTDATED_NOTICE = "SQL view needs an update"
DATA_ERROR_NOTICE = "Could not load dimension usage"

TYPE_LABELS = {
    "CATEGORY": "Category",
    "ORGUNIT_GROUP_SET": "Organisation unit group set",
    "DATAELEMENT_GROUP_SET": "Data element group set",
    "CATEGORYOPTION_GROUP_SET": "Category option group set",
}
TYPE_ENDPOINTS = {
    "CATEGORY": "categories",
    "ORGUNIT_GROUP_SET": "organisationUnitGroupSets",
    "DATAELEMENT_GROUP_SET": "dataElementGroupSets",
    "CATEGORYOPTION_GROUP_SET": "categoryOptionGroupSets",
}

DEFAULT_COLUMNS = (
    "type",
    "name",
    "uid",
    "favorites",
    "views",
    "percent",
    "dataSetReports",
)
DATA_SET_REPORTS_COLUMN = "dataSetReports"
DATA_SET_REPORTS_DETAILS = f"[data-test='usage-cell-details-{DATA_SET_REPORTS_COLUMN}']"
TOOLTIP = "[data-test='dhis2-uicore-tooltip-content']"
# Column keys shown only after the user asks for them, and the oracle key
# each of them is cross-checked against.
SHARING_COLUMNS = {
    "publicFavorites": "public",
    "sharedFavorites": "shared",
    "privateFavorites": "private",
}
FAVORITE_COLUMNS = {"favorites": "favorites", **SHARING_COLUMNS}
# One chooser entry per column defined in src/components/columns.ts.
COLUMN_COUNT = 11
CHOOSER_COLUMN = "privateFavorites"
CHOOSER_COLUMN_LABEL = "Private"
CROSSCHECK_ROW_LIMIT = 3
# A right-aligned header's content may end no further from its column's
# right edge than the cell's own inline padding (12px), plus a px for
# rounding.
MAX_HEADER_OFFSET_PX = 13

# The suite creates this user and deletes it again, so its password is
# generated per run and no credential is kept in the repo. DHIS2 requires at
# least 8 characters including an upper case letter, a digit and a symbol.
LIMITED_PASSWORD = os.environ.get("DHIS2_LIMITED_PASSWORD") or "".join(
    (
        secrets.choice(string.ascii_uppercase),
        secrets.choice(string.ascii_lowercase),
        secrets.choice(string.digits),
        secrets.choice("!@#$%&*"),
        secrets.token_urlsafe(12),
    )
)
SQL_VIEW_AUTHORITY_TEXT = "Add/Update SQL view"
# The limited role needs an authority the acting user can actually grant.
PREFERRED_LIMITED_AUTHORITIES = ("F_SQLVIEW_EXECUTE", "F_DATAVALUE_ADD")


@dataclass
class Context:
    """Everything a flow needs. One browser page, reused across flows."""

    page: object
    client: Dhis2Client
    recorder: ui.ConsoleRecorder
    base_url: str
    label: str
    minor: int
    out_dir: Path
    browser: object
    # Key the server gave the installed app: its URL and M_ authority.
    app_key: str = ""
    # The run record (state.RunState): every change is written to it first.
    state: object = None
    # The throwaway non-superuser account, created on first use.
    limited: Optional[Dhis2Client] = None
    disabled: list = field(default_factory=list)


def _frame(ctx):
    """The app frame, opening the app first when the page is elsewhere."""
    if f"/api/apps/{ctx.app_key}/" not in (ctx.page.url or ""):
        return ui.open_app(ctx.page, ctx.base_url, ctx.app_key)
    return ui.app_frame(ctx.page)


def _table_frame(ctx):
    """The app frame with the usage table rendered (creates the view if missing).

    Right after a load the status query is still in flight and neither the
    table nor a notice exists yet, so wait for whichever the app settles on
    before deciding that the view has to be created.
    """
    frame = _frame(ctx)
    frame.locator(f"{ui.USAGE_TABLE}, {ui.NOTICE_BOX}").first.wait_for(
        state="visible", timeout=ui.DEFAULT_TIMEOUT_MS
    )
    if frame.locator(ui.USAGE_TABLE).count() == 0:
        ui.click_button(frame, ui.CREATE_BUTTON)
    ui.wait_for_table(frame)
    return frame


def _shot(ctx, name):
    path = ui.screenshot(ctx.page, ctx.out_dir, f"{ctx.label}-{name}")
    return path.name


def _click_dialog_button(frame, dialog_selector, name):
    frame.locator(dialog_selector).get_by_role("button", name=name, exact=True).click()


def flow_load_missing(ctx):
    """Check 1a/7/8: fresh load with no view shows the create notice."""
    results = []
    frame = ui.open_app(ctx.page, ctx.base_url, ctx.app_key)
    title = ui.notice_title(frame)
    results.append(
        (
            "Fresh load shows the 'SQL view not installed' notice",
            PASS if MISSING_NOTICE in title else FAIL,
            _shot(ctx, "01-missing-notice"),
        )
    )
    headers = ui.header_bar_count(ctx.page)
    shell = "global shell iframe" if ui.in_global_shell(ctx.page) else "top level"
    results.append(
        (
            "Exactly one header bar renders",
            PASS if headers == 1 else FAIL,
            f"{headers} header bar(s), app served {shell}",
        )
    )
    return results


def flow_create_view(ctx):
    """Checks 1b/9: create the view, table lists all four types, counts match."""
    results = []
    frame = _frame(ctx)
    ui.click_button(frame, ui.CREATE_BUTTON)
    ui.wait_for_table(frame)
    results.append(("Create SQL view yields the usage table", PASS, _shot(ctx, "02-table")))

    status, view = ctx.client.sql_view(fields="name,sharing")
    sharing = (view.get("sharing") or {}).get("public")
    results.append(
        (
            "Created view has the expected name and public sharing",
            PASS
            if status == 200
            and view.get("name") == SQL_VIEW_NAME
            and sharing == "r-r-----"
            else FAIL,
            f"name={view.get('name')!r} sharing.public={sharing!r}",
        )
    )

    data_status, payload, seconds = ctx.client.sql_view_data()
    api_rows = grid_rows(payload)
    results.append(
        (
            "SQL view data endpoint responds",
            PASS if data_status == 200 else FAIL,
            f"HTTP {data_status}, {len(api_rows)} rows, {seconds * 1000:.0f} ms",
        )
    )
    results.append(
        ("Response time of /sqlViews/{id}/data", INFO, f"{seconds * 1000:.0f} ms")
    )

    results.extend(_compare_table_with_api(ctx, frame, api_rows))
    return results


def _compare_table_with_api(ctx, frame, api_rows):
    results = []
    dom_rows = ui.table_rows(frame)
    results.append(
        (
            "Table row count matches the SQL view payload",
            PASS if len(dom_rows) == len(api_rows) else FAIL,
            f"{len(dom_rows)} rows shown, {len(api_rows)} rows returned",
        )
    )

    api_views = {row["uid"]: int(row["views"]) for row in api_rows}
    mismatches = [
        row["uid"]
        for row in dom_rows
        if api_views.get(row["uid"]) != int(row["views"] or 0)
    ]
    results.append(
        (
            "Every row shows the view count the server returned",
            PASS if not mismatches else FAIL,
            "all match" if not mismatches else f"mismatched uids: {mismatches}",
        )
    )

    label = ui.count_label(frame)
    label_match = re.match(r"^(\d+) enabled dimension", label)
    label_count = int(label_match.group(1)) if label_match else None
    results.append(
        (
            "Row count label matches the rows shown",
            PASS if label_count == len(dom_rows) else FAIL,
            label,
        )
    )

    # Not every database enables all four types (the Laos HMIS demo has no
    # data element group set dimension), so compare with what the server
    # returned rather than requiring four.
    present = {row["type"] for row in dom_rows}
    returned = {TYPE_LABELS[key] for key in _api_types(api_rows)}
    results.append(
        (
            "Every dimension type the server returns appears in the table",
            PASS if present == returned else FAIL,
            f"types shown: {sorted(present)}, returned: {sorted(returned)}",
        )
    )

    results.extend(_favorite_column_checks(ctx, frame, api_rows))
    results.extend(_data_set_report_checks(ctx, frame, api_rows))
    return results


def _sql_names(api_row):
    try:
        return sorted(json.loads(api_row.get("data_set_report_names") or "[]"))
    except ValueError:
        return None


def _data_set_report_checks(ctx, frame, api_rows):
    """Sub-total data sets per category: SQL vs the metadata API, then the UI."""
    step = "Data set report sub-totals match an independent count from /api/dataSets"
    try:
        expected = data_set_report_names(ctx.client)
    except UnreadableMetadata as error:
        return [(step, SKIP, str(error))]
    categories = [row for row in api_rows if row["type"] == "CATEGORY"]
    mismatches = [
        f"{row['name']}: view {_sql_names(row)}, API {expected.get(row['uid'], [])}"
        for row in categories
        if _sql_names(row) != expected.get(row["uid"], [])
        or int(row["data_set_reports"]) != len(expected.get(row["uid"], []))
    ]
    group_sets_with_counts = [
        row["name"]
        for row in api_rows
        if row["type"] != "CATEGORY" and int(row["data_set_reports"]) != 0
    ]
    affected = sum(1 for row in categories if int(row["data_set_reports"]) > 0)
    results = [
        (
            step,
            PASS if not mismatches and not group_sets_with_counts else FAIL,
            f"{len(categories)} categories, {affected} with sub-totals"
            if not mismatches and not group_sets_with_counts
            else f"mismatches: {mismatches}; group sets with counts: {group_sets_with_counts}",
        )
    ]
    results.append(_data_set_report_tooltip_check(ctx, frame, categories))
    return results


def _data_set_report_tooltip_check(ctx, frame, categories):
    step = "Hovering a data set report count lists its data sets"
    target = max(categories, key=lambda row: int(row["data_set_reports"]), default=None)
    if target is None or int(target["data_set_reports"]) == 0:
        return (step, SKIP, "no category shows sub-totals in any data set report")
    row = frame.locator(ui.USAGE_ROW).filter(has_text=target["uid"]).first
    row.locator(DATA_SET_REPORTS_DETAILS).hover()
    tooltip = frame.locator(TOOLTIP).first
    tooltip.wait_for(state="visible", timeout=ui.DEFAULT_TIMEOUT_MS)
    listed = sorted(
        item.strip() for item in tooltip.locator("li").all_inner_texts()
    )
    _shot(ctx, "02c-data-set-report-tooltip")
    ctx.page.mouse.move(0, 0)  # close the tooltip before the next flow
    return (
        step,
        PASS if listed == _sql_names(target) else FAIL,
        f"{target['name']}: {listed}",
    )


def _api_types(api_rows):
    return {row["type"] for row in api_rows}


def _crosscheck_targets(api_rows):
    """The few most-used dimensions: the rows with anything to compare."""
    ranked = sorted(api_rows, key=lambda row: int(row["favorites"]), reverse=True)
    return ranked[:CROSSCHECK_ROW_LIMIT]


def _favorite_crosscheck(ctx, shown, api_row):
    """One row's four favorite counts against a second, independent count."""
    uid = api_row["uid"]
    step = f"Favorite counts match an independent count ({api_row['name']})"
    try:
        counts = favorite_counts(
            ctx.client, api_row["type"], uid, ctx.minor, ctx.state
        )
    except UnreadableFavorites as error:
        return (step, SKIP, str(error))
    row = shown.get(uid) or {}
    expected = {key: str(counts[oracle]) for key, oracle in FAVORITE_COLUMNS.items()}
    actual = {key: row.get(key) for key in FAVORITE_COLUMNS}
    return (
        step,
        PASS if actual == expected else FAIL,
        f"{uid}: table {actual}, server {expected}",
    )


def _favorite_column_checks(ctx, frame, api_rows):
    """Show the sharing breakdown, prove it against SQL, hide it again."""
    results = []
    ui.set_columns(frame, list(FAVORITE_COLUMNS), True)
    keys = ui.visible_column_keys(frame)
    results.append(
        (
            "The chooser adds the favorite-count columns",
            PASS if all(key in keys for key in FAVORITE_COLUMNS) else FAIL,
            f"columns shown: {keys}",
        )
    )
    shown = {row["uid"]: row for row in ui.table_rows(frame)}
    _shot(ctx, "02b-favorite-columns")
    results.extend(
        _favorite_crosscheck(ctx, shown, api_row)
        for api_row in _crosscheck_targets(api_rows)
    )
    ui.set_columns(frame, list(SHARING_COLUMNS), False)
    return results


def _column_state(frame, step, shown):
    keys = ui.visible_column_keys(frame)
    return (
        step,
        PASS if (CHOOSER_COLUMN in keys) == shown else FAIL,
        f"columns shown: {keys}",
    )


def _reload_table(ctx):
    ctx.page.reload(wait_until="domcontentloaded")
    frame = ui.app_frame(ctx.page)
    ui.wait_for_table(frame)
    return frame


def flow_columns_chooser(ctx):
    """The chooser shows a column and remembers the choice for this browser."""
    results = []
    frame = _table_frame(ctx)
    keys = ui.visible_column_keys(frame)
    results.append(
        (
            "The table opens with the default columns",
            PASS if tuple(keys) == DEFAULT_COLUMNS else FAIL,
            f"columns shown: {keys}",
        )
    )

    ui.set_columns(frame, [CHOOSER_COLUMN], True)
    results.append(
        _column_state(frame, f"Ticking '{CHOOSER_COLUMN_LABEL}' adds the column", True)
    )
    _shot(ctx, "12-columns-chosen")

    frame = _reload_table(ctx)
    results.append(
        _column_state(frame, "The chosen column survives a page reload", True)
    )

    ui.set_columns(frame, [CHOOSER_COLUMN], False)
    results.append(
        _column_state(
            frame, f"Unticking '{CHOOSER_COLUMN_LABEL}' removes the column", False
        )
    )
    return results


def _design_tokens_step(frame):
    tokens = ui.design_tokens(frame)
    missing = [name for name, value in tokens.items() if not value]
    return (
        "The DHIS2 design tokens the stylesheets use resolve",
        PASS if not missing else FAIL,
        f"undefined: {missing}" if missing else f"resolved: {tokens}",
    )


def _header_alignment_step(frame):
    layout = ui.header_layout(frame)
    numeric = {key: col for key, col in layout.items() if col["numeric"]}
    strayed = {
        key: col["offset"]
        for key, col in numeric.items()
        if col["offset"] > MAX_HEADER_OFFSET_PX
    }
    return (
        "Numeric column headers sit above their numbers",
        PASS if numeric and not strayed else FAIL,
        f"px from the right edge: { {k: c['offset'] for k, c in numeric.items()} }",
    )


def _sort_icon_step(frame):
    """The sort icon must not swap sides between columns (review, 2026-09-24)."""
    layout = ui.header_layout(frame)
    swapped = [key for key, col in layout.items() if not col["icon_after_label"]]
    return (
        "Every sort icon sits after its column label",
        PASS if layout and not swapped else FAIL,
        f"{len(layout)} headers checked, icon before the label in: {swapped}",
    )


def _chooser_checkbox_step(frame):
    shown = set(ui.visible_column_keys(frame))
    ui.open_column_chooser(frame)
    boxes = ui.column_checkboxes(frame)
    ui.close_column_chooser(frame)
    ticked = {key for key, checked in boxes.items() if checked}
    return (
        "Every chooser entry draws a checkbox matching the table",
        PASS if len(boxes) == COLUMN_COUNT and ticked == shown else FAIL,
        f"ticked: {sorted(ticked)}, shown: {sorted(shown)}",
    )


def flow_layout(ctx):
    """The table is spaced, aligned and ticked the way the design calls for."""
    frame = _table_frame(ctx)
    results = [
        _design_tokens_step(frame),
        _header_alignment_step(frame),
        _sort_icon_step(frame),
        _chooser_checkbox_step(frame),
    ]
    _shot(ctx, "13-layout")
    return results


def flow_filter_and_sort(ctx):
    """Check 3: filter by each type, sort by name and by views both ways."""
    results = []
    frame = _table_frame(ctx)
    _, payload, _ = ctx.client.sql_view_data()
    api_rows = grid_rows(payload)

    for key, label in TYPE_LABELS.items():
        expected = sum(1 for row in api_rows if row["type"] == key)
        ui.select_type_filter(frame, label)
        shown = ui.table_rows(frame)
        wrong_type = [row for row in shown if row["type"] != label]
        results.append(
            (
                f"Filter '{label}' shows only that type",
                PASS if len(shown) == expected and not wrong_type else FAIL,
                f"{len(shown)} rows shown, {expected} expected",
            )
        )
    ui.select_type_filter(frame, "All types")
    _shot(ctx, "03-filter")

    results.extend(_sort_checks(frame, [row["name"] for row in api_rows]))
    _shot(ctx, "04-sorted")
    return results


# The app compares names with the browser's localeCompare (ICU collation,
# base sensitivity), which orders punctuation differently from Python's
# str.lower: "Age (<1- 30+ years)" sorts before "Age (0-59 months)". So the
# expected order comes from the same browser. It sorts the raw names from the
# API, as the app does: the table's rendered text collapses runs of spaces
# (the Laos database has "Age in years  (0-4, 5-9, unknown)"), which can
# change the order. Both sides are compared with whitespace collapsed.
LOCALE_SORT_JS = """([names, direction]) => {
    const compare = (a, b) => a.localeCompare(b, undefined, { sensitivity: 'base' })
    const sign = direction === 'asc' ? 1 : -1
    return [...names].sort((a, b) => sign * compare(a, b) || compare(a, b))
}"""


def _collapse(name):
    return " ".join(name.split())


def _locale_sorted(frame, names, direction):
    """The raw names in the app's order, as rendered text."""
    return [_collapse(name) for name in frame.evaluate(LOCALE_SORT_JS, [names, direction])]


def _order_verdict(shown, expected):
    """(status, detail) for a sort check, naming the first misplaced row."""
    if shown == expected:
        return PASS, f"first: {shown[:2]}"
    index = next(i for i, (a, b) in enumerate(zip(shown, expected)) if a != b)
    return FAIL, f"row {index}: shown {shown[index]!r}, expected {expected[index]!r}"


def _sort_checks(frame, raw_names):
    results = []
    ui.sort_by(frame, "name")
    ascending = [_collapse(name) for name in ui.column_values(frame, "name")]
    results.append(
        (
            "Sort by name ascending",
            *_order_verdict(ascending, _locale_sorted(frame, raw_names, "asc")),
        )
    )
    ui.sort_by(frame, "name")
    descending = [_collapse(name) for name in ui.column_values(frame, "name")]
    results.append(
        (
            "Sort by name descending",
            *_order_verdict(descending, _locale_sorted(frame, raw_names, "desc")),
        )
    )
    # Numeric columns start descending (most-viewed first is this tool's
    # purpose), text columns ascending - see UsageTable.defaultDirectionFor.
    ui.sort_by(frame, "views")
    views_desc = [int(value) for value in ui.column_values(frame, "views")]
    results.append(
        (
            "Sort by views descending (the first click on a numeric column)",
            PASS if views_desc == sorted(views_desc, reverse=True) else FAIL,
            f"first: {views_desc[:3]}",
        )
    )
    ui.sort_by(frame, "views")
    views_asc = [int(value) for value in ui.column_values(frame, "views")]
    results.append(
        (
            "Sort by views ascending",
            PASS if views_asc == sorted(views_asc) else FAIL,
            f"first: {views_asc[:3]}",
        )
    )
    return results


def _least_used_row_per_type(api_rows):
    """One candidate row per type: the least-viewed, so the instance suffers least."""
    candidates = {}
    for row in api_rows:
        key = row["type"]
        current = candidates.get(key)
        if current is None or int(row["views"]) < int(current["views"]):
            candidates[key] = row
    return candidates


def flow_disable_one_per_type(ctx):
    """Check 4: disable one object of each type, verify, then re-enable."""
    results = []
    frame = _table_frame(ctx)
    _, payload, _ = ctx.client.sql_view_data()
    candidates = _least_used_row_per_type(grid_rows(payload))

    for key, label in TYPE_LABELS.items():
        row = candidates.get(key)
        if row is None:
            results.append((f"Disable a {label}", SKIP, "no enabled object of this type"))
            continue
        results.extend(_disable_one(ctx, frame, key, label, row))
    _shot(ctx, "05-after-disable")
    return results


def _disable_one(ctx, frame, key, label, row):
    results = []
    uid, name = row["uid"], row["name"]
    target = frame.locator(ui.USAGE_ROW).filter(has_text=uid).first
    target.get_by_role("button", name=ui.DISABLE_BUTTON, exact=True).click()

    dialog = frame.locator(ui.DISABLE_DIALOG)
    dialog.wait_for(state="visible", timeout=ui.DEFAULT_TIMEOUT_MS)
    dialog_text = dialog.text_content() or ""
    results.append(
        (
            f"Disable dialog names the object and type ({label})",
            PASS if name in dialog_text and label.lower() in dialog_text else FAIL,
            f"{name} / {label.lower()}",
        )
    )
    if key == "CATEGORY":
        _shot(ctx, "06-disable-dialog")

    endpoint = TYPE_ENDPOINTS[key]
    ctx.state.record(run_state.data_dimension_entry(endpoint, uid))
    _click_dialog_button(frame, ui.DISABLE_DIALOG, ui.DISABLE_BUTTON)
    dialog.wait_for(state="detached", timeout=ui.DEFAULT_TIMEOUT_MS)
    # Alerts stack and auto-hide, so match the bar carrying this row's name
    # rather than whichever alert happens to be first in the DOM.
    alert = ui.alert_text_for(frame, name)
    results.append(
        (
            f"Success alert names the disabled object ({label})",
            PASS if alert is not None else FAIL,
            (alert or "no alert mentioning the object appeared").strip(),
        )
    )

    frame.locator(ui.USAGE_ROW).filter(has_text=uid).first.wait_for(
        state="detached", timeout=ui.DEFAULT_TIMEOUT_MS
    )
    server_value = ctx.client.data_dimension(endpoint, uid)
    results.append(
        (
            f"Server reports dataDimension=false ({label})",
            PASS if server_value is False else FAIL,
            f"{endpoint}/{uid} -> {server_value}",
        )
    )
    ctx.disabled.append((endpoint, uid, name))
    return results


def flow_reenable(ctx):
    """Leave the instance as found: re-enable everything the suite disabled."""
    results = []
    for endpoint, uid, name in ctx.disabled:
        status = ctx.client.set_data_dimension(endpoint, uid, True)
        value = ctx.client.data_dimension(endpoint, uid)
        results.append(
            (
                f"Re-enabled {name}",
                PASS if value is True else FAIL,
                f"{endpoint}/{uid} HTTP {status} -> dataDimension={value}",
            )
        )
    ctx.disabled.clear()
    return results


def flow_remove_and_recreate(ctx):
    """Check 6: remove the view from the app, then create it again."""
    results = []
    frame = _table_frame(ctx)
    ui.click_button(frame, ui.REMOVE_BUTTON)
    frame.locator(ui.REMOVE_DIALOG).wait_for(
        state="visible", timeout=ui.DEFAULT_TIMEOUT_MS
    )
    _click_dialog_button(frame, ui.REMOVE_DIALOG, ui.REMOVE_BUTTON)

    ui.wait_for_notice(frame, MISSING_NOTICE)
    status, _ = ctx.client.sql_view(fields="id")
    results.append(
        (
            "Remove SQL view returns to the create notice",
            PASS if status == 404 else FAIL,
            f"GET {SQL_VIEW_PATH} -> HTTP {status}",
        )
    )
    _shot(ctx, "07-removed")

    ui.click_button(frame, ui.CREATE_BUTTON)
    ui.wait_for_table(frame)
    status, _ = ctx.client.sql_view(fields="id")
    results.append(
        (
            "Creating the view again restores the table",
            PASS if status == 200 else FAIL,
            f"GET {SQL_VIEW_PATH} -> HTTP {status}",
        )
    )
    return results


def _set_view_sharing(client, public_access):
    """Sharing is set through /api/sharing: a JSON Patch on /sharing no-ops."""
    return client.put(
        f"/api/sharing?type=sqlView&id={SQL_VIEW_ID}",
        {"object": {"publicAccess": public_access, "externalAccess": False}},
    )[0]


def flow_data_error(ctx):
    """Design section 6: a readable view whose data endpoint fails shows a notice.

    Reproduced by removing data read from the view's sharing, which makes
    `/sqlViews/{id}/data` answer 409 E4312 while the query itself still
    matches, so the app is in the READY state. Sharing does not restrict an
    account with ALL, so this runs as the throwaway non-superuser.
    """
    results = []
    _table_frame(ctx)  # the view exists before its sharing is narrowed
    _set_view_sharing(ctx.client, METADATA_READ_ONLY_SHARING)
    with _limited_page(ctx) as page:
        frame = ui.open_app(page, ctx.base_url, ctx.app_key)
        ui.wait_for_notice(frame, DATA_ERROR_NOTICE)
        notice = frame.locator(ui.NOTICE_BOX).first.text_content() or ""
        results.append(
            (
                "Unreadable view data shows an error notice with the server message",
                PASS if "E4312" in notice or "not authorised" in notice else FAIL,
                notice.strip()[:160],
            )
        )
        results.append(
            (
                "Remove SQL view stays available in the error state",
                PASS
                if frame.get_by_role("button", name=ui.REMOVE_BUTTON).count() > 0
                else FAIL,
                _shot_page(ctx, page, "11-data-error"),
            )
        )

        _set_view_sharing(ctx.client, READABLE_SHARING)
        ui.click_button(frame, "Retry")
        ui.wait_for_table(frame)
        results.append(("Retry loads the table once access is restored", PASS, ""))
    return results


def flow_outdated_update(ctx):
    """Check 2: a legacy category-only view is detected and updated in place."""
    results = []
    ctx.client.delete_sql_view_if_present()
    create_status, _ = ctx.client.post(
        "/api/sqlViews", legacy_definition(SQL_VIEW_ID, ctx.minor)
    )
    if create_status >= 400:
        return [("Install the legacy SQL view", FAIL, f"HTTP {create_status}")]

    frame = ui.open_app(ctx.page, ctx.base_url, ctx.app_key)
    ui.wait_for_notice(frame, OUTDATED_NOTICE)
    results.append(
        ("Legacy view is detected as outdated", PASS, _shot(ctx, "08-outdated-notice"))
    )

    ui.click_button(frame, ui.UPDATE_BUTTON)
    ui.wait_for_table(frame)
    _, view = ctx.client.sql_view(fields="id,name,sharing")
    sharing = (view.get("sharing") or {}).get("public")
    results.append(
        (
            "Update renames the view in place (same UID)",
            PASS if view.get("name") == SQL_VIEW_NAME else FAIL,
            f"name={view.get('name')!r} (was {LEGACY_NAME!r}), id={view.get('id')}",
        )
    )
    results.append(
        (
            "Update sets public sharing to r-r----- (metadata+data read)",
            PASS if sharing == "r-r-----" else FAIL,
            f"sharing.public={sharing!r}",
        )
    )
    _shot(ctx, "09-after-update")
    return results


def _grantable_authority(client):
    """An authority the acting user actually holds.

    A user can only grant a role whose authorities it has itself, so picking
    blind produces `E3003 not allowed to grant`.
    """
    _, me = client.get("/api/me?fields=authorities")
    held = set(me.get("authorities") or [])
    if "ALL" in held:
        return PREFERRED_LIMITED_AUTHORITIES[0]
    for candidate in PREFERRED_LIMITED_AUTHORITIES:
        if candidate in held:
            return candidate
    return min(held)


def _app_authority(client, app_key):
    """The `M_<app>` authority the server generated for the installed app.

    Without it the 2.42+ global shell answers "Unable to find an app for this
    URL" instead of loading the app.
    """
    expected = "M_" + app_key.replace("-", "")
    _, body = client.get("/api/authorities?pageSize=2000")
    for entry in body.get("systemAuthorities") or body.get("authorities") or []:
        if entry.get("id") == expected:
            return expected
    return None


def _limited_role_authorities(ctx):
    authorities = [_grantable_authority(ctx.client)]
    app_authority = _app_authority(ctx.client, ctx.app_key)
    if app_authority:
        authorities.append(app_authority)
    return authorities


def _limited_client(ctx):
    """The throwaway user that can open the app but holds no ALL.

    Created once per run, with run-unique uids and names written to the run
    record first; the run's cleanup deletes it.
    """
    if ctx.limited is not None:
        return ctx.limited
    role_id = run_state.new_uid()
    ctx.state.record(run_state.user_role_entry(role_id))
    status, body = ctx.client.post(
        "/api/userRoles",
        {
            "id": role_id,
            "name": ctx.state.name("app only"),
            "authorities": _limited_role_authorities(ctx),
        },
    )
    if status >= 400:
        raise AssertionError(f"Could not create the limited role: {body}")

    _, org_units = ctx.client.get("/api/organisationUnits?level=1&fields=id")
    org_unit_id = org_units["organisationUnits"][0]["id"]
    user_id = run_state.new_uid()
    username = f"e2e-ddd-{ctx.state.run_id}".lower()
    ctx.state.record(run_state.user_entry(user_id))
    status, body = ctx.client.post(
        "/api/users",
        {
            "id": user_id,
            "username": username,
            "password": LIMITED_PASSWORD,
            "firstName": "E2E",
            "surname": ctx.state.run_id,
            "userRoles": [{"id": role_id}],
            "organisationUnits": [{"id": org_unit_id}],
        },
    )
    if status >= 400:
        raise AssertionError(f"Could not create the limited user: {body}")
    ctx.limited = Dhis2Client(ctx.base_url, username, LIMITED_PASSWORD)
    return ctx.limited


@contextmanager
def _limited_page(ctx):
    """A browser page logged in as the throwaway non-superuser."""
    name, value = _limited_client(ctx).session_cookie()
    context = ctx.browser.new_context(viewport={"width": 1280, "height": 900})
    try:
        context.add_cookies(
            [
                {
                    "name": name,
                    "value": value,
                    "domain": hostname_of(ctx.base_url),
                    "path": "/",
                }
            ]
        )
        yield context.new_page()
    finally:
        context.close()


def _shot_page(ctx, page, name):
    ui.screenshot(page, ctx.out_dir, f"{ctx.label}-{name}")
    return f"{ctx.label}-{name}.png"


def flow_limited_user(ctx):
    """Check 5: a user without the SQL view authority gets a clear error."""
    results = []
    ctx.client.delete_sql_view_if_present()
    with _limited_page(ctx) as page:
        recorder = ui.ConsoleRecorder(page)
        frame = ui.open_app(page, ctx.base_url, ctx.app_key)
        ui.wait_for_notice(frame, MISSING_NOTICE)
        ui.click_button(frame, ui.CREATE_BUTTON)
        error_box = frame.locator(ui.MUTATION_ERROR).first
        error_box.wait_for(state="visible", timeout=ui.DEFAULT_TIMEOUT_MS)
        message = error_box.text_content() or ""
        results.append(
            (
                "Create without the authority shows the server message",
                PASS if message.strip() else FAIL,
                message.strip()[:200],
            )
        )
        results.append(
            (
                "Error names the 'Add/Update SQL view' authority",
                PASS if SQL_VIEW_AUTHORITY_TEXT in message else FAIL,
                SQL_VIEW_AUTHORITY_TEXT,
            )
        )
        results.append(
            (
                "App stays usable (intro still rendered, no page error)",
                PASS
                if frame.locator(ui.APP_MARKER).count() > 0 and not recorder.page_errors
                else FAIL,
                f"page errors: {recorder.page_errors}",
            )
        )
        results.append(
            ("Limited-user screenshot", INFO, _shot_page(ctx, page, "10-limited-user"))
        )
    return results


def flow_console_clean(ctx):
    """Check 8: no app-level console errors, no React key warnings."""
    errors = ctx.recorder.significant_console_errors()
    http_errors = ctx.recorder.significant_http_errors()
    keys = ctx.recorder.react_key_warnings()
    return [
        (
            "No unexpected console errors",
            PASS if not errors else FAIL,
            "none" if not errors else str(errors[:3]),
        ),
        (
            "No React duplicate-key warnings",
            PASS if not keys else FAIL,
            "none" if not keys else str(keys[:3]),
        ),
        (
            "No unexpected HTTP error responses",
            PASS if not http_errors else FAIL,
            "none" if not http_errors else str(http_errors[:5]),
        ),
    ]


FLOWS = [
    ("load-missing", flow_load_missing),
    ("create-view", flow_create_view),
    ("columns-chooser", flow_columns_chooser),
    ("layout", flow_layout),
    ("filter-sort", flow_filter_and_sort),
    ("disable-per-type", flow_disable_one_per_type),
    ("re-enable", flow_reenable),
    ("remove-recreate", flow_remove_and_recreate),
    ("data-error", flow_data_error),
    ("outdated-update", flow_outdated_update),
    ("limited-user", flow_limited_user),
    ("console-clean", flow_console_clean),
]
