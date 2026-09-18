#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
# A local caller must supply an existing, explicitly selected Simulator. This
# script neither creates nor resets local devices and does not install any app.
if [[ "${1:-}" != --locked ]]; then echo 'Usage: build-local.sh --locked' >&2; exit 2; fi
: "${RERIME_SIMULATOR_UDID:?Set the existing task-selected Simulator UDID}"
: "${RERIME_BUILD_WORK:?Set a new task-owned build directory}"
: "${RERIME_BUILD_OUTPUT:?Set a new artifact directory}"
: "${RERIME_PACKAGE_REVISION:?Set the proposed immutable package revision}"
: "${RERIME_APP_BUILD:?Set the minimum compatible App build}"
python3 tools/engine.py
xcrun swiftc tools/sign.swift -o .build/bin/sign
python3 tools/adapt.py --work "$RERIME_BUILD_WORK" ${RERIME_UPSTREAM_REVISION:+--revision "$RERIME_UPSTREAM_REVISION"}
if [[ -n "${RERIME_CHECK_PLAN:-}" ]]; then
  python3 tools/check_release.py verify-source --plan "$RERIME_CHECK_PLAN" --work "$RERIME_BUILD_WORK"
fi
export SIMCTL_CHILD_RERIME_QUALIFICATION_CACHE="${RERIME_QUALIFICATION_CACHE:-$PWD/.build/qualification-cache}"
export SIMCTL_CHILD_RERIME_QUALIFICATION_CONTEXT="$(python3 - <<'CACHEPY'
import hashlib
from pathlib import Path
h=hashlib.sha256()
for p in sorted([*Path('tools').glob('Glyph*.swift'),Path('locks/engine.json')]):
 h.update(p.name.encode());h.update(p.read_bytes())
print(h.hexdigest())
CACHEPY
)"
xcrun simctl spawn "$RERIME_SIMULATOR_UDID" "$PWD/.build/bin/GlyphQualifier" "$RERIME_BUILD_WORK/adapted" "$RERIME_BUILD_WORK/qualified"
python3 - "$RERIME_BUILD_WORK/qualified" <<'PY'
from pathlib import Path
import os,sys
for path in Path(sys.argv[1]).rglob('*'):
 if path.is_file():os.utime(path,(1767225600,1767225600))
PY
xcrun simctl spawn "$RERIME_SIMULATOR_UDID" "$PWD/.build/bin/RimeBuilder" "$RERIME_BUILD_WORK/qualified"
python3 tools/pack.py prepare --work "$RERIME_BUILD_WORK" --output "$RERIME_BUILD_OUTPUT" \
  --revision "$RERIME_PACKAGE_REVISION" --adapter-revision "$(git rev-parse HEAD)" --app-build "$RERIME_APP_BUILD"
python3 tools/verify.py --directory "$RERIME_BUILD_OUTPUT"
