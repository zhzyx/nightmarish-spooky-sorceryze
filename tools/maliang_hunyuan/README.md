# Offline Maliang editor

Build on Apple Silicon macOS or x86-64 Windows with a native editor compiled from the source revision that includes the bundled Hunyuan integration. Use a separate output directory. The bundled macOS Python wheels require macOS 14 or newer.

```sh
python3 tools/package_maliang_editor.py --editor bin/godot.macos.editor.arm64 --output dist/Maliang.app
```

```powershell
py -3 tools/package_maliang_editor.py --editor bin/godot.windows.editor.x86_64.exe --output dist/Maliang
```

The macOS input can also be a complete Godot-derived app. The builder preserves its resources and signing identity. Use `--sign-identity` to select a local signing certificate. Raw binary builds use the repository’s app template and an ad-hoc signature by default. For Windows, the builder copies the editor directory with its native libraries and exported resources.

The default recipe downloads CPython 3.12.16, the platform wheel set, the pinned ComfyUI source, the Tencent license and the 3,819,958,234-byte Hunyuan3D-2mini checkpoint. The Windows build also supplies Microsoft’s x64 Visual C++ runtime beside both executables. The model is included before the package is delivered. Check `maliang-hunyuan/config.json` for the checkpoint identity and `sources.json` and `licenses/` for distribution sources and notices.

To reuse validated inputs, add `--runtime PATH` where PATH contains `python/` and `ComfyUI-src/`. Pass `--checkpoint FILE` and `--license FILE` if those files live separately. A complete runtime includes `models/checkpoints/hunyuan3d-mini.safetensors` and `licenses/HUNYUAN-LICENSE`. Build inputs remain in place. The builder stages and relocates the candidate, verifies CPU tensor execution and model discovery, and checks the macOS signature before replacing a previous output.

On a Windows test host with PowerShell 7 and an enabled Windows Firewall, this command packages an editor, blocks outbound traffic for its programs, and connects with fresh user settings. It waits for the backend to exit, moves the package, then generates and reopens a mesh using the saved settings. Use an elevated shell for the per-program firewall rules. Choose a new work directory outside the source tree. The resulting distribution, native scene and reports stay in that directory.

```powershell
./tests/editor/run_bundled_hunyuan_windows.ps1 -Editor bin/godot.windows.editor.x86_64.exe -WorkRoot D:/MaliangAcceptance
```

The “Maliang offline Windows editor” Actions workflow performs the same run on the selected source revision. It transfers the native build between jobs and uploads the Windows receipt and logs. The checkpoint and the assembled model distribution stay on the build machine.
