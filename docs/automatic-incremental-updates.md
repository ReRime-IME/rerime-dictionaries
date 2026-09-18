# Automatic build reuse and optional incremental delivery

The Owner authorized both layers after source unification (2026-09-18). Preserve
offline bundled first use, the global regional additions, existing signed full
packages and installed personal data. Mainland mirrors remain out of scope.

## Build reuse

The native qualifier caches complete filtered dictionary shards under
`.build/qualification-cache`, capped at512 MiB. Exact source bytes, qualifier/cache
code, engine/toolchain lock, actual runtime build and OpenCC conversion resources
bind a cache entry. Missing, malformed, corrupt or mismatched entries are misses.
Files are independently reused; an ordinary dictionary update need not repeat glyph
work for every unchanged shard. Only the existing main-only workflow restores/saves
this trusted producer cache. No App user dictionaries are read or cached here.

Cold/warm runs produce identical qualified bytes and signed qualification reports.
Cache hit/miss counts and timings are recorded separately in build-resources. A native
regression checks cold/warm parity, one-file changes, context changes and corruption
before publishing. Local full-public-dictionary evidence:22 cold misses versus22 warm
hits, 128,157 ms versus134 ms, identical output. This measures qualification only;
small files can cost more to cache than to inspect and whole-pipeline savings vary.

## Optional delivery delta

The publisher verifies the previous signed channel's ZIP and creates a delta against
that exact base. Unchanged raw ZIP members are copied; changed members and the target
ZIP directory become literals. A self-replay must reconstruct the exact target ZIP.
Publish `delta.json` and `delta.bin` only when combined size saves at least5%.
Unavailable base, failed optimization or negligible savings publishes the ordinary
full package instead. Every release retains the full signed ZIP and editable sources.

Delta metadata is a bounded untrusted transfer hint. It cannot choose external URLs,
introduce a trust key or authorize installation. The client binds target size/hash to
its already verified signed channel, bounds operations and byte ranges, checks the
base and literal hashes, reconstructs to a new temporary file and verifies the full
target archive. The existing signed installer alone owns schema validation, personal
layer preservation and atomic activation. No table patching or compilation on phones.

The App keeps at most one successful public ZIP in its disposable Caches directory;
its bundled ZIP is another read-only base. An exact authenticated local target is
reused without another archive download. Missing/mismatched base or malformed,
unavailable or damaged delta falls back once to full download. Explicit cancellation
stops the whole operation and does not trigger fallback. Old clients and old releases
keep working through full downloads. The download starts under the existing user
update action; no new background download consent or scheduling is introduced.

The first delta is member-granular: a changed Chinese table still downloads in full.
Do not describe it as per-word updates or promise a tiny download for every release.
Subfile algorithms are deferred until representative update measurements justify
additional complexity. Full dictionary text is processed by scripts, never dumped
into agent context; only hashes, counts and timings are inspected.

## Compatibility and rollback

Current App scope is iOS27 by default and iOS26 backward compatibility. Glyph evidence
remains truthful about where it was measured; it is separate from runtime admission.
App recipe/ABI/key trust and staged real-schema checks remain mandatory. Earlier and
future systems are not added by this work.

Disable optional delta assets or revert client download composition to return to full
downloads. Remove/evict the disposable build cache to run cold without changing output.
Preserve immutable releases/channel floors, existing data and credentials.

## Rollout

The actual server-triggered run
[35402857564](https://github.com/ReRime-IME/rerime-dictionaries/actions/runs/35402857564)
succeeded at producer969537445ec08f3c9a3a713ebc5745efc2908d85. Native consumer
and cache parity/invalidation checks passed before promotion; the first cold run
saved the bounded cloud cache for subsequent builds. Full cloud qualification took
196,836 ms (22 misses); total native pipeline407,081 ms. No second warm cloud
build is claimed; warm behavior is established by the parity tests and local full run.

Revision14/channel14 was promoted at ccd308c580d8a2366c16c39685145edc495f1ff1
after all12 immutable assets passed anonymous download verification. Full ZIP is
41,683,918 bytes with SHA256
`41bd0f394e27d10891508acbab7f0e0602021994f0792534357c0bc0a48bc79c`.
The production App catalog/downloader verified the live signed channel and downloaded
only delta.json + delta.bin (8,532 bytes), then reconstructed that exact ZIP from
published revision13. Only manifest/build-receipt bytes changed in this pair; runtime
payload bytes are identical, so this is not a typical new-vocabulary savings claim.
The existing watcher reconciled the same run as successful. Client optimization still
requires shipping the updated App; dictionary publication does not update App code.
