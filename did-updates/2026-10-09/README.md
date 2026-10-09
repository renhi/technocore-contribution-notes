# DID-linked follow-up evidence index — 2026-10-09

This index links renhi's 12 post-announcement evidence bundles to the existing public DID. Prepared with Codex assistance. Original authors and earlier reviewers retain their credit; this is independent validation/companion material, not an original-author claim.

The first signed announcement (Technocore seq13943024, 2026-10-01) covered the initial 47-case PR238 suite. It is preserved in the repository's `public-identity.json` and is not being reposted. This follow-up indexes later examples/reviews/integration work. Numbers are historical results at pinned code versions; tests are not rerun as part of publication.

`evidence-index.json` pins existing repository commit `61d0f601aa63240f7e9faf242a0b84affc91be5f`, tree `61d0f601aa63240f7e9faf242a0b84affc91be5f`, all101 artifact Git blobs, and 12 validation blob SHA-256 hashes. Its own SHA-256 is `6288d68d40fcb4987628290f0392049809fa97e08727cef6074ca188ddea1d20`. A single subsequent Technocore message will sign the index URL and this digest. The signature binds the statement and digest to the DID; it does not prove test truth, personal/legal identity, main merge, or reward eligibility. Server sequence/timestamp are not signed.

Incomplete results remain explicit: the reader has seven additional unmet requirements; export framing still has an unresolved missing chunk terminator; the IPv6 Windows startup defect was not reproduced; production/Linux/Worker coverage is limited. PR735's author explicitly referred to renhi's reproduction, which is contribution acknowledgment rather than main merge or airdrop approval.

Only public identity, evidence, signatures and messages may be added here. No private key or protected key ciphertext is included. After delivery, `signed-announcement.json` and `verification.json` will preserve the returned public record and offline verification result. The live room has limited retention; GitHub and local saved records preserve the evidence.

## Verified delivery

One signed POST was read back from Technocore room `technocore`, seq`16342113`, server timestamp `2026-10-09T14:14:32.808283Z`. The preserved public tuple verifies with the unchanged official PyNaCl verifier. There were no retries or repeated first-announcement posts. See `signed-announcement.json` and `verification.json`; the room is not permanent storage. The protected key was only used internally for the authorized signature/MCP configuration.
