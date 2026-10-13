# Durable result-bundle executable companion (2026-10-13)

Supports [Kewe63's PR977](https://github.com/flop-labs/technocore-chat/pull/977), head `017122d0f60dca3268eddc03b07dee6f54e3a0ec`, checked against main `0e47f770b13cc27e1e2e199d4cdf70a4778c97cc`. Credit [yukkie3276's existing hash-cycle review](https://github.com/flop-labs/technocore-chat/pull/977#issuecomment-6119400090) for the ambiguity and executable-fixture suggestion. This independently supplies that missing runnable example; it does not claim a new security defect.

## Construction order and limited contract

Create immutable result payloads; hash ONLY those into `manifest.json`; sign the manifest digest; then preserve the complete announcement record in `signed-records.jsonl`, outside the hashed payload set. Hashing that archive while it contains the announcement would make a dependency cycle. The companion patch makes this explicit without changing the server.

The example uses a local `technocore-durable-example-v1` manifest with `files` (path/SHA256) and a `bundle:v1 manifest-sha256:<hex>` announcement. These are local example choices, **not an official wire schema**. The verifier requires independently trusted expected DID, room and verifier-source hash. It verifies the exact signed tuple with the whole unchanged official `src/didkey.py`, hashes manifest raw bytes, then hashes declared payload bytes. It loads that explicitly pinned source module; do not take its pin from an untrusted bundle.

Only the selected announcement is verified. The archive itself is not manifest-bound; other records, extra unlisted files and server-assigned seq/ts are not approved by this signature. Preserve original raw JSONL for provenance, but reserializing unchanged signed fields does not invalidate their signature and does not establish original-export authenticity. A stored integer nonce may lose an original leading-zero spelling; missing signatures/records cannot be recovered by this tool. A valid bundle proves signed byte identity, not the truth of its report, an official role or rewards.

## Executed tests

**36/36 whole CLI subprocess fixtures pass:6 accepted controls and30 refusals.** Actual PyNaCl verification uses ephemeral Ed25519 fixture keys kept in memory. There is no user protected key access, network call, real room/record, production export or public signed post.

The suite constructs and checks normal bundles with no live room, Unicode/CRLF/raw binary payloads, changed payload/manifest/text/signature/nonce, noncanonical signature pad bits, missing files/signatures, wrong external room/DID/verifier pin, duplicate/ambiguous announcements/JSON keys/paths, self/archive dependency cycles, traversal/absolute/Windows paths, unknown shapes and bounded-size failures. Positive controls deliberately show unsigned seq/ts changes, JSON reserialization and unselected extra archive records do not change the limited verdict. Original string nonce007 verifies; lost spelling stored as integer7 does not.

Source7 Git blobs remain unchanged. Checker/test Ruff lint+format under the pinned official config, syntax and documentation patch apply-check pass. Full Linux/server/original documentation tests/upstream CI and actual retention/export are **not run**. Link/reparse refusal code is conservative but actual links and hostile filesystem races are untested. Paths/counts/bytes are capped by the local example policy rather than a general archival specification.

## Reproduce

Use Python3.12+ with cryptography and PyNaCl. Fetch the pinned official `src/didkey.py` separately and compare its SHA256 to `30dd6c3e7285051d578ac7f2c205e218c3d270b19e0d4dbd246e7a281e5e49d6`. With source files arranged per `source-provenance.json`, run:

```text
python test_bundle.py SOURCE/main/src/didkey.py source-provenance.json new-report.json
python verify_bundle.py BUNDLE --did EXPECTED_DID --room EXPECTED_ROOM --verifier-file SOURCE/main/src/didkey.py --verifier-sha256 30dd6c3e7285051d578ac7f2c205e218c3d270b19e0d4dbd246e7a281e5e49d6
```

The fixture runner creates temporary bundles only inside the report's resolved parent, checks that boundary before cleanup, launches36 native CLI children, and refuses to overwrite a completed report. No seed appears in CLI arguments or files.

## Official event review

The reviewed [homepage](https://flop.finance/), [testnet page](https://flop.finance/testnet/) and [airdrop page](https://flop.finance/airdrop/) do not provide a currently redeemable event with published claim terms. Testnet opening remains draft/readiness-gated; ecosystem programme terms are separate before opening. Existing application forms do not confirm payout. The official X page returned403, so latest social posts could not be checked; this is a scoped negative search, not proof that no other announcement exists. No wallet connection, form submission, token claim or settlement was performed.

Prepared by renhi with Codex. This task publishes companion evidence in the existing personal repository; no new PR, peer comment or personal DID-signed Technocore post is included.
