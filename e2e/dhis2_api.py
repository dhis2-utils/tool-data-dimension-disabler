"""Minimal DHIS2 REST helpers for the end-to-end suite.

No hard-coded hosts: every caller passes the instance URL, which
``run_suite`` reads from the ``DHIS2_URL`` environment variable.
"""

import base64
import json
import secrets
import time
import urllib.error
import urllib.request
import zipfile
from pathlib import Path
from urllib.parse import urlparse

JSON_CONTENT_TYPE = "application/json"
JSON_PATCH_CONTENT_TYPE = "application/json-patch+json"
SQL_VIEW_ID = "GOLswS44mh8"
SQL_VIEW_PATH = f"/api/sqlViews/{SQL_VIEW_ID}"


class Dhis2Client:
    """Basic-auth REST client. Returns (status, parsed body)."""

    def __init__(self, base_url, username, password):
        self.base_url = base_url.rstrip("/")
        token = base64.b64encode(f"{username}:{password}".encode()).decode()
        self.auth_header = f"Basic {token}"

    def _request(self, method, path, body=None, content_type=JSON_CONTENT_TYPE):
        data = None if body is None else json.dumps(body).encode()
        request = urllib.request.Request(
            f"{self.base_url}{path}", data=data, method=method
        )
        request.add_header("Authorization", self.auth_header)
        if data is not None:
            request.add_header("Content-Type", content_type)
        try:
            with urllib.request.urlopen(request) as response:
                return response.status, _parse(response.read())
        except urllib.error.HTTPError as error:
            return error.code, _parse(error.read())

    def get(self, path):
        return self._request("GET", path)

    def post(self, path, body=None):
        return self._request("POST", path, body)

    def put(self, path, body):
        return self._request("PUT", path, body)

    def delete(self, path):
        return self._request("DELETE", path)

    def json_patch(self, path, operations):
        return self._request(
            "PATCH", path, operations, content_type=JSON_PATCH_CONTENT_TYPE
        )

    def session_cookie(self):
        """Authenticated session cookie, for injection into the browser.

        Uses Basic-auth ``GET /api/me``: ``POST /api/auth/login`` redirects to
        the legacy login page on 2.40 and yields an anonymous cookie instead.
        """
        request = urllib.request.Request(f"{self.base_url}/api/me")
        request.add_header("Authorization", self.auth_header)
        with urllib.request.urlopen(request) as response:
            for header in response.headers.get_all("Set-Cookie") or []:
                name, _, value = header.split(";", 1)[0].partition("=")
                if "JSESSIONID" in name:
                    return name.strip(), value.strip()
        raise RuntimeError("No JSESSIONID cookie returned by /api/me")

    def install_app(self, zip_path):
        """POST the bundle to /api/apps as multipart form data; returns the status."""
        boundary = f"----e2e{secrets.token_hex(8)}"
        payload = Path(zip_path).read_bytes()
        body = b"".join(
            [
                f"--{boundary}\r\n".encode(),
                (
                    'Content-Disposition: form-data; name="file"; '
                    f'filename="{Path(zip_path).name}"\r\n'
                ).encode(),
                b"Content-Type: application/zip\r\n\r\n",
                payload,
                f"\r\n--{boundary}--\r\n".encode(),
            ]
        )
        request = urllib.request.Request(
            f"{self.base_url}/api/apps", data=body, method="POST"
        )
        request.add_header("Authorization", self.auth_header)
        request.add_header("Content-Type", f"multipart/form-data; boundary={boundary}")
        try:
            with urllib.request.urlopen(request) as response:
                return response.status
        except urllib.error.HTTPError as error:
            return error.code

    def app_key_by_name(self, name):
        """Key the server gave the installed app whose manifest name is `name`."""
        status, apps = self.get("/api/apps")
        if status != 200 or not isinstance(apps, list):
            return None
        for app in apps:
            if app.get("name") == name:
                return app.get("key")
        return None

    def server_version(self):
        _, info = self.get("/api/system/info")
        return info.get("version", "unknown")

    def sql_view(self, fields="id,name,sharing,sqlQuery"):
        return self.get(f"{SQL_VIEW_PATH}?fields={fields}")

    def delete_sql_view_if_present(self):
        status, _ = self.sql_view(fields="id")
        if status == 200:
            return self.delete(SQL_VIEW_PATH)[0]
        return status

    def sql_view_data(self):
        """The ranked rows plus the wall-clock duration of the request."""
        started = time.monotonic()
        status, body = self.get(f"{SQL_VIEW_PATH}/data?paging=false")
        return status, body, time.monotonic() - started

    def data_dimension(self, endpoint, uid):
        _, body = self.get(f"/api/{endpoint}/{uid}?fields=dataDimension")
        return body.get("dataDimension")

    def set_data_dimension(self, endpoint, uid, value):
        return self.json_patch(
            f"/api/{endpoint}/{uid}",
            [{"op": "add", "path": "/dataDimension", "value": value}],
        )[0]


def _parse(raw):
    if not raw:
        return {}
    try:
        return json.loads(raw)
    except ValueError:
        return {"raw": raw.decode("utf-8", "replace")}


def read_manifest(zip_path):
    """`manifest.webapp` of a built bundle, as a dict."""
    with zipfile.ZipFile(zip_path) as bundle:
        return json.loads(bundle.read("manifest.webapp"))


def hostname_of(url):
    """Hostname of an instance URL, for cookie injection."""
    return urlparse(url).hostname


def grid_rows(payload):
    """`/sqlViews/{id}/data` listGrid as a list of dicts keyed by column name."""
    grid = payload.get("listGrid") or {}
    headers = [header["name"] for header in grid.get("headers", [])]
    return [dict(zip(headers, row)) for row in grid.get("rows", [])]
