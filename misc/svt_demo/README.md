# Streaming Virtual Texture demo

Self-test and showcase for `RuntimeVirtualTexture` with `source = SOURCE_STREAM` (baked page files).

```
godot --path misc/svt_demo                       # orbiting camera over a streamed 64 x 64 m layer
godot --path misc/svt_demo -- --svt-test          # numeric self test, exit code 0 on PASS
godot --path misc/svt_demo --rendering-method mobile -- --svt-test
godot --path misc/svt_demo --rendering-driver d3d12 -- --svt-test
```

`--svt-test` bakes `out/terrain_rgba8.svt` and `out/terrain_bc1.svt` on first run (cached), then:

1. waits until streaming converges and checks that only the coarse levels exist on the first frames and
   that level 0 pages stream in afterwards;
2. captures the same quad with a directly sampled texture and with the SVT, and compares
   (mean absolute difference / outlier fraction);
3. repeats at a far camera (coarser pages, eviction happens when the camera moves);
4. swaps to the BC1 page file at runtime and compares again;
5. shrinks the pool to 3x3 pages (9 slots) to force truncated requests and coarse fallback.

## Using it in a project

```gdscript
var rvt := RuntimeVirtualTexture.new()
rvt.pool_size = 8                      # physical pool: pool_size x pool_size pages
rvt.page_file = "res://terrain.svt"    # switches source to SOURCE_STREAM and adopts the baked layout

var volume := RuntimeVirtualTextureVolume.new()
volume.virtual_texture = rvt
volume.size = Vector3(64, 8, 64)
add_child(volume)

rvt.apply_to_material(material, "rvt")  # same uniforms as the rendered RVT
```

Baking:

```gdscript
RuntimeVirtualTexture.bake_page_file(
    "res://terrain.svt", image,
    3,      # log2_tile_count: 2^3 = 8 pages a side
    128,    # tile_size in texels
    4,      # tile_border: edge clamped neighbours for bilinear filtering
    RuntimeVirtualTexture.FORMAT_BC1,   # or FORMAT_RGBA8 / FORMAT_BC7 / FORMAT_R32F
    true)   # sRGB encoded bytes (the shader include decodes once)
```

The bake slices `image` into a page pyramid. BC1/BC7 need `tile_size` and `tile_border` to be
multiples of 4 (128 and 4 here, so a page is 34x34 blocks).

## File format (`GSVT`, little endian)

| Section | Content |
|---|---|
| header, 48 B | magic `GSVT`, version, flags (bit 0 sRGB), format, `log2_tile_count`, `tile_size`, `tile_border`, layer count, level count, 3 reserved |
| index | per level: `u32 tiles_x`, `u32 tiles_y`, then `tiles_x * tiles_y` entries of `u64 offset, u32 size` |
| payload | compressed/raw tiles, `tile_size + 2 * tile_border` on a side |

`FORMAT_RGBA8` / `FORMAT_R32F` pages are `136 * 136 * 4` bytes; `FORMAT_BC1` is `34 * 34 * 8`;
`FORMAT_BC7` is `34 * 34 * 16`.

## Runtime notes

- Pages are read on a `WorkerThreadPool` task and uploaded on the render thread with
  `texture_update` into a tile sized staging texture followed by a region `texture_copy` into the pool.
- Streaming pools are UNORM: the shader include (`rvt.gdshaderinc`) decodes sRGB itself, the same
  contract the rendered RVT pool uses. Binding an sRGB view would decode twice.
- `RuntimeVirtualTexture.get_stats()` exposes `streaming`, `levels` (resident pages per level),
  `evicted_total` and `rendered_total` (uploads) to make streaming observable from a test.
- Pages are immutable; `invalidate()` re-reads them. Material parameter changes still need an explicit
  `invalidate()`.

## Debug views

The same keys as the RVT demo work here (streamed pages go through the same page table and shader
include): `0`-`5` debug modes, `L` cycle forced LOD, `P` pick + lock the page under the screen
center, `U` unlock. `RuntimeVirtualTexture.debug_mode`, `debug_force_lod`, `pick_page()`,
`lock_page()` and `get_page_info()` are available from script.

## Console variables

The same `r.VT.RVT.*` names are registered with the engine `CVars` singleton: the in-game console
(key left of `1`) opens in a window, and `--cvar-file <path>` / `--cvar-exec "..."` / `--cvar
name=value` drive it headless or on device. Commands: `r.VT.RVT.DebugView`, `r.VT.RVT.ForceLod`,
`r.VT.RVT.PickAtScreenCenter`, `r.VT.RVT.UnlockAll`, `r.VT.RVT.Stats`, `r.VT.RVT.PageInfo`. See
`misc/rvt_demo/README.md` for the details.
