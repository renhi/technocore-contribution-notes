"""Read-only, pinned raw-byte integrity audit of Technocore's published skill.

The expected digest/version must come from a separately trusted pinned source.
Matching the service's own index alone does not authenticate the document.
No downloaded text is executed, installed, or treated as instructions.
"""

from __future__ import annotations

import argparse
import hashlib
import http.client
import json
import re
import ssl
import urllib.error
import urllib.parse
import urllib.request

DIGEST_RE = re.compile(r"[0-9a-f]{64}")
INDEX_LIMIT = 128 * 1024
SKILL_LIMIT = 1024 * 1024


class AuditError(Exception):
    """A failed observation, never a successful installation receipt."""


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def fetch(url: str, limit: int, allowed_types: tuple[str, ...]) -> bytes:
    opener = urllib.request.build_opener(
        NoRedirect(), urllib.request.HTTPSHandler(context=ssl.create_default_context())
    )
    request = urllib.request.Request(url, headers={"Accept-Encoding": "identity"})
    try:
        with opener.open(request, timeout=10) as response:
            if response.status != 200:
                raise AuditError(f"HTTP {response.status}: {url}")
            if response.headers.get_content_type() not in allowed_types:
                raise AuditError("unexpected content type")
            if response.headers.get("Content-Encoding", "identity").lower() != "identity":
                raise AuditError("unexpected content encoding; raw bytes must be comparable")
            length = response.headers.get("Content-Length")
            if length is not None and (not re.fullmatch(r"[0-9]+", length) or int(length) > limit):
                raise AuditError("invalid or oversized declared response length")
            body = response.read(limit + 1)
            if length is not None and len(body) != int(length):
                raise AuditError("body does not match its declared response length")
    except (urllib.error.URLError, OSError, http.client.HTTPException) as exc:
        raise AuditError(f"HTTP/transport observation failed: {exc}") from exc
    if len(body) > limit:
        raise AuditError("response exceeds the audit byte limit")
    return body


def audit(base: str, expected_digest: str, expected_version: str) -> dict:
    base = base.rstrip("/")
    try:
        parsed = urllib.parse.urlsplit(base)
    except ValueError as exc:
        raise AuditError("base could not be parsed as an origin") from exc
    if (
        parsed.scheme not in ("http", "https")
        or not parsed.netloc
        or parsed.username is not None
        or parsed.password is not None
        or parsed.path
        or parsed.query
        or parsed.fragment
    ):
        raise AuditError("base must be a credential-free HTTP(S) origin")
    if parsed.scheme == "http" and parsed.hostname not in ("127.0.0.1", "::1", "localhost"):
        raise AuditError("plain HTTP is allowed only for disposable loopback fixtures")
    if not DIGEST_RE.fullmatch(expected_digest) or not expected_version:
        raise AuditError("a pinned lowercase SHA256 and version are required")
    index_url, skill_url = base + "/.well-known/agent-skills/index.json", base + "/skill.md"
    raw_index = fetch(index_url, INDEX_LIMIT, ("application/json",))
    try:
        index = json.loads(raw_index.decode("utf-8"))
    except (ValueError, UnicodeError) as exc:
        raise AuditError("index is not UTF-8 JSON") from exc
    if not isinstance(index, dict) or not isinstance(index.get("skills"), list):
        raise AuditError("index must contain a skills array")
    if any(not isinstance(entry, dict) for entry in index["skills"]):
        raise AuditError("each skill entry must be an object")
    entries = [entry for entry in index["skills"] if entry.get("name") == "technocore-chat"]
    if len(entries) != 1:
        raise AuditError("expected exactly one technocore-chat entry")
    entry = entries[0]
    if entry.get("type") != "skill-md":
        raise AuditError("unexpected skill type")
    # Validate untrusted discovery data BEFORE following any URL it advertises.
    if entry.get("url") != skill_url:
        raise AuditError("index URL is not the exact same-origin /skill.md path")
    if entry.get("version") != expected_version:
        raise AuditError("index version differs from the independently pinned version")
    if entry.get("digest") != "sha256:" + expected_digest:
        raise AuditError("index digest differs from the independently pinned source")
    raw_skill = fetch(skill_url, SKILL_LIMIT, ("text/plain", "text/markdown"))
    computed = hashlib.sha256(raw_skill).hexdigest()
    if computed != expected_digest:
        raise AuditError("served raw skill bytes do not match the pinned/index digest")
    return {
        "passed": True,
        "index_url": index_url,
        "skill_url": skill_url,
        "expected_version": expected_version,
        "index_sha256": hashlib.sha256(raw_index).hexdigest(),
        "skill_sha256": computed,
        "skill_bytes": len(raw_skill),
        "index_matches_external_pin": True,
        "served_bytes_match_external_pin": True,
        "redirects_followed": 0,
        "http_method": "GET",
        "scope": "Raw-byte distribution integrity, not correctness of instructions, complete discovery-schema validation, source authorship, adoption or reward eligibility.",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--base", default="https://technocore.chat")
    parser.add_argument("--expected-sha256", required=True)
    parser.add_argument("--expected-version", required=True)
    args = parser.parse_args()
    try:
        result = audit(args.base, args.expected_sha256, args.expected_version)
    except AuditError as exc:
        print(json.dumps({"passed": False, "error": str(exc)}))
        return 1
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
