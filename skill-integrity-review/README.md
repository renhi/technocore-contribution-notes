# Official skill distribution integrity audit (2026-10-11)

New independent, read-only stdlib contribution for [Technocore](https://github.com/flop-labs/technocore-chat). The official [Agent Skills index](https://technocore.chat/.well-known/agent-skills/index.json) advertises a SHA256 of the exact [/skill.md](https://technocore.chat/skill.md) bytes. This auditor checks that advertisement and the fetched bytes against a **separately pinned official repository source**, rather than trusting two mutually consistent responses from one service.

## Verified live observation

Source commit: `0e47f770b13cc27e1e2e199d4cdf70a4778c97cc`. Source version: `0.14.5`. Skill length: `6631` bytes. Source, advertised digest and deployed raw bytes all match SHA256 `f2616b7195eeacbbba21ca493211866f0768ea2bea7e0d4059d7045da7bcffe3`. This is a successful integrity check, **not a claim of discovered corruption**. Final live audit used2 public-service GETs; initial inspection used3 additional GETs. No service write or retry was used for these checks.

## Reusable contribution

`audit_skill.py` accepts an operator-supplied source digest and version, fetches only the known index and exact same-origin `/skill.md`, and compares raw bytes without trimming, Unicode normalization, line-ending conversion or BOM removal. It refuses redirects, mismatched advertised URLs, unsupported media/encoding, oversized/truncated declared bodies, ambiguous target entries, wrong pins and transport failures. It neither installs nor executes the document. Untrusted discovery text cannot select an arbitrary fetch destination. HTTPS certificate verification remains enabled; plain HTTP is limited to loopback fixtures.

`test_audit_skill.py` executes the complete auditor normally in subprocesses against disposable loopback HTTP. **34/34 tests pass**,48 actual requests,0 unexpected errors. Controls accept exact LF and independently pinned exact CRLF documents. Negative fixtures include one-byte edits, BOM/newline/normalization changes, a wrong document with its own internally consistent index, malformed discovery data, foreign URLs, HTTP404/429, redirects, media/encoding/size problems and incomplete declared framing. They verify nonzero failure, request counts and no redirect/extra fetch. These are synthetic controls, not production vulnerabilities.

For contributors with Python3.12+, place both scripts together and run `python test_audit_skill.py`. To repeat the currently pinned read-only live audit:

```text
python audit_skill.py --expected-sha256 f2616b7195eeacbbba21ca493211866f0768ea2bea7e0d4059d7045da7bcffe3 --expected-version 0.14.5
```

The external pin is intentionally explicit. For a later source commit, independently review and pin the new source rather than replacing the pin with whatever the service says. Full JSON output gives the observed digests and scope. A failed read is not an instruction to retry a write.

## Relationship and boundaries

Credit to zkasuran's [PR #935](https://github.com/flop-labs/technocore-chat/pull/935), which adds server-side checks linking SKILL room/idle prose constants to code. This complements that work by checking **deployed document bytes**. It does not execute or certify those PR tests. All5 pinned main source files and the inspected PR test blob were checked without modification. New auditor/test Ruff lint/format under the pinned project's config and syntax checks pass. No full server, Linux repository gate or upstream CI was run, and no project adoption is claimed.

Matching hashes establish byte identity under the chosen source trust; they do not validate every instruction, authenticate source authorship, prove current ownership/roles, or guarantee future cache/deployment freshness. This service-specific checker is not a generic discovery-schema validator or hardened installer. Strict redirect/identity-encoding policies are our conservative audit choices. There is a socket timeout and byte caps, not a total deadline. TLS/proxy attack fixtures were not exercised; no local tests used user keys or wallet credentials.

Independent contribution prepared by renhi with Codex. See `source-provenance.json`, `fixture-validation.json`, `live-verification.json` and `validation.json` for pins and precise scope. The separately authorized existing-DID summary and verification receipt will be appended after delivery. No official role, settled testnet compute, reward or airdrop eligibility is implied.
