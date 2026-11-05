"""Host transport adapters. Invocation, admission, budget and tool authority belong to the caller."""
import json
import urllib.error
import urllib.parse
import urllib.request

PROTOCOLS = ("responses", "chat-completions", "anthropic-messages", "gemini-generate-content")


def endpoint(value):
    url = urllib.parse.urlsplit(value)
    local = url.scheme == "http" and url.hostname in {"localhost", "127.0.0.1", "::1"}
    if (url.scheme != "https" and not local) or not url.hostname or url.username or url.password or url.query or url.fragment:
        raise ValueError("请使用不含凭据的 HTTPS 地址，或本机 HTTP 地址")
    return value


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def request_data(profile, text, images, key, limit):
    model = profile["model"]
    protocol = profile["protocol"]
    headers = {"Content-Type":"application/json"}
    if protocol == "anthropic-messages":
        headers.update({"x-api-key":key, "anthropic-version":"2023-06-01"})
        content = [{"type":"image","source":{"type":"base64","media_type":image["mime"],"data":image["data"]}} for image in images]
        content.append({"type":"text","text":text})
        body = {"model":model,"max_tokens":limit,"messages":[{"role":"user","content":content}]}
    elif protocol == "gemini-generate-content":
        headers["x-goog-api-key"] = key
        parts = [{"inlineData":{"mimeType":image["mime"],"data":image["data"]}} for image in images]
        parts.append({"text":text})
        body = {"contents":[{"role":"user","parts":parts}],"generationConfig":{"maxOutputTokens":limit}}
    elif protocol in {"responses","chat-completions"}:
        headers["Authorization"] = "Bearer " + key
        image_urls = ["data:" + x["mime"] + ";base64," + x["data"] for x in images]
        if protocol == "responses":
            content = [{"type":"input_image","image_url":value} for value in image_urls]
            content.append({"type":"input_text","text":text})
            body = {"model":model,"input":[{"role":"user","content":content}],"max_output_tokens":limit,"store":False}
        else:
            content = [{"type":"image_url","image_url":{"url":value}} for value in image_urls]
            content.append({"type":"text","text":text})
            body = {"model":model, "messages":[{"role":"user","content":content if images else text}],
                    "max_tokens":limit, "stream":False}
    else:
        raise ValueError("未知模型协议")
    url = profile["endpoint"]
    if protocol == "gemini-generate-content":
        if "{model}" not in url:
            raise ValueError("Gemini 地址须含 {model}，以便按所选型号调用")
        url = url.replace("{model}",urllib.parse.quote(model,safe=""))
    return endpoint(url), headers, body


def result_data(protocol, raw):
    observed = raw.get("model") or raw.get("modelVersion")
    if protocol == "anthropic-messages":
        text = "".join(x["text"] for x in raw["content"] if x.get("type") == "text")
        complete = raw.get("stop_reason") in {"end_turn","stop_sequence"}
    elif protocol == "gemini-generate-content":
        candidate = raw["candidates"][0]
        text = "".join(x.get("text","") for x in candidate["content"]["parts"] if not x.get("thought"))
        complete = candidate.get("finishReason") == "STOP"
    elif protocol == "responses":
        text = "".join(x["text"] for message in raw["output"] if message.get("type") == "message"
                       for x in message.get("content",[]) if x.get("type") == "output_text")
        complete = raw.get("status") == "completed"
    else:
        choice = raw["choices"][0]
        text = choice["message"]["content"]
        complete = choice.get("finish_reason") == "stop"
    if not complete or not isinstance(text,str) or not text.strip():
        raise ValueError("供应商未返回完整文本结果")
    return {"text":text,"observed_model":observed,"provider_request_id":raw.get("id") or raw.get("responseId")}


def invoke(profile, text, images, key=None, limit=None):
    # The admitted host may pass a catalog profile. Resolve executable bindings
    # from the personal registry before launching anything supplied by a caller.
    if profile["protocol"] in {"codex-cli", "codebuddy-cli"}:
        from contextlib import closing
        from model_catalog import database, identity, profiles
        from local_models import invoke_cli

        if limit is not None:
            raise ValueError("CLI 桥接无法强制输出 token 上限，请使用支持此预算的 API")
        with closing(database()) as db:
            registered = profiles(db).get(identity(profile))
        if registered != profile:
            raise ValueError("CLI 配置未登记在本机模型库中")
        return invoke_cli(registered, text, images)
    if key is None:
        from credentials import secret
        from model_catalog import identity

        key = secret(identity(profile))
    if limit is None:
        limit = 1024
    url, headers, body = request_data(profile,text,images,key,limit)
    req = urllib.request.Request(url, data=json.dumps(body).encode(), headers=headers, method="POST")
    try:
        opener = urllib.request.build_opener(NoRedirect())
        with opener.open(req,timeout=90) as stream:
            response = stream.read(4_000_001)
        if len(response)>4_000_000:
            raise ValueError("回复超过上限")
        return result_data(profile["protocol"],json.loads(response))
    except urllib.error.HTTPError as error:
        raise ValueError(f"模型服务 HTTP {error.code}；请核对原请求回执") from None
    except (OSError, ValueError, KeyError, IndexError, TypeError):
        raise ValueError("模型调用回执不完整，须核对原请求后再重试") from None
