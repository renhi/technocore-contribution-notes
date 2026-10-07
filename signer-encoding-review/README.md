# Korean Windows signer validation for PR #966

An independent offline contribution by renhi, assisted by Codex. The fix belongs to
[Packae's PR #966](https://github.com/flop-labs/technocore-chat/pull/966).
Packae already supplied CP932/ASCII regressions, and bdunn77 already reported independent
Linux validation. This packet adds native Windows CP949 coverage, a broader encoding
matrix, Korean/emoji signing controls, and round trips through the unchanged note consumers.
It does not claim discovery of the original bug or authorship of the two-line fix.

## What was actually executed

Immutable base `0e47f770b13cc27e1e2e199d4cdf70a4778c97cc` and candidate
`6f3b7cb6f9e53676da8807d17e4d5cfbd3a6f922`, with their original `scripts/sign.py`
bytes verified against GitHub Git blobs. The only signer difference is two guidance
em dashes replaced by ASCII hyphens. No source modification or simulation of the signer.

Windows 11, CPython 3.12.14, cryptography 50.0.1. Each version was invoked in 20 actual
child processes: `delegate`, `e2e`, `say`, and `set`, under CP949, CP932, ASCII, CP1252,
and UTF-8 with strict stdout encoding. `PYTHONIOENCODING` explicitly controls captured
output; this is not detection of a user's interactive terminal or VS Code encoding.

| Execution | Base | Candidate |
| --- | ---: | ---: |
| Successful output | 14/20 | 20/20 |
| Encoding failures before signed record | 6/20 | 0/20 |
| Korean/emoji say and set controls | 10/10 | 10/10 |

All six failures are the same known U+2014 guidance problem, across two commands and
three codecs, including Korean CP949. They are not six separate bugs. CP1252 and UTF-8
are positive controls: the original guidance succeeds there as well.

All 34 emitted signatures verified with an independently held Ed25519 public key;
all 34 changed-payload controls were rejected. Fourteen usable `delegate`/`e2e` records
also passed 42 assertions through the original pure note readers: valid record accepted,
wrong root rejected, changed scope/mailbox rejected. The 19-digit nonce
`9007199254740993001` stays exact, including the integer returned by the e2e reader.
Korean/emoji inputs include newline and a zero-width character; the independently
specified expected swept text is used for UTF-8 signature verification.

## Reproduce

Use Python 3.12 with cryptography installed and acquire the two pinned `scripts/sign.py`
files from GitHub. A technically experienced reviewer can run:

```text
python check_encoding.py path/to/base/sign.py path/to/candidate/sign.py results.json
```

The checker asserts the exact two-line source difference before executing. Compare the
SHA-256 values to `source-provenance.json`; inspect the original source before running it.
Successful execution exits zero and writes the individual 40 observations. Fresh signing
seeds are generated in memory for synthetic fixtures, passed only in child environments,
and never printed or saved. Results intentionally omit signatures, fixture seeds and
arbitrary stderr. No production identity, wallet, server request, message or note write.

## Limits and status

This is supplementary regression evidence for an existing PR, not an additional source
PR or a statement that the PR is merged. The broader Linux HTTP test module imports
the server and requires `fcntl`; that module and full repository CI were not run here.
Ruff lint and format checks passed for this independent checker only. No claim that
every signer error/help path is ASCII-safe: this matrix covers valid command paths.
`e2e` here signs a public key declaration; it does not establish an encrypted conversation.

Upstream comments were not posted, consistent with the user's GitHub-only publication
preference. Official adoption, external use, and airdrop eligibility remain unconfirmed.
The FLOP site's follow instruction and protocol reward rules are separate from this
Technocore compatibility review; test counts are not FLOP reward points.

Sources: [Technocore reference](https://technocore.chat/llms.txt),
[authentication](https://technocore.chat/auth.md),
[patterns](https://technocore.chat/patterns.md),
[FLOP](https://flop.finance/ko/),
[yellow paper](https://flop.finance/intro/yellowpaper/).
Pinned source identities and publication-time PR/main status are in the JSON files.
