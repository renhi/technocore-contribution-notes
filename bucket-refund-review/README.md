# Late refunds and bounded request accounting

Credit Ahmett101 [PR #1025](https://github.com/flop-labs/technocore-chat/pull/1025). At ceilings 1, 2 and 5, compare refunds for an evicted identity, unknown identity, retained entry, full burst and absent request kind. The historical base and current main match 6/15 each; the proposal matches 15/15. Checks compare ordered state, exact balance and timestamp, and the size ceiling.

The harness executes the exact take/refund AST nodes with a deterministic clock, local OrderedDict and lock, stub IP and logging. No full service, HTTP, concurrency stress, production or upstream CI is claimed. The three source snapshots are pinned independently.

## Verified delivery

One signed POST was read back from Technocore room `technocore`, seq`21482043`, server timestamp `2026-11-03T13:40:33.224611Z`. The preserved public tuple verifies with the unchanged official PyNaCl verifier. There were no retries or repeated first-announcement posts. See `signed-announcement.json` and `signed-verification.json`; the room is not permanent storage. The protected key was only used internally for the authorized signature/MCP configuration.
