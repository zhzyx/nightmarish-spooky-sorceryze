"""Create an explicitly identified release derivative with relative diagnostic paths."""

import argparse
import hashlib
import json
import struct
from pathlib import Path


def sha(data):
    return hashlib.sha256(data).hexdigest()


def pe_sections(data):
    if data[:2] != b"MZ":
        raise ValueError("Not a PE image")
    pe = struct.unpack_from("<I", data, 0x3C)[0]
    if data[pe : pe + 4] != b"PE\0\0":
        raise ValueError("Invalid PE signature")
    count = struct.unpack_from("<H", data, pe + 6)[0]
    optional = pe + 24
    optional_size = struct.unpack_from("<H", data, pe + 20)[0]
    if struct.unpack_from("<H", data, optional)[0] != 0x20B:
        raise ValueError("Only PE32+ is supported")
    if any(struct.unpack_from("<II", data, optional + 112 + 4 * 8)):
        raise ValueError("Signed images must not be transformed")
    if struct.unpack_from("<I", data, optional + 64)[0]:
        raise ValueError("Nonzero PE checksum requires a separately reviewed build")
    sections = []
    for index in range(count):
        pos = optional + optional_size + index * 40
        name = data[pos : pos + 8].rstrip(b"\0").decode("ascii")
        size, start = struct.unpack_from("<II", data, pos + 16)
        flags = struct.unpack_from("<I", data, pos + 36)[0]
        if start + size > len(data):
            raise ValueError("Section outside image")
        sections.append({"name": name, "start": start, "size": size, "flags": flags})
    return sections


def prepare(source, destination, policy, source_root, workspace):
    original = source.read_bytes()
    if sha(original) != policy["input_sha256"]:
        raise ValueError("Unreviewed editor digest")
    prefix = (str(source_root.resolve()).replace("/", "\\").rstrip("\\") + "\\").encode("ascii")
    if sha(prefix) != policy["source_prefix_sha256"] or len(prefix) < 2:
        raise ValueError("Unreviewed source prefix")
    replacement = b"./" * (len(prefix) // 2) + (b"/" if len(prefix) % 2 else b"")
    sections = pe_sections(original)
    expected = sorted(item["offset"] for item in policy["paths"])
    actual = []
    offset = original.find(prefix)
    while offset >= 0:
        actual.append(offset)
        offset = original.find(prefix, offset + len(prefix))
    if actual != expected or len(expected) != len(set(expected)):
        raise ValueError("Unexpected or duplicate path occurrence")
    changed = bytearray(original)
    records = []
    for item in sorted(policy["paths"], key=lambda p: p["offset"]):
        offset = item["offset"]
        end = original.index(b"\0", offset)
        suffix = original[offset + len(prefix) : end]
        if sha(suffix) != item["suffix_sha256"]:
            raise ValueError("Unexpected diagnostic string suffix")
        owner = [s for s in sections if s["start"] <= offset and end < s["start"] + s["size"]]
        if (
            len(owner) != 1
            or owner[0]["name"] != ".rdata"
            or owner[0]["flags"] & 0xA0000000
            or not owner[0]["flags"] & 0x40000000
        ):
            raise ValueError("Path is not exclusively in read-only non-executable .rdata")
        target = (workspace / suffix.decode("ascii").replace("\\", "/")).resolve()
        target.relative_to(workspace.resolve())
        if (
            not target.is_file()
            or target.relative_to(workspace.resolve()).as_posix() != item["source_file"]
            or sha(target.read_bytes()) != item["source_sha256"]
        ):
            raise ValueError("Diagnostic path does not match reviewed source")
        changed[offset : offset + len(prefix)] = replacement
        records.append({
            "offset": offset,
            "source_file": item["source_file"],
            "preceded_by_nul": original[offset - 1] == 0,
        })
    cursor = 0
    for offset in expected:
        if original[cursor:offset] != changed[cursor:offset]:
            raise ValueError("Unexpected changed byte outside path prefix")
        cursor = offset + len(prefix)
    if original[cursor:] != changed[cursor:] or len(original) != len(changed) or prefix in changed:
        raise ValueError("Transformation integrity failure")
    executable = {}
    for section in sections:
        if section["flags"] & 0x20000000:
            start, size = section["start"], section["size"]
            if original[start : start + size] != changed[start : start + size]:
                raise ValueError("Executable section changed")
            executable[section["name"]] = sha(original[start : start + size])
    if destination.exists():
        raise ValueError("Release derivative destination must be new")
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(changed)
    return {
        "method": "reviewed_equal_length_readonly_diagnostic_prefix_v1",
        "input_sha256": sha(original),
        "output_sha256": sha(changed),
        "bytes": len(changed),
        "prefix_bytes": len(prefix),
        "relative_prefix": replacement.decode(),
        "paths": records,
        "executable_section_sha256": executable,
        "all_other_bytes_unchanged": True,
        "signed_input": False,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("input", "output", "policy", "source-root", "workspace", "report"):
        parser.add_argument("--" + name, type=Path, required=True)
    args = parser.parse_args()
    result = prepare(
        args.input, args.output, json.loads(args.policy.read_text(encoding="utf-8")), args.source_root, args.workspace
    )
    args.report.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8", newline="\n")


if __name__ == "__main__":
    main()
