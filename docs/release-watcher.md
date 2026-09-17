# Private official-release watcher

The server performs outbound GitHub API requests. GitHub-hosted standard macOS
runners retain the existing native build, consumer validation and protected signing
key. Host addresses, login accounts, credentials and deployment receipts must never
be added to this repository, workflow inputs, run names, artifacts or public logs.

## Behavior

- Query the upstream latest official Release daily using ETag when supported.
  Ignore drafts and prereleases, including `dict-nightly`. Ordinary branch commits
  do not qualify. Cloud code resolves the tag (including annotated tags) to a commit.
- Cloud code compares the current package's upstream commit against that Release.
  A behind/diverged Release cannot roll data backward. Same/ahead Releases retain
  relevant-file identity comparison before building.
- A 15-minute systemd timer reconciles pending runs. When no work is pending and
  daily checks are not due it performs no HTTP requests. It is not a 15-minute
  upstream poll or a continuously running process.
- One atomic local state file and flock prevent overlapping dispatches. A random
  request ID is saved before POST. A timeout is reconciled against cloud run names;
  it is never assumed to mean failure to dispatch. An unresolved dispatch after
  24 hours blocks for operator review. Failed cloud runs retry after six hours,
  up to three attempts; blocked status and the systemd failure are visible privately.
- Completion is recorded only after the matching cloud run succeeds. A no-op due
  to an older official Release is successful reconciliation, not a data downgrade.
- A daily channel check requests `renew` within ten days of expiry. Cloud code
  validates the signed current channel and manifest; renewal reuses the existing
  package and preserves the last genuine upstream-check timestamp. The server's
  channel read is only advisory and does not replace signature verification.

## Credentials

Use a dedicated fine-grained GitHub token scoped to this repository, with Actions
read/write and automatically required metadata read. No contents-write permission,
SSH key, account password or dictionary signing key is needed by the watcher.
Use a finite expiry and record the renewal date in the private operations record.
The public script never prints tokens, HTTP response bodies, config or exception
messages that can contain connection details. GitHub still sees the source network
address of API connections; it is not written into the public repository.

Provision the token outside Git as `/etc/rerime-release-watch/github-token`, owned
by root with mode 0600 and parent mode 0700. systemd `LoadCredential` provides it
to the unprivileged dynamic service user. Do not put it in shell arguments, public
workflow inputs, unit environment values, or command history. Do not copy a broad
personal GitHub CLI credential to the server as a shortcut.

## Install and activate

1. Review a pinned commit and run `python3 -m unittest discover -s tests -v`.
2. Transfer only its `ops/` directory to a task-owned private staging directory.
3. As an authorized administrator, run `bash ops/install.sh FULL_COMMIT_SHA`.
   It installs a versioned code directory, current symlink and systemd units;
   it does not activate the timer or provision a credential.
4. Read-only connectivity probe:
   `python3 -I /opt/rerime-release-watch/current/release_watch.py --state /tmp/unused --probe`.
   Probe mode reads public release/channel metadata only and creates no state.
5. Provision the dedicated token privately. Start the service manually, inspect
   the redacted event, then start it again after the cloud run finishes. Confirm
   matching `last_run_id`, success and `completed_release` in private state.
6. Enable the timer with `systemctl enable --now rerime-release-watch.timer`.
7. Only after the real dispatch/completion round trip is verified, remove GitHub
   cron and automatic push triggers; retain explicit manual dispatch as recovery.

The service has no inbound listener, no root runtime, and no code auto-update.
No DNS/firewall change is required. Root is used only for scoped installation and
credential provisioning. Updates deploy another reviewed commit and change the
current symlink. Local/source privacy scans precede every public push.

## Inspect and recover

Use `systemctl status rerime-release-watch.timer rerime-release-watch.service` and
`journalctl -u rerime-release-watch.service` privately. Inspect token expiry/access
when status reports `dispatch-access-or-input`; never print the token for debugging.
A blocked state is deliberately not retried indefinitely. Stop the timer, back up
state, verify the correlated GitHub run and current channel, repair the named issue,
and clear only the resolved `blocked`/pending fields. Never mark a release completed
without verifying its run outcome. Archive private state instead of erasing history.

Rollback: stop/disable the timer and restore the prior weekly GitHub schedule.
For a code rollback, switch `current` to the previous installed commit. Preserve
public immutable releases, the signed channel and private credentials. The old
App's 72-hour advisory is a separate UI maintenance item, not a reason to invent
fresh upstream checks during renewal.

See [PLAN+TASK](release-watcher-plan.md) for rollout status and evidence.

## GitHub App authentication migration

The owner-approved target is a private organization GitHub App installed only on
`ReRime-IME/rerime-dictionaries`. Repository visibility, public Releases and anonymous
client downloads remain unchanged. App permissions are Actions read/write and
Metadata read only; webhooks and user OAuth are unnecessary.

Provision two root-owned 0600 files under the existing 0700 credential directory:

- `github-app.json`: `{"client_id":"APP_CLIENT_ID","installation_id":123}`
  (replace both placeholders with the registered App and verified installation).
- `github-app.pem`: the private RSA key downloaded from GitHub, never in Git.

Deploy the reviewed watcher code first. Stop the timer and finish any active service
run before installing `ops/github-app.conf` as
`/etc/systemd/system/rerime-release-watch.service.d/github-app.conf`. This resets
credential loading to those two files. Run `systemctl daemon-reload`, verify units,
and perform the App-authenticated dispatch/completion round trip before enabling
the timer again. Preserve existing state, package identity and prior PAT for rollback.
For a one-time authentication acceptance run, use a separate private state file and
then reconcile its run to completion; do not erase production release history.

The App private key has no automatic expiry. A short JWT is signed with system
OpenSSL; the installation token is requested with explicit repository and permission
limits, validated and cached only in process memory. Busy processes renew it before
expiry; idle ticks never sign or request tokens. A revoked/suspended App or invalid
credential fails visibly without silently reverting to a personal identity.
No key, JWT, token, raw API response or private installation metadata is logged.

Rollback: remove only the App service drop-in, reload systemd and restore the prior
reviewed code if needed. Existing personal-token credential remains available until
explicitly revoked; do not delete or revoke it as implicit cleanup.

Official contracts: [JWT signing](https://docs.github.com/en/apps/creating-github-apps/authenticating-with-a-github-app/generating-a-json-web-token-jwt-for-a-github-app),
[installation tokens](https://docs.github.com/en/apps/creating-github-apps/authenticating-with-a-github-app/generating-an-installation-access-token-for-a-github-app),
[private keys](https://docs.github.com/en/apps/creating-github-apps/authenticating-with-a-github-app/managing-private-keys-for-github-apps).
Actual activation status is in the rollout plan; code support alone is not deployment.
