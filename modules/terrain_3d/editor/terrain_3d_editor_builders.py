"""Embed Terrain3D editor tools and their raw assets in the tools-enabled executable."""

import base64
import hashlib
import zlib
from pathlib import Path


def make_editor_bundle(target, source, env):
    from methods import generated_wrapper

    digest = hashlib.sha256()
    names = []
    with generated_wrapper(str(target[0])) as out:
        for i, src in enumerate(source):
            path = Path(str(src))
            relative = "/".join(path.parts[-2:])
            raw = path.read_bytes()
            digest.update(relative.encode() + b"\0" + hashlib.sha256(raw).digest())
            compressed = zlib.compress(raw, 9)
            # Split at a base64 quantum and stay below MSVC's string literal limit.
            out.write(f"static constexpr const char *terrain_3d_editor_data_{i}[] = {{\n")
            for j in range(0, len(compressed), 3072):
                encoded = base64.b64encode(compressed[j : j + 3072]).decode()
                out.write(f'\t"{encoded}",\n')
            out.write("};\n")
            names.append((relative, len(raw), len(compressed), b"@TERRAIN3D_EDITOR_ROOT@" in raw))

        out.write(f'static constexpr char terrain_3d_editor_revision[] = "{digest.hexdigest()}";\n')
        out.write("static constexpr Terrain3DEditorFile terrain_3d_editor_files[] = {\n")
        for i, (name, size, compressed, replace_root) in enumerate(names):
            out.write(
                f'\t{{ "{name}", {size}, {compressed}, {str(replace_root).lower()}, '
                f"terrain_3d_editor_data_{i}, std::size(terrain_3d_editor_data_{i}) }},\n"
            )
        out.write("};\n")
