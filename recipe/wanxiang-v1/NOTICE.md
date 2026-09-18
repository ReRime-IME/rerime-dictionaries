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

Symbol and word-triggered Emoji inputs come from pinned Wanxiang revision
`3e0ab702725ffeec790bce5959fdd8319fe4bf64`. `upstream-auxiliary/source-lock.json`
records the original files and hashes. Wanxiang's symbol file retains its Rime/
Squirrel attribution, and its Codex symbol data credits typst/codex. Their source
headers accompany the corresponding editable sources.

ReRime converts Wanxiang Emoji rows to OpenCC at build time, retaining the original
word followed by upstream alternatives. No Ice alias table is merged. The source
lock and iOS qualification bind the exact generated and qualified mappings. Color
Emoji is allowed for these candidates. Symbols use native glyph qualification,
exclude unsupported or actual color Emoji items, preserve source order, and retain
ReRime category/pair presentation and finite name lookup. Punctuation-only upstream
command aliases outside the native command grammar are not imported.

English table codes use ASCII lowercase for case-compatible local learning;
candidate display text and public weights remain unchanged.
