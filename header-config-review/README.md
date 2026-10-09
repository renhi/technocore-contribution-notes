# Native Windows HTTP header configuration matrix — PR #923

This companion evidence independently imports the unchanged `src/config.py` in a fresh Windows CPython interpreter for each setting. It expands boundary coverage for the existing fix; it is not a new defect claim or competing patch. Prepared with Codex assistance for renhi.

Credit: **RobGenins** for [PR #923](https://github.com/flop-labs/technocore-chat/pull/923) and its project tests; **bdunn77** for [earlier Linux and causal validation](https://github.com/flop-labs/technocore-chat/pull/923#issuecomment-5999275813). The existing report is tracked as [#745](https://github.com/flop-labs/technocore-chat/issues/745).

## Pinned source and observed result

- Main: `0e47f770b13cc27e1e2e199d4cdf70a4778c97cc`
- Candidate: `58c08a469fad95e02aa0a35f32c01abcc710ddc2`
- Runtime: Windows-11-10.0.26200-SP0; CPython 3.12.14
- Eight source/guidance/test/configuration blobs verified against GitHub Git blob hashes. Full config modules are executed; no extracted guard, monkeypatch, store substitute, or fcntl stub.

| Same 418 cases per version | Main | Existing candidate |
| --- | ---: | ---: |
| Expected outcomes matched | 175 | 418 |
| Outcomes mismatched | 243 | 0 |
| Unexpected import/process errors | 0 | 0 |
| Valid/default/disabled configurations accepted | 175 | 175 |
| Invalid configurations refused by the setting's ValueError | 0 | 243 |

The 243 mismatches are instances of the already reported missing validation, **not 243 independent vulnerabilities**. There are 836 actual child-process imports. A refusal is counted only for a `ValueError` naming `CHAT_CLIENT_IP_HEADER`, never for arbitrary process failure.

## Added coverage

- All 127 non-NUL ASCII characters, once alone and once embedded between `x` and `y`: 254 cases.
- Every Latin-1 non-ASCII code point U+0080..U+00FF embedded inside a name: 128 cases.
- Twenty-four Unicode cases: Kelvin sign and other case/lookalike boundaries, Korean composed/jamo text, emoji, combining marks, fullwidth letters, Cyrillic lookalikes, zero-width/bidi/BOM and line separators, plus surrounding whitespace.
- Twelve controls: unset/empty settings, mixed case, common proxy names, trimming, all token punctuation, letters/digits, separators and an embedded CRLF.

The independent oracle uses the ASCII `token` grammar from [RFC 9110 section 5.6.2](https://www.rfc-editor.org/rfc/rfc9110.html#section-5.6.2), **after the existing operator configuration's `.strip()`**, followed by lowercase for accepted names. Empty is the opt-out. This deliberately preserves existing trimming: surrounding NBSP/ideographic spaces are removed, and whitespace-only input disables the setting. It does not claim raw untrimmed values are all HTTP field names. Embedded forbidden characters still refuse.

Windows passes each test value through a real process environment. A new interpreter executes the entire pinned module and reports its configured value or the specific refusal. Accepted imports additionally verify that neither `app` nor `store` was imported. Results include every supplied value (JSON escaped), expected and actual verdict, and source/checker SHA-256 hashes.

## Reproduction for reviewers

Obtain unchanged `src/config.py` at the two pinned commit links:

- [Main source](https://github.com/flop-labs/technocore-chat/blob/0e47f770b13cc27e1e2e199d4cdf70a4778c97cc/src/config.py)
- [Candidate source](https://github.com/flop-labs/technocore-chat/blob/58c08a469fad95e02aa0a35f32c01abcc710ddc2/src/config.py)

Run Python 3.12+ against those two files, without editing them:

```console
python check_header_config.py --before before/src/config.py --after after/src/config.py --output native-results.json
```

The checker uses only the Python standard library. It exits nonzero on candidate mismatches or unexpected baseline process errors. The same cases and grammar run on both versions. NUL is excluded because a process environment cannot represent it; unpaired UTF-16 surrogates are excluded. Stored results are from Windows, not a claimed test of other operating systems.

## Scope

No Linux server boot, existing Linux-dependent test module, repository coverage gate, reverse-proxy deployment, actual HTTP ingress or live-service writes were run. Thus this evidence covers configuration import/refusal only, not proxy header trust, rate-limit correctness, service-wide readiness or actual production rejection. Existing tests remain byte-identical and were not substituted. No official source or installed MCP package was modified. No protected user key, wallet, X post, GitHub review/comment, or Technocore post was used. GitHub API traffic was used to obtain sources and publish this evidence, not to exercise the hosted chat.

This artifact supports review of the pinned candidate. It is not proof of upstream acceptance, downstream use, testnet settlement, an official role, or airdrop eligibility.
