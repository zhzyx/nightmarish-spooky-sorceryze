#!/usr/bin/env bash

set -euo pipefail

echo ".gitignore validation..."

# Stream tracked names instead of exceeding the host argument limit.
# NUL delimiters preserve spaces and newlines. Command errors must fail CI.
paths=$(mktemp)
matches=$(mktemp)
trap 'rm -f "$paths" "$matches"' EXIT
git ls-files -z > "$paths"
if git -c core.ignorecase=true check-ignore --verbose --no-index --stdin -z < "$paths" > "$matches"; then
    :
else
    result=$?
    # Exit 1 means that no rules match; other failures must propagate.
    if [ "$result" -ne 1 ]; then
        exit "$result"
    fi
fi

# Verbose NUL records: source, line, pattern, path. Negations are inclusions.
awk -v RS='\0' '
    NR % 4 == 3 { ignored = substr($0, 1, 1) != "!" }
    NR % 4 == 0 && ignored { print $0; failed = 1 }
    END { exit failed ? 1 : 0 }
' "$matches"
