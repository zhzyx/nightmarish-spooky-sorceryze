# Runtime Virtual Texture demo

Self-test and showcase for the engine's `RuntimeVirtualTexture` / `RuntimeVirtualTextureVolume`.

```
godot --path misc/rvt_demo                       # orbiting camera, left half direct, right half sampled from the RVT ([T] toggles)
godot --path misc/rvt_demo -- --rvt-test         # numeric self test, exit code 0 on PASS, screenshots in out/
godot --path misc/rvt_demo -- --rvt-height       # WORLD_HEIGHT type, checks tower/ground heights
godot --path misc/rvt_demo -- --rvt-shot         # lit (albedo + normal + roughness) showcase, writes out/lit_*.png
godot ... -- --rvt-test --pool=8                 # tiny page pool, exercises eviction / truncated requests
```

`--rendering-method mobile` and `--rendering-driver d3d12` are supported too.

## Using it in a project

1. Add a `RuntimeVirtualTextureVolume` node, set `size` (meters) and assign a `RuntimeVirtualTexture`.
2. Put the meshes that should be baked on a visual layer that is part of `RuntimeVirtualTexture.cull_mask`.
   Use another layer for meshes that must only show up through the RVT and exclude it from the camera cull mask.
3. Sample it from a spatial shader:

```glsl
shader_type spatial;
#include "res://rvt.gdshaderinc"
varying vec3 world_pos;
void vertex() { world_pos = (MODEL_MATRIX * vec4(VERTEX, 1.0)).xyz; }
void fragment() {
	vec4 color; vec3 n; float roughness; float metallic; bool inside;
	rvt_sample(world_pos, color, n, roughness, metallic, inside);
	ALBEDO = color.rgb;
}
```

```gdscript
rvt.apply_to_material(material, "rvt")   # fills rvt_page_table / rvt_physical0/1 / rvt_params0/1 / rvt_world_to_uv / rvt_normal_basis
```

Moving, showing/hiding and re-layering meshes refreshes the covered pages automatically.
After changing material parameters call `rvt.invalidate(aabb)`.

## How it works

- `RVTPageManager` (CPU, unit tested): quadtree of virtual pages, page table mips with ancestor fallback, LRU physical page pool, invalidation.
- `RendererSceneCull`: collects the cameras that rendered last frame (replacement for UE's GPU feedback), requests pages by pixel footprint + frustum, culls geometry per page.
- `RuntimeVirtualTextureRD`: renders each page with the existing material pass (`render_material`, same as VoxelGI), then a compute pass writes albedo / normal / roughness / metallic / height into the physical page pool.

## Debug views (UE-style)

Runtime toggles mirror UE's `r.VT.RVT.DebugView` / `MipColors` / pick debug:

| Key | Effect |
|---|---|
| `0`-`5` | Debug mode: off / page table / residency per level / physical pool / LOD heat map / page borders |
| `L` | Cycle `debug_force_lod` (-1 = auto, then 0..max) |
| `P` | Pick the page under the screen center and lock it for 5 s (refreshed every frame, protected from eviction) |
| `U` | Release all locked pages |
| `T` | Toggle the receiver |

Same knobs from code:

```gdscript
rvt.debug_mode = RuntimeVirtualTexture.DEBUG_PAGE_TABLE   # 0..5, or the debug_mode property
rvt.debug_force_lod = 2                                    # -1 = auto
var page := rvt.pick_page(world_position, 0)               # Vector3i(level, x, y)
rvt.lock_page(page.x, page.y, page.z, 5.0)                 # max 6 locked pages
print(rvt.get_page_info(page.x, page.y, page.z))           # resident / pool tile / locked ...
rvt.unlock_all_pages()
```

The debug views are computed in `rvt.gdshaderinc` from the same page table the sampler reads,
so what you see is exactly the indirection the material resolves. `--rvt-test` asserts the page
table and forced-LOD views actually change the image, and that a picked page becomes resident,
stays locked, and is released again.

## Console variables

The demo registers the UE-style `r.VT.RVT.*` names with the engine's `CVars` singleton
(`Engine.get_singleton("CVars")`), so the in-game console, `--cvar`, `--cvar-exec` and
`--cvar-file` all drive the same state:

```
help
r.VT.RVT.DebugView 1          # same knobs as the UE CVar
r.VT.RVT.ForceLod 3
r.VT.RVT.PickAtScreenCenter 5 # lock the page under the crosshair for 5 s
r.VT.RVT.LockPage 0 12 9
r.VT.RVT.PageInfo 0 12 9
r.VT.RVT.UnlockAll
r.VT.RVT.Stats
```

Three ways to feed it, chosen by where you are debugging:

| Source | How | Works on |
|---|---|---|
| In-game console | press the key left of `1` (`` ` `` / `~`), type, `Esc` closes | windowed builds |
| Watched file | `--cvar-file <path>`, edit the file and it is re-read (`con.ConfigPollMs`, default 500 ms) | any build |
| Startup commands | `--cvar-exec "r.VT.RVT.DebugView 1;r.VT.RVT.ForceLod 2"`, or `--cvar r.VT.RVT.DebugView=1` | CI and scripted runs |

Startup values are parsed before the scene exists: variables arrive through `get_value()` and
`set_changed_callback()`, and `--cvar-exec` lines are replayed when the demo registers the command
they name. That is why `--cvar-exec "r.VT.RVT.Stats"` prints a line at startup even though the
command is only registered in `_ready()`.

The demo's in-game console is the engine one (`con.AutoConsole`), which is created for windowed,
non-editor runs; the editor opens the same console from the Editor menu or with the same key when
no text field has focus.
