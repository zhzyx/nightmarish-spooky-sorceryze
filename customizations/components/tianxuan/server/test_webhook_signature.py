"""Gitea webhook 签名与事件归一化（纯函数，不需要 FastAPI）。"""

from __future__ import annotations

import hashlib
import hmac
import unittest

from webhooks import summarize_gitea_event, verify_gitea_signature

SECRET = "webhook-secret-not-real"


def _sign(body: bytes, secret: str = SECRET) -> str:
    return hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()


class SignatureTests(unittest.TestCase):
    def test_valid_signature_with_and_without_prefix(self) -> None:
        body = b'{"ok": true}'
        self.assertTrue(verify_gitea_signature(SECRET, body, _sign(body)))
        self.assertTrue(verify_gitea_signature(SECRET, body, f"sha256={_sign(body)}"))

    def test_invalid_signature_rejected(self) -> None:
        body = b'{"ok": true}'
        self.assertFalse(verify_gitea_signature(SECRET, body, _sign(body + b"x")))
        self.assertFalse(verify_gitea_signature(SECRET, body, ""))
        self.assertFalse(verify_gitea_signature("", body, _sign(body)))
        self.assertFalse(verify_gitea_signature(SECRET, b"other", _sign(body)))


class SummarizeTests(unittest.TestCase):
    def test_push_event(self) -> None:
        payload = {
            "repository": {"full_name": "octo/duobao", "html_url": "https://gitea/octo/duobao"},
            "ref": "refs/heads/main",
            "before": "a" * 40,
            "after": "b" * 40,
            "created": False,
            "deleted": False,
            "forced": True,
            "commits": [{"id": "b" * 40}],
            "pusher": {"login": "alice"},
        }
        summary = summarize_gitea_event("push", payload)
        assert summary is not None
        self.assertEqual(summary["type"], "repo.push")
        self.assertEqual(summary["target"], "octo/duobao")
        self.assertEqual(summary["payload"]["owner"], "octo")
        self.assertEqual(summary["payload"]["name"], "duobao")
        self.assertEqual(summary["payload"]["commits"], 1)
        self.assertEqual(summary["payload"]["pusher"], "alice")
        self.assertTrue(summary["payload"]["forced"])

    def test_pull_request_event(self) -> None:
        payload = {
            "action": "opened",
            "repository": {"full_name": "octo/duobao"},
            "pull_request": {
                "number": 7,
                "title": "feat",
                "state": "open",
                "merged": False,
                "html_url": "https://gitea/octo/duobao/pulls/7",
                "user": {"login": "bob"},
                "head": {"ref": "feature", "sha": "c" * 40},
                "base": {"ref": "main", "sha": "d" * 40},
            },
        }
        summary = summarize_gitea_event("pull_request", payload)
        assert summary is not None
        self.assertEqual(summary["type"], "repo.pull_request")
        self.assertEqual(summary["payload"]["action"], "opened")
        self.assertEqual(summary["payload"]["number"], 7)
        self.assertEqual(summary["payload"]["head_sha"], "c" * 40)
        self.assertEqual(summary["payload"]["base"], "main")

    def test_unsupported_or_malformed_events_return_none(self) -> None:
        self.assertIsNone(summarize_gitea_event("issues", {"repository": {"full_name": "octo/duobao"}}))
        self.assertIsNone(summarize_gitea_event("push", {"repository": {"full_name": "invalid"}}))
        self.assertIsNone(summarize_gitea_event("push", {"repository": {}}))
        self.assertIsNone(summarize_gitea_event("pull_request", {"repository": {"full_name": "octo/duobao"}}))
        self.assertIsNone(summarize_gitea_event("push", []))  # type: ignore[arg-type]


if __name__ == "__main__":
    unittest.main()
