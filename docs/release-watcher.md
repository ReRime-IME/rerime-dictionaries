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
