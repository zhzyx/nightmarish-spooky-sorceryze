import copy
import hashlib
import io
import json
import os
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from tools.check_engine_next_contract import (
    audit_link_manifest,
    audit_sources,
    evaluate,
    load_json,
    main,
    validate_contract,
)

CONTRACT_PATH = Path(__file__).with_name("engine_next_contract.json")


class EngineNextContractTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.contract = validate_contract(load_json(CONTRACT_PATH))

    def write(self, name, content=""):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(content, bytes):
            path.write_bytes(content)
        else:
            path.write_text(content, encoding="utf-8")
        return path

    def artifact(self, name, content=b"artifact"):
        path = self.write(name, content)
        return {"path": name, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}

    def make_manifest(self):
        document = {
            "schema_version": 1,
            "target": "next_runtime",
            "producer": {
                "kind": "linker_response",
                **self.artifact("build/runtime_next/next_runtime.rsp", b"response"),
            },
            "objects": [self.artifact("build/engine_next/prediction.o")],
            "libraries": [self.artifact("build/engine_next/libengine_next.a")],
            "runtime_files": [self.artifact("build/runtime_next/assets.pack")],
            "system_libraries": ["c++"],
        }
        path = self.write("build/runtime_next/link_manifest.json", json.dumps(document))
        return path, document

    def save_manifest(self, path, document):
        path.write_text(json.dumps(document), encoding="utf-8")

    def test_independent_sources_and_transitive_local_headers_pass(self):
        self.write(
            "engine_next/main.cpp",
            '#include <cstdint>\n#include <charconv>\n#include <vector>\n#include "engine_next/include/types.h"\nint main() { return 0; }\n',
        )
        self.write(
            "engine_next/include/types.h",
            '#pragma once\n#include "engine_next/include/detail.h"\nstruct State { int value; };\n',
        )
        self.write("engine_next/include/detail.h", "#pragma once\n#include <cstdint>\n")
        result = audit_sources(self.root, self.contract, True)
        self.assertTrue(result["passed"], result["violations"])
        self.assertEqual(result["source_files"], 3)
        self.assertEqual(result["local_includes"], 2)

    def test_declared_public_root_and_safe_relative_include_pass(self):
        self.write("engine_next/Tests/Gameplay/Main.cpp", '#include "../Framework.h"\n#include "Types.h"\n')
        self.write("engine_next/Tests/Framework.h", "#pragma once\n")
        self.write("engine_next/include/Types.h", '#pragma once\n#include "Detail.h"\n')
        self.write("engine_next/include/Detail.h", "#pragma once\n")
        result = audit_sources(self.root, self.contract, True)
        self.assertTrue(result["passed"], result["violations"])
        self.assertEqual(result["local_includes"], 3)

    def test_direct_godot_includes_are_rejected(self):
        for directive in ('#include "core/object/object.h"', "#include <scene/main/node.h>"):
            with self.subTest(directive=directive):
                self.write("engine_next/main.cpp", directive + "\n")
                result = audit_sources(self.root, self.contract, True)
                self.assertIn("godot_include", {item["code"] for item in result["violations"]})

    def test_transitive_godot_include_is_rejected(self):
        self.write("engine_next/main.cpp", '#include "engine_next/include/wrapper.h"\n')
        self.write("engine_next/include/wrapper.h", '#include "core/object/object.h"\n')
        result = audit_sources(self.root, self.contract, True)
        self.assertEqual([item["code"] for item in result["violations"]], ["godot_include"])
        self.assertEqual(result["violations"][0]["path"], "engine_next/include/wrapper.h")

    def test_comments_and_literals_do_not_create_token_false_positives(self):
        self.write(
            "engine_next/main.cpp",
            "// GDCLASS(Fake, Node) and Variant\n"
            "/* RefCounted and GDVIRTUAL0(fake) */\n"
            'const char *text = "Variant and ObjectID";\n'
            'const char *raw = R"tag(GDCLASS(Fake, Node) and StringName)tag";\n'
            "int main() { return 0; }\n",
        )
        result = audit_sources(self.root, self.contract, True)
        self.assertTrue(result["passed"], result["violations"])

    def test_godot_macros_and_types_are_rejected(self):
        for token in (
            "GDCLASS",
            "GDVIRTUAL0",
            "GDREGISTER_CLASS",
            "Variant",
            "RefCounted",
            "StringName",
            "Node",
            "Resource",
        ):
            with self.subTest(token=token):
                self.write("engine_next/main.cpp", token + "\n")
                result = audit_sources(self.root, self.contract, True)
                self.assertIn("forbidden_cpp_token", {item["code"] for item in result["violations"]})

    def test_unknown_angle_and_missing_local_includes_are_rejected(self):
        self.write("engine_next/main.cpp", "#include <not_a_system_header.hpp>\n")
        angle = audit_sources(self.root, self.contract, True)
        self.assertIn("unknown_angle_include", {item["code"] for item in angle["violations"]})
        self.write("engine_next/main.cpp", '#include "missing.h"\n')
        local = audit_sources(self.root, self.contract, True)
        self.assertIn("missing_include", {item["code"] for item in local["violations"]})

    def test_existing_but_undeclared_third_party_include_is_rejected(self):
        self.write("engine_next/main.cpp", "#include <thirdparty/enet/enet.h>\n")
        self.write("thirdparty/enet/enet.h", "// independent third-party header\n")
        result = audit_sources(self.root, self.contract, True)
        self.assertIn("undeclared_local_include", {item["code"] for item in result["violations"]})

    def test_engine_next_third_party_root_and_enet_angle_include_pass(self):
        self.write("engine_next/main.cpp", '#include "enet/enet.h"\n')
        self.write("engine_next/thirdparty/enet/include/enet/enet.h", "// upstream ENet\n")
        result = audit_sources(self.root, self.contract, True)
        self.assertTrue(result["passed"], result["violations"])

    def test_escaping_local_include_is_rejected(self):
        self.write("engine_next/core/main.cpp", '#include "../../outside.h"\n')
        self.write("outside.h", "// outside\n")
        result = audit_sources(self.root, self.contract, True)
        self.assertIn("include_path_escape", {item["code"] for item in result["violations"]})

    def test_linked_source_is_rejected(self):
        self.write("outside.h", "// outside\n")
        self.write("engine_next/.keep", "")
        try:
            os.symlink(self.root / "outside.h", self.root / "engine_next" / "linked.h")
        except (OSError, NotImplementedError):
            self.skipTest("Symlinks are unavailable")
        result = audit_sources(self.root, self.contract)
        self.assertIn("linked_source_path", {item["code"] for item in result["violations"]})

    def test_empty_source_tree_is_not_a_runtime_success(self):
        result = audit_sources(self.root, self.contract)
        self.assertEqual(result["state"], "no_sources")
        required = audit_sources(self.root, self.contract, True)
        self.assertFalse(required["passed"])
        self.assertIn("no_sources", {item["code"] for item in required["violations"]})

    def test_cyclic_local_headers_terminate(self):
        self.write("engine_next/include/a.h", '#include "engine_next/include/b.h"\n')
        self.write("engine_next/include/b.h", '#include "engine_next/include/a.h"\n')
        result = audit_sources(self.root, self.contract, True)
        self.assertTrue(result["passed"], result["violations"])

    def test_contract_rejects_overlapping_godot_source_root(self):
        contract = copy.deepcopy(self.contract)
        contract["source_roots"] = ["core"]
        with self.assertRaises(ValueError):
            validate_contract(contract)

    def test_valid_link_manifest_passes(self):
        path, _ = self.make_manifest()
        result = audit_link_manifest(self.root, self.contract, path)
        self.assertTrue(result["passed"], result["violations"])
        self.assertEqual(result["objects"], 1)
        self.assertEqual(result["libraries"], 1)

    def test_godot_link_input_is_rejected(self):
        path, document = self.make_manifest()
        document["objects"] = [{"path": "core/object.o", "sha256": "0" * 64}]
        self.save_manifest(path, document)
        result = audit_link_manifest(self.root, self.contract, path)
        self.assertIn("godot_link_input", {item["code"] for item in result["violations"]})

    def test_godot_runtime_asset_is_rejected(self):
        path, document = self.make_manifest()
        document["runtime_files"] = [self.artifact("build/runtime_next/project.tscn")]
        self.save_manifest(path, document)
        result = audit_link_manifest(self.root, self.contract, path)
        self.assertIn("forbidden_runtime_file", {item["code"] for item in result["violations"]})

    def test_missing_artifact_and_hash_mismatch_are_rejected(self):
        path, document = self.make_manifest()
        (self.root / "build/engine_next/prediction.o").unlink()
        missing = audit_link_manifest(self.root, self.contract, path)
        self.assertIn("missing_artifact", {item["code"] for item in missing["violations"]})
        self.write("build/engine_next/prediction.o", b"changed")
        mismatch = audit_link_manifest(self.root, self.contract, path)
        self.assertIn("artifact_sha256_mismatch", {item["code"] for item in mismatch["violations"]})

    def test_undeclared_system_library_is_rejected(self):
        path, document = self.make_manifest()
        document["system_libraries"] = ["GodotCore"]
        self.save_manifest(path, document)
        result = audit_link_manifest(self.root, self.contract, path)
        self.assertIn("undeclared_system_library", {item["code"] for item in result["violations"]})

    def test_handwritten_producer_is_not_accepted_as_linker_evidence(self):
        path, document = self.make_manifest()
        document["producer"]["kind"] = "handwritten"
        self.save_manifest(path, document)
        result = audit_link_manifest(self.root, self.contract, path)
        self.assertIn("invalid_link_producer", {item["code"] for item in result["violations"]})

    def test_duplicate_artifacts_are_rejected(self):
        path, document = self.make_manifest()
        document["libraries"] = document["objects"] + document["libraries"]
        self.save_manifest(path, document)
        result = audit_link_manifest(self.root, self.contract, path)
        self.assertIn("duplicate_artifact", {item["code"] for item in result["violations"]})

    def test_combined_evaluation_requires_real_sources_and_manifest(self):
        report = evaluate(self.root, CONTRACT_PATH, require_sources=True, require_link_manifest=True)
        self.assertFalse(report["passed"])
        self.assertFalse(report["godot_free_runtime_verified"])
        self.assertIn("no_sources", {item["code"] for item in report["violations"]})
        self.assertIn("missing_link_manifest", {item["code"] for item in report["violations"]})

    def test_cli_exit_codes_and_no_sources_state(self):
        output = io.StringIO()
        with redirect_stdout(output):
            status = main(["--repo", str(self.root), "--contract", str(CONTRACT_PATH)])
        self.assertEqual(status, 0)
        self.assertEqual(json.loads(output.getvalue())["state"], "no_sources")
        output = io.StringIO()
        with redirect_stdout(output):
            status = main(["--repo", str(self.root), "--contract", str(CONTRACT_PATH), "--require-sources"])
        self.assertEqual(status, 1)


if __name__ == "__main__":
    unittest.main()
