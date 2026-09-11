# ReRime public dictionaries

This repository builds the public Wanxiang dictionary resources consumed by ReRime.
It contains public data recipes and build tools. The ReRime application source,
user dictionaries, clipboard data and typing history are not part of this repository.

A compatible iPhone downloads an authenticated, already compiled package. It checks
its identity, preserves the on-device personal layer and opens the compiled schemas
before activating the update. The keyboard operates offline.

## Build contract

The first compatibility profile is `wanxiang-ios-arm64-rime1161-v1`: the pinned
LibrimeKit-iOS v0.1.0 engine (Rime 1.16.1), arm64, Xcode 26.6 build 17F113 and iOS
26.5 Simulator glyph qualification. A different OS or engine requires new evidence
and explicit client compatibility support. Fixed filenames and schemas live in
`contract/`; exact engine and recipe identities live in `locks/`.

The adapter reads dictionary data at a fixed upstream commit. It does not interpret
arbitrary YAML, execute upstream scripts or include Lua and grammar models. Chinese
entries are checked in their original and OpenCC traditional forms with CoreText
inside the qualified iOS runtime. English codes use ASCII lowercase; display text
and source weights are preserved. The pinned recipe retains qualified symbol and
word-triggered Emoji resources and their provenance.

## Local verification

Use an existing iOS 26.5 Simulator on a macOS arm64 host with the pinned Xcode.
The build scripts do not create, reset or install apps on local Simulators. Start
and manage the selected device with your own host's approved Simulator workflow.

```sh
python3 tools/engine.py
xcrun swiftc tools/sign.swift -o .build/bin/sign
python3 -m unittest discover -s tests -v
export RERIME_SIMULATOR_UDID=YOUR_EXISTING_SIMULATOR_UDID
export RERIME_BUILD_WORK="$PWD/.build/run-1"
export RERIME_BUILD_OUTPUT="$PWD/.build/output-1"
export RERIME_PACKAGE_REVISION=2026091101
export RERIME_APP_BUILD=21
bash scripts/build-local.sh --locked
bash scripts/test-consumer.sh --no-deploy
```

Every build uses new work/output directories. To test reproducibility, repeat with
new directories and compare manifest payloads, source archives and unsigned runtime
archives at the same upstream and tool commits. Resource timestamps, ZIP entry times
and ordering are fixed. Runner image metadata is a separate receipt, not an input to
public resource identity.

`pack.py prepare` produces unsigned candidate files. Publishing requires a separate
Ed25519 signature. `tools/sign.swift` reads a protected key file or the dedicated
publish environment; it never prints private bytes. The public fixture key is only
for contract tests and must never be trusted by an App release.

## Distribution and failure behavior

The versioned package contract separates package revisions from signed channel
sequences. Releases contain runtime and editable source archives, signed manifest,
glyph qualification and build receipts. Only after complete anonymous download
verification may a signed channel point at the new release. Failed builds retain the
previous channel. GitHub schedules can be delayed; a scheduled configuration is not
a guarantee of real-time updates.

The first signed release and authenticated channel are available. The initial
[manual build](https://github.com/Nongfsq/rerime-dictionaries/actions/runs/34589812884)
passed complete qualification, compilation, source-free consumer checks and anonymous
asset verification. A second [unchanged-input run](https://github.com/Nongfsq/rerime-dictionaries/actions/runs/34590902668)
skipped both build and promotion. See [initial distribution evidence](docs/initial-distribution.md)
and [publication and recovery](docs/release-recovery.md). Hourly scheduling is
configured; these two manual runs do not establish scheduled execution.

## Licenses

New build tools use Apache-2.0 (`LICENSE`). Wanxiang data and spelling rules use
CC BY 4.0; derived Rime Ice symbol/Emoji resources retain GPL-3.0-only; OpenCC data
retains Apache-2.0. See `recipe/wanxiang-v1/NOTICE.md` and the included original
license files. Every release includes corresponding editable dictionary and recipe
sources and the public build tools used to produce it. These distinct licenses must
not be replaced by the tool license.
