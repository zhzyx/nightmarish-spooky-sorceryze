"""Single isolated model worker. Production callers must launch behind the admitted host."""
import json
import sys
from urllib.parse import urlsplit

from model_api import invoke


def fixture_call(request):
    profile = request["profile"]
    url = urlsplit(profile["endpoint"])
    if url.scheme != "http" or url.hostname not in {"127.0.0.1","::1"}:
        raise ValueError("模拟执行仅接受本机回环服务")
    return invoke(profile,request["text"],request.get("images",[]),"daqian-fixture")


if __name__ == "__main__":
    # Only the synthetic transport harness is directly executable. The live transport
    # function is called from the admitted host, which owns the signed mandate and budgets.
    try:
        if sys.argv[1:] != ["--fixture"]:
            raise ValueError("生产派发需要已准入的共工宿主")
        print(json.dumps(fixture_call(json.load(sys.stdin)),ensure_ascii=False))
    except (KeyError, ValueError, OSError) as error:
        print(json.dumps({"error":str(error)},ensure_ascii=False))
        sys.exit(1)
