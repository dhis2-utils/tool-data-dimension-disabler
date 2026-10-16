"""An independent second count of the favorites per sharing class.

The app's own SQL view produces `favorites`, `public_favorites`,
`shared_favorites` and `private_favorites` in one pass, all from one SQL
`CASE`. Comparing the table with that same payload would only prove the app
rendered what it was given, and restating the same `CASE` here would only
prove it was copied correctly — neither can catch a misclassification.

So the two halves are split across two layers:

- **which favorites use the dimension** comes from a throwaway SQL view that
  returns nothing but `(favorite uid, favorite kind)` pairs, reached through
  the join tables. No sharing logic at all, and therefore no `CASE` to
  restate;
- **how each of those favorites is shared** comes from the Web API
  (`/api/visualizations`, `/api/maps`, `/api/eventVisualizations`) and is
  classified in Python, from the JSON the server itself reports.

Reading that sharing needs an account that can see every favorite: a private
favorite owned by somebody else is a 404 for a demo `admin` without `ALL`,
and guessing "unreadable means private" would quietly turn a *shared*
favorite into a private one — exactly the class this oracle exists to check.
The suite runs as a superuser (`DHIS2_USER`, see e2e/README.md), which can;
if it cannot, the oracle raises `UnreadableFavorites` rather than guess.

The schema knowledge below is deliberately spelled out rather than derived
from `src/`: an oracle built from the code under test proves nothing.
Verified against 2.40.12 and 2.43.1 (see `docs/schema-check.md`).
"""

import re

from dhis2_api import grid_rows
from state import new_uid, sql_view_entry

PUBLIC = "public"
SHARED = "shared"
PRIVATE = "private"
SHARING_CLASSES = (PUBLIC, SHARED, PRIVATE)
TOTAL_KEY = "favorites"
UID_PATTERN = re.compile(r"^[A-Za-z][A-Za-z0-9]{10}$")
API_PAGE_SIZE = 200

# (join-table prefix, metadata endpoint, SQL reaching that favorite as `f`).
# The prefix doubles as the kind tag the query emits, so the right endpoint
# can be asked for each uid afterwards. Note `mapview` tags a favorite that
# is actually a *map*: a view event names the map, not the map view, so the
# join goes mapview -> mapmapviews -> map and `/api/maps` holds its sharing.
VISUALIZATION_SOURCE = (
    "visualization",
    "visualizations",
    "JOIN visualization f ON f.visualizationid = a.visualizationid",
)
MAP_SOURCE = (
    "mapview",
    "maps",
    "JOIN mapmapviews mm ON mm.mapviewid = a.mapviewid\n"
    "        JOIN map f ON f.mapid = mm.mapid",
)
EVENT_VISUALIZATION_SOURCE = (
    "eventvisualization",
    "eventVisualizations",
    "JOIN eventvisualization f ON f.eventvisualizationid = a.eventvisualizationid",
)
ALL_SOURCES = (VISUALIZATION_SOURCE, MAP_SOURCE, EVENT_VISUALIZATION_SOURCE)
ENDPOINT_BY_KIND = {prefix: endpoint for prefix, endpoint, _ in ALL_SOURCES}

# Every type has all three favorite sources except DATAELEMENT_GROUP_SET,
# which only visualizations can carry: no mapview_ or
# eventvisualization_dataelementgroupsetdimensions table exists on any
# supported version (docs/schema-check.md). Category option group sets do
# have all three.
DIMENSION_SCHEMA = {
    "CATEGORY": {
        "table": "category",
        "table_before_41": "dataelementcategory",
        "pk": "categoryid",
        "dimension_table": "categorydimension",
        "dimension_pk": "categorydimensionid",
        "dimension_fk": "categoryid",
        "join_suffix": "categorydimensions",
        "sources": ALL_SOURCES,
    },
    "ORGUNIT_GROUP_SET": {
        "table": "orgunitgroupset",
        "pk": "orgunitgroupsetid",
        "dimension_table": "orgunitgroupsetdimension",
        "dimension_pk": "orgunitgroupsetdimensionid",
        "dimension_fk": "orgunitgroupsetid",
        "join_suffix": "orgunitgroupsetdimensions",
        "sources": ALL_SOURCES,
    },
    "DATAELEMENT_GROUP_SET": {
        "table": "dataelementgroupset",
        "pk": "dataelementgroupsetid",
        "dimension_table": "dataelementgroupsetdimension",
        "dimension_pk": "dataelementgroupsetdimensionid",
        "dimension_fk": "dataelementgroupsetid",
        "join_suffix": "dataelementgroupsetdimensions",
        "sources": (VISUALIZATION_SOURCE,),
    },
    "CATEGORYOPTION_GROUP_SET": {
        "table": "categoryoptiongroupset",
        "pk": "categoryoptiongroupsetid",
        "dimension_table": "categoryoptiongroupsetdimension",
        "dimension_pk": "categoryoptiongroupsetdimensionid",
        "dimension_fk": "categoryoptiongroupsetid",
        "join_suffix": "categoryoptiongroupsetdimensions",
        "sources": ALL_SOURCES,
    },
}


class UnreadableFavorites(Exception):
    """Some favorite's sharing could not be read by the acting account."""


def _entity_table(schema, minor):
    """The entity table; the category table was renamed in 2.41."""
    if minor < 41 and "table_before_41" in schema:
        return schema["table_before_41"]
    return schema["table"]


def _source_branch(schema, source, uid, minor):
    """One (favorite uid, favorite kind) branch for a single favorite kind."""
    prefix, _, favorite_join = source
    return (
        f"      SELECT DISTINCT f.uid AS favoriteuid, '{prefix}' AS favoritekind\n"
        f"        FROM {prefix}_{schema['join_suffix']} a\n"
        f"        JOIN {schema['dimension_table']} d"
        f" ON d.{schema['dimension_pk']} = a.{schema['dimension_pk']}\n"
        f"        JOIN {_entity_table(schema, minor)} z"
        f" ON z.{schema['pk']} = d.{schema['dimension_fk']} AND z.uid = '{uid}'\n"
        f"        {favorite_join}"
    )


def crosscheck_query(type_key, uid, minor):
    """The favorites of one dimension: uid and kind, no sharing logic."""
    if not UID_PATTERN.match(uid):
        raise ValueError(f"Not a DHIS2 uid: {uid!r}")
    schema = DIMENSION_SCHEMA[type_key]
    return "\n      UNION\n".join(
        _source_branch(schema, source, uid, minor) for source in schema["sources"]
    )


def _crosscheck_definition(view_id, name, query):
    return {
        "id": view_id,
        "name": name,
        "description": "Throwaway view created and deleted by the e2e suite",
        "type": "QUERY",
        "cacheStrategy": "NO_CACHE",
        "sharing": {"public": "r-r-----"},
        "sqlQuery": query,
    }


def favorite_uids(client, type_key, uid, minor, state):
    """`{kind: [favorite uid, ...]}` for one dimension, straight from the DB.

    Installs the join query as a throwaway SQL view with a run-unique uid and
    name, recorded in the run record before it is created, reads it, and
    removes it again.
    """
    view_id = new_uid()
    path = f"/api/sqlViews/{view_id}"
    state.record(sql_view_entry(view_id))
    status, body = client.post(
        "/api/sqlViews",
        _crosscheck_definition(
            view_id,
            state.name(f"favorite cross-check {view_id}"),
            crosscheck_query(type_key, uid, minor),
        ),
    )
    if status >= 400:
        raise AssertionError(f"Could not create the cross-check SQL view: {body}")
    try:
        _, payload = client.get(f"{path}/data?paging=false")
        return _uids_by_kind(grid_rows(payload))
    finally:
        client.delete(path)


def _uids_by_kind(rows):
    by_kind = {prefix: [] for prefix in ENDPOINT_BY_KIND}
    for row in rows:
        by_kind[row["favoritekind"]].append(row["favoriteuid"])
    return by_kind


def sharing_class(sharing):
    """Classify one favorite from the `sharing` object the API reports.

    public  - the public access string grants metadata read (starts with 'r')
    shared  - not public, but shared with at least one user or user group
    private - neither; `None`, a missing key and `{}` all mean "not shared"
    """
    sharing = sharing or {}
    if str(sharing.get("public") or "").startswith("r"):
        return PUBLIC
    for key in ("users", "userGroups"):
        value = sharing.get(key)
        if isinstance(value, dict) and value:
            return SHARED
    return PRIVATE


def _sharing_by_uid(client, endpoint, uids):
    """`{uid: sharing}` for one favorite kind, in a single filtered request."""
    if not uids:
        return {}
    ids = ",".join(sorted(set(uids)))
    _, body = client.get(
        f"/api/{endpoint}?filter=id:in:[{ids}]"
        f"&fields=id,sharing&paging=false&pageSize={API_PAGE_SIZE}"
    )
    found = body.get(endpoint) or []
    return {entry["id"]: entry.get("sharing") for entry in found}


def _classify_kind(client, kind, uids):
    """The sharing class of every favorite of one kind."""
    endpoint = ENDPOINT_BY_KIND[kind]
    sharing = _sharing_by_uid(client, endpoint, uids)
    missing = [uid for uid in uids if uid not in sharing]
    if missing:
        raise UnreadableFavorites(
            f"/api/{endpoint} did not return {missing} - the account reading "
            "the sharing cannot see them; DHIS2_USER must hold ALL"
        )
    return [sharing_class(sharing[uid]) for uid in uids]


def favorite_counts(client, type_key, uid, minor, state):
    """Count one dimension's favorites per sharing class, independently.

    The join comes from SQL, the classification from the Web API: neither
    half restates the app's own `CASE`. The client must see every favorite
    (see the module docstring).
    """
    by_kind = favorite_uids(client, type_key, uid, minor, state)
    counts = dict.fromkeys(SHARING_CLASSES, 0)
    for kind, uids in by_kind.items():
        for name in _classify_kind(client, kind, uids):
            counts[name] += 1
    counts[TOTAL_KEY] = sum(counts[name] for name in SHARING_CLASSES)
    return counts
