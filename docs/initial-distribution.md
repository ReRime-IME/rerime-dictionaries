# Initial signed distribution

The standard public macos-26 workflow at producer commit
`04be4fe` completed on 2026-09-11. The
[manual run](https://github.com/Nongfsq/rerime-dictionaries/actions/runs/34589812884)
produced immutable release
[wanxiang-precompiled-1-1dab297c7abe](https://github.com/Nongfsq/rerime-dictionaries/releases/tag/wanxiang-precompiled-1-1dab297c7abe).

The runtime archive is 41,676,878 bytes, SHA-256
`903e2103b54c9e21eab29edd3053504c4ae2cbe693770f77355b54d9ed947547`.
The signed manifest SHA-256 is
`86297059cdb02b2c6e25c69150139c4372c3c07a899e374b08a6329810906945`.
All ten release attachments were anonymously downloaded and verified before
channel sequence 1 was promoted in commit
`fd918d87f2c756d05042919f997729836c683c15`.

The producer checked 2,289,663 public source rows. Native qualification took
262,463 ms with peak resident memory 123,731,968 bytes; compilation took
13,228 ms with peak resident memory 1,354,235,904 bytes. These are runner
process measurements, not physical iPhone install latency. The separate source-free
consumer passed seven cases and missing-table rejection without deployment.

A second [manual check](https://github.com/Nongfsq/rerime-dictionaries/actions/runs/34590902668)
confirmed identical relevant inputs, selected `noop`, and skipped build and promotion.
The channel and existing immutable assets were unchanged. These are actual manual
receipts; the configured hourly schedule requires a separate scheduled-event receipt.

The profile remains limited to the documented engine/recipe/iOS 26.5 compatibility
set and clients that explicitly embed this publisher's public key. No physical-device
or universal-OS qualification is implied.
