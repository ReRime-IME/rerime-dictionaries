# Taiwan and Hong Kong word-triggered flags

2026-09-16 (America/Vancouver).

## Scope and implementation

The owner requested Taiwan and Hong Kong words/flags that survive upstream Wanxiang
synchronization, and a weekly or fortnightly update cadence. The base recipe already
contains `香港 → 🇭🇰`; it lacks a Taiwan flag mapping. This does not establish why
any particular installed device failed to display Hong Kong.

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

Scheduled checks run Monday at 08:17 UTC, rather than hourly. Manual dispatch and
relevant producer changes on main still run. Unchanged input avoids compilation;
the 30-day signed-channel lifetime accommodates weekly refresh.

Existing App versions show a delayed-check advisory after 72 hours. With weekly
checks that message can occur during a normal interval. This repository change does
not update installed App binaries or their UI threshold. It does not expire an
installed dictionary or disable offline typing. Track the advisory threshold in the
next App maintenance update; do not falsify the upstream-check timestamp to hide it.

## Verification

- 17 local tests pass, including two isolated upstream adaptation runs with no region
  words, persistence of all additions, repeat application, preserving existing Emoji
  alternatives, and the weekly workflow contract.
- Native build run [35179603130](https://github.com/ReRime-IME/rerime-dictionaries/actions/runs/35179603130)
  compiled the dictionary and passed 11 source-free consumer cases. The four added
  cases select and commit 🇹🇼 / 🇭🇰 using simplified and traditional settings.
  Original Chinese/English/mixed/personal cases and missing-table rejection passed.
- That run's publication was correctly blocked because the publisher still expected
  the old seven-case list. Commit `2a18cbc` uses one shared case definition for the
  consumer and publisher. No release/channel mutation occurred in the failed run.
- ZIP inspection confirms the runtime Emoji mappings and all overlay source/receipt
  files are present in their respective archives.
- The downloaded real unsigned artifact passes the corrected publication validator.
  Removing any one of the four flag case results causes `consumer-cases` rejection.
- Final publication uses a fresh build of the corrected source; see the release
  receipt below. No installed personal dictionaries or user input history were read
  or modified by this task.

## Published release receipt

- Producer source: `2a18cbcf3614a520483be4fc00dd95bf5c893242`.
- [Successful workflow 35180251020](https://github.com/ReRime-IME/rerime-dictionaries/actions/runs/35180251020): check, build and promote all passed.
- [Published package revision 11](https://github.com/ReRime-IME/rerime-dictionaries/releases/tag/wanxiang-precompiled-11-7718bc30d435).
- All 11 native consumer cases passed again, including all four flag cases and
  personal dictionary edit preservation. Ten published assets were downloaded
  anonymously and verified before channel promotion.
- Authenticated channel sequence: `11`.
- Channel commit: `bcc2b7193b1ea2d8ba81913a6674339d12d92ad0`.
- Runtime ZIP SHA-256: `6397a76f77f14ad741c0f26da07a45e73b0dbdd85c725b91c648d1f500a7efce`.
- Publication verified at 2026-09-17 04:11:27 UTC (2026-09-16 local).

This proves the published data and native candidate/commit paths. It does not claim
that an already installed App has downloaded the update or that all regional OS
configurations render the flags identically.
