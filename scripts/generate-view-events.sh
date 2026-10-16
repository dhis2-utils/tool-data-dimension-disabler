#!/usr/bin/env bash
# Record favorite view events on a DHIS2 instance so the usage ranking is
# non-trivial when testing. Usage:
#   scripts/generate-view-events.sh http://localhost:8080 <user:password>
# Writes usage statistics: use a throwaway instance, never a server whose
# statistics matter.
# Records N views per favorite, where N decreases along the list, for the
# first 5 visualizations, 3 maps and 3 event visualizations that actually use
# at least one of the four dimension types this app ranks -- a favorite that
# uses none of them would only ever contribute 0 views, which defeats the
# point of seeding data.
#
# Selection uses the `~size` field transformer (e.g. `categoryDimensions~size`)
# rather than the `!empty` filter operator: `!empty` is rejected by 2.40 with
# `400 E1003 "!empty is not a valid operator"`, while `~size` works from 2.40
# through 2.43. jq then keeps only the favorites whose dimension sizes sum to
# more than 0.
set -euo pipefail
BASE="${1:?base url}"; AUTH="${2:?user:password}"

record() { # eventType uid count
    local event_type="$1" favorite="$2" views="$3"
    for _ in $(seq 1 "$views"); do
        curl -s -o /dev/null -u "$AUTH" -X POST \
            "$BASE/api/dataStatistics?eventType=$event_type&favorite=$favorite"
    done
    echo "$event_type $favorite x$views"
}

# GETs $1 (a path+query starting with /api/...). Prints the body on 2xx.
# On any other status, prints a warning to stderr (instead of the previous
# version's blanket `|| true`, which turned a 400 into a silent empty
# result) and prints an empty JSON object so callers can keep going under
# `set -euo pipefail`.
fetch() { # path
    local response status body
    response=$(curl -sS --globoff -u "$AUTH" -w '\n%{http_code}' "$BASE$1")
    status=${response##*$'\n'}
    body=${response%$'\n'*}
    if [[ ! $status =~ ^2 ]]; then
        echo "warning: GET $1 -> HTTP $status: $body" >&2
        echo '{}'
        return 0
    fi
    echo "$body"
}

# Prints the ids of the first $2 favorites in the JSON array $1 (each object
# a favorite with an `id` plus one or more `*Dimensions` size fields, or a
# `mapViews` array of such objects for maps) whose dimension sizes sum to
# more than 0, and a one-line summary of how many favorites had dimensions
# to stderr.
select_with_dimensions() { # favoritesArrayJson limit label
    local array="$1" limit="$2" label="$3"
    local stats
    stats=$(jq -c --argjson limit "$limit" '
        def dimSum:
            if has("mapViews") then
                [(.mapViews // [])[] | to_entries | map(select(.key != "id") | .value) | add // 0] | add // 0
            else
                to_entries | map(select(.key != "id") | .value) | add // 0
            end;
        {
            total: length,
            withDimensions: ([.[] | select(dimSum > 0)] | length),
            ids: ([.[] | select(dimSum > 0)] | .[0:$limit] | map(.id))
        }
    ' <<<"$array")
    echo "$label: $(jq -r '"\(.withDimensions)/\(.total) favorites carry a dimension"' <<<"$stats")" >&2
    jq -r '.ids[]' <<<"$stats"
}

n=5
visualizations=$(fetch "/api/visualizations?fields=id,categoryDimensions~size,organisationUnitGroupSetDimensions~size,dataElementGroupSetDimensions~size,categoryOptionGroupSetDimensions~size&paging=false" | jq -c '.visualizations // []')
for uid in $(select_with_dimensions "$visualizations" 5 visualizations); do
    record VISUALIZATION_VIEW "$uid" "$n"; n=$((n>1 ? n-1 : 1))
done

n=3
maps=$(fetch "/api/maps?fields=id,mapViews[categoryDimensions~size,organisationUnitGroupSetDimensions~size,categoryOptionGroupSetDimensions~size]&paging=false" | jq -c '.maps // []')
for uid in $(select_with_dimensions "$maps" 3 maps); do
    record MAP_VIEW "$uid" "$n"; n=$((n>1 ? n-1 : 1))
done

n=3
event_visualizations=$(fetch "/api/eventVisualizations?fields=id,categoryDimensions~size,organisationUnitGroupSetDimensions~size,categoryOptionGroupSetDimensions~size&paging=false" | jq -c '.eventVisualizations // []')
for uid in $(select_with_dimensions "$event_visualizations" 3 event_visualizations); do
    record EVENT_VISUALIZATION_VIEW "$uid" "$n"; n=$((n>1 ? n-1 : 1))
done
