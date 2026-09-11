# ReRime Wanxiang public library

Dictionary data and the full-Pinyin spelling rules come from
[amzxyz/rime-wanxiang](https://github.com/amzxyz/rime-wanxiang), under Creative
Commons Attribution 4.0 International; the upstream LICENSE is included unchanged.
The exact revision and individual source hashes are recorded in upstream-lock.json
and the package manifest. The upstream authors and dictionary contributors retain
their attribution in the distributed source files.

ReRime supplies a native mobile full-Pinyin configuration and extracts the upstream
Base full-Pinyin algebra. The package includes Chinese, English and mixed tables.
It does not include upstream Lua scripts or grammar models; its behavior is an iOS
adaptation rather than the complete upstream desktop input scheme.

OpenCC simplified-to-traditional resources retain their Apache 2.0 license in
opencc/LICENSE. Personal entries and learning are produced on the device and are
never included in this public archive.

The restored symbol routes also derive from iDvel/rime-ice `symbols_v.yaml`,
revision `fbb516b2786e4d5444383706d13c31c2e4d10c08`, under GPL-3.0-only.
Its unchanged license accompanies this archive as `LICENSE-rime-ice.txt`.
Original source: https://github.com/iDvel/rime-ice/blob/fbb516b2786e4d5444383706d13c31c2e4d10c08/symbols_v.yaml
Wanxiang symbol and Codex-name additions retain CC BY 4.0 attribution above.
ReRime filters unsupported iOS glyphs and actual color Emoji, preserves the retained
original ordering, and adds native mathematical groups and finite name-prefix aliases.
`rerime_symbols.yaml` is the complete editable, generated route source distributed
under those source notices; `ios-symbol-qualification.json` binds its exact hash.

Word-triggered Emoji and the accompanying text aliases restore the selected
iDvel/rime-ice no-Lua OpenCC resources from revision
`569ff3bc65dd4aec0a26b33c49c8bbdfa8b5fd57`, under GPL-3.0-only with the same included
`LICENSE-rime-ice.txt`. `emoji-source-lock.json` records the original hashes;
`ios-emoji-qualification.json` binds the iOS-qualified output alternatives, keeping
their original order. Color Emoji is allowed for these candidates.
Source: https://github.com/iDvel/rime-ice/tree/569ff3bc65dd4aec0a26b33c49c8bbdfa8b5fd57/opencc

English table codes use ASCII lowercase for case-compatible local learning;
candidate display text and public weights remain unchanged.
