# Initial producer validation

The producer at commit `96f7afa` was built locally on macOS arm64 with Xcode 26.6
(build 17F113) and iOS 26.5 Simulator. The upstream input was
`1dab297c7abeee199dc2866f7994d5dba5fe0844`; the recipe digest was
`c21dbaec7e43052ea95de8729e59ed3bc80902413cb6d8f57bd2bbc94dbe98d8`.

Two complete adaptation, glyph qualification, compilation and packaging runs
produced identical manifest payloads, unsigned runtime archives, corresponding
source archives, qualification receipts, build receipts and upstream locks.

- Source rows checked: 2,289,663; excluded by the original/traditional glyph policy: 16,677.
- Runtime files: 27; unsigned runtime ZIP: 41,673,567 bytes.
- Runtime ZIP SHA256: `d8ac3ebf219b366a113d8d86a35427d38d37cb39dd9330fd3724af2054a07229`.
- Editable source ZIP SHA256: `e6128be90c7fe42323e76628b1a3c5eaf7c0059fd511c2bd331a46e1deda76fd`.
- Manifest payload SHA256: `6708b2af9f36801638dc345658a282081c8ccd66cdba940755d81ad954d587db`.

The separate source-free consumer passed Chinese, English, mixed-code,
traditional, personal-entry and personal-entry-edit cases. Its source makes no
public deployment call. Public file hashes stayed unchanged, and removing a table
caused a rejection without regenerating the file.

Five public unit-test methods cover the data parser, normalization, bounded ZIP
layout and 31 common signed contract cases. The same 31 cases were consumed by the
client's separate Swift verifier with matching results. The test signing keys are
not production trust roots.

This is local producer evidence. It does not establish GitHub runner execution,
scheduled publication, public download availability or physical-device behavior.
Those are separate distribution and release gates.
