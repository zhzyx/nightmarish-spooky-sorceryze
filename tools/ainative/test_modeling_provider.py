"""Schema and GLB validation for the fixed Godot modeling builder."""

import copy
import json
import os
import shutil
import unittest
from pathlib import Path

from modeling_provider import (
    modeling_schema,
    validate_mesh,
    validate_plan,
)

ROOT = Path(__file__).resolve().parents[2]
GODOT = (
    Path(os.environ["AINATIVE_TEST_GODOT"])
    if os.environ.get("AINATIVE_TEST_GODOT")
    else next(
        (
            candidate
            for candidate in (
                ROOT / "bin/godot.windows.editor.x86_64.exe",
                ROOT / "bin/godot.linuxbsd.editor.x86_64",
            )
            if candidate.is_file()
        ),
        Path(shutil.which("godot") or "__godot_unavailable__"),
    )
)
BUILDER = ROOT / "samples/ainative-workbench/addons/ainative/modeling_builder.gd"
KEY = "a" * 64
PLAN = {
    "version": 1,
    "name": "Table",
    "parts": [
        {
            "name": "Top",
            "primitive": "box",
            "position": [0, 1, 0],
            "rotation_degrees": [0, 0, 0],
            "size": [2, 0.1, 1],
            "color": [0.4, 0.2, 0.1, 1],
        }
    ],
}


class PlanTests(unittest.TestCase):
    def test_accepts_primitives_and_returns_independent_data(self):
        plan = copy.deepcopy(PLAN)
        for primitive in ("box", "sphere", "cylinder", "capsule", "torus"):
            plan["parts"][0]["primitive"] = primitive
            self.assertEqual(validate_plan(plan), plan)
        validated = validate_plan(plan)
        validated["parts"].clear()
        self.assertEqual(len(plan["parts"]), 1)

    def test_rejects_executable_fields_unknown_primitive_and_invalid_shape(self):
        invalid = []
        for extra in ("script", "file", "code"):
            plan = copy.deepcopy(PLAN)
            plan[extra] = "print('not executed')"
            invalid.append(plan)
        for field, value in (
            ("primitive", "script"),
            ("position", [0, 0]),
            ("size", [0, 1, 1]),
            ("color", [1, 1, 1, 2]),
            ("rotation_degrees", [0, 0, 4000]),
        ):
            plan = copy.deepcopy(PLAN)
            plan["parts"][0][field] = value
            invalid.append(plan)
        for plan in invalid:
            with self.subTest(plan=plan), self.assertRaisesRegex(ValueError, "plan_invalid"):
                validate_plan(plan)

    def test_rejects_nonfinite_and_bool_numbers(self):
        for value in (True, False, float("nan"), float("inf"), -float("inf")):
            plan = copy.deepcopy(PLAN)
            plan["parts"][0]["position"][0] = value
            with self.subTest(value=value), self.assertRaisesRegex(ValueError, "plan_invalid"):
                validate_plan(plan)

    def test_rejects_names_and_duplicate_or_unbounded_parts(self):
        for name in (
            "../x",
            "script.gd",
            "a/b",
            "a\\b",
            "a:b",
            "a@b",
            "a%b",
            'a"b',
            "a\x7fb",
            "a\nb",
            "  x",
            "",
            "x" * 81,
        ):
            plan = copy.deepcopy(PLAN)
            plan["parts"][0]["name"] = name
            with self.subTest(name=name), self.assertRaisesRegex(ValueError, "plan_invalid"):
                validate_plan(plan)
        for count in (0, 2, 65):
            plan = copy.deepcopy(PLAN)
            plan["parts"] *= count
            with self.subTest(count=count), self.assertRaisesRegex(ValueError, "plan_invalid"):
                validate_plan(plan)

    def test_schema_is_closed_at_each_object_boundary(self):
        schema = modeling_schema()
        self.assertFalse(schema["additionalProperties"])
        self.assertFalse(schema["properties"]["parts"]["items"]["additionalProperties"])
        self.assertEqual(schema["properties"]["parts"]["maxItems"], 64)

    def test_rejects_empty_glb_header_instead_of_reporting_mesh_success(self):
        import struct

        data = json.dumps({"asset": {"version": "2.0"}}).encode()
        data += b" " * ((-len(data)) % 4)
        glb = b"glTF" + struct.pack("<IIII", 2, 20 + len(data), len(data), 0x4E4F534A) + data
        with self.assertRaisesRegex(ValueError, "mesh_invalid"):
            validate_mesh(glb)


if __name__ == "__main__":
    unittest.main()
