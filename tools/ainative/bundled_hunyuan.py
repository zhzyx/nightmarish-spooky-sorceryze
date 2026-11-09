"""Identity and offline launcher for the Hunyuan runtime shipped with Ma Liang."""

import os
import runpy
import subprocess
import sys
from pathlib import Path

DISTRIBUTION = "maliang-hunyuan3d-2mini-v1"
COMFY_REVISION = "63e5bf594339f676b4b15e072529873e3448409e"
MODEL_REVISION = "f90a0f7df7d5e6f71109cf333f6a95a0ae3194a6"
MODEL_NAME = "hunyuan3d-mini.safetensors"
MODEL_SIZE = 3819958234
MODEL_SHA256 = "3cc66f3bea33e4062b7dbc875ffe1d70c4888914aec3e91b60f94e9bd01b522b"


def python_path(root):
    return root / ("python/python.exe" if os.name == "nt" else "python/bin/python3.12")


def launch(main, arguments):
    # Third-party modules read these variables at import time.
    os.environ.update(
        HF_HUB_OFFLINE="1",
        TRANSFORMERS_OFFLINE="1",
        HF_HUB_DISABLE_TELEMETRY="1",
        PYTORCH_ENABLE_MPS_FALLBACK="1",
        PYTHONDONTWRITEBYTECODE="1",
    )
    # ComfyUI sets allocator options before importing Torch. Probe separately
    # so a Windows machine without a CUDA device can still use its CPU.
    probe = subprocess.run(
        [
            sys.executable,
            "-I",
            "-B",
            "-c",
            "import torch; print(torch.cuda.is_available() or torch.backends.mps.is_available())",
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    if probe.stdout.strip() == "False":
        arguments.append("--cpu")
    sys.path.insert(0, str(main.parent))
    sys.argv = [str(main), *arguments]
    runpy.run_path(str(main), run_name="__main__")


if __name__ == "__main__":
    launch(Path(sys.argv[1]).resolve(strict=True), sys.argv[2:])
