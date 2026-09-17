# Publication and recovery

`Public dictionaries` accepts explicit workflow dispatches. The private watcher
checks official upstream Releases daily and dispatches only a newly observed
Release, a bounded retry, or signed-channel renewal near expiry. GitHub cron and
automatic producer-push triggers are disabled. See [watcher operations](release-watcher.md)
for private service inspection, credential renewal and recovery.

An unchanged input skips native compilation. The signed channel expires after
30 days; the watcher requests renewal within ten days of expiry without rebuilding
the existing package. Renewal preserves the last genuine upstream-check timestamp.
Older clients may consequently show their 72-hour freshness advisory during a quiet
upstream period; it does not invalidate installed dictionaries. Server polling does
not by itself update signed public metadata or claim a new dictionary release.

All jobs use the standard public-repository `macos-26` runner. The producer requires
Xcode 26.6 (17F113), arm64 and an existing iOS 26.5 iPhone 17 Pro Simulator. An image
change that removes this combination fails qualification; it does not silently
approve another OS. Check/build jobs have read-only repository access. Only the
main-only `dictionary-release` environment provides the signing secret to the final
promotion step. No pull-request or fork event can publish.

The publisher creates a draft with a complete asset allowlist, verifies uploaded
sizes/digests, publishes an immutable release, downloads every asset anonymously,
and then advances the signed channel. Runtime and corresponding source archives,
manifest, qualification, consumer, resource and build receipts are retained together.
The channel branch is independent of main and advances without force updates.

For a failed check or build, inspect its failing stage, correct the named input or
tool issue, and dispatch again. The previous channel remains usable until its signed
expiry; installed dictionaries remain offline. A failed promotion can be rerun from
the same run while its check plan is under four hours old and artifacts remain
available (seven-day artifact retention). Existing assets must match exactly; the
publisher never overwrites them. A fresh run refuses to conceal a published release
without an initial channel. If that occurs after the plan expires, inspect the
immutable release and receipts and prepare an explicitly reviewed recovery; do not
delete the release or fabricate a successful check timestamp.

For a channel race, reread the current authentic channel and start a fresh check.
After CDN readback timeout, inspect the recorded channel commit before retrying:
publication may already have succeeded. Do not force the branch backward. Restoring
older public content requires a new, higher package revision and a higher channel
sequence, or the client's local last-good recovery contract.

The dedicated Ed25519 key is kept outside the repository and in the restricted
GitHub environment. Only its public key is committed under `keys/`. Rotation requires
an App trust update before using the new key; remote metadata cannot introduce a
new trust root. Stop the workflow to pause future promotion while preserving all
published assets and current client installations.

A configured timer or HTTP dispatch response is not proof of completion. Record
the correlated successful cloud run and server reconciliation separately. The
initial server round trip is documented in the [rollout plan](release-watcher-plan.md).
