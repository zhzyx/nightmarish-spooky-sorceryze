"""Executed by the relocated distribution's isolated interpreter during packaging."""

import importlib
import importlib.metadata
import json
import platform
import sys
from pathlib import Path


def inspect(root, target):
    python = root / "python"
    if Path(sys.prefix).resolve() != python or sys.base_prefix != sys.prefix or sys.version_info[:2] != (3, 12):
        raise ValueError("Expected the package's standalone CPython 3.12.")
    if any(not Path(entry).resolve().is_relative_to(python) for entry in sys.path):
        raise ValueError("Interpreter imports from outside the relocated package.")
    for dependency in (
        "aiohttp",
        "PIL.Image",
        "safetensors.torch",
        "skimage.measure",
        "transformers",
        "trimesh",
        "yaml",
    ):
        importlib.import_module(dependency)
    import torch
    import torchvision

    windows = target == "windows"
    system = "win32" if windows else "darwin"
    machine = "amd64" if windows else "arm64"
    if sys.platform != system or platform.machine().lower() != machine:
        raise ValueError(f"Expected native {target} {machine} runtime.")
    torch_version = "2.9.1+cu128" if windows else "2.9.1"
    vision_version = "0.24.1+cu128" if windows else "0.24.1"
    if torch.__version__ != torch_version or torchvision.__version__ != vision_version:
        raise ValueError(f"Expected torch {torch_version} and torchvision {vision_version}.")
    if windows:
        import ctypes
        from ctypes import wintypes

        if torch.version.cuda != "12.8":
            raise ValueError("Missing PyTorch CUDA 12.8 runtime libraries.")
        get_filename = ctypes.WinDLL("kernel32").GetModuleFileNameW
        get_filename.argtypes = [wintypes.HMODULE, wintypes.LPWSTR, wintypes.DWORD]
        get_filename.restype = wintypes.DWORD
        for name in ("msvcp140.dll", "vcruntime140.dll", "vcruntime140_1.dll"):
            library = ctypes.WinDLL(name)
            path = ctypes.create_unicode_buffer(32768)
            if not get_filename(library._handle, path, len(path)) or not Path(path.value).resolve().is_relative_to(
                python
            ):
                raise ValueError(f"The shipped interpreter depends on a system copy of {name}.")
    if torch.tensor([1.0, 2.0], device="cpu").sum().item() != 3.0:
        raise ValueError("Bundled CPU tensor operations failed.")
    sys.path.insert(0, str(root / "ComfyUI-src"))
    import folder_paths
    from utils.extra_config import load_extra_path_config

    config = json.loads((root / "config.json").read_text(encoding="utf-8"))
    name = config["checkpoints"]["mesh"]["name"]
    load_extra_path_config(str(root / "model_paths.yaml"))
    if Path(folder_paths.get_full_path("checkpoints", name)).resolve() != root / "models/checkpoints" / name:
        raise ValueError("ComfyUI did not locate the checkpoint inside the moved package.")
    return dict(
        python=platform.python_version(),
        architecture=platform.machine(),
        torch=str(torch.__version__),
        torchvision=str(torchvision.__version__),
        cuda=torch.version.cuda,
        distributions={d.metadata["Name"]: d.version for d in importlib.metadata.distributions()},
    )


if __name__ == "__main__":
    print(json.dumps(inspect(Path(sys.argv[1]).resolve(), sys.argv[2]), sort_keys=True))
