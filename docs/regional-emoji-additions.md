# Taiwan and Hong Kong word-triggered flags

## Scope and implementation

Taiwan and Hong Kong words and flags survive upstream Wanxiang synchronization.
The base recipe already contains `香港 → 🇭🇰`; it lacks a Taiwan flag mapping.

`tools/local_additions.json` contains 12 simplified/traditional triggers, including
台湾 / 臺灣 / 台灣, 香港, explicit flag names and 紫荆花旗 / 紫荊花旗. `adapt.build`
always applies these additions after copying the immutable recipe and adapting the
upstream tables. A separately imported `dicts/rerime_regions` table supplies the
words and Pinyin. OpenCC Emoji alternatives are merged without removing prior
alternatives or duplicating flags. Repeating the overlay is idempotent.

The public upstream source and recipe hashes remain unchanged: the overlay is a
producer transformation, bound through `tool_digest` / `input_identity`. The source
ZIP includes the overlay data, implementation and its resulting hashes. The runtime
ZIP keeps the existing client-compatible file set and signature contract. The old
recipe Emoji qualification is historical evidence for the base resources only; it
is not relabeled as qualification of the additions. Device-specific glyph rendering
remains separate from candidate/commit correctness.

## Cadence and compatibility

The [release watcher](release-watcher.md) checks official upstream Releases daily
using conditional requests; ordinary commits, drafts and prereleases do not trigger
a dictionary update. Workflow dispatch is the only cloud build/publication entry.
Signed-channel renewal is separate from upstream data updates.

Apps show a delayed-check advisory after 72 hours without a newer upstream check.
Renewal preserves the real upstream-check timestamp rather than hiding the advisory.
Publishing never modifies installed App binaries, expires installed dictionaries or
disables offline typing.

## Verification

Local tests cover isolated upstream adaptation runs with no region words,
persistence of all additions, repeat application and preservation of existing
Emoji alternatives. Four source-free consumer cases select and commit 🇹🇼 / 🇭🇰 with
simplified and traditional settings; the publisher shares the consumer's case list.
