# Mirrors and retention

GitHub remains the origin: `Public dictionaries` builds, signs and publishes there.
`Dictionary mirrors` (`.github/workflows/mirror.yml`, `mirror/`) then copies the
files the App downloads to two mirrors and prunes old releases. It runs after every
successful `Public dictionaries` run, including channel renewals, and on manual dispatch.

Mirrors are untrusted transport. The App verifies the channel signature, the
manifest signature and every hash, so a mirror can only withhold, delay or serve an
older still-valid signed channel. The mirror job has no access to the signing key.

| Mirror | Channel file | Package files |
| --- | --- | --- |
| Cloudflare R2, `dict.rerime.com` | `https://dict.rerime.com/channels/<profile>.json` | `https://dict.rerime.com/releases/<release>/<file>` |
| CNB, `cnb.cool/ReRime-IME/rerime-dictionaries` | `https://cnb.cool/ReRime-IME/rerime-dictionaries/-/git/raw/channel/channels/<profile>.json` | `https://cnb.cool/ReRime-IME/rerime-dictionaries/-/releases/download/<release>/<file>` (redirects to `asset.cnb.cool`) |

Only `ReRime-<release>.zip`, `manifest.json` and, when published, `delta.json` and
`delta.bin` are mirrored. Source archives, receipts and licenses stay on GitHub.
The signed channel still names the GitHub package URL; clients build mirror URLs
from the release identity and never take a host from a downloaded document.

For each profile the job downloads the files from GitHub, checks them against
`release-files.json` and the channel's hashes, uploads them, reads them back
anonymously and only then replaces that mirror's channel file. A mirror that fails
is reported and retried on the next run; it never blocks GitHub or the other mirror.

## Retention

`ops/retention.json` keeps the newest `keep_per_profile` (5) published releases of
each profile on GitHub and both mirrors. A release a channel points at is always
kept, as are `pinned_releases`: list there the release bundled in the shipping App,
so its source archive and receipts stay available. Drafts and tags that are not
`wanxiang-precompiled-<revision>-<commit>` are never touched. Pruning runs only
after every profile was copied to every mirror, refuses to delete more than 12
releases at once, and deletes the GitHub release and then its tag. A deleted tag
name cannot be reused; revisions only increase, so it never needs to be.

A client more than five releases behind downloads the full current package.

```sh
gh workflow run mirror.yml --repo ReRime-IME/rerime-dictionaries --ref main -f retention=dry-run
gh workflow run mirror.yml --repo ReRime-IME/rerime-dictionaries --ref main -f retention=apply
```

`dry-run` copies and prints the retention plan without deleting. Manual dispatch
defaults to `dry-run`; runs that follow a publication apply the plan.

## Configuration

Repository secrets `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY` (object read and write
on the `rerime-dictionaries` bucket only) and `CNB_TOKEN` (that one repository,
`repo-code` and `repo-release` write); repository variable `R2_ACCOUNT_ID`.
`mirror/` and `ops/` are outside the producer input identity, so changing them does
not rebuild dictionaries.
