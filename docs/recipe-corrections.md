# ReRime corrections to Wanxiang spelling rules

2026-09-24 (America/Vancouver). Requested by the owner after the ReRime app's
IME-231I audit.

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

Current correction: `tei-is-a-syllable` narrows the rule to
`derive/([wfghkz])ei$/$1ie/`. Re-running the app repository's
`tools/input-intelligence/audit_typo_derivations.py` on the corrected file reports
0 real-syllable collisions (previously 1) and the same 28 swapped-letter derivations
that split into real syllables.

To correct another upstream rule, add an entry with the exact `find` line
(including indentation and newline), its `replace` line, a reason and the
evidence, then run the tests.

## Verification

- `tests/test_recipe_corrections.py` covers:
  - two isolated upstream adaptation runs correct the adapted copy and leave the
    recipe untouched;
  - repeat application is idempotent;
  - a reworded or missing rule stops the build;
  - only the one rule line changes.
- The full local suite passes (51 tests).
- Not yet done: a native build and consumer run on this change, and publication.
  The existing consumer tool can assert only that a candidate is present, not that
  one is absent.
