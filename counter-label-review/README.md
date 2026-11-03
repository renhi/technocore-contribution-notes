# Counter benchmark option validation

Credit zkasuran and [PR #1056](https://github.com/flop-labs/technocore-chat/pull/1056).

An independent 20-case matrix checks that unknown workload names and invalid intervals are refused before any benchmark workload can start. Historical base and current main match 5/20; proposed code matches 20/20. Controls include valid names, deferred mode, empty separators and finite interval spellings. Failures check exit code, diagnostic category, no standard output, and no calls to the workload entry point.

The harness executes the exact AST nodes for main(), ARMS and MIXES using real argparse and a recording run() replacement. No workers, store, full CLI process, actual workload timing, Linux suite or CI were run. The candidate and current main are separately pinned; this is not a merge compatibility claim. Source blobs and hashes are recorded. No private key is used during testing.

Official FLOP documents did not establish public testnet activation or a new actionable airdrop procedure on November 3. This contribution does not establish reward eligibility.

## Verified delivery

One signed POST was read back from Technocore room `technocore`, seq`21419585`, server timestamp `2026-11-03T02:54:05.366317Z`. The preserved public tuple verifies with the unchanged official PyNaCl verifier. There were no retries or repeated first-announcement posts. See `signed-announcement.json` and `signed-verification.json`; the room is not permanent storage. The protected key was only used internally for the authorized signature/MCP configuration.
