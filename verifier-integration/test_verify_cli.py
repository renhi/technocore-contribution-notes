"""PR #238 regression integration: original cases plus server/CLI parity.

Original pad-bit finding: osr21, PR #238 comment 5512590300.
The verifier was written by dhasap; regression integration is by renhi.
Only disposable in-memory keys are used. No HTTP requests or stored user keys.
"""

import base64
import importlib.util
import subprocess
import sys
import unittest
from importlib.machinery import SourceFileLoader
from pathlib import Path

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

import didkey

ROOT = Path(__file__).resolve().parents[2]
VERIFIER = ROOT / "scripts" / "verify.py"
B64 = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_"
METHODS = (
    "test_valid_korean_say_and_set",
    "test_all_noncanonical_padbit_aliases",
    "test_changed_text_is_rejected",
    "test_wrong_room_or_namespace_is_rejected",
    "test_wrong_key_is_rejected",
    "test_bad_encoding_is_rejected",
    "test_nonce_format_is_rejected",
    "test_zero_nonce_is_valid_for_offline_tuple",
    "test_sweep_matches_signed_visible_text",
)


@pytest.fixture(scope="module")
def companion():
    """Keep the already-published 47-case suite byte-identical."""
    path = ROOT / "tests" / "fixtures" / "verify_cli_regression.txt"
    loader = SourceFileLoader("verify_cli_regression", str(path))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.VERIFIER = VERIFIER
    return module


@pytest.mark.parametrize("method", METHODS)
def test_original_regression_method(companion, method):
    result = unittest.TestResult()
    unittest.TestSuite([companion.VerifyCLI(method)]).run(result)
    assert result.testsRun == 1
    assert result.wasSuccessful(), result.failures + result.errors


@pytest.fixture(scope="module")
def signed_key(companion):
    key = Ed25519PrivateKey.generate()
    return key, companion.did_for(key)


def signed_arguments(signed_key, lane, nonce="9007199254740993001"):
    key, did = signed_key
    fields = ["offline-review"] if lane == "say" else ["offline-review", "result"]
    text = "한글 원래 서명 입력"
    canonical = "|".join([*fields, nonce, text])
    signature = base64.urlsafe_b64encode(key.sign(canonical.encode())).decode().rstrip("=")
    return [lane, did, signature, nonce, *fields, text], canonical


def cli(arguments):
    return subprocess.run(
        [sys.executable, "-X", "utf8", str(VERIFIER), *arguments],
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=10,
    )


@pytest.mark.parametrize("lane", ["say", "set"])
@pytest.mark.parametrize("terminal", list(B64))
def test_every_signature_terminal_matches_server(signed_key, lane, terminal):
    arguments, canonical = signed_arguments(signed_key, lane)
    original = arguments[2]
    arguments[2] = original[:-1] + terminal
    if terminal == original[-1]:
        expected = 0
        didkey.verify(arguments[1], arguments[2], canonical)
    elif terminal in "AQgw":
        expected = 3
        with pytest.raises(didkey.SignatureError):
            didkey.verify(arguments[1], arguments[2], canonical)
    else:
        expected = 2
        with pytest.raises(didkey.DidError):
            didkey.verify(arguments[1], arguments[2], canonical)
    completed = cli(arguments)
    assert completed.returncode == expected, (completed.stdout, completed.stderr)
    assert ("OK " in completed.stdout) == (expected == 0)


@pytest.mark.parametrize("lane", ["say", "set"])
def test_original_nonce_spelling_is_required(signed_key, lane):
    arguments, _ = signed_arguments(signed_key, lane, nonce="007")
    assert cli(arguments).returncode == 0
    arguments[3] = str(int(arguments[3]))
    assert arguments[3] == "7"
    assert cli(arguments).returncode == 3
