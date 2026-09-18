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
previous channel. A private watcher checks official upstream Releases daily and
dispatches GitHub builds only when needed; this is not real-time push notification.

The first signed release and authenticated channel are available. The initial
[manual build](https://github.com/Nongfsq/rerime-dictionaries/actions/runs/34589812884)
passed complete qualification, compilation, source-free consumer checks and anonymous
asset verification. A second [unchanged-input run](https://github.com/Nongfsq/rerime-dictionaries/actions/runs/34590902668)
skipped both build and promotion. See [initial distribution evidence](docs/initial-distribution.md)
and [publication and recovery](docs/release-recovery.md). Automatic checks are dispatched by the private release watcher; explicit manual
dispatch remains available. GitHub cron and automatic push triggers are removed.
These initial manual runs remain historical evidence.

## Licenses

New build tools use Apache-2.0 (`LICENSE`). Wanxiang data and spelling rules use
CC BY 4.0. The active recipe uses Wanxiang auxiliary inputs only; historical signed
fixtures retain their original Ice notices. OpenCC data
retains Apache-2.0. See `recipe/wanxiang-v1/NOTICE.md` and the included original
license files. Every release includes corresponding editable dictionary and recipe
sources and the public build tools used to produce it. These distinct licenses must
not be replaced by the tool license.

## Organization transfer (2026-09-11)

This repository now lives at `ReRime-IME/rerime-dictionaries`. Existing releases,
assets, signatures and channel history are preserved. The publisher targets the
organization and accepts both exact historical and organization channel identities,
with each package URL bound to its channel's own repository. Existing signed fixtures
remain unchanged.

Older ReRime builds that reject repository-migration redirects need an App update
to restore online dictionary downloads after the transfer. Installed dictionaries
and offline typing remain available.

Migration validation: 15 local test methods pass, including organization identity,
unknown repositories and cross-repository package mismatches. The existing latest
release was downloaded anonymously from the organization; its 41,676,811-byte
archive matches the signed channel SHA-256, with channel and manifest signatures
verified. This does not claim a newly built release or an updated installed App.

## ReRime regional word and Emoji additions

`tools/local_additions.json` owns Taiwan and Hong Kong simplified/traditional
word triggers and the standard 🇹🇼 / 🇭🇰 sequences. Every adaptation applies this
layer after copying the pinned recipe and fetching upstream dictionaries. It adds
a dedicated `rerime_regions` table and merges Emoji alternatives without removing
existing ones. Upstream deletion or replacement cannot remove these additions.
The original upstream files and recipe remain unchanged for attribution; overlay
data/code and its receipt are included in the corresponding-source archive and
bound by the producer identity. The old recipe Emoji qualification describes only
the base resources, not this overlay. Source-free consumer tests require actual
flag candidates and matching commits before publishing a new package.

Hong Kong already existed in the base Emoji mapping; Taiwan did not. This change
protects both and adds explicit flag-name triggers. Emoji glyph appearance is
controlled by the device OS and region as well as the dictionary; candidate
coverage does not guarantee identical rendering on every device.

See [regional additions and verification](docs/regional-emoji-additions.md) for
the sync-preservation mechanism, release evidence, and older-client advisory caveat.

## Official-release watcher migration

The producer now resolves official upstream Releases to exact commits and rejects
automatic rollback to an older/diverged release. A private outbound-only watcher
is deployed and active with a private GitHub App installed on this repository only.
The server automatically obtains short-lived installation tokens; routine operation
no longer depends on a personal token or periodic manual token renewal.
The repository, Releases and anonymous downloads remain public.
The [server-triggered verification](https://github.com/ReRime-IME/rerime-dictionaries/actions/runs/35184339643)
succeeded and was reconciled by the watcher. The older official Release correctly
produced no build or promotion, preserving the existing package. Daily release
checks use conditional requests; pending runs are reconciled every 15 minutes.
Channel renewal near expiry retains the existing package and signing gates.
The [App-authenticated verification](https://github.com/ReRime-IME/rerime-dictionaries/actions/runs/35188394866)
succeeded under `rerime-dictionary-watcher[bot]` and was reconciled on the server.
See [watcher operations](docs/release-watcher.md) and
[PLAN+TASK and rollout status](docs/release-watcher-plan.md).

## Local Wanxiang auxiliary-source migration (IME-182)

The new recipe replaces Ice Emoji/alias tables and symbol inputs with pinned
Wanxiang data. The original word remains selectable; alternatives retain Wanxiang
order. ReRime regional additions remain applied and independently tested. Active
runtime inventory drops `opencc/others.txt` and `LICENSE-rime-ice.txt`; the recipe
digest selects this inventory. Legacy signed fixtures are accepted only with their
original inventory. Source archives include original auxiliary inputs, adaptation
metadata and native glyph evidence.

The engine ABI is unchanged. The current local producer requires Xcode 27 and
iOS 27 glyph evidence; old iOS 26 qualification must not be copied onto new bytes.
The Owner authorized remote rollout on 2026-09-18. See
[source-unification rollout](docs/source-unification-rollout.md) for the current
server/cloud acceptance receipt. A local candidate is not a published release.

## Automatic incremental updates

Unchanged dictionary shards reuse qualified build results. Compatible Apps can use
optional deltas to reconstruct the same signed full package, with automatic full
download fallback. See [behavior, limits and rollout](docs/automatic-incremental-updates.md).
