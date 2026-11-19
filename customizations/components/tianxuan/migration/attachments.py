"""Collect referenced GitHub uploads without forwarding credentials to linked sites."""
import argparse
import hashlib
import json
import os
import tempfile
from pathlib import Path
from urllib.parse import urlsplit
from urllib.request import build_opener, HTTPRedirectHandler


def checked_url(url):
    parsed = urlsplit(url)
    host = parsed.hostname or ""
    if (parsed.scheme != "https" or parsed.username or parsed.password or parsed.port not in (None, 443)
            or not (host == "github.com" or host.endswith(".githubusercontent.com"))):
        raise ValueError("unexpected attachment host")
    return url


class CheckedRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return super().redirect_request(req, fp, code, msg, headers, checked_url(newurl))


def capture(manifest, output):
    output.mkdir(parents=True, exist_ok=True)
    opener = build_opener(CheckedRedirect())
    records = {}
    failures = {}
    checkpoint = output / "attachments.json"
    previous = json.loads(checkpoint.read_bytes()).get("records", {}) if checkpoint.exists() else {}

    def save():
        with tempfile.NamedTemporaryFile(dir=output, delete=False) as stream:
            stream.write(json.dumps({"records": records, "failures": failures}, indent=2).encode())
            staged = Path(stream.name)
        os.replace(staged, checkpoint)

    with manifest.open(encoding="utf-8") as source:
        for raw in source:
            row = json.loads(raw)
            if row["kind"] != "attachment":
                continue
            key = row["source_id"]
            temp = None
            try:
                url = checked_url(row["content"]["url"])
                entry = previous.get(key, {})
                sha = entry.get("sha256", "")
                if len(sha) == 64 and all(c in "0123456789abcdef" for c in sha):
                    cached = output / sha
                    if cached.is_file() and cached.stat().st_size == entry.get("bytes"):
                        with cached.open("rb") as stream:
                            if hashlib.file_digest(stream, "sha256").hexdigest() == sha:
                                records[key] = entry
                                continue
                with opener.open(url, timeout=40) as response, tempfile.NamedTemporaryFile(
                        dir=output, delete=False) as stream:
                    temp = Path(stream.name)
                    if response.headers.get_content_type() == "text/html":
                        raise ValueError("received HTML instead of attachment")
                    digest = hashlib.sha256()
                    size = 0
                    while chunk := response.read(1024 * 1024):
                        stream.write(chunk)
                        digest.update(chunk)
                        size += len(chunk)
                    length = response.headers.get("Content-Length")
                    if length is not None and size != int(length):
                        raise ValueError("incomplete response")
                name = digest.hexdigest()
                os.replace(temp, output / name)
                records[key] = {"sha256":name, "bytes":size}
            except (OSError, ValueError) as exc:
                failures[key] = type(exc).__name__ + " " + str(getattr(exc, "code", ""))
            finally:
                if temp:
                    temp.unlink(missing_ok=True)
            save()
    save()
    result = {"records": records, "failures": failures}

    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("records", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    result = capture(args.records, args.output)
    print(json.dumps({key:len(items) for key,items in result.items()}))
    raise SystemExit(bool(result["failures"]))
