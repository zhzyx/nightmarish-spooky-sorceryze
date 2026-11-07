"""Host transport adapters. Invocation, admission, budget and tool authority belong to the caller."""

# Load from the installed host tree, independently of the selected workspace or cwd.
import importlib.util
import json
import urllib.error
import urllib.request
from pathlib import Path

_protocol_path = Path(__file__).resolve().parents[3] / "platforms/ai-access/daqian/http_protocols.py"
_spec = importlib.util.spec_from_file_location("daqian_http_protocols", _protocol_path)
if _spec is None or _spec.loader is None:
    raise ImportError("Cannot load the Tianshu HTTP protocol adapter")
_protocols = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_protocols)
PROTOCOLS = _protocols.PROTOCOLS
endpoint = _protocols.endpoint
NoRedirect = _protocols.NoRedirect
request_data = _protocols.request_data
result_data = _protocols.result_data


def invoke(profile, text, images, key=None, limit=None):
    # The admitted host may pass a catalog profile. Resolve executable bindings
    # from the personal registry before launching anything supplied by a caller.
    if profile["protocol"] in {"codex-cli", "codebuddy-cli"}:
        from contextlib import closing

        from local_models import invoke_cli
        from model_catalog import database, identity, profiles

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
    url, headers, body = request_data(profile, text, images, key, limit)
    req = urllib.request.Request(url, data=json.dumps(body).encode(), headers=headers, method="POST")
    try:
        opener = urllib.request.build_opener(NoRedirect())
        with opener.open(req, timeout=90) as stream:
            response = stream.read(4_000_001)
        if len(response) > 4_000_000:
            raise ValueError("回复超过上限")
        return result_data(profile["protocol"], json.loads(response))
    except urllib.error.HTTPError as error:
        raise ValueError(f"模型服务 HTTP {error.code}；请核对原请求回执") from None
    except (OSError, ValueError, KeyError, IndexError, TypeError):
        raise ValueError("模型调用回执不完整，须核对原请求后再重试") from None
