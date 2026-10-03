# Windows redirect review for Technocore PR #944

An independent Windows/CPython validation companion for [PR #944](https://github.com/flop-labs/technocore-chat/pull/944), which addresses [issue #943](https://github.com/flop-labs/technocore-chat/issues/943). Prepared by renhi with Codex assistance on 2026-10-03.

Credit: Bornoz implemented the original fix; almondous supplied the integrated Worker correction and uncertainty wording. Existing reviewers and upstream tests already cover this problem. This contribution adds an actual Windows two-origin socket matrix; it is not a new discovery or a competing fix.

## Problem and result

A POST can encounter a redirect. On the original implementation, 301/302/303 can become a GET of the destination and be reported as success; 307/308 and redirects with no Location can also be returned without a tool error. A redirect can arrive *after* the original server stored the write, so an error must describe an unconfirmed outcome and recommend checking before retrying.

| Pinned source | Cases | Passed | Failed |
|---|---:|---:|---:|
| Official main `0e47f770b13cc27e1e2e199d4cdf70a4778c97cc` | 27 | 11 | 16 |
| PR #944 head `82db3e9936860cfc2c3eff0a4cea98385dd93a29` | 27 | 27 | 0 |

The same final checker ran against both unchanged source versions. The baseline failures are expected observations of the existing issue, not 16 separate bugs. The candidate files match GitHub's Git blob hashes; `source-provenance.json` records them, and both reports carry their SHA-256 hashes.

## Coverage

- Five redirect statuses: 301, 302, 303, 307, 308.
- POST before storage, POST after fixture storage, and POST without Location: 15 cases.
- GET and HEAD redirect controls: 10 cases.
- One unfollowable GET and one direct successful POST: 2 cases.
- Checks include one origin request, no redirected destination request for a write, correct unconfirmed-outcome wording, read-appropriate errors, and preservation of Korean JSON at the original endpoint.

Both origins bind only to `127.0.0.1` on dynamically assigned ports. Outgoing socket connections are restricted to that address during the matrix. The real CPython urllib transport and shared `_request` layer execute. The origin's commit list is a synthetic fixture; no Technocore message or note is posted. No production key is loaded and no financial operation occurs.

HEAD's redirect becomes GET on this Python runtime, both before and after the patch. The control checks that it follows as a read; it does not claim HEAD method preservation. The initial checker incorrectly required preservation of HEAD, which produced five additional failures on both versions. That expectation was corrected before the final comparable runs. No candidate code was changed.

## Reproduce — reviewer or assisting agent

Use Python 3.12 with the workspace's official MCP dependencies (`mcp==2.2.0`). Obtain and review the four package files named in `source-provenance.json` at the pinned commits: `__init__.py`, `server.py`, `fetch.py`, `signing.py`, under `mcp/src/technocore_mcp/`. Verify their hashes. Run each source in a separate process:

```text
python check_write_redirects.py --source /reviewed/source/technocore_mcp --report results.json
```

Exit 1 is expected on pinned main; exit 0 is expected on the pinned PR candidate. Do not point the fixture at the production service or load a signing key. The beginner operator does not need to type commands: their assisting agent performs this work.

## Limits

This does not initialize a stdio MCP session, run the full Linux server suite, test Cloudflare/Pyodide, establish deployment of the fix, or reproduce the authors' broader CI results. Upstream adoption and airdrop eligibility are unconfirmed. The production workspace and installed package were not modified.

## 한국어 설명

메시지를 보냈다고 표시되지만 실제로는 다른 주소의 읽기 결과만 받은 문제를 검사했습니다. 우리 PC 안의 가짜 서버 두 개로만 시험했고, 공개 채팅·메모·지갑에는 아무 작업도 하지 않았습니다. 수정 전에는 27가지 중 16가지가 예상과 달랐고, 다른 참여자들이 만든 최신 수정안은 모두 통과했습니다. 수정안이 공식 서비스에 적용됐다는 뜻이나 에어드랍 자격을 뜻하지는 않습니다.

Code: Apache-2.0, matching the companion repository's root LICENSE.
