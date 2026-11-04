"""Download only pinned public source blobs and verify both recorded digests.

Usage: python fetch_sources.py source-provenance.json SNAPSHOT_ROOT
Existing files must already match. No credential or git working tree is needed.
"""

import hashlib
import json
import sys
import urllib.request
from pathlib import Path

provenance = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
destination = Path(sys.argv[2]).resolve()
for row in provenance["files"]:
    assert row["label"] in {"base", "main", "candidate", "verifier"}
    ref = row["ref"]
    assert len(ref) == 40 and all(c in "0123456789abcdef" for c in ref)
    path = row["path"]
    assert not path.startswith("/") and ".." not in Path(path).parts
    target = (destination / row["label"] / path).resolve()
    assert target.is_relative_to(destination)
    if target.exists():
        raw = target.read_bytes()
    else:
        url = (
            f"https://raw.githubusercontent.com/flop-labs/technocore-chat/{ref}/{path}"
        )
        with urllib.request.urlopen(url, timeout=30) as response:
            raw = response.read(4 * 1024 * 1024)
    assert hashlib.sha256(raw).hexdigest() == row["sha256"]
    assert (
        hashlib.sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest()
        == row["blob"]
    )
    if not target.exists():
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("xb") as stream:
            stream.write(raw)
print(f"Verified {len(provenance['files'])} pinned source blobs.")
