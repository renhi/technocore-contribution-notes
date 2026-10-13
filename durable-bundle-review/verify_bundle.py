"""Offline executable companion to PR977; this local profile is not an official wire format.

Verify one externally selected DID/room announcement, the exact manifest bytes and its
payloads. The unsigned archive is OUTSIDE the manifest's payload list. Other archive
records and server-assigned seq/ts are not authenticated by this check.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import re
import stat
from pathlib import Path

MAX_BYTES = 1024 * 1024
HEX = re.compile(r"[0-9a-f]{64}")
NAME = re.compile(r"[a-z0-9][a-z0-9_-]{0,47}")
MARKER = re.compile(r"bundle:v1 manifest-sha256:([0-9a-f]{64})")


class BundleError(ValueError):
    """The bundle cannot establish this profile's limited evidence claim."""


def require(condition, message):
    if not condition:
        raise BundleError(message)


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, "duplicate JSON object key")
        result[key] = value
    return result


def strict_json(raw):
    try:
        return json.loads(
            raw.decode("utf-8"),
            object_pairs_hook=unique_object,
            parse_constant=lambda _: (_ for _ in ()).throw(BundleError("nonfinite JSON")),
        )
    except (UnicodeError, json.JSONDecodeError, RecursionError) as exc:
        raise BundleError("invalid UTF8 JSON") from exc


def ordinary(path):
    try:
        info = path.lstat()
    except OSError as exc:
        raise BundleError("missing bundle path") from exc
    require(not path.is_symlink(), "symlink path refused")
    require(
        not getattr(info, "st_file_attributes", 0)
        & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0),
        "reparse path refused",
    )
    return info


def bounded_file(path):
    require(stat.S_ISREG(ordinary(path).st_mode), "not a regular file")
    try:
        with path.open("rb") as stream:
            raw = stream.read(MAX_BYTES + 1)
    except OSError as exc:
        raise BundleError("unreadable file") from exc
    require(len(raw) <= MAX_BYTES, "file exceeds local profile cap")
    return raw


def payload_path(base, name):
    require(isinstance(name, str) and 0 < len(name) <= 240, "bad payload path")
    require("\\" not in name and ":" not in name, "nonrelative path")
    parts = name.split("/")
    require(all(part and part not in {".", ".."} for part in parts), "path traversal")
    require(
        parts[0].casefold() not in {"manifest.json", "signed-records.jsonl"},
        "manifest or announcement archive cannot be a hashed payload",
    )
    path = base
    for part in parts:
        require(not part.endswith((".", " ")), "ambiguous Windows path")
        require(not any(ord(c) < 32 for c in part), "control in path")
        path = path / part
        ordinary(path)
    require(path.resolve().is_relative_to(base.resolve()), "payload leaves bundle")
    return path


def load_verifier(path, sha256):
    raw = bounded_file(path)
    require(HEX.fullmatch(sha256) is not None, "bad external verifier pin")
    require(hashlib.sha256(raw).hexdigest() == sha256, "external verifier pin mismatch")
    # The caller independently pins this trusted official source before execution.
    spec = importlib.util.spec_from_file_location("pinned_official_bundle_verifier", path)
    require(spec is not None and spec.loader is not None, "unloadable verifier")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def verify_bundle(base, expected_did, room, verifier):
    require(NAME.fullmatch(room) is not None, "bad externally supplied room")
    require(stat.S_ISDIR(ordinary(base).st_mode), "bundle is not a directory")
    manifest_raw = bounded_file(base / "manifest.json")
    archive_raw = bounded_file(base / "signed-records.jsonl")
    manifest = strict_json(manifest_raw)
    require(
        isinstance(manifest, dict) and set(manifest) == {"profile", "files"},
        "bad manifest shape",
    )
    require(manifest["profile"] == "technocore-durable-example-v1", "unknown local profile")
    entries = manifest["files"]
    require(isinstance(entries, list) and 1 <= len(entries) <= 128, "bad payload list")
    require(archive_raw.endswith(b"\n"), "archive requires complete JSONL lines")
    lines = archive_raw.splitlines()
    require(1 <= len(lines) <= 128 and all(lines), "bad archive record list")
    selected = []
    for line in lines:
        record = strict_json(line)
        require(isinstance(record, dict), "archive record is not an object")
        text = record.get("text")
        if record.get("from") == expected_did and isinstance(text, str):
            marker = MARKER.fullmatch(text)
            if marker:
                selected.append((record, marker.group(1)))
    require(len(selected) == 1, "expected exactly one selected announcement")
    record, bound_digest = selected[0]
    nonce = record.get("nonce")
    require(type(nonce) in {int, str}, "missing or wrong nonce type")
    nonce = str(nonce)
    require(re.fullmatch(r"[0-9]{1,19}", nonce) is not None, "bad original nonce spelling")
    signature = record.get("sig")
    require(isinstance(signature, str), "missing signature")
    try:
        verifier.verify(expected_did, signature, f"{room}|{nonce}|{record['text']}")
    except (ValueError, TypeError, UnicodeError) as exc:
        raise BundleError("selected announcement signature invalid") from exc
    digest = hashlib.sha256(manifest_raw).hexdigest()
    require(bound_digest == digest, "signed manifest digest mismatch")
    seen = set()
    checked = []
    for entry in entries:
        require(isinstance(entry, dict) and set(entry) == {"path", "sha256"}, "bad file entry")
        name, sha256 = entry["path"], entry["sha256"]
        require(isinstance(name, str), "file path is not a string")
        require(name.casefold() not in seen, "duplicate or case-ambiguous payload path")
        seen.add(name.casefold())
        require(isinstance(sha256, str) and HEX.fullmatch(sha256) is not None, "bad file digest")
        raw = bounded_file(payload_path(base, name))
        require(hashlib.sha256(raw).hexdigest() == sha256, "payload digest mismatch")
        checked.append(name)
    return {
        "signature_valid": True,
        "manifest_sha256": digest,
        "payloads_verified": checked,
        "expected_did": expected_did,
        "room": room,
        "seq_ts_authenticated": False,
        "raw_archive_byte_authenticity_established": False,
        "other_archive_records_authenticated": False,
        "file_content_truth_or_official_approval": False,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("bundle", type=Path)
    parser.add_argument("--did", required=True)
    parser.add_argument("--room", required=True)
    parser.add_argument("--verifier-file", type=Path, required=True)
    parser.add_argument("--verifier-sha256", required=True)
    args = parser.parse_args()
    try:
        verifier = load_verifier(args.verifier_file, args.verifier_sha256)
        result = verify_bundle(args.bundle, args.did, args.room, verifier)
    except BundleError as exc:
        print(json.dumps({"ok": False, "reason": str(exc)}))
        raise SystemExit(1) from None
    print(json.dumps({"ok": True, **result}))


if __name__ == "__main__":
    main()
