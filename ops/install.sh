#!/usr/bin/env bash
# Run from the reviewed ops directory as an authorized administrator.
# Installs code/units only. Credential provisioning and activation are separate.
set -euo pipefail
[[ $(id -u) == 0 ]] || { echo 'Administrator required' >&2; exit 1; }
[[ $# == 1 && $1 =~ ^[0-9a-f]{40}$ ]] || { echo 'Expected full source commit' >&2; exit 1; }
cd -- "$(dirname -- "$0")"
release_dir="/opt/rerime-release-watch/releases/$1"
[[ ! -e "$release_dir" ]] || { echo 'Release already exists; inspect before replacing' >&2; exit 1; }
install -d -m 0755 "$release_dir"
install -m 0644 release_watch.py "$release_dir/release_watch.py"
install -d -m 0700 /etc/rerime-release-watch
install -m 0644 rerime-release-watch.service /etc/systemd/system/
install -m 0644 rerime-release-watch.timer /etc/systemd/system/
ln -sfn "$release_dir" /opt/rerime-release-watch/current
systemctl daemon-reload
systemd-analyze verify /etc/systemd/system/rerime-release-watch.service /etc/systemd/system/rerime-release-watch.timer
printf 'Installed; timer activation is a separate verified cutover step.\n'
