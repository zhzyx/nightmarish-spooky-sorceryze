"""Check one bounded UTF-8 document in a Duobao input snapshot."""

import os
from pathlib import Path


def main():
    root = Path(os.environ["DUOBAO_INPUT"]).resolve(strict=True)
    candidates = list(root.glob("*-text/output"))
    if len(candidates) != 1:
        raise ValueError("Expected one text output")
    path = candidates[0]
    if path.is_symlink() or not path.is_file() or path.resolve(strict=True) != path:
        raise ValueError("Expected a regular snapshot file")
    with path.open("rb") as stream:
        data = stream.read(65537)
    if len(data) > 65536 or not data.decode("utf-8").strip():
        raise ValueError("Expected a nonempty UTF-8 document up to 65536 bytes")


if __name__ == "__main__":
    main()
