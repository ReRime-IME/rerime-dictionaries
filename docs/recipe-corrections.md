# ReRime corrections to Wanxiang spelling rules

## Problem

The pinned recipe's `wanxiang_full_pinyin.yaml` carries upstream Wanxiang typo
derivations. One of them, `derive/([wtfghkz])ei$/$1ie/`, turns the real syllable
`tei` (忒) into the spelling `tie`. Typing a correct `tie` (铁, 贴) therefore also
matches 忒 without any correction mark. Of the 38 typo derivations it is the only
one that collides with a real syllable. The others are transpositions that
only take effect when the letters were actually swapped. They are kept, because
they are how swapped-letter typos get fixed.

## Mechanism

`tools/recipe_corrections.json` lists exact rule-line replacements. `adapt.build`
applies them to the adapted copy right after copying the locked recipe, before
upstream tables are fetched and before glyph qualification and compilation. So
the compiled `wanxiang.schema.yaml` and `wanxiang.prism.bin` carry the corrected
rules, and the on-device fuzzy Pinyin prism, which reuses the compiled algebra,
inherits them.

- The locked recipe and `locks/recipe.json` stay byte-identical. The package keeps
  the same `recipe_sha256`, so current App trust lists accept it without an App
  update.
- Repeat application is idempotent.
- If a listed rule line is neither present nor already corrected, the build fails
  with `recipe-correction-missing:<id>`. A future recipe refresh therefore cannot
  silently bring a corrected rule back or leave a stale correction behind; it
  needs review.
- Upstream Release synchronization fetches only `*.dict.yaml` and `LICENSE`, so it
  cannot reintroduce the rule. The rule could only return through a deliberate
  recipe refresh, and the check above catches that.
- `recipe-corrections-receipt.json` (data hash, corrected file hashes) goes into the
  corresponding-source archive. The tool and data change the producer tool digest,
  so the Release watcher builds and publishes a new package revision.

Current corrections:

- `tei-is-a-syllable` narrows the rule to `derive/([wfghkz])ei$/$1ie/`. After it,
  none of the typo derivations collides with a real syllable.
- `t9-rerime-script-translator` and `t9-tail-completion` (IME-545, v2 only) turn on
  ReRime's nine-key tail completion in `wanxiang_t9.schema.yaml`; see below.

A correction may name `profiles`. It then applies only to builds of those profiles
(the nine-key schema is not part of a v1 build), and within them it must apply like
any other: a missing file or rule line stops the build. A correction without
`profiles` applies to every profile.

## Nine-key tail completion (IME-545)

librime completes a short last syllable only when the digits cannot be read
entirely as whole syllables. On a phone pad they nearly always can (2, 3 and 6 are
the syllables a, e and o), so 7443 reads si'ge and never offers 是的 (shi'd…), and
5468 offers 李牧 before 今天. ReRime's App and keyboard carry their own copy of
librime 1.16.1's script translator, registered as `rerime_dual_script_translator`
from App build 63 (ReRime IME-315), which can complete the last one or two letters
anyway (ReRime IME-532). Two corrections turn it on:

- `translators:` names `rerime_dual_script_translator` in place of
  `script_translator`;
- `translator/rerime_tail_completion: true`.

An App that registers the translator but predates the key ignores the key and
behaves as before. An App without the translator (build 62, the first nine-key
build) would lose nine-key candidates, so the v2 profile's minimum App build is 63
(`locks/release.json`); such an App keeps its installed dictionary. The source-free
consumer uses librime's stock translator, so it checks that the compiled schema
names ReRime's translator once and carries the key, then types its nine-key cases
with the stock translator in its scratch copy (`t9_rerime_translator`,
`t9_tail_completion` in the consumer receipt). ReRime's `nine-key.ranking-benchmark`
measures the ranking itself.

To correct another upstream rule, add an entry with the exact `find` line
(including indentation and newline), its `replace` line, a reason and the
evidence, then run the tests.

## Verification

- `tests/test_recipe_corrections.py` covers:
  - two isolated upstream adaptation runs correct the adapted copy and leave the
    recipe untouched;
  - the nine-key corrections apply to v2 builds only, change exactly their two lines
    and add the one key, and must apply in a v2 build;
  - repeat application is idempotent;
  - a reworded or missing rule stops the build;
  - only the one rule line changes.
- The consumer tool can assert only that a candidate is present, not that one is
  absent.
