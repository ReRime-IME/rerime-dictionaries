# Wanxiang source unification: remote rollout

2026-09-18. Owner authorized synchronizing the existing GitHub producer and private
server watcher after local IME-182 qualification. Preserve the public repository's
visibility, existing GitHub App credentials, signing key, immutable releases and
channel history. This authorizes the existing dictionary workflow; it does not
enable GitHub automation in the application repository.

## Execution and acceptance

1. Update producer change detection, pinned runner selection and promotion checks.
   Regression tests must cover recipe-only changes, lagging upstream releases,
   no rollback, failed-run reconciliation and unchanged-input skips.
2. Push the reviewed producer to main without rewriting history. Deploy only its
   versioned ops directory on the existing watcher host; preserve a private state
   backup and the old code target. Retain least-privilege credentials and timer.
3. Trigger through the actual service. Accept only a correlated successful cloud
   run, authenticated/anonymous published asset verification and server success
   reconciliation. A running timer or successful dispatch is insufficient.
4. Record receipts and limitations without publishing host addresses or credentials.

Rollback stops new watcher dispatches and restores the previous versioned code and
compatible workflow commit through a forward revert. Preserve signed channel and
releases; do not roll the channel backward. Failed build/promotion leaves the prior
channel in place. Existing installed and bundled dictionaries stay offline-capable.

## Independent update cadences

Chinese/English dictionary input follows official upstream Releases and exact Git
blob identities. Emoji, symbols, spelling recipe and native evidence stay pinned in
the reviewed recipe. An upstream dictionary release cannot silently change those
auxiliary resources. Updating auxiliaries requires a reviewed source lock, native
qualification, new recipe digest and corresponding App trust support.

The private watcher compares relevant producer tree blobs once daily as well as
upstream Releases. Documentation/ops-only changes do not trigger data builds.
Producer changes dispatch even when the upstream release is unchanged. The cloud
compares exact source/tool/recipe/engine identity and skips unchanged compilation.
If an official tag lags or diverges from the already published dictionary baseline,
a producer migration rebuilds that authenticated current baseline, never the older
or diverged source. A renewal alone never claims a new source qualification.

## Delivery and future incremental work

Keep a qualified, signed full dictionary bundled with every application release.
First launch/offline typing must not depend on reaching GitHub. Release acceptance
must bind descriptor/archive hashes, App recipe trust and supported OS evidence.
The new recipe is currently qualified on iOS 27 only; it does not gain iOS 26
qualification from historical packages. Old clients may require an App update.

For now users download a complete authenticated ZIP, then activate a complete
validated staging generation atomically. Their personal dictionary is separate.
This is not replacement of personal learning. Full packages remain rollback and
first-install artifacts even if a future delta transport is added.

Prioritize measured server work reduction before client patch complexity: cache
per-entry glyph results keyed by source text, conversion data, font/OS and policy;
reuse compilation only across verified identical dependencies. This is a future
proposal, not implemented cache evidence. Compiled Rime table/prism changes are not
safely modeled as appending new source rows: deletions, frequencies and indices also
change. A future delta should reconstruct exact signed target bytes in staging,
verify the full target manifest and fall back to the full ZIP if base identity or
patch verification fails. Never patch active tables in place or compile on phones.

Mainland GitHub availability remains an acknowledged unresolved distribution issue.
A possible future domestic copy is not a migration of the canonical repository and
is not approved or implemented here. If its content differs, the Owner-mentioned
regional Emoji requirement needs an explicit product/content policy, distinct signed
variant identity, tests and channel; it must not masquerade as a byte-identical mirror.
Current Taiwan/Hong Kong regional data and global channel remain unchanged.

## Rollout receipt

Verified on 2026-09-18. Main producer and deployed watcher code:
`e1ffeb764af2fe0196408523da5209813b913d8e`. All 44 local tests and workflow lint pass.
The actual server-triggered [run 35395400030](https://github.com/ReRime-IME/rerime-dictionaries/actions/runs/35395400030)
passed check, native build/14 source-free consumer cases, signing, ten anonymous
asset downloads and channel promotion. Release `wanxiang-precompiled-13-64c9c8c10524`
and channel sequence13 are live; channel commit is
`00cd34def870c2944a000d769d9f2ec3c3c248fa`.

Published archive: 41,683,912 bytes, SHA-256
`4a5ce926a65f46828bfd96d7ffe94a2605a67b6d4138e98b1472fdd18a7579f4`.
The server reconciled the exact run successfully with no pending/blocked state;
its timer remains active. A subsequent tick returned `unchanged`. An independent
check against the live signed channel returned `noop`, skipping native compilation.

Cloud glyph qualification took 259,560 ms, Rime compilation 13,365 ms, and the
native pipeline including setup 500,990 ms. These measurements support prioritizing
future glyph-cache investigation; no incremental transport or cache is claimed.

The App workspace now bundles the exact published signed bytes, with descriptor
hashes aligned. Its real native installation bridge passed 13 checks without
compilation; App/extension Debug build and built-resource identity checks passed.
This does not publish the App or qualify iOS 26. Existing clients need matching
recipe trust, and package OS qualification remains iOS 27 only.

The previous server code and private state backup remain available privately for
rollback. This document contains no host addresses or credentials.
