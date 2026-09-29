# ReRime public dictionaries

This repository builds the public Wanxiang dictionary resources consumed by ReRime.
It contains public data recipes and build tools. The ReRime application source,
user dictionaries, clipboard data and typing history are not part of this repository.

A compatible iPhone downloads an authenticated, already compiled package. It checks
its identity, preserves the on-device personal layer and opens the compiled schemas
before activating the update. The keyboard operates offline.

## Build contract

The first compatibility profile is `wanxiang-ios-arm64-rime1161-v1`: the pinned
LibrimeKit-iOS v0.1.0 engine (Rime 1.16.1), arm64, Xcode 27.0 build 27A266a and iOS
27.0 Simulator glyph qualification. A different OS or engine requires new evidence
and explicit client compatibility support. Fixed filenames and schemas live in
`contract/`; exact engine and recipe identities live in `locks/`.

The adapter reads dictionary data at a fixed upstream commit. It does not interpret
arbitrary YAML, execute upstream scripts or include Lua and grammar models. Chinese
entries are checked in their original and OpenCC traditional forms with CoreText
inside the qualified iOS runtime. English codes use ASCII lowercase; display text
and source weights are preserved. The pinned recipe retains qualified symbol and
word-triggered Emoji resources and their provenance.

## Local verification

Use an existing iOS 27.0 Simulator on a macOS arm64 host with the pinned Xcode.
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
previous channel. A watcher checks official upstream Releases daily and dispatches
the `Public dictionaries` workflow only when needed; manual dispatch remains
available. The producer resolves official upstream Releases to exact commits and
never rolls back to an older or diverged release. Channel renewal near expiry keeps
the existing package and signing gates. See [publication and recovery](docs/release-recovery.md)
and [watcher operations](docs/release-watcher.md).

Unchanged dictionary shards reuse qualified build results. Compatible Apps can use
optional deltas to reconstruct the same signed full package, with automatic full
download fallback. See [automatic incremental updates](docs/automatic-incremental-updates.md).

## Profiles

Each profile has its own signed channel file on the `channel` branch
(`channels/<profile>.json`) and its own releases. A promotion replaces only its own
profile's file. Package revisions are one repository-wide counter, so release tags
keep the `wanxiang-precompiled-<revision>-<commit>` form and never collide; each
profile's revisions only increase. Release bodies name the profile; only v1 releases
are marked GitHub's "latest". Both profiles are qualified for iOS 27.0 only.

- **v1** `wanxiang-ios-arm64-rime1161-v1`: full-Pinyin, English and mixed schemas.
- **v2** `wanxiang-ios-arm64-rime1161-v2`: v1 plus the `wanxiang_t9` nine-key schema
  (`recipe/wanxiang-v1/wanxiang_t9.schema.yaml`), adapted from upstream Wanxiang's T9
  speller at the pinned source revision without Lua, grammar or abbreviation rules.
  It mounts the shared `wanxiang` dictionary under its own `wanxiang_t9` prism
  (`contract/compatibility-rime1161-v2.json`). `locks/recipe-v2.json` selects the v1
  recipe files plus `wanxiang_t9.schema.yaml` and `default.custom.yaml`.

The workflow's `profile` input selects the profile; absent means v1. Minimum App
builds per profile are in `locks/release.json`.

## Regional word and Emoji additions

`tools/local_additions.json` owns Taiwan and Hong Kong simplified/traditional
word triggers and the standard 🇹🇼 / 🇭🇰 sequences. Every adaptation applies this
layer after copying the pinned recipe and fetching upstream dictionaries, in a
dedicated `rerime_regions` table, merging Emoji alternatives without removing
existing ones. Emoji glyph appearance also depends on the device OS and region.
See [regional additions](docs/regional-emoji-additions.md).

## Corrections to Wanxiang spelling rules

`tools/recipe_corrections.json` replaces exact upstream rule lines in the adapted
copy on every build. The locked recipe and its hash stay unchanged, so installed
Apps accept the package. A rule that no longer matches stops the build for
review. The first correction stops typed `tie` from also reading as `tei` (忒). See
[recipe corrections](docs/recipe-corrections.md).

## Licenses

New build tools use Apache-2.0 (`LICENSE`). Wanxiang data and spelling rules use
CC BY 4.0. The recipe uses Wanxiang auxiliary inputs only; historical signed
fixtures retain their original notices. OpenCC data retains Apache-2.0. See
`recipe/wanxiang-v1/NOTICE.md` and the included original license files. Every
release includes corresponding editable dictionary and recipe sources and the
public build tools used to produce it. These distinct licenses must not be
replaced by the tool license.
