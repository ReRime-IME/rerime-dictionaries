#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
if [[ "${1:-}" != --no-deploy ]]; then echo 'Usage: test-consumer.sh --no-deploy' >&2; exit 2; fi
: "${RERIME_SIMULATOR_UDID:?Set the task-selected Simulator}"
: "${RERIME_BUILD_OUTPUT:?Set the package output directory}"
python3 tools/consumer_test.py --directory "$RERIME_BUILD_OUTPUT" --simulator "$RERIME_SIMULATOR_UDID"
