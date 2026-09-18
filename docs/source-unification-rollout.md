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

Pending real server-to-cloud round trip. Update this section with observed results.
