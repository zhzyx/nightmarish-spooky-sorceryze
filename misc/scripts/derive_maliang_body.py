"""Derive fixed CC0 body data from pinned mesh/target/rig DATA, without MakeHuman code.

All input files are supplied locally and checked against exact SHA256 values.
Run with --obj, --young, --old, --rig, --weights and a new --output Python path.
The output is asset data, not an executable model instruction or neural model.
"""

import argparse
import hashlib
import json
import math
from pathlib import Path

COMMIT = "a8bc2d54ff0ac92e78ff71431b1023eda42bf482"
PINNED = {
    "base.obj": "8e761e6624b8f54536409135d1636da63b32486a90d4897f84e121d144f6fb4c",
    "caucasian-male-young.target": "70e228ba7164737dae664454394536fc5935fa48d333c1a97d77e2dc6eacc5f5",
    "caucasian-male-old.target": "b0d2b1d58cba0358af59833740e70229265f7da1c20a11240f4123b7192cfd6d",
    "default.mhskel": "99f179bce0aa850b45d4191a1d0d234c5851f881c057439470ded3bddf729a24",
    "default_weights.mhw": "0f3641d651ae3d00ad6b4ccee43142edb109d3bd909d27d9e4139ef1beed8625",
}


def checked(path):
    data = path.read_bytes()
    if hashlib.sha256(data).hexdigest() != PINNED[path.name]:
        raise ValueError("Pinned source hash mismatch")
    return data.decode("utf-8")


def target(text):
    result = {}
    for line in text.splitlines():
        values = line.split()
        if not values or values[0].startswith("#"):
            continue
        if len(values) != 4 or int(values[0]) in result:
            raise ValueError("Invalid sparse delta")
        result[int(values[0])] = tuple(map(float, values[1:]))
    return result


def rounded(values):
    return tuple(round(value, 10) for value in values)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("obj", "young", "old", "rig", "weights", "output"):
        parser.add_argument("--" + name, required=True, type=Path)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError("Output must be new")
    vertices, faces, group = [], [], ""
    for line in checked(args.obj).splitlines():
        values = line.split()
        if not values:
            continue
        if values[0] == "v":
            vertices.append(tuple(map(float, values[1:4])))
        elif values[0] == "g":
            group = values[1]
        elif values[0] == "f" and group == "body":
            faces.append(tuple(int(value.split("/")[0]) - 1 for value in values[1:]))
    young, old = target(checked(args.young)), target(checked(args.old))
    rig, weight_data = json.loads(checked(args.rig)), json.loads(checked(args.weights))
    if rig.get("license") != "CC0" or weight_data.get("license") != "CC0":
        raise ValueError("CC0 data required")
    baseline = [tuple(p[a] + young.get(i, (0, 0, 0))[a] for a in range(3)) for i, p in enumerate(vertices)]
    deltas = [
        tuple(old.get(i, (0, 0, 0))[a] - young.get(i, (0, 0, 0))[a] for a in range(3)) for i in range(len(vertices))
    ]
    indices = sorted({i for face in faces for i in face})
    index_map = {source: local for local, source in enumerate(indices)}
    floor = min(baseline[i][1] for i in indices)
    height = max(baseline[i][1] for i in indices) - floor
    center_x = (min(baseline[i][0] for i in indices) + max(baseline[i][0] for i in indices)) / 2
    center_z = (min(baseline[i][2] for i in indices) + max(baseline[i][2] for i in indices)) / 2

    def normalized(point):
        return rounded(((point[0] - center_x) / height, (point[1] - floor) / height, (point[2] - center_z) / height))

    def normalized_delta(point):
        return rounded(value / height for value in point)

    def joint(name, values):
        ids = rig["joints"][name]
        return tuple(sum(values[i][axis] for i in ids) / len(ids) for axis in range(3))

    landmarks = {
        "head_base": "head____head",
        "head": "head____tail",
        "jaw": "jaw____tail",
        "neck_base": "neck01____head",
        "neck": "neck03____head",
    }
    for side in ("L", "R"):
        landmarks.update({
            "eye" + side: "eye." + side + "____head",
            "shoulder" + side: "upperarm01." + side + "____head",
            "elbow" + side: "lowerarm01." + side + "____head",
            "wrist" + side: "wrist." + side + "____head",
            "palm" + side: "wrist." + side + "____tail",
            "hip" + side: "upperleg01." + side + "____head",
            "knee" + side: "lowerleg01." + side + "____head",
            "ankle" + side: "foot." + side + "____head",
        })
    points = {name: normalized(joint(j, baseline)) for name, j in landmarks.items()}
    point_deltas = {name: normalized_delta(joint(j, deltas)) for name, j in landmarks.items()}
    crown = max(indices, key=lambda i: (baseline[i][1], -abs(baseline[i][0])))
    points["head_top"] = normalized(baseline[crown])
    point_deltas["head_top"] = normalized_delta(deltas[crown])
    points["chin"] = points["jaw"]
    point_deltas["chin"] = point_deltas["jaw"]
    digit_points, digit_deltas = {}, {}
    for side in ("L", "R"):
        names = ["finger" + str(i) + "-3." + side + "____tail" for i in range(1, 6)]
        digit_points[side] = tuple(normalized(joint(name, baseline)) for name in names)
        digit_deltas[side] = tuple(normalized_delta(joint(name, deltas)) for name in names)
    chains = []
    for root in ("upperarm01.L", "upperarm01.R", "wrist.L", "wrist.R", "lowerarm01.L", "lowerarm01.R"):
        chain = {root}
        while True:
            expanded = chain | {name for name, bone in rig["bones"].items() if bone["parent"] in chain}
            if expanded == chain:
                break
            chain = expanded
        chains.append(chain)
    total = [0.0] * len(vertices)
    arm_sums = [[0.0] * len(vertices) for _ in chains]
    for bone, rows in weight_data["weights"].items():
        for i, weight in rows:
            if type(i) is not int or not 0 <= i < len(vertices) or not math.isfinite(weight) or weight < 0:
                raise ValueError("Invalid source skin weight")
            total[i] += weight
            for side, chain in enumerate(chains):
                if bone in chain:
                    arm_sums[side][i] += weight
    arm_weights = [rounded(arm_sums[side][i] / total[i] if total[i] else 0 for side in (0, 1)) for i in indices]
    hand_weights = [rounded(arm_sums[side][i] / total[i] if total[i] else 0 for side in (2, 3)) for i in indices]
    forearm_weights = [rounded(arm_sums[side][i] / total[i] if total[i] else 0 for side in (4, 5)) for i in indices]
    if not all(all(0 <= value <= 1 for value in pair) and sum(pair) <= 1.0000000001 for pair in arm_weights):
        raise ValueError("Derived arm weights invalid")
    if not all(all(0 <= value <= 1 for value in pair) and sum(pair) <= 1.0000000001 for pair in forearm_weights):
        raise ValueError("Derived forearm weights invalid")
    body = [normalized(baseline[i]) for i in indices]
    age = [normalized_delta(deltas[i]) for i in indices]
    polygons = [tuple(index_map[i] for i in face) for face in faces]
    if not all(len(face) == 4 for face in polygons):
        raise ValueError("Pinned body quads required")
    data = {
        "BODY_SOURCE_INDICES": tuple(indices),
        "BODY_VERTICES": tuple(body),
        "BODY_AGE_DELTAS": tuple(age),
        "BODY_FACES": tuple(polygons),
        "BODY_ARM_WEIGHTS": tuple(arm_weights),
        "BODY_HAND_WEIGHTS": tuple(hand_weights),
        "BODY_FOREARM_WEIGHTS": tuple(forearm_weights),
    }
    header = f'''# SPDX-License-Identifier: CC0-1.0
# Asset data copyright (c) 2020-2021 Data Collection AB, Joel Palmius, Jonas Hauquier.
"""Fixed CC0 body cage data; not neural weights or a user-reference reconstruction.

Official MakeHuman source commit: {COMMIT}
Only BODY faces/vertices are retained; all helpers/rig objects are excluded.
Baseline is base + pinned male-young artist target, not an ethnicity inference.
Coordinates are Y-up with +Z front, baseline floor 0 and crown height 1.
Age deltas are (old-young) divided by the SAME young-baseline height; the
runtime applies a bounded coefficient and normalizes requested final height.
Arm pairs are (official L, official R), normalized sums of descendants of
upperarm01.L/R divided by all official vertex weights (rounding normalized).
Hand pairs similarly sum wrist.L/R descendants and use the same denominator.
Forearm pairs sum lowerarm01.L/R descendants using the same denominator;
BODY_FOREARM_CHAIN_BONES records the exact included source bone names.
Official L is positive X and official R negative X; runtime may map aliases.
No MakeHuman program code is included. Reproduce with
misc/scripts/derive_maliang_body.py and the five exact pinned source files.
"""

'''
    chunks = [header, "BODY_SOURCE_SHA256 = " + json.dumps(PINNED, indent=4) + "\n\n"]
    normalization = dict(floor_y=floor, height=height, center_x=center_x, center_z=center_z)
    chunks.append("BODY_NORMALIZATION = " + repr(normalization) + "\n\n")
    base_frame = dict(origin=normalized((0, 7.341025, 0.16075)), height=round(2.30055 / height, 10))
    chunks.append("BODY_BASE_HEAD_FRAME = " + repr(base_frame) + "\n\n")
    head_indices = [i for i in indices if vertices[i][1] >= 6.19075]
    head_center_z = (min(baseline[i][2] for i in head_indices) + max(baseline[i][2] for i in head_indices)) / 2
    crown_y, chin_y = baseline[crown][1], joint("jaw____tail", baseline)[1]
    frame = dict(
        origin=normalized((0, (crown_y + chin_y) / 2, head_center_z)), height=round((crown_y - chin_y) / height, 10)
    )
    chunks.append("BODY_HEAD_FRAME = " + repr(frame) + "\n\n")
    for name, rows in data.items():
        chunks.append(name + " = (\n")
        if name == "BODY_SOURCE_INDICES":
            for offset in range(0, len(rows), 12):
                chunks.append("    " + ", ".join(map(str, rows[offset : offset + 12])) + ",\n")
        else:
            chunks.extend("    " + repr(row) + ",\n" for row in rows)
        chunks.append(")\n\n")
    for name, values in (
        ("BODY_LANDMARKS", points),
        ("BODY_LANDMARK_AGE_DELTAS", point_deltas),
        ("BODY_DIGIT_TIPS", digit_points),
        ("BODY_DIGIT_TIP_AGE_DELTAS", digit_deltas),
        ("BODY_FOREARM_CHAIN_BONES", dict(L=tuple(sorted(chains[4])), R=tuple(sorted(chains[5])))),
    ):
        chunks.append(name + " = {\n")
        chunks.extend("    " + json.dumps(key) + ": " + repr(value) + ",\n" for key, value in values.items())
        chunks.append("}\n\n")
    args.output.write_bytes("".join(chunks).encode("utf-8"))
    print(
        json.dumps(
            dict(
                output=str(args.output),
                sha256=hashlib.sha256(args.output.read_bytes()).hexdigest(),
                vertices=len(body),
                quads=len(polygons),
                arm_chains=[len(c) for c in chains],
                normalization=dict(height=height, floor_y=floor),
            )
        )
    )


if __name__ == "__main__":
    main()
