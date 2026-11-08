"""Read Windows Internet Settings without modifying caller environment."""

import json
import os
import sys
import urllib.request
from urllib.parse import urlsplit


def windows_https_proxy_environment(hosts, env):
    """Return HTTPS_PROXY/NO_PROXY delta; explicit environment always wins."""
    if sys.platform != "win32" or any(
        key.lower() in {"https_proxy", "http_proxy", "all_proxy", "no_proxy", "openai_base_url"} and value
        for key, value in env.items()
    ):
        return {}
    try:
        proxy = urllib.request.getproxies_registry().get("https", "")
        if not proxy or any(c in proxy for c in "\r\n"):
            return {}
        if "://" not in proxy:
            proxy = "http://" + proxy
        parsed = urlsplit(proxy)
        if (
            parsed.scheme not in {"http", "https", "socks5", "socks5h"}
            or not parsed.hostname
            or parsed.username
            or parsed.password
        ):
            return {}
        if any(not isinstance(host, str) or not host or any(c in host for c in "/\r\n, ") for host in hosts):
            return {}
        bypass = [host for host in hosts if urllib.request.proxy_bypass_registry(host)]
        result = {"HTTPS_PROXY": proxy}
        if bypass:
            result["NO_PROXY"] = ",".join(bypass)
        return result
    except (OSError, ValueError, AttributeError):
        return {}


if __name__ == "__main__":
    print(json.dumps(windows_https_proxy_environment(sys.argv[1:], os.environ)))
