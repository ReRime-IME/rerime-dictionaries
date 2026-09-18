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
its bundled ZIP is another read-only base. Missing/mismatched base or malformed,
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

Local producer tests, native cache parity, Python-to-Swift real ZIP reconstruction,
and App fallback/cancellation tests pass. Remote rollout receipt is added after the
actual server-triggered run completes; code availability is not a published result.
