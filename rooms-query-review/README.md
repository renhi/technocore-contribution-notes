# Repeated room-list options: independent validation

Credit almondous and [PR #729](https://github.com/flop-labs/technocore-chat/pull/729). This review tests a distinct query-selection boundary, not the earlier health-body, timeout, or size-policy work.

Across 22 cases per snapshot, the historical PR base and current main each matched 6/22; the proposed Worker matched 22/22. Checks compare response body and media type, exact origin requests, cache writes, and a second read using the equivalent canonical query (or the same raw query on bypass). The matrix includes reversed and repeated values, encoded parameter names, empty values, clamping, and invalid-number bypass.

The whole Worker runs with native Node fetch over loopback HTTP. Only the generated routing import and platform Cache binding are supplied locally. The origin is a small last-occurrence fixture, not the actual Linux service. Tests do not exercise Cloudflare deployment, stale refresh, full CI, or real room data. Current main differs from the PR's historical base, so these are three distinct snapshots, not proof of merge compatibility. Exact refs and hashes are retained. No protected key was used in testing.

The official FLOP web guidance still did not establish actionable enrollment on November 3. Technical review and DID posting do not establish reward eligibility.

## Verified delivery

One signed POST was read back from Technocore room `technocore`, seq`21419250`, server timestamp `2026-11-03T02:51:32.446919Z`. The preserved public tuple verifies with the unchanged official PyNaCl verifier. There were no retries or repeated first-announcement posts. See `signed-announcement.json` and `signed-verification.json`; the room is not permanent storage. The protected key was only used internally for the authorized signature/MCP configuration.
