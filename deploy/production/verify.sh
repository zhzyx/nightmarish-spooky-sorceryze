#!/usr/bin/env bash
# Read-only acceptance of HTTPS and personal-key authentication.
set -euo pipefail
HOST=${TIANXUAN_HOST:?set TIANXUAN_HOST}
KEY_FILE=${TIANXUAN_ACCESS_TOKEN_FILE:?set the private personal-key file}
BASE="https://$HOST"
CHECK_DIR=$(mktemp -d)
trap 'rm -rf "$CHECK_DIR"' EXIT
chmod 700 "$CHECK_DIR"

expect() {
    expected=$1; shift
    code=$(curl -sS -D "$CHECK_DIR/headers" -o "$CHECK_DIR/body" -w '%{http_code}' "$@")
    [ "$code" = "$expected" ] || { echo "HTTP assertion failed: expected $expected, got $code" >&2; exit 1; }
}
expect 302 "$BASE/"
python3 - "$CHECK_DIR/headers" "$BASE/login" <<'PY'
import pathlib,sys
headers=pathlib.Path(sys.argv[1]).read_text().splitlines()
location=next((line.partition(":")[2].strip() for line in headers if line.lower().startswith("location:")), "")
assert location in {"/login", sys.argv[2]}, "unauthenticated pages must redirect to the login URL"
PY
expect 200 "$BASE/login"
expect 401 "$BASE/api/v1/docs"
expect 401 -H 'X-Actor: forged-admin' "$BASE/api/v1/docs"
expect 401 -H 'Authorization: Bearer invalid-key' "$BASE/api/v1/docs"
expect 410 "$BASE/gate?key=obsolete-test-key"
expect 200 "$BASE/api/v1/health"
echo 'TLS and unauthenticated access: passed'
python3 - "$KEY_FILE" "$CHECK_DIR/login.json" <<'PY'
import json, pathlib, sys
pathlib.Path(sys.argv[2]).write_text(json.dumps({"key": pathlib.Path(sys.argv[1]).read_text().strip()}))
PY
expect 200 -H "Origin: $BASE" -H 'Content-Type: application/json' -c "$CHECK_DIR/cookies" --data-binary "@$CHECK_DIR/login.json" "$BASE/api/v1/auth/key-login"
for path in / /docs /issues /requirements /search /repos /settings /accounts /api/v1/auth/me /api/v1/docs /api/v1/issues; do
    expect 200 -b "$CHECK_DIR/cookies" "$BASE$path"
done
expect 403 -b "$CHECK_DIR/cookies" -H 'Origin: https://untrusted.example' -H 'Content-Type: application/json' -d '{}' "$BASE/api/v1/docs"
echo 'Authenticated pages, API and cross-origin rejection: passed'
expect 200 -b "$CHECK_DIR/cookies" "$BASE/api/v1/docs"
DOC_ID=$(python3 - "$CHECK_DIR/body" <<'PY'
import json,sys
with open(sys.argv[1]) as stream:
    docs=json.load(stream)["docs"]
assert docs, "a real document is required for export acceptance"
print(docs[0]["id"])
PY
)
for format in md html docx pdf; do
    expect 200 -b "$CHECK_DIR/cookies" "$BASE/api/v1/docs/$DOC_ID/export/file?format=$format"
    test -s "$CHECK_DIR/body"
    python3 - "$format" "$CHECK_DIR/body" <<'PY'
import pathlib,sys
content=pathlib.Path(sys.argv[2]).read_bytes()
if sys.argv[1]=="pdf": assert content.startswith(b"%PDF")
if sys.argv[1]=="docx": assert content.startswith(b"PK")
PY
done
echo 'Document exports: passed'
echo 'PRODUCTION_READONLY_ACCEPTANCE_OK'
