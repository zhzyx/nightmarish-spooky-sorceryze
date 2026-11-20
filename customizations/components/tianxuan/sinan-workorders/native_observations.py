"""Public projection of provider evidence from authenticated role receipts."""

import re

OBSERVATION_PROTOCOL = "native-model-observation-v1"
TOKEN_FIELDS = {
    "inputTokens",
    "cachedInputTokens",
    "cacheWriteInputTokens",
    "outputTokens",
    "reasoningOutputTokens",
    "totalTokens",
}


def public_model_name(value):
    if isinstance(value, str) and re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9.:-]{0,127}", value):
        return value
    return None


def model_observation(model, raw):
    # Only provider-reported token counters and the observed model may leave
    # the node. Last and cumulative counts keep their provider semantics.
    usage = {}
    if isinstance(raw, dict):
        for group in ("last", "total"):
            counts = raw.get(group)
            if isinstance(counts, dict):
                facts = {k: v for k, v in counts.items() if k in TOKEN_FIELDS and type(v) is int and v >= 0}
                if facts:
                    usage[group] = facts
    return {"provider_model": public_model_name(model), "usage": usage or None}


def valid_producer_calls(calls):
    """Only completed, numbered provider calls from the original execution journal."""
    if not isinstance(calls, list) or not 1 <= len(calls) <= 100:
        return False
    previous = 0
    for call in calls:
        if (
            not isinstance(call, dict)
            or set(call) != {"call", "source", "requested_model", "provider_model", "usage"}
            or type(call["call"]) is not int
            or not previous < call["call"] <= 100
            or call["source"] not in ("codex-cli", "local-agent", None)
            or call["requested_model"] != public_model_name(call["requested_model"])
            or model_observation(call["provider_model"], call["usage"])
            != {"provider_model": call["provider_model"], "usage": call["usage"]}
        ):
            return False
        previous = call["call"]
    return True
