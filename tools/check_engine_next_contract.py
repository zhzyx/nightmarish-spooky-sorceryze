"""Audit Engine Next source and link-input boundaries without building Godot."""

import argparse
import hashlib
import json
import os
import posixpath
import re
import sys
from pathlib import Path, PurePosixPath

STANDARD_ANGLE_INCLUDES = frozenset({
    "algorithm",
    "any",
    "array",
    "assert.h",
    "atomic",
    "barrier",
    "bit",
    "bitset",
    "cassert",
    "cctype",
    "cerrno",
    "cfenv",
    "cfloat",
    "chrono",
    "charconv",
    "cinttypes",
    "climits",
    "cmath",
    "codecvt",
    "compare",
    "complex",
    "concepts",
    "condition_variable",
    "coroutine",
    "csetjmp",
    "csignal",
    "cstdarg",
    "cstddef",
    "cstdint",
    "cstdio",
    "cstdlib",
    "cstring",
    "ctime",
    "ctype.h",
    "cwchar",
    "cwctype",
    "deque",
    "errno.h",
    "exception",
    "execution",
    "expected",
    "fenv.h",
    "filesystem",
    "float.h",
    "format",
    "forward_list",
    "fstream",
    "functional",
    "future",
    "generator",
    "initializer_list",
    "inttypes.h",
    "iomanip",
    "ios",
    "iosfwd",
    "iostream",
    "istream",
    "iterator",
    "latch",
    "limits",
    "limits.h",
    "list",
    "locale",
    "locale.h",
    "map",
    "math.h",
    "memory",
    "memory_resource",
    "mutex",
    "new",
    "numbers",
    "numeric",
    "optional",
    "ostream",
    "print",
    "queue",
    "random",
    "ranges",
    "ratio",
    "regex",
    "scoped_allocator",
    "semaphore",
    "set",
    "setjmp.h",
    "shared_mutex",
    "signal.h",
    "source_location",
    "span",
    "spanstream",
    "sstream",
    "stack",
    "stacktrace",
    "stdarg.h",
    "stdbool.h",
    "stddef.h",
    "stdexcept",
    "stdint.h",
    "stdio.h",
    "stdlib.h",
    "stop_token",
    "streambuf",
    "string",
    "string.h",
    "string_view",
    "strstream",
    "syncstream",
    "system_error",
    "thread",
    "time.h",
    "tuple",
    "type_traits",
    "typeindex",
    "typeinfo",
    "uchar.h",
    "unordered_map",
    "unordered_set",
    "utility",
    "valarray",
    "variant",
    "vector",
    "version",
    "wchar.h",
    "wctype.h",
})
IDENTIFIER = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
INCLUDE = re.compile(r'^[ \t]*#[ \t]*include[ \t]*([<"])([^<>"\r\n]+)[>"]')
INCLUDE_START = re.compile(r"^[ \t]*#[ \t]*include\b")
RAW_STRING = re.compile(r'(?:u8|u|U|L)?R"([^\s()\\]{0,16})\(.*?\)\1"', re.DOTALL)
SHA256 = re.compile(r"[a-f0-9]{64}")
IDENTITY = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*")
TOP_LEVEL = {
    "schema_version",
    "contract_id",
    "target",
    "source_roots",
    "public_header_roots",
    "source_extensions",
    "godot_roots",
    "third_party_roots",
    "allowed_angle_include_prefixes",
    "forbidden_cpp_tokens",
    "forbidden_cpp_prefixes",
    "link",
}
LINK_LEVEL = {
    "allowed_local_roots",
    "allowed_producers",
    "allowed_system_libraries",
    "forbidden_library_name_fragments",
    "forbidden_runtime_names",
    "forbidden_runtime_suffixes",
}


def _pairs(items):
    result = {}
    for key, value in items:
        if key in result:
            raise ValueError("Duplicate JSON field: " + key)
        result[key] = value
    return result


def load_json(path):
    return json.loads(
        Path(path).read_text(encoding="utf-8"),
        object_pairs_hook=_pairs,
        parse_constant=lambda value: (_ for _ in ()).throw(ValueError("Nonfinite JSON: " + value)),
    )


def _relative(value, field):
    if not isinstance(value, str) or not value or "\\" in value or "\0" in value or re.match(r"^[A-Za-z]:", value):
        raise ValueError("Invalid repository-relative path in " + field)
    path = PurePosixPath(value)
    if path.is_absolute() or value != path.as_posix() or any(part in {"", ".", ".."} for part in path.parts):
        raise ValueError("Non-canonical repository-relative path in " + field)
    return value


def _strings(document, key, *, allow_empty=True):
    value = document.get(key)
    if not isinstance(value, list) or (not allow_empty and not value) or any(not isinstance(x, str) for x in value):
        raise ValueError("Expected a string list for " + key)
    if len(set(value)) != len(value):
        raise ValueError("Duplicate list entry for " + key)
    return value


def _inside(path, root):
    return path == root or path.startswith(root + "/")


def validate_contract(document):
    if not isinstance(document, dict) or set(document) != TOP_LEVEL:
        raise ValueError("Contract fields must exactly match schema 1")
    if document["schema_version"] != 1:
        raise ValueError("Unsupported contract schema")
    if not isinstance(document["contract_id"], str) or not IDENTITY.fullmatch(document["contract_id"]):
        raise ValueError("Invalid contract_id")
    if not isinstance(document["target"], str) or not re.fullmatch(r"[a-z0-9]+(?:[_-][a-z0-9]+)*", document["target"]):
        raise ValueError("Invalid target")
    for key in ("source_roots", "public_header_roots", "godot_roots", "third_party_roots"):
        values = _strings(document, key, allow_empty=key != "source_roots")
        for value in values:
            _relative(value, key)
    for value in document["third_party_roots"]:
        if not _inside(value, "thirdparty"):
            raise ValueError("Third-party roots must be below thirdparty/")
    extensions = _strings(document, "source_extensions", allow_empty=False)
    if any(not value.startswith(".") or value != value.lower() for value in extensions):
        raise ValueError("Source extensions must be lowercase suffixes")
    prefixes = _strings(document, "allowed_angle_include_prefixes")
    for value in prefixes:
        if not value or "\\" in value or "\0" in value or posixpath.isabs(value):
            raise ValueError("Invalid angle include prefix")
        normalized = posixpath.normpath(value.rstrip("/"))
        if normalized in {"", ".", ".."} or normalized.startswith("../"):
            raise ValueError("Escaping angle include prefix")
    tokens = _strings(document, "forbidden_cpp_tokens")
    if any(not IDENTIFIER.fullmatch(value) for value in tokens):
        raise ValueError("Forbidden C++ tokens must be identifiers")
    token_prefixes = _strings(document, "forbidden_cpp_prefixes")
    if any(not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", value) for value in token_prefixes):
        raise ValueError("Forbidden C++ prefixes must be identifiers or identifier prefixes")
    for source in document["source_roots"]:
        for godot in document["godot_roots"]:
            if _inside(source, godot) or _inside(godot, source):
                raise ValueError("Source roots and Godot roots overlap")
    for public in document["public_header_roots"]:
        if not any(_inside(public, source) for source in document["source_roots"]):
            raise ValueError("Public header roots must be below a source root")
    link = document["link"]
    if not isinstance(link, dict) or set(link) != LINK_LEVEL:
        raise ValueError("Link fields must exactly match schema 1")
    for key in (
        "allowed_local_roots",
        "allowed_producers",
        "allowed_system_libraries",
        "forbidden_library_name_fragments",
        "forbidden_runtime_names",
        "forbidden_runtime_suffixes",
    ):
        _strings(link, key)
    for value in link["allowed_local_roots"]:
        _relative(value, "link.allowed_local_roots")
        if any(_inside(value, godot) for godot in document["godot_roots"]):
            raise ValueError("Link allowlist cannot contain Godot roots")
    for value in link["forbidden_runtime_names"]:
        if PurePosixPath(value).name != value or not value:
            raise ValueError("Forbidden runtime names must be file names")
    if any(not value.startswith(".") for value in link["forbidden_runtime_suffixes"]):
        raise ValueError("Forbidden runtime suffixes must start with a dot")
    return document


def code_only(text, preserve_literals=False):
    """Blank comments and optionally literals while preserving line positions."""
    text = RAW_STRING.sub(lambda match: "\n" * match.group(0).count("\n"), text)
    output = list(text)
    state = "code"
    index = 0
    while index < len(text):
        char = text[index]
        following = text[index + 1] if index + 1 < len(text) else ""
        if state == "code":
            if char == "/" and following == "/":
                output[index] = output[index + 1] = " "
                state = "line_comment"
                index += 2
                continue
            if char == "/" and following == "*":
                output[index] = output[index + 1] = " "
                state = "block_comment"
                index += 2
                continue
            if char in {'"', "'"}:
                quote = char
                if not preserve_literals:
                    output[index] = " "
                state = "string"
                index += 1
                continue
        elif state == "line_comment":
            if char == "\n":
                state = "code"
            else:
                output[index] = " "
        elif state == "block_comment":
            if char == "*" and following == "/":
                output[index] = output[index + 1] = " "
                state = "code"
                index += 2
                continue
            if char != "\n":
                output[index] = " "
        elif state == "string":
            if char == "\\":
                if not preserve_literals:
                    output[index] = " "
                    if following and following != "\n":
                        output[index + 1] = " "
                index += 2
                continue
            elif char == quote:
                if not preserve_literals:
                    output[index] = " "
                state = "code"
            elif not preserve_literals and char != "\n":
                output[index] = " "
        index += 1
    return "".join(output)


def violation(code, path, line=None, **details):
    item = {"code": code, "path": path}
    if line is not None:
        item["line"] = line
    item.update(details)
    return item


class SourceAudit:
    def __init__(self, root, contract):
        self.root = root
        self.contract = contract
        self.violations = []
        self.sources = set()
        self.visited = set()
        self.includes = 0

    def discover(self):
        def fail(error):
            raise error

        for name in self.contract["source_roots"]:
            base = self.root / name
            if not base.exists():
                continue
            if base.is_symlink() or not base.is_dir():
                self.violations.append(violation("invalid_source_root", name))
                continue
            for directory, folders, files in os.walk(base, onerror=fail, followlinks=False):
                folders.sort()
                files.sort()
                for folder in list(folders):
                    path = Path(directory) / folder
                    if path.is_symlink():
                        self.violations.append(violation("linked_source_path", path.relative_to(self.root).as_posix()))
                        folders.remove(folder)
                for filename in files:
                    path = Path(directory) / filename
                    relative = path.relative_to(self.root).as_posix()
                    if path.is_symlink():
                        self.violations.append(violation("linked_source_path", relative))
                    elif path.suffix in self.contract["source_extensions"]:
                        if not path.is_file():
                            self.violations.append(violation("invalid_source_file", relative))
                        else:
                            self.sources.add(relative)

    def classify(self, path):
        if path == ".." or path.startswith("../") or PurePosixPath(path).is_absolute():
            return "include_path_escape"
        if any(_inside(path, godot) for godot in self.contract["godot_roots"]):
            return "godot_include"
        allowed = [*self.contract["source_roots"], *self.contract["third_party_roots"]]
        if any(_inside(path, root) for root in allowed):
            return "allowed"
        return "undeclared_local_include"

    def scan(self, relative):
        if relative in self.visited:
            return
        self.visited.add(relative)
        path = self.root / relative
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeError):
            self.violations.append(violation("source_read_failure", relative))
            return
        directives = code_only(text, preserve_literals=True)
        code = code_only(text)
        for line_number, (directive_line, code_line) in enumerate(zip(directives.splitlines(), code.splitlines()), 1):
            match = INCLUDE.match(directive_line)
            if match:
                self.include(relative, line_number, *match.groups())
            elif INCLUDE_START.match(directive_line):
                self.violations.append(violation("invalid_include", relative, line_number))
            for token in IDENTIFIER.finditer(code_line):
                value = token.group(0)
                if value in self.contract["forbidden_cpp_tokens"] or any(
                    value.startswith(prefix) for prefix in self.contract["forbidden_cpp_prefixes"]
                ):
                    self.violations.append(violation("forbidden_cpp_token", relative, line_number, token=value))
                    break

    def include(self, source, line_number, delimiter, target):
        normalized_target = posixpath.normpath(target) if target else target
        if (
            not target
            or "\\" in target
            or "\0" in target
            or PurePosixPath(target).is_absolute()
            or re.match(r"^[A-Za-z]:", target)
        ):
            self.violations.append(violation("invalid_include_path", source, line_number, include=target))
            return
        if delimiter == "<" and (
            target in STANDARD_ANGLE_INCLUDES
            or any(
                target == prefix or target.startswith(prefix)
                for prefix in self.contract["allowed_angle_include_prefixes"]
            )
        ):
            return
        if delimiter == "<":
            candidates = [normalized_target]
        else:
            parent = PurePosixPath(source).parent.as_posix()
            candidates = [posixpath.normpath(posixpath.join(parent, target))]
            candidates.extend(
                posixpath.normpath(posixpath.join(public_root, target))
                for public_root in self.contract["public_header_roots"]
            )
            candidates.append(normalized_target)
        candidates = list(dict.fromkeys(candidates))
        selected = None
        fallback = None
        for candidate in candidates:
            classification = self.classify(candidate)
            path = self.root / candidate
            if path.exists() or path.is_symlink():
                selected = candidate
                break
            if fallback is None and classification in {"include_path_escape", "godot_include"}:
                fallback = (candidate, classification)
        if selected is None:
            if fallback is not None:
                candidate, code = fallback
                self.violations.append(violation(code, source, line_number, include=target, resolved=candidate))
            else:
                code = "unknown_angle_include" if delimiter == "<" else "missing_include"
                self.violations.append(violation(code, source, line_number, include=target))
            return
        classification = self.classify(selected)
        if classification == "undeclared_local_include" and normalized_target.startswith("../"):
            classification = "include_path_escape"
        if classification != "allowed":
            self.violations.append(violation(classification, source, line_number, include=target, resolved=selected))
            return
        path = self.root / selected
        if path.is_symlink() or not path.is_file():
            self.violations.append(violation("invalid_local_include", source, line_number, include=target))
            return
        self.includes += 1
        self.scan(selected)

    def run(self, require_sources=False):
        self.discover()
        for source in sorted(self.sources):
            self.scan(source)
        if require_sources and not self.sources:
            self.violations.append(violation("no_sources", "engine_next"))
        self.violations.sort(
            key=lambda item: (item["path"], item.get("line", 0), item["code"], item.get("include", ""))
        )
        return {
            "passed": not self.violations,
            "state": "no_sources"
            if not self.sources
            else ("sources_passed" if not self.violations else "sources_failed"),
            "source_files": len(self.sources),
            "local_includes": self.includes,
            "violations": self.violations,
        }


def audit_sources(root, contract, require_sources=False):
    return SourceAudit(Path(root).resolve(), contract).run(require_sources)


def _manifest_artifact(root, contract, entry, kind):
    if not isinstance(entry, dict) or set(entry) != {"path", "sha256"}:
        return [violation("invalid_artifact_record", kind)]
    name = entry["path"]
    digest = entry["sha256"]
    if not isinstance(name, str) or not isinstance(digest, str) or not SHA256.fullmatch(digest):
        return [violation("invalid_artifact_record", kind)]
    try:
        _relative(name, kind)
    except ValueError:
        return [violation("invalid_artifact_path", kind, path=name)]
    failures = []
    if any(_inside(name, godot) for godot in contract["godot_roots"]):
        failures.append(violation("godot_link_input", name, artifact_kind=kind))
    if not any(_inside(name, allowed) for allowed in contract["link"]["allowed_local_roots"]):
        failures.append(violation("link_path_outside_allowlist", name, artifact_kind=kind))
    basename = PurePosixPath(name).name.lower()
    if any(fragment in basename for fragment in contract["link"]["forbidden_library_name_fragments"]):
        failures.append(violation("forbidden_library_name", name, artifact_kind=kind))
    if kind == "runtime_files" and (
        PurePosixPath(name).name in contract["link"]["forbidden_runtime_names"]
        or PurePosixPath(name).suffix in contract["link"]["forbidden_runtime_suffixes"]
    ):
        failures.append(violation("forbidden_runtime_file", name))
    path = root / name
    if path.is_symlink():
        failures.append(violation("linked_artifact", name))
    elif not path.is_file():
        failures.append(violation("missing_artifact", name))
    else:
        actual = hashlib.sha256()
        with path.open("rb") as stream:
            for block in iter(lambda: stream.read(1024 * 1024), b""):
                actual.update(block)
        if actual.hexdigest() != digest:
            failures.append(violation("artifact_sha256_mismatch", name))
    return failures


def audit_link_manifest(root, contract, manifest_path):
    root = Path(root).resolve()
    manifest_path = Path(manifest_path)
    try:
        manifest_name = manifest_path.resolve().relative_to(root).as_posix()
    except ValueError:
        manifest_name = manifest_path.name
    document = load_json(manifest_path)
    required = {"schema_version", "target", "producer", "objects", "libraries", "runtime_files", "system_libraries"}
    if not isinstance(document, dict) or set(document) != required:
        return {"passed": False, "violations": [violation("invalid_link_manifest", manifest_name)]}
    failures = []
    if document["schema_version"] != 1 or document["target"] != contract["target"]:
        failures.append(violation("link_target_mismatch", manifest_name))
    producer = document["producer"]
    if not isinstance(producer, dict) or set(producer) != {"kind", "path", "sha256"}:
        failures.append(violation("invalid_link_producer", manifest_name))
    else:
        if producer["kind"] not in contract["link"]["allowed_producers"]:
            failures.append(violation("invalid_link_producer", manifest_name))
        failures.extend(
            _manifest_artifact(root, contract, {"path": producer["path"], "sha256": producer["sha256"]}, "producer")
        )
    seen = set()
    for kind in ("objects", "libraries", "runtime_files"):
        entries = document[kind]
        if not isinstance(entries, list):
            failures.append(violation("invalid_artifact_list", kind))
            continue
        for entry in entries:
            if isinstance(entry, dict) and isinstance(entry.get("path"), str):
                if entry["path"] in seen:
                    failures.append(violation("duplicate_artifact", entry["path"]))
                seen.add(entry["path"])
            failures.extend(_manifest_artifact(root, contract, entry, kind))
    if not document["objects"] and not document["libraries"]:
        failures.append(violation("empty_link_inputs", manifest_name))
    libraries = document["system_libraries"]
    if not isinstance(libraries, list) or any(not isinstance(value, str) for value in libraries):
        failures.append(violation("invalid_system_libraries", manifest_name))
    else:
        if len(set(libraries)) != len(libraries):
            failures.append(violation("duplicate_system_library", manifest_name))
        for value in libraries:
            if value not in contract["link"]["allowed_system_libraries"]:
                failures.append(violation("undeclared_system_library", manifest_name, library=value))
    failures.sort(key=lambda item: (item["path"], item["code"]))
    return {
        "passed": not failures,
        "state": "link_passed" if not failures else "link_failed",
        "objects": len(document["objects"]) if isinstance(document["objects"], list) else 0,
        "libraries": len(document["libraries"]) if isinstance(document["libraries"], list) else 0,
        "runtime_files": len(document["runtime_files"]) if isinstance(document["runtime_files"], list) else 0,
        "violations": failures,
    }


def evaluate(root, contract_path, *, require_sources=False, link_manifest=None, require_link_manifest=False):
    root = Path(root).resolve()
    contract = validate_contract(load_json(contract_path))
    sources = audit_sources(root, contract, require_sources)
    failures = list(sources["violations"])
    link = None
    if link_manifest is not None:
        link = audit_link_manifest(root, contract, link_manifest)
        failures.extend(link["violations"])
    elif require_link_manifest:
        failures.append(violation("missing_link_manifest", contract["target"]))
    passed = not failures
    state = (
        "no_sources" if not sources["source_files"] and passed else ("contract_passed" if passed else "contract_failed")
    )
    return {
        "schema_version": 1,
        "contract_id": contract["contract_id"],
        "target": contract["target"],
        "state": state,
        "passed": passed,
        "scope": "source_and_declared_link_manifest_only",
        "godot_free_runtime_verified": False,
        "verification_boundary": "A real target must still bind linker-produced inputs, symbols and a clean-environment run.",
        "sources": {key: value for key, value in sources.items() if key != "violations"},
        "link": {key: value for key, value in link.items() if key != "violations"}
        if link
        else {"state": "not_provided"},
        "violations": failures,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=Path.cwd())
    parser.add_argument("--contract", default="tools/engine_next_contract.json")
    parser.add_argument("--require-sources", action="store_true")
    parser.add_argument("--link-manifest")
    parser.add_argument("--require-link-manifest", action="store_true")
    args = parser.parse_args(argv)
    root = args.repo.resolve()
    contract_path = Path(args.contract)
    if not contract_path.is_absolute():
        contract_path = root / contract_path
    manifest = Path(args.link_manifest) if args.link_manifest else None
    if manifest is not None and not manifest.is_absolute():
        manifest = root / manifest
    try:
        report = evaluate(
            root,
            contract_path,
            require_sources=args.require_sources,
            link_manifest=manifest,
            require_link_manifest=args.require_link_manifest,
        )
    except (OSError, UnicodeError, ValueError, json.JSONDecodeError) as error:
        report = {"schema_version": 1, "state": "invalid_input", "passed": False, "error": str(error)}
        print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
        return 2
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
