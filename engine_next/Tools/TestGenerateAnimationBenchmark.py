"""Validate the generated E scene's GLB channel shapes and reproducibility."""

import json
import struct
import unittest

import GenerateAnimationBenchmark as benchmark


def document(payload):
    json_bytes = struct.unpack_from("<I", payload, 12)[0]
    return json.loads(payload[20 : 20 + json_bytes])


class AnimationBenchmarkTests(unittest.TestCase):
    def test_character_bytes_and_rig_are_reproducible(self):
        first, stats = benchmark.character()
        second, repeated_stats = benchmark.character()
        self.assertEqual(first, second)
        self.assertEqual(stats, repeated_stats)
        self.assertEqual(stats, {"joints": 16, "vertices": 5200, "triangles": 8448, "duration_seconds": 2})
        data = document(first)
        self.assertEqual(len(data["skins"][0]["joints"]), 16)
        self.assertEqual(data["scenes"][0]["nodes"], [0, 1])
        self.assertEqual(len(data["animations"][0]["channels"]), 7)
        primitive = data["meshes"][0]["primitives"][0]
        for index in primitive["attributes"].values():
            self.assertEqual(data["accessors"][index]["count"], 5200)
        for sampler in data["animations"][0]["samplers"]:
            times = data["accessors"][sampler["input"]]
            self.assertEqual(times["min"], [0])
            self.assertEqual(times["max"], [2])

    def test_floor_has_consistent_vertex_channels_and_material(self):
        first = benchmark.floor_mesh()
        self.assertEqual(first, benchmark.floor_mesh())
        data = document(first)
        primitive = data["meshes"][0]["primitives"][0]
        for index in primitive["attributes"].values():
            self.assertEqual(data["accessors"][index]["count"], 4)
        self.assertEqual(data["accessors"][primitive["attributes"]["TANGENT"]]["type"], "VEC4")
        self.assertEqual(data["materials"][0]["pbrMetallicRoughness"]["baseColorFactor"], [0.45, 0.45, 0.45, 1])


if __name__ == "__main__":
    unittest.main()
