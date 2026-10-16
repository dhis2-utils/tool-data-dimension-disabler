"""The record of what a run changed on the instance, and how to undo it.

A run can be killed at any point (a timeout, a cancelled job), and then its
own cleanup never happens. So every change is written to a record on the
instance *before* it is made, in the dataStore at `e2e-state/<repo name>`,
and every run starts by undoing whatever an earlier run left in that record.
At the end of a clean run the record is gone.

Each entry is a small dict naming one change; `undo` reverses it and is safe
to repeat (deleting something already gone, or re-enabling something already
enabled, is not an error).
"""

import secrets
import string
from datetime import datetime, timezone

NAMESPACE = "e2e-state"
RECORD_KEY = "tool-data-dimension-disabler"
RECORD_PATH = f"/api/dataStore/{NAMESPACE}/{RECORD_KEY}"
NAME_PREFIX = "E2E tool-data-dimension-disabler"
UID_ALPHABET = string.ascii_letters + string.digits


def new_run_id():
    """Sortable, unique enough for one instance: 20261016T101205-a1b2."""
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    return f"{stamp}-{secrets.token_hex(2)}"


def new_uid():
    """A DHIS2 uid: a letter, then ten letters or digits."""
    return secrets.choice(string.ascii_letters) + "".join(
        secrets.choice(UID_ALPHABET) for _ in range(10)
    )


def sql_view_entry(uid):
    return {"type": "sqlView", "id": uid}


def user_entry(uid):
    return {"type": "user", "id": uid}


def user_role_entry(uid):
    return {"type": "userRole", "id": uid}


def data_dimension_entry(endpoint, uid):
    """A dimension the run disables; undo enables it again."""
    return {"type": "dataDimension", "endpoint": endpoint, "id": uid}


def app_sql_view_entry(view_id, original):
    """The app's own SQL view as it was before the run (None: absent)."""
    return {"type": "appSqlView", "id": view_id, "original": original}


def app_entry(name):
    """The app the run installs; undo uninstalls it, found by manifest name."""
    return {"type": "app", "name": name}


def _delete(client, path):
    status, _ = client.delete(path)
    return status in (200, 204, 404)


def _undo_app_sql_view(client, entry):
    path = f"/api/sqlViews/{entry['id']}"
    _delete(client, path)
    original = entry.get("original")
    if original is None:
        return True
    status, _ = client.post("/api/sqlViews", original)
    return status < 400


def _undo_app(client, entry):
    status, apps = client.get("/api/apps")
    if status != 200 or not isinstance(apps, list):
        return False
    keys = [app.get("key") for app in apps if app.get("name") == entry["name"]]
    return all(_delete(client, f"/api/apps/{key}") for key in keys)


def undo(client, entry):
    """Reverse one recorded change. True when the instance is back as it was."""
    kind = entry.get("type")
    if kind == "sqlView":
        return _delete(client, f"/api/sqlViews/{entry['id']}")
    if kind == "user":
        return _delete(client, f"/api/users/{entry['id']}")
    if kind == "userRole":
        return _delete(client, f"/api/userRoles/{entry['id']}")
    if kind == "dataDimension":
        return client.set_data_dimension(entry["endpoint"], entry["id"], True) < 400
    if kind == "appSqlView":
        return _undo_app_sql_view(client, entry)
    if kind == "app":
        return _undo_app(client, entry)
    return False


class RunState:
    """This run's record, kept on the instance as it grows."""

    def __init__(self, client, run_id):
        self.client = client
        self.run_id = run_id
        self.entries = []

    def name(self, suffix=""):
        """A run-unique display name for something the suite creates."""
        return f"{NAME_PREFIX} {self.run_id}{' ' + suffix if suffix else ''}"

    def record(self, entry):
        """Write the entry to the instance *before* the change is made."""
        self.entries.append(entry)
        status, _ = self.client.put(RECORD_PATH, self.entries)
        if status == 404:
            status, _ = self.client.post(RECORD_PATH, self.entries)
        if status >= 400:
            raise RuntimeError(f"Could not write the run record ({status})")

    def undo_leftovers(self):
        """Undo what an earlier, killed run recorded. Returns the entries undone."""
        status, leftovers = self.client.get(RECORD_PATH)
        if status != 200 or not isinstance(leftovers, list):
            return []
        _undo_all(self.client, leftovers)
        self.client.delete(RECORD_PATH)
        return leftovers

    def finish(self):
        """Undo this run's changes, newest first, then drop the record.

        The record is kept when something could not be undone, so the next
        run tries again.
        """
        failed = _undo_all(self.client, self.entries)
        if not failed:
            self.client.delete(RECORD_PATH)
        return failed


def _undo_all(client, entries):
    failed = []
    for entry in reversed(entries):
        try:
            if not undo(client, entry):
                failed.append(entry)
        except Exception:  # noqa: BLE001 - keep undoing the rest
            failed.append(entry)
    return failed
