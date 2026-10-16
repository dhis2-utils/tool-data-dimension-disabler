#!/usr/bin/env bash
# Entry point of the end-to-end suite (contract: reference-tool-conventions
# TESTING.md, version 1). The suite changes and deletes data: run it only
# against a throwaway DHIS2 instance. See e2e/README.md.
#
#   DHIS2_URL=http://localhost:8080 DHIS2_USER=<superuser> DHIS2_PASS=<password> \
#   APP_ZIP=$PWD/build/bundle/<app>.zip RESULTS_DIR=/tmp/e2e-results \
#     e2e/run.sh
#
# Exit codes: 0 all passed, 1 a test failed, 2 the suite could not run.
set -u

missing=()
for name in DHIS2_URL DHIS2_USER DHIS2_PASS APP_ZIP RESULTS_DIR; do
    [ -n "${!name:-}" ] || missing+=("$name")
done
if [ ${#missing[@]} -gt 0 ]; then
    echo "e2e/run.sh: not set: ${missing[*]} (no defaults, see e2e/README.md)" >&2
    exit 2
fi
if [ ! -f "$APP_ZIP" ]; then
    echo "e2e/run.sh: APP_ZIP does not exist: $APP_ZIP" >&2
    exit 2
fi
if [ ! -d "$RESULTS_DIR" ]; then
    echo "e2e/run.sh: RESULTS_DIR is not a directory: $RESULTS_DIR" >&2
    exit 2
fi

exec python3 "$(dirname "$0")/run_suite.py"
