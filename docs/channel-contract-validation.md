# Authenticated channel contract

The channel uses the package contract's strict JSON envelope and a distinct Ed25519
signing domain, `rerime.precompiled.channel.v1` followed by one LF and the original
canonical payload bytes. The channel schema is fixed in `contract/channel-v1.schema.json`.
`tools/channel.py` checks its release URL and time relationships in addition to schema.

The public `contract/channel-fixtures` corpus contains 23 signed positive/negative
cases. The temporary fixture signing key was discarded; its public key is only a test
fixture and must never become a production trust root. Python and the independent
Swift consumer both pass the same corpus. Client-only replay floors and bounded
transport failure/cancellation cases are additionally verified in the application
repository; no application implementation is copied here.

This checkpoint introduces the contract and local tests. A production signing key,
GitHub workflow, release attachments and live channel are introduced by the separate
publication task. Local contract success does not mean the service is live.
