# Publication and recovery

`Public dictionaries` resolves the latest official Release and checks its relevant
dictionary blobs weekly on Monday at
08:17 UTC, on manual dispatch, and after producer changes on main. GitHub can delay
or omit scheduled runs. The signed channel carries the last successful upstream
check; older clients report a delayed check after 72 hours, which can now occur during
a normal weekly interval; this advisory does not invalidate installed dictionaries.
The signed channel expires after 30 days, so weekly refresh remains within its lifetime. An unchanged input skips native
compilation, with authenticated check metadata refreshed at most once per day.

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

A configured schedule is not evidence of a scheduled run. The first real manual
build, anonymous release/channel verification and subsequent schedule receipts must
be recorded separately before making distribution claims.
