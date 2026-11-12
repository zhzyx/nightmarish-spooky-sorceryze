"""Synthetic transport identity regressions; no credentials or provider calls."""

import io
import json
import unittest
from unittest.mock import patch

from adapters import MODEL_ID_MAX_BYTES, TransportUnknown, call


class ModelProvenanceTests(unittest.TestCase):
    def payload(self, protocol):
        if protocol == "chat-completions":
            return {"choices": [{"message": {"content": "ok"}, "finish_reason": "stop"}]}
        if protocol == "ollama-chat":
            return {"message": {"content": "ok"}, "done": True}
        return {"text": "ok", "finish_reason": "stop"}

    def profile(self, protocol, model="requested-model"):
        return {"protocol": protocol, "model": model, "endpoint": "http://127.0.0.1/unused"}

    def invoke(self, profile, payload):
        with patch("adapters.urllib.request.build_opener") as opener:
            opener.return_value.open.return_value = io.BytesIO(json.dumps(payload).encode())
            response = call(profile, [{"role": "user", "content": "synthetic"}], 10)
            request = opener.return_value.open.call_args.args[0]
            self.assertEqual(json.loads(request.data)["model"], profile["model"])
        return response

    def test_supported_protocols_preserve_aliases_without_verifying_identity(self):
        for protocol in ("chat-completions", "ollama-chat", "gonggong-json"):
            for model in (
                "requested-model",
                "different-observed-model",
                "requested-model-2026-11-01",
                "library/local-model:latest",
                "m" * MODEL_ID_MAX_BYTES,
                "模" * 170,
            ):
                with self.subTest(protocol=protocol, model=model):
                    response = self.invoke(
                        self.profile(protocol),
                        {
                            **self.payload(protocol),
                            "model": model,
                            "requested_model": "forged",
                            "observed_model": "forged",
                            "protocol": "forged",
                            "model_identity_verified": True,
                        },
                    )
                    self.assertEqual(response["requested_model"], "requested-model")
                    self.assertEqual(response["observed_model"], model)
                    self.assertEqual(response["protocol"], protocol)
                    self.assertEqual(response["observed_model_source"], "response.model")
                    self.assertEqual(response["observed_model_status"], "provider_reported")
                    self.assertIs(response["model_identity_verified"], False)

    def test_missing_null_and_malformed_model_never_fabricate_identity(self):
        malformed = [
            "",
            " ",
            " padded",
            "trailing ",
            "line\nbreak",
            "control\x00",
            "\ud800",
            42,
            True,
            1.5,
            {},
            [],
            ["model"],
            "m" * (MODEL_ID_MAX_BYTES + 1),
            "模" * 171,
        ]
        for protocol in ("chat-completions", "ollama-chat", "gonggong-json"):
            for fields in ({}, {"model": None}, *({"model": value} for value in malformed)):
                with self.subTest(protocol=protocol, fields=fields):
                    response = self.invoke(self.profile(protocol), {**self.payload(protocol), **fields})
                    self.assertIsNone(response["observed_model"])
                    self.assertIsNone(response["observed_model_source"])
                    self.assertEqual(
                        response["observed_model_status"], "unavailable" if fields.get("model") is None else "invalid"
                    )
                    self.assertEqual(response["requested_model"], "requested-model")
                    self.assertEqual(response["text"], "ok")
                    self.assertIs(response["model_identity_verified"], False)

    def test_invalid_request_identity_rejected_before_network(self):
        for model in (None, 1, True, {}, [], "", " ", "m" * 513, "模" * 171, "\ud800", "x\ny"):
            with self.subTest(model=model), patch("adapters.urllib.request.build_opener") as opener:
                with self.assertRaises(ValueError):
                    call(self.profile("chat-completions", model), [], 10)
                opener.assert_not_called()

    def test_malformed_response_still_requires_reconciliation(self):
        for protocol in ("chat-completions", "ollama-chat", "gonggong-json"):
            with self.subTest(protocol=protocol):
                with self.assertRaises(TransportUnknown):
                    self.invoke(self.profile(protocol), {"model": "reported-without-valid-result"})


if __name__ == "__main__":
    unittest.main()
