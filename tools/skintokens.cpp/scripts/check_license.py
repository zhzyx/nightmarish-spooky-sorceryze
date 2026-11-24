"""Check this independent port's license root without imposing Godot authorship."""

import hashlib
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    required = {
        "LICENSE": ("Apache License", "Version 2.0, January 2004", "http://www.apache.org/licenses/"),
        "NOTICE": (
            "https://github.com/ggml-org/ggml",
            "https://github.com/VAST-AI-Research/SkinTokens",
            "licensed under the MIT License",
            "https://github.com/numpy/numpy/tree/v1.26.4/numpy/random",
        ),
    }
    for name, markers in required.items():
        text = (ROOT / name).read_text(encoding="utf-8")
        for marker in markers:
            if marker not in text:
                raise SystemExit(f"{name}: missing required license/provenance marker {marker!r}")
    patches = {
        "0001-vulkan-honor-precise-f32-matmul-on-coopmat-devices.patch": "930e791822b79ce8b1c65113624264561d3662b6d9cbdd7ff05c0ff9fab23b88",
        "0002-vulkan-handle-F16-weights-with-F32-inputs-on-coopmat.patch": "489f290cc4a3c5ce907a5ca37b98d3fb8a19cbd7e3161b99e35e202f7801bbd2",
    }
    actual = {path.name for path in (ROOT / "patches" / "ggml").glob("*.patch")}
    if actual != set(patches):
        raise SystemExit(f"GGML patch inventory changed: expected {sorted(patches)}, found {sorted(actual)}")
    for name, digest in patches.items():
        patch = ROOT / "patches" / "ggml" / name
        if hashlib.sha256(patch.read_bytes()).hexdigest() != digest:
            raise SystemExit(f"{name}: pinned upstream patch changed; revalidate its source and application")
        subprocess.run(["git", "apply", "--numstat", str(patch)], check=True, capture_output=True)
    print("SkinTokens Apache-2.0 license and upstream notices verified")


if __name__ == "__main__":
    main()
