# 小鹤双拼 profile (v4)

ReRime IME-554 (task A1 of the IME-547 双拼 plan). Profile
`wanxiang-ios-arm64-rime1161-v4` is profile v2 plus one schema, `wanxiang_xiaohe`
(小鹤双拼). The schema mounts the shared `wanxiang` dictionary under its own prism, as
`wanxiang_t9` does. The package therefore gains exactly two runtime files,
`build/wanxiang_xiaohe.schema.yaml` and `build/wanxiang_xiaohe.prism.bin`
(`contract/compatibility-rime1161-v4.json`).

v3 was ReRime's retired grammar profile (IME-350); its ID is never reused. v2 stays
as it is: its recipe hash, which installed Apps trust, does not change, and an App
that does not know v4 never asks for the v4 channel.

## The schema

`recipe/wanxiang-v1/wanxiang_xiaohe.schema.yaml`, selected only by `locks/recipe-v4.json`:

- **Speller.** The `base/小鹤双拼` block of upstream `wanxiang_algebra.yaml` at the pinned
  recipe revision (`64c9c8c1`, `locks/source.json`), rule for rule, with three marked
  ReRime changes in its last rules:
  - upstream's own commented-out 简拼 rule `abbrev/^([a-z]).+$/$1/` is on, so a lone
    initial works alone and in the middle of an input (`dyg` 第一个, `jbttmqi` 今天天气,
    `uim` 失眠);
  - the tone-digit spellings are left out: `derive/^(..)(\d)$/$1/` becomes `xform`, and
    `derive/^(.).+(\d)$/$1$2/` is dropped. The alphabet has no digits, so they could never be
    typed. The prism is 58,176 bytes (upstream 小鹤 without 简拼: 107,344; with 简拼 and
    the tone digits: 132,496).

  `v` and `V` are initials (zh = v). There are no 26-key typo derivations and no Lua.
- **Two keys are one character.** Two lone initials are always also a full 小鹤 code
  (`ud` is 晒 shai, not 是的). When the whole input reads as full codes, librime 1.16.1's
  syllabifier drops every abbreviated path (`algo/syllabifier.cc`, "remove disqualified
  syllables … when there is a path of more favored type"), so `ud` offers 晒. 简拼 therefore
  needs three or more keys, or an input that does not read as full codes. A `fuzz/` rule
  instead of `abbrev/` would keep the 简拼 path (fuzzy spellings survive that pruning, with
  the same log 0.5 penalty), but measured on the 500 highest-weight single characters, it
  puts a two-character phrase first for 58 of their 269 two-key codes (`vg` 这个 before 正,
  `tm` 他们 before 天). Character top-3 falls from 430 to 379. Typing one character with two
  keys is the core of 双拼, so the schema keeps `abbrev/`, as rime-ice's 小鹤 schema does.
- **Translator.** The same settings as 全拼 (`initial_quality`, completion, sentence,
  learning in the shared `wanxiang` user dictionary). `prism: wanxiang_xiaohe`. Each
  candidate comment carries its toneless full Pinyin (`spelling_hints: 50`, the nine-key
  comment format), for example `shi de` for `uide`. ReRime's composition line reads it
  (IME-547 task C). There is no `preedit_format`, so the raw input stays the typed codes.
- **Grammar.** `translators:` names `rerime_dual_script_translator@translator` and the
  schema ends with the `grammar:` block. Both are exactly what ReRime's App writes when it
  opts 全拼 in (`GrammarSecondCandidateStaging`), so the App's opt-in and the
  `shuangpin.benchmark` opt-in both accept the schema unchanged. ReRime's translator
  turns the grammar sentence off when the `rerime-grammar` model is absent or the
  sentence option is off. App builds without the translator would lose candidates, so
  v4's minimum App build is 63, the first build that registers it (`locks/release.json`).
- **Personal words.** `table_translator@personal_xiaohe` reads `rerime_personal_xiaohe`
  (joined 小鹤 codes, written by the App like `rerime_personal_t9`; IME-547 task D).
- **Everything else** (switches, English and mixed tables, emoji, traditional, punctuation)
  is the 全拼 schema's.
- **Schema list.** The v4-only correction `v4-deploys-xiaohe` adds `wanxiang_xiaohe` to
  `default.custom.yaml`, so the build compiles its prism and `build/default.yaml` lists it.
  With the schema listed, a session that last used 小鹤 opens it directly instead of
  building 全拼 first (IME-548).

## Symbol trigger: Shift+V

ReRime's 全拼 opens a symbol code with `v` (`vfh` ©, `vjt` →, `v1` ①) or with `/`. In
小鹤 `v` is the zh initial, so `vi` must read 知 and `vd` 债. 小鹤 opens the same codes
with **Shift+V**: `Vjt` →, `Vfh` ©, `V1` ①. `/` keeps working (`/jt` →).

How other setups solve this:

- Rime's default symbol table and upstream Wanxiang use `/` in every scheme.
- rime-ice, whose `v` codes ReRime's table follows, uses uppercase `V` in its
  双拼 schemas (`symbols_caps_v.yaml`, recognizer `^V…`) and lowercase `v` in 全拼.

Which keys are free in 小鹤:

- No lowercase letter is free. Every letter starts a 小鹤 code: `v`, `i` and `u` are
  zh, ch and sh, and `a`, `o` and `e` start the zero-initial syllables (`aa`, `oo`,
  `ee`, `ai`, `ou`, `er` …). With lone-initial 简拼 on, any letter pair also parses as
  two syllables.
- Uppercase letters start no 小鹤 code. ReRime's keyboard already sends Shift+letter to
  Rime as an uppercase letter in Chinese mode.
- Non-letters (`/`, `;`, `` ` ``) are free in the schema, but they sit on the 123 page,
  and ReRime's keyboard commits them directly instead of sending them to Rime.

Choice: **`V` (Shift+V)**. It stays on the letter page, uses the same key as 全拼 (the
same codes, one Shift), and needs no keyboard change. It matches rime-ice's 双拼 convention.
The cost: a capitalised English word that is exactly `V` plus a symbol code (for example
`Vue`) goes to the symbol list, as `vue` already does in 全拼. Other `V…` input still
reaches the speller and the English tables.

Rejected:

- `/` alone: needs a page switch, and the keyboard would have to stop committing `/`
  directly, which changes literal `/` (dates, paths). It is kept as a second route.
- `;`, `'` and `` ` ``: also off the letter page. `'` is the syllable delimiter.
- A lowercase letter or letter pair (for example `oo` or `vv`): all are valid 小鹤 codes.
- Dropping symbol codes in 小鹤: the Space-hold symbol browser stays, but the codes are
  an existing 全拼 feature that 小鹤 users would lose.

### Mechanism

`tools/xiaohe_symbols.py` runs in v4 builds right after the recipe is copied. It writes
`rerime_xiaohe_symbols.yaml` into the adapted copy:

- `symbols:` holds every `/` entry of `rerime_symbols.yaml` unchanged, and every `v` entry
  with `v` replaced by `V`;
- `patterns/punct` is the recognizer pattern of `rerime_symbol_recognizer.yaml`, also with
  `v` replaced by `V`.

The 全拼 `abc` pattern is not copied, because it only exists to let non-code `v` input
reach the speller. Nothing is copied by hand, so the table follows the qualified symbol
catalog. A source whose shape changed (an entry that does not parse, a `v` code without
its `/` twin, a changed pattern) stops the build. The schema compiles the table in, like
全拼's, so the generated file is not a runtime file. The tool ships in the
corresponding-source archive with the other build tools.

## Verification

- `tests/test_xiaohe_profile.py`: the v4 inventory and contract, profile selection and
  manifest binding, the App floor, the adapter (v4-only files), the prism format check, the
  speller (upstream rules, `v`/`V` initials, 简拼), the translator and grammar opt-in form,
  parity with the 全拼 schema, the symbol generator (every code moved, `/` kept,
  `vi`/`vjt` left to the speller, a changed source stops the build), and that the consumer
  cases are real 小鹤 codes.
- The consumer (`tools/consumer_test.py`, v4 cases `xh-*`): full codes, a short last code,
  lone initials alone and mid-input, two keys as one character (`vg` 正), zh = v (`vi` 知),
  `Vjt` and `/jt` →, traditional,
  the `shi de` comment, the `rerime_personal_xiaohe` companion table, and a missing
  `wanxiang_xiaohe` prism must fail. The stock CLI types through librime's own translator
  in its scratch copy, after checking that the compiled schema names ReRime's translator
  once in the App's form and carries the grammar block.
- Ranking, the grammar sentence and speed are measured in ReRime with
  `shuangpin.benchmark --runtime <built> --xiaohe-schema wanxiang_xiaohe`.
