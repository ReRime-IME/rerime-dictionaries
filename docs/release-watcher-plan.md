# Private release watcher — PLAN+TASK

Plan identity: DRS-20260916. Revision: 5. Readiness: READY.

## Approved decisions and current reality

The owner authorizes implementation and deployment of a private server watcher:
only official upstream Releases trigger synchronization; public GitHub standard
macOS runners retain compilation, iOS qualification, signing and publication.
Server identities, addresses, credentials and operational receipts stay outside
this public repository. No inbound port, DNS change, root-running daemon or signing
key transfer is required. A narrowly scoped Actions-write credential is provisioned
privately. Access metadata is not public evidence.

Pre-migration baseline: weekly cron and producer pushes; source followed branch HEAD.
Existing signed channel expires in 30 days. Native build, immutable assets, signature
and consumer gates remain intact. Existing public package may be newer than the
latest stable upstream tag: compare ancestry and never automatically downgrade.
Sources: owner's approved discussion; dictionary.yml; check_release.py; promote.py;
docs/release-recovery.md. No earlier DRS task IDs exist in the repository.

UI/client work: N/A; no App binary or installed user dictionary changes.
Product/architecture decisions are supplied above; no additional framework required.

## Tasks

### DRS-001 — Release-bound producer and maintenance
- Status: done
- Depends on: none
- Files: tools/upstream_release.py (new), tools/check_release.py, tools/promote.py,
  .github/workflows/dictionary.yml, tests/test_release_trigger.py (new).
- Change: Resolve published non-prerelease tags to exact commits; validate ancestry;
  separate release checks from channel-only renewal; accept bounded workflow inputs.
  Introduce dispatch support before removing cron or push triggers.
- Acceptance: Ordinary commits cannot advance release mode; older/diverged releases
  cannot replace current data; renewal preserves data identity and last upstream
  check time; existing signatures and all consumer gates remain required.
- Validation: unittest discovery; mock release/tag/compare failures; actual read-only
  upstream selection; cloud manual dispatch proving no rollback.
- Parallelism: sequential; owns shared producer files.
- Rollback: previous workflow commit; leave immutable public assets/channel intact.
- Observability: public release IDs, commit hashes, mode and reason only.

### DRS-002 — Private watcher and durable handoff
- Status: done
- Depends on: DRS-001
- Files: ops/release_watch.py, ops/rerime-release-watch.service,
  ops/rerime-release-watch.timer (new),
  tests/test_release_watch.py (new).
- Change: Standard-library watcher checks official Releases daily with conditional
  requests; stores ETag/release/attempt/run state atomically; tracks dispatched runs
  by random public correlation ID; confirms run success before marking completion.
  Uses isolated signed-channel renewal dispatch near expiry. Timer wakes every
  15 minutes only to reconcile pending work; ordinary release GET remains daily.
- Acceptance: No secret/private metadata in dispatch, logs or public files; one
  in-flight task, flock exclusion, bounded retry/backoff, ambiguous dispatch retained
  for reconciliation, no publication success inferred from HTTP 204. Failed run is
  visible locally and retryable; offline days don't lose pending identity.
- Validation: unit tests with fake HTTP, clock and state; no-change/release/failure/
  ambiguous dispatch/expiry/restart cases; syntax and systemd verification.
- Parallelism: sequential.
- Rollback: disable watcher timer; preserve private state and existing public channel.
- Observability: redacted status codes and opaque request/run IDs; no response bodies.

### DRS-003 — Deployment and schedule cutover
- Status: done
- Depends on: DRS-001, DRS-002
- Files: ops/install.sh (new); docs/release-watcher.md (new); README.md;
  .github/workflows/dictionary.yml; private deployment receipt outside Git.
- Change: Verify authorized host identity and sudo; deploy pinned code under /opt,
  unprivileged service with protected credential and persistent state; validate
  read-only poll and authorized dispatch. Remove GitHub schedule/push trigger only
  after server dispatch and completion reconciliation are proven.
- Acceptance: Daily release poll active; no duplicate trigger source; self-contained
  rollback instructions; public diff contains no host, user, grant, token or path
  identity; no wider personal GitHub token copied to server.
- Validation: local full tests, privilege/file permissions, systemd-analyze verify,
  actual server service run and cloud result, sanitized public receipt and Git status.
- Parallelism: sequential; credential provisioning may proceed during code work.
- Rollback: stop timer and restore previous GitHub weekly schedule. Do not revoke
  unrelated credentials or change shared host/firewall services.

## Rollout and security boundaries

Use expand → deploy → verify → switch triggers. Server config/credential/state are
private; examples use placeholders. Workflow never trusts requested SHA: resolve
release through GitHub and compare authenticated current package ancestry. Renewal
verifies current signed channel/manifest and keeps last true upstream check time.
Public code is manually deployed at a verified commit; no pull-and-execute remote
upstream scripts. Signing remains in existing GitHub protected environment.

Credential availability gates activation, not independent code/tests. The plan
location and normal scoped implementation are authorized by the user's explicit
PLAN+TASK + execution request. No additional approval gate is introduced.

PLAN_GATE: PASS
PLAN_TASKS_STATUS: READY

## Execution evidence

- Local release selection against current public state returned `release-behind`,
  mode `noop`, preserving package 11. Renewal preflight returned `noop` because
  the current channel is not near expiry. Five release-bound producer tests pass.

- 28 local test methods pass; Python compilation and shell syntax checks pass.
- Cloud producer run [35183553706](https://github.com/ReRime-IME/rerime-dictionaries/actions/runs/35183553706)
  succeeded after switching to official-release selection.
- Watcher commit `560645e958413d37b3c577a260b8e41ab6bfc368` installed on the
  authorized private host; installed script SHA-256 matches the reviewed source.
  systemd unit validation and public release/channel connectivity probe passed.
- Dedicated single-repository Actions-write credential provisioned privately; root
  0600 credential, 0700 parent, DynamicUser and strict service sandbox verified.
- Server-triggered cloud run [35184339643](https://github.com/ReRime-IME/rerime-dictionaries/actions/runs/35184339643)
  passed; check succeeded and build/promotion were correctly skipped for an older
  upstream Release. Server reconciled success and recorded the completed release.
- Timer enabled and active. GitHub cron and producer-push triggers removed after
  successful reconciliation; manual dispatch remains available.
- Actual host, access metadata, credential expiry and deployment receipt remain
  private outside Git. This verifies dispatch and no-rollback behavior, not a new
  package build; earlier full package qualification evidence remains separate.

## Approved GitHub App migration

Owner authorizes a private organization GitHub App identity while the dictionary
repository, signed channel and downloads stay public. No client or data migration.
The server retains the App private key; short-lived installation tokens are minted
on demand and never persisted. Personal-token operation remains the rollout fallback.

### DRS-004 — Automatic installation authentication
- Status: done — 35 tests pass; activation tracked separately in DRS-005
- Depends on: DRS-003
- Files: ops/release_watch.py, tests/test_release_watch_auth.py (new),
  ops/github-app.conf (new), docs/release-watcher.md, README.md.
- Change: Add lazy RS256 App authentication using system OpenSSL, exact installation
  endpoint and repository/permission narrowing. Protected systemd credentials carry
  App configuration and key. No network requests or signing on idle ticks.
- Acceptance: Token renewal is automatic; tokens/keys never enter state or logs;
  invalid App configuration fails closed without falling back to a personal token;
  existing dispatch/reconciliation and public downloads remain unchanged.
- Validation: Real temporary RSA signature verification; mocked scope/expiry/refresh,
  failed exchange and no-idle-auth tests; full unittest discovery; syntax checks.
- Parallelism: sequential; owns authentication and deployment configuration.
- Rollback: remove App drop-in and restart with existing protected personal token.
- Observability: sanitized authentication failure only; no JWT/key/response body.

### DRS-005 — Register, install and verify App cutover
- Status: in progress — registration form prepared, final owner confirmation pending
- Depends on: DRS-004
- Files: docs/release-watcher-plan.md; private deployment receipt outside Git.
- Change: Register private organization App, Actions write and Metadata read only;
  install on dictionary repository only, securely provision key and config; deploy
  pinned code; verify App-authenticated cloud dispatch and completed reconciliation.
- Acceptance: Timer enabled on App identity; same public repository/downloads;
  no personal-token dependency, private host/credentials absent from public artifacts.
- Validation: Installation scope, file permissions, actual cloud actor/run success,
  server reconciliation and idle check. No duplicate dispatch after restart.
- Parallelism: sequential; owner interaction only for required credential/UI steps.
- Rollback: retain prior deployed version and protected PAT; restore old configuration
  on failed migration. Do not revoke credentials without explicit owner instruction.
