# Independent fixture review of the corrected `since` reader

Prepared by renhi with Codex assistance, 2026-10-05. This package provides an executable Windows/Node review of pepedesigner's corrected reader in [official issue #919](https://github.com/flop-labs/technocore-chat/issues/919#issuecomment-5980922352). Credit to pepedesigner for acknowledging and correcting the earlier retention-boundary bug, and to shibainu-inu and earlier reviewers for the retention evidence. No competing server/bridge PR is proposed.

The subject is an example in an issue discussion, **not official server code or an adopted reference client**. The source is not redistributed. The checker verifies the SHA-256 of the comment body and then executes the reviewed, unchanged JavaScript block with fixture globals.

## Actual result

On Windows and the Node version recorded in `behaviour-results.json`: **17 cases, 10 passing controls, 7 unmet consumer-safety requirements**. The checker exits 1 deliberately because these requirements remain unmet. These are not seven confirmed production bugs, and no deployed-service incident, live recovery, fix or full upstream CI is claimed. The initial 16-case publication was extended after checking the documented rate-limit guidance.

The controls establish contiguous `since` reads, export recovery of a tail gap, explicit retention-floor and interior-export loss, empty-read fallback, cursor preservation after exhausted empty/error exports, bounded 503 attempts, subsequent successful recovery, exclusion of pre-cursor rows, and preservation of Korean/combining-character text. Every response comes from an in-memory fixture; no actual HTTP request is performed.

## Additional boundaries to review

| Fixture | Observed result | Consumer contract being tested |
| --- | --- | --- |
| Persisted checkpoint generation 7; `since` generation 8 | `ok: true`, no returned generation | Distinguish a different conversation before associating rows with the checkpoint |
| `since` generation 7; export header generation 8 | `ok: true` over export rows | Detect a generation transition between two responses |
| `since` rows 11 and 13, cursor 10 | `ok: true`, cursor 13 | Check interior continuity if promising no missing sequence interval |
| Read observes up to 15; subsequent export contains 11–13 | `ok: true`, cursor 13 | Do not label the entire observed interval recovered before covering its head |
| Export has an invalid physical line between valid rows | Invalid line discarded; `ok: true` | Refuse or explicitly report malformed input rather than silently dropping it |
| Final physical line is incomplete | Final line discarded; `ok: true` for the prefix | Distinguish a partial/malformed export from a complete verified interval |
| Export returns 429 and `Retry-After: 60` | Three export attempts, with no wait/defer in the code | Stop/defer requests until the stated retry delay rather than treating 429 like 503 |

The 429 case follows the [official rate-limit guidance](https://technocore.chat/llms.txt): read and honor the retry delay. The fixture supplies a 60-second delay without advancing time; the unchanged loop immediately continues on every non-2xx response. This is a demonstrated control-flow issue in the example, not an actual rate-limiting incident. No real 429 was provoked and no sleep or network request is used.

The first generation case assumes the caller already has a `{generation: 7, cursor: 10}` checkpoint. The current function accepts only a numeric cursor and provides no generation reconciliation mechanism. That is the limitation being illustrated, not a claim it already promises a generation-aware contract.

The shorter-export case is explicitly a **stronger complete-interval recovery requirement**. Returning a valid prefix can be legitimate for an incremental reader; `ok` must be documented accordingly. It is not automatically data loss. Likewise, sequence gaps can be intentional in ephemeral rooms or reflect reserved sequence numbers rather than stored messages. The tests describe strict numeric continuity for the controlled fixtures; they do not prove a missing `seq` was ever an actual message.

Malformed/torn fixtures test refusal behavior if upstream data or an intermediary violates the expected shape. The [official export contract](https://technocore.chat/llms.txt) says the service snapshots complete raw LF-delimited records and provides `X-Room-Generation`; ordinary exports are not alleged to contain these malformed lines. The [coordination patterns](https://technocore.chat/patterns.md) and [auth guide](https://technocore.chat/auth.md) were also checked. This is neither signature verification nor a byte-exact archive tool: normal JavaScript JSON parsing must not be treated as lossless handling of 19-digit nonce values.

## Reproduce with an assisting agent

1. Retrieve and review the JSON response from `https://api.github.com/repos/flop-labs/technocore-chat/issues/comments/5980922352`; save it as `comment.json`.
2. Check that its `body` hash matches `source-provenance.json`. A changed comment is a new review target, not something to silently normalize.
3. Use Node 24, without installing packages:

```text
node check_reader.mjs comment.json source-provenance.json results.json
```

The tool performs no network requests. Node `vm` supplies mock globals; it is not a security sandbox for arbitrary untrusted source. Only use the reviewed, pinned comment. The beginner user does not need to type these commands.

## Review direction

Please clarify whether `ok` means a contiguous prefix or recovery through an observed head, expose/reconcile generation if the reader is used across calls, and explicitly reject/report malformed export records. The fixture results can serve as regression material for the author's design. No corrected replacement or verified patch is supplied in this package.

## 한국어 설명

이번 기여는 대화를 이어서 읽는 예제의 추가 안전 조건을 검사하는 것입니다. 기본 상황 10개는 통과했습니다. 방이 다시 만들어졌거나 응답 중간에 빈 구간·잘못된 줄이 있는 등 추가 상황 7개에서는 요구한 안전 조건을 충족하지 못했습니다. 일부 조건은 ‘어디까지 복구됐다고 볼 것인지’를 먼저 합의해야 합니다. 제한 응답의 대기 시간을 따르지 않고 다시 요청하는 동작도 포함됩니다. 운영 서버에서 실제 오류가 발생했다거나 수정이 끝났다고 주장하지 않습니다.

Independently authored checker: Apache-2.0, see the companion repository root LICENSE. The external comment source is fetched separately and is not relicensed or republished here. Adoption, external usage and airdrop eligibility are unconfirmed.
