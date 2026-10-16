#!/usr/bin/env python3
"""Run the end-to-end suite against one throwaway DHIS2 instance.

Start it through `e2e/run.sh`, which checks the environment first. See
e2e/README.md: the suite changes and deletes data, so never point it at an
instance whose content matters.

Configuration, environment only (no defaults for the instance or account):

    DHIS2_URL     instance base URL, e.g. http://localhost:8080
    DHIS2_USER    a superuser (holds ALL)
    DHIS2_PASS    its password
    APP_ZIP       absolute path of the built bundle to install and test
    RESULTS_DIR   existing directory for results.json, screenshots and logs
    LABEL         optional; label for output and screenshots (default: server version)
    APP_KEY       optional; default: the key the server reports after installing
    E2E_FLOWS     optional; comma-separated subset of flow ids
    E2E_HEADED    optional; 1 to watch the browser

Exit codes: 0 every test passed, 1 at least one failed, 2 the suite could
not run (the reason is in results.json under "error").
"""

import json
import os
import re
import sys
import time
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from playwright.sync_api import sync_playwright  # noqa: E402

import app_driver as ui  # noqa: E402
import flows  # noqa: E402
import state as run_state  # noqa: E402
from dhis2_api import (  # noqa: E402
    SQL_VIEW_PATH,
    Dhis2Client,
    hostname_of,
    read_manifest,
)

CONTRACT_VERSION = 1
VIEWPORT = {"width": 1400, "height": 1000}
BROWSER_ARGS = ["--no-sandbox", "--disable-dev-shm-usage"]
REQUIRED = ("DHIS2_URL", "DHIS2_USER", "DHIS2_PASS", "APP_ZIP", "RESULTS_DIR")
STATUS_MAP = {flows.PASS: "pass", flows.FAIL: "fail", flows.SKIP: "skip"}
# Fields of the app's SQL view kept so the run can put it back exactly.
VIEW_FIELDS = "id,name,description,type,cacheStrategy,sharing,sqlQuery"


class SetupError(Exception):
    """The suite could not run: exit 2, with the stage in results.json."""


def read_settings():
    missing = [name for name in REQUIRED if not os.environ.get(name)]
    if missing:
        raise SetupError(f"not set: {', '.join(missing)}")
    selected = os.environ.get("E2E_FLOWS", "")
    return {
        "base_url": os.environ["DHIS2_URL"].rstrip("/"),
        "user": os.environ["DHIS2_USER"],
        "password": os.environ["DHIS2_PASS"],
        "app_zip": os.environ["APP_ZIP"],
        "results_dir": Path(os.environ["RESULTS_DIR"]),
        "label": os.environ.get("LABEL"),
        "app_key": os.environ.get("APP_KEY"),
        "flow_ids": [name for name in selected.split(",") if name],
        "headed": os.environ.get("E2E_HEADED") == "1",
    }


def minor_version(version):
    parts = version.split(".")
    return int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 0


def selected_flows(flow_ids):
    if not flow_ids:
        return flows.FLOWS
    return [entry for entry in flows.FLOWS if entry[0] in flow_ids]


def run_flow(context, flow_id, flow):
    try:
        return [
            {"flow": flow_id, "step": step, "status": status, "detail": detail}
            for step, status, detail in flow(context)
        ]
    except Exception:  # noqa: BLE001 - a broken flow must not stop the suite
        detail = traceback.format_exc(limit=4).strip().splitlines()[-1]
        ui.screenshot(context.page, context.out_dir, f"{context.label}-error-{flow_id}")
        return [
            {
                "flow": flow_id,
                "step": "flow raised an exception",
                "status": flows.FAIL,
                "detail": detail,
            }
        ]


def install_app(client, settings, state):
    """Install APP_ZIP and return (manifest, key)."""
    manifest = read_manifest(settings["app_zip"])
    state.record(run_state.app_entry(manifest["name"]))
    status = client.install_app(settings["app_zip"])
    if not 200 <= status < 300:
        raise SetupError(f"install: POST /api/apps answered {status}")
    key = settings["app_key"] or client.app_key_by_name(manifest["name"])
    if not key:
        raise SetupError(f"install: no installed app named {manifest['name']!r}")
    return manifest, key


def clear_app_sql_view(client, state):
    """Record the app's SQL view as found, then remove it: the suite starts without one."""
    status, view = client.get(f"{SQL_VIEW_PATH}?fields={VIEW_FIELDS}")
    state.record(
        run_state.app_sql_view_entry(
            flows.SQL_VIEW_ID, view if status == 200 else None
        )
    )
    client.delete_sql_view_if_present()


def run_flows(settings, client, version, app_key, state):
    cookie_name, cookie_value = client.session_cookie()
    results = []
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(
            headless=not settings["headed"], args=BROWSER_ARGS
        )
        context = browser.new_context(viewport=VIEWPORT)
        context.add_cookies(
            [
                {
                    "name": cookie_name,
                    "value": cookie_value,
                    "domain": hostname_of(settings["base_url"]),
                    "path": "/",
                }
            ]
        )
        page = context.new_page()
        suite_context = flows.Context(
            page=page,
            client=client,
            recorder=ui.ConsoleRecorder(page),
            base_url=settings["base_url"],
            label=settings["label"],
            minor=minor_version(version),
            out_dir=settings["results_dir"],
            browser=browser,
            app_key=app_key,
            state=state,
        )
        try:
            for flow_id, flow in selected_flows(settings["flow_ids"]):
                results.extend(run_flow(suite_context, flow_id, flow))
        finally:
            results.extend(run_flow(suite_context, "re-enable", flows.flow_reenable))
            context.close()
            browser.close()
    return results


def test_id(row):
    """Stable id per step: the flow plus a slug of the step text."""
    slug = re.sub(r"[^a-z0-9]+", "-", row["step"].lower()).strip("-")
    return f"{row['flow']}/{slug}"


def contract_results(settings, version, manifest, app_key, rows, started, error=None):
    tests = [
        {
            "id": test_id(row),
            "status": STATUS_MAP[row["status"]],
            "message": str(row["detail"]),
        }
        for row in rows
        if row["status"] in STATUS_MAP
    ]
    tally = {status: sum(1 for t in tests if t["status"] == status) for status in ("pass", "fail", "skip")}
    payload = {
        "contract_version": CONTRACT_VERSION,
        "label": settings.get("label") or version,
        "server_version": version,
        "app_key": app_key,
        "app_version": (manifest or {}).get("version"),
        "duration_s": round(time.monotonic() - started),
        "total": len(tests),
        "passed": tally["pass"],
        "failed": tally["fail"],
        "skipped": tally["skip"],
        "tests": tests,
    }
    if error:
        payload["error"] = error
    return payload


def write_results(results_dir, payload, rows):
    results_dir.mkdir(parents=True, exist_ok=True)
    (results_dir / "results.json").write_text(
        json.dumps(payload, indent=2), encoding="utf-8"
    )
    lines = ["| Flow | Step | Status | Detail |", "|---|---|---|---|"]
    lines += [
        f"| {row['flow']} | {row['step']} | {row['status']} | {row['detail']} |"
        for row in rows
    ]
    (results_dir / "results.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def cleanup_rows(state):
    failed = state.finish()
    return [
        {
            "flow": "cleanup",
            "step": "Instance left as found (run record undone)",
            "status": flows.PASS if not failed else flows.FAIL,
            "detail": "nothing left" if not failed else f"could not undo: {failed}",
        }
    ]


def main():
    started = time.monotonic()
    try:
        settings = read_settings()
    except SetupError as error:
        print(f"e2e: {error}", file=sys.stderr)
        return 2
    client = Dhis2Client(settings["base_url"], settings["user"], settings["password"])
    version, manifest, app_key, rows, error = "unknown", None, None, [], None
    state = run_state.RunState(client, run_state.new_run_id())
    try:
        version = client.server_version()
        settings["label"] = settings["label"] or version
        state.undo_leftovers()
        manifest, app_key = install_app(client, settings, state)
        clear_app_sql_view(client, state)
        rows = run_flows(settings, client, version, app_key, state)
    except SetupError as setup_error:
        error = str(setup_error)
    except Exception:  # noqa: BLE001 - report, clean up, exit 2
        error = traceback.format_exc(limit=4).strip().splitlines()[-1]
    finally:
        rows.extend(cleanup_rows(state))

    payload = contract_results(
        settings, version, manifest, app_key, [] if error else rows, started, error
    )
    write_results(settings["results_dir"], payload, rows)
    print(
        f"{payload['label']} ({version}): {payload['passed']} passed, "
        f"{payload['failed']} failed, {payload['skipped']} skipped"
        + (f", error: {error}" if error else "")
    )
    for row in rows:
        print(f"  [{row['status']}] {row['flow']} / {row['step']} — {row['detail']}")
    if error:
        return 2
    return 1 if payload["failed"] else 0


if __name__ == "__main__":
    sys.exit(main())
