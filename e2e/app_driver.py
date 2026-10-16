"""Browser-side helpers: locating the app, its widgets, and its console output.

The app is driven as installed on the instance
(`<base>/api/apps/<app key>/index.html`). From DHIS2 2.42 the
server wraps that URL in the global-shell iframe, while 2.40/2.41 serve it at
top level, so every locator goes through `app_frame()`.
"""

import re
import time

from playwright.sync_api import TimeoutError as PlaywrightTimeoutError

APP_PATH = "/api/apps/{key}/index.html"

# Selectors (module constants: they repeat across flows)
# The app renders no <h1> of its own (the header bar carries the app name),
# so the app frame is recognised by the intro block, which every state shows.
APP_MARKER = "details > summary"
APP_MARKER_TEXT = "About this tool"
NOTICE_BOX = "[data-test='dhis2-uicore-noticebox']"
MUTATION_ERROR = "[data-test='sql-view-mutation-error']"
USAGE_TABLE = "[data-test='usage-table']"
USAGE_ROW = "[data-test='usage-row']"
USAGE_COUNT = "[data-test='usage-count']"
USAGE_HEADER_PREFIX = "usage-header-"
USAGE_HEADER = f"[data-test^='{USAGE_HEADER_PREFIX}']"
COLUMN_CHOOSER = "[data-test='column-chooser']"
COLUMN_CHOOSER_MENU = "[data-test='column-chooser-menu']"
COLUMN_CHOOSER_ITEM = "[data-test='column-chooser-{key}'] [role='menuitemcheckbox']"
COLUMN_CHECK_PREFIX = "column-check-"
COLUMN_CHECK = f"[data-test^='{COLUMN_CHECK_PREFIX}']"
# The label span the app puts in each column header, next to the sort icon.
HEADER_LABEL = "[class*='_label_']"
# One design token per section the stylesheets use. They resolve only when
# the app renders <CssVariables>, which the app-platform shell does not.
DESIGN_TOKENS = ("--spacers-dp16", "--colors-grey700")
LAYER_BACKDROP = "[data-test='dhis2-uicore-layer'] .backdrop"
DISABLE_DIALOG = "[data-test='disable-dialog']"
REMOVE_DIALOG = "[data-test='remove-view-dialog']"
ALERT_BAR = "[data-test='dhis2-uicore-alertbar']"
SELECT_INPUT = "[data-test='dhis2-uicore-select-input']"
SELECT_MENU = "[data-test='dhis2-uicore-select-menu-menuwrapper']"
SORT_BUTTON = "[data-test='dhis2-uicore-tableheadercellaction']"

CREATE_BUTTON = "Create SQL view"
UPDATE_BUTTON = "Update SQL view"
REMOVE_BUTTON = "Remove SQL view"
DISABLE_BUTTON = "Disable"

DEFAULT_TIMEOUT_MS = 30_000

# Console noise that is not the app's doing: the platform's PWA/offline layer
# complains on plain http, and the shell probes optional endpoints.
BENIGN_CONSOLE = (
    re.compile(r"not a secure context", re.I),
    re.compile(r"PWA features will not work", re.I),
    re.compile(r"Failed to load resource", re.I),
)
BENIGN_HTTP_404 = (
    re.compile(r"/staticContent/logo_banner"),
    re.compile(r"/dataStore/custom-translations/"),
    re.compile(r"/sqlViews/GOLswS44mh8"),  # expected while the view is missing
)


class ConsoleRecorder:
    """Collects console errors, page errors and HTTP failures for one page."""

    def __init__(self, page):
        self.console_errors = []
        self.page_errors = []
        self.http_errors = []
        page.on("console", self._on_console)
        page.on("pageerror", lambda error: self.page_errors.append(str(error)))
        page.on("response", self._on_response)

    def _on_console(self, message):
        if message.type == "error":
            self.console_errors.append(message.text)

    def _on_response(self, response):
        if response.status >= 400:
            self.http_errors.append(f"{response.status} {response.url}")

    def significant_console_errors(self):
        return [
            text
            for text in self.console_errors
            if not any(pattern.search(text) for pattern in BENIGN_CONSOLE)
        ]

    def react_key_warnings(self):
        return [
            text
            for text in self.console_errors + self.page_errors
            if "unique \"key\"" in text or 'unique "key"' in text
        ]

    def significant_http_errors(self):
        return [
            entry
            for entry in self.http_errors
            if not any(pattern.search(entry) for pattern in BENIGN_HTTP_404)
        ]


def open_app(page, base_url, app_key):
    """Navigate to the installed app and return its frame."""
    path = APP_PATH.format(key=app_key)
    page.goto(f"{base_url.rstrip('/')}{path}", wait_until="domcontentloaded")
    return app_frame(page)


def app_frame(page, timeout_ms=DEFAULT_TIMEOUT_MS):
    """The frame holding the app: the top document, or the global-shell iframe."""
    deadline = time.monotonic() + timeout_ms / 1000
    while time.monotonic() < deadline:
        for frame in page.frames:
            try:
                marker = frame.locator(APP_MARKER).first
                if marker.count() > 0 and APP_MARKER_TEXT in (
                    marker.text_content() or ""
                ):
                    return frame
            except PlaywrightTimeoutError:
                continue
            except Exception:  # noqa: BLE001 - frame detached mid-scan
                continue
        page.wait_for_timeout(250)
    raise AssertionError("App frame with the expected intro never appeared")


def in_global_shell(page):
    """True when the instance wrapped the app in the global-shell iframe."""
    return len(page.frames) > 1


VISIBLE_HEADERS_JS = """() => Array.from(document.querySelectorAll('header'))
    .filter((element) => element.getBoundingClientRect().height > 0).length"""


def header_bar_count(page):
    """Visible DHIS2 header bars across all frames (expected: exactly 1).

    From 2.42 the app still renders its own header bar inside the global-shell
    iframe, but the shell hides it with `display: none` - so counting elements
    rather than visible ones reports a false double header.
    """
    return sum(frame.evaluate(VISIBLE_HEADERS_JS) for frame in page.frames)


def notice_title(frame):
    box = frame.locator(NOTICE_BOX).first
    box.wait_for(state="visible", timeout=DEFAULT_TIMEOUT_MS)
    return box.text_content() or ""


def click_button(frame, name):
    frame.get_by_role("button", name=name, exact=True).first.click()


def wait_for_table(frame, timeout_ms=DEFAULT_TIMEOUT_MS):
    frame.locator(USAGE_TABLE).first.wait_for(state="visible", timeout=timeout_ms)


def wait_for_notice(frame, expected_title, timeout_ms=DEFAULT_TIMEOUT_MS):
    frame.get_by_text(expected_title, exact=False).first.wait_for(
        state="visible", timeout=timeout_ms
    )


def visible_column_keys(frame):
    """Keys of the currently shown columns, in display order.

    Read off the header cells' `data-test` suffixes, so the reader follows
    whatever the column chooser has enabled instead of a fixed cell order.
    """
    headers = frame.locator(USAGE_HEADER)
    return [
        (headers.nth(index).get_attribute("data-test") or "").removeprefix(
            USAGE_HEADER_PREFIX
        )
        for index in range(headers.count())
    ]


def table_rows(frame):
    """Visible rows as dicts keyed by column key, for the visible columns.

    Each row carries one trailing action cell with no header of its own;
    zipping against the header keys drops it.
    """
    keys = visible_column_keys(frame)
    rows = []
    row_locators = frame.locator(USAGE_ROW)
    for index in range(row_locators.count()):
        cells = row_locators.nth(index).locator("td")
        values = [cells.nth(i).inner_text().strip() for i in range(cells.count())]
        rows.append(dict(zip(keys, values)))
    return rows


def open_column_chooser(frame):
    """Open the "Manage view" dropdown and return its menu."""
    frame.locator(COLUMN_CHOOSER).get_by_role("button").first.click()
    menu = frame.locator(COLUMN_CHOOSER_MENU).first
    menu.wait_for(state="visible", timeout=DEFAULT_TIMEOUT_MS)
    return menu


def close_column_chooser(frame):
    """Close the "Manage view" dropdown by clicking away from it.

    Ticking an item deliberately leaves the menu open, and the flyout's
    backdrop then covers the toggle button, so the way out is the same as
    a user's: a click on the backdrop.
    """
    frame.locator(LAYER_BACKDROP).first.click(position={"x": 5, "y": 5})
    frame.locator(COLUMN_CHOOSER_MENU).first.wait_for(
        state="detached", timeout=DEFAULT_TIMEOUT_MS
    )


def column_checked(frame, key):
    """True when the chooser reports the column as shown."""
    menu = frame.locator(COLUMN_CHOOSER_MENU).first
    item = menu.locator(COLUMN_CHOOSER_ITEM.format(key=key)).first
    return item.get_attribute("aria-checked") == "true"


def set_columns(frame, keys, shown):
    """Show (or hide) each named column through the chooser, then close it."""
    menu = open_column_chooser(frame)
    for key in keys:
        if column_checked(frame, key) != shown:
            menu.locator(COLUMN_CHOOSER_ITEM.format(key=key)).first.click()
    close_column_chooser(frame)


def column_checkboxes(frame):
    """Each column's tick state as the open chooser draws it, keyed by column."""
    boxes = frame.locator(COLUMN_CHOOSER_MENU).first.locator(COLUMN_CHECK)
    return {
        (boxes.nth(index).get_attribute("data-test") or "").removeprefix(
            COLUMN_CHECK_PREFIX
        ): boxes.nth(index).get_attribute("data-checked") == "true"
        for index in range(boxes.count())
    }


def design_tokens(frame):
    """What the browser resolves DESIGN_TOKENS to, empty string when undefined."""
    return frame.evaluate(
        """(names) => {
            const styles = getComputedStyle(document.documentElement)
            return Object.fromEntries(
                names.map((name) => [name, styles.getPropertyValue(name).trim()])
            )
        }""",
        list(DESIGN_TOKENS),
    )


def header_layout(frame):
    """Where each sortable column header's label and sort icon sit.

    Per column: `offset` is the px from the right edge of the header's content
    (its last element, the sort icon) to the right edge of its cells, and
    `icon_after_label` says whether the sort icon follows the label rather
    than preceding it. A right-aligned column whose header sits on the left
    reads as belonging to the column beside it; a sort icon that swaps sides
    between columns reads as an inconsistency.
    """
    return frame.evaluate(
        """({ headerPrefix, labelSelector, sortSelector }) => {
            const layout = {}
            for (const header of document.querySelectorAll(
                `[data-test^="${headerPrefix}"]`
            )) {
                const key = header
                    .getAttribute('data-test')
                    .slice(headerPrefix.length)
                // The name column's cell keeps its own older data-test.
                const cell = document.querySelector(
                    key === 'name'
                        ? '[data-test="usage-row-name"]'
                        : `[data-test="usage-cell-${key}"]`
                )
                const label = header.querySelector(labelSelector)
                const sorter = header.querySelector(sortSelector)
                if (!cell || !label || !sorter) {
                    continue
                }
                layout[key] = {
                    numeric: getComputedStyle(cell).textAlign === 'right',
                    offset: Math.round(
                        cell.getBoundingClientRect().right -
                            sorter.getBoundingClientRect().right
                    ),
                    icon_after_label:
                        sorter.getBoundingClientRect().left >=
                        label.getBoundingClientRect().right,
                }
            }
            return layout
        }""",
        {
            "headerPrefix": USAGE_HEADER_PREFIX,
            "labelSelector": HEADER_LABEL,
            "sortSelector": SORT_BUTTON,
        },
    )


def count_label(frame):
    """The "<n> enabled dimensions" line above the table."""
    return (frame.locator(USAGE_COUNT).first.text_content() or "").strip()


def select_type_filter(frame, option_label):
    frame.locator(SELECT_INPUT).first.click()
    menu = frame.locator(SELECT_MENU).first
    menu.wait_for(state="visible", timeout=DEFAULT_TIMEOUT_MS)
    menu.get_by_text(option_label, exact=True).first.click()
    menu.wait_for(state="detached", timeout=DEFAULT_TIMEOUT_MS)


def sort_by(frame, column):
    frame.locator(f"[data-test='usage-header-{column}'] {SORT_BUTTON}").first.click()


def column_values(frame, key):
    return [row[key] for row in table_rows(frame)]


def alert_text_for(frame, expected_text, timeout_ms=DEFAULT_TIMEOUT_MS):
    """Text of the alert bar mentioning `expected_text`, or None if none appears.

    Alerts stack and auto-hide, so an earlier alert can still be the first in
    the DOM when the next one arrives.
    """
    alert = frame.locator(ALERT_BAR).filter(has_text=expected_text).first
    try:
        alert.wait_for(state="visible", timeout=timeout_ms)
    except PlaywrightTimeoutError:
        return None
    return alert.text_content() or ""


def screenshot(page, directory, name):
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{name}.png"
    page.screenshot(path=str(path), full_page=True)
    return path
