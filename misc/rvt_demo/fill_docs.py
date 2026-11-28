import os
import re

# Run from anywhere: fill the class reference descriptions for the RVT/SVT classes.
os.chdir(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))


def rd(p):
    return open(p, encoding="utf-8").read()


def wr(p, t):
    open(p, "w", encoding="utf-8", newline="\n").write(t)


def fill(t, kind, name, text):
    tag = {"method": "method", "member": "member", "constant": "constant"}[kind]
    pat = re.compile(rf'(<{tag} name="{re.escape(name)}"[^>]*>.*?<description>)(.*?)(</description>)', re.S)
    if kind == "member":
        pat = re.compile(rf'(<member name="{re.escape(name)}"[^>]*>)(.*?)(</member>)', re.S)
    if kind == "constant":
        pat = re.compile(rf'(<constant name="{re.escape(name)}"[^>]*>)(.*?)(</constant>)', re.S)
    new, n = pat.subn(lambda m: m.group(1) + "\n\t\t\t" + text + "\n\t\t" + m.group(3), t, count=1)
    assert n == 1, (kind, name)
    return new


# ---------------------------------------------------------------- RuntimeVirtualTexture
p = "doc/classes/RuntimeVirtualTexture.xml"
t = rd(p)
t = t.replace(
    "<brief_description>\n\t</brief_description>",
    "<brief_description>\n\tA sparse texture that is either rendered from the scene every frame or streamed from a baked page file.\n\t</brief_description>",
    1,
)
t = t.replace(
    "<description>\n\t</description>",
    """<description>
		A runtime virtual texture renders the geometry inside a [RuntimeVirtualTextureVolume] from above into a pool of fixed size pages, and only keeps the pages that cameras currently need. With [member source] set to [constant SOURCE_STREAM] the pages are instead read from a page file baked with [method bake_page_file], which trades per-frame rendering for disk streaming plus block compression.
		Materials sample the result with [method apply_to_material] and a world position. Pages that are not resident yet fall back to the closest lower resolution page that is.
		When rendering pages, meshes contribute when their [member VisualInstance3D.layers] intersect [member cull_mask]; moving, showing, hiding or re-layering them refreshes the affected pages automatically. Changes to material parameters are not tracked, call [method invalidate] after changing them.
		For debugging, [member debug_mode] replaces the sampled color with page table, residency, pool or border visualizations, [member debug_force_lod] pins the sampled level, and [method lock_page] keeps a picked page produced and resident.
		[b]Note:[/b] Only the Forward+ and Mobile renderers support runtime virtual textures.
	</description>""",
    1,
)

methods = {
    "apply_to_material": "Writes the uniforms that the RVT shader include expects into [param material]: [code]{prefix}_page_table[/code], [code]{prefix}_physical0[/code], [code]{prefix}_physical1[/code], [code]{prefix}_params0[/code], [code]{prefix}_params1[/code], [code]{prefix}_world_to_uv[/code], [code]{prefix}_normal_basis[/code], [code]{prefix}_debug_mode[/code] and [code]{prefix}_debug_force_lod[/code]. The material keeps being updated when the volume moves or the debug settings change.",
    "bake_page_file": "Bakes [param image] into a page file that [member source] = [constant SOURCE_STREAM] can stream. The virtual texture is [code]2 ^ log2_tile_count * tile_size[/code] texels wide; every page carries [param tile_border] texels of edge clamped neighbours so bilinear filtering works across page edges. [constant FORMAT_BC1] and [constant FORMAT_BC7] require the tile size and border to be multiples of 4. Returns [constant OK] on success.",
    "get_layer_count": "Returns the number of physical texture layers used by the current [member material_type] and [member source].",
    "get_page_table_texture": "Returns the indirection texture that maps virtual pages to physical pages. It has one mipmap per virtual texture level and must be read with [code]texelFetch[/code].",
    "get_physical_texture": "Returns the physical page pool texture of the given [param layer].",
    "get_page_info": "Returns the state of one page: [code]exists[/code], [code]resident[/code], [code]dirty[/code], [code]blocked[/code], [code]pool_x[/code], [code]pool_y[/code], [code]in_flight[/code], [code]locked[/code] and [code]lock_seconds_left[/code].",
    "get_stats": "Returns debugging statistics: [code]resident_pages[/code], [code]pool_pages[/code], [code]requested_pages[/code], [code]rendered_this_frame[/code], [code]rendered_total[/code], [code]evicted_total[/code], [code]gpu_ready[/code], [code]streaming[/code] and [code]levels[/code] (resident pages per level).",
    "invalidate": "Marks all pages overlapping [param world_aabb] as stale so they are rendered (or re-read) again.",
    "invalidate_all": "Marks all pages as stale so they are rendered (or re-read) again.",
    "lock_page": "Keeps the page produced and resident for [param seconds], even when it is off screen, and refreshes it every frame (mirrors UE's pick + refresh debug). At most 6 pages can be locked; locking a seventh releases the one expiring first.",
    "pick_page": "Maps a world position to the page covering it at [param level], returned as [code]Vector3i(level, x, y)[/code]. Pair with [method get_page_info] and [method lock_page].",
    "unlock_all_pages": "Releases all locked pages.",
    "unlock_page": "Releases a page locked with [method lock_page].",
}
for k, v in methods.items():
    t = fill(t, "method", k, v)

members = {
    "cull_mask": "Only [VisualInstance3D]s whose layers intersect this mask are rendered into the texture.",
    "debug_force_lod": "Pins the sampled mip level to this value. [code]-1[/code] uses the level computed from the camera distance.",
    "debug_mode": "Replaces the sampled color with a debug visualization: page table, residency per level, physical pool tiles, LOD heat map or page borders. Requires the receiver material to call the RVT shader include.",
    "enabled": "If [code]false[/code], no new pages are produced. Pages that are already resident keep being sampled.",
    "lod_bias": "Bias added to the mip level selected from the camera distance. Positive values use lower resolution pages.",
    "log2_tile_count": "Base 2 logarithm of the number of pages along one side of the virtual texture. The virtual texture is [code]2 ^ log2_tile_count * tile_size[/code] texels wide. A page file overrides this value.",
    "material_type": "What is stored in the texture when [member source] is [constant SOURCE_RENDER].",
    "max_pages_per_frame": "Maximum number of pages rendered (or loaded) per frame.",
    "page_file": "Page file to stream when [member source] is [constant SOURCE_STREAM]. Setting it switches [member source] to [constant SOURCE_STREAM] and adopts the layout stored in the file.",
    "pool_size": "Number of physical pages along one side of the page pool. The pool holds [code]pool_size * pool_size[/code] pages. When it is too small, the finest pages are dropped first.",
    "source": "Where page contents come from: rendered from the scene every frame, or streamed from [member page_file].",
    "tile_border": "Border in texels added around each page so bilinear filtering works across page edges. A page file overrides this value.",
    "tile_size": "Size of one page in texels, without border. A page file overrides this value.",
}
for k, v in members.items():
    t = fill(t, "member", k, v)

constants = {
    "MATERIAL_BASE_COLOR": "Stores albedo in the first layer (sRGB encoded, alpha holds coverage).",
    "MATERIAL_BASE_COLOR_NORMAL_ROUGHNESS": "Stores albedo in the first layer and normal (x and z of the volume local normal), roughness and metallic in the second layer.",
    "MATERIAL_WORLD_HEIGHT": "Stores the height inside the volume, normalized to [code]0..1[/code], in a single float layer.",
    "SOURCE_RENDER": "Pages are rendered from the scene every frame (runtime virtual texture).",
    "SOURCE_STREAM": "Pages are streamed from a baked page file (streaming virtual texture).",
    "FORMAT_RGBA8": "Uncompressed 8 bit per channel tiles.",
    "FORMAT_BC1": "BC1 compressed tiles, 8 bytes per 4x4 block. No alpha.",
    "FORMAT_BC7": "BC7 compressed tiles, 16 bytes per 4x4 block.",
    "FORMAT_R32F": "Single precision float tiles, used by [constant MATERIAL_WORLD_HEIGHT].",
    "DEBUG_OFF": "No debug visualization.",
    "DEBUG_PAGE_TABLE": "Colors every page by the physical pool tile it resolves to; coarser fallbacks are darker, invalid pages are magenta, page edges are white.",
    "DEBUG_PAGE_TABLE_MIP": "Colors every page by the level it actually resolves to (one color per level), which shows fallbacks directly.",
    "DEBUG_PHYSICAL_POOL": "Colors pages by their pool tile and draws the per tile border band in green.",
    "DEBUG_LOD": "Heat map of the LOD used for sampling: blue is level 0, red is the coarsest level.",
    "DEBUG_BORDERS": "Draws the page grid in red and the tile border ring in green over a dark background.",
}
for k, v in constants.items():
    t = fill(t, "constant", k, v)
wr(p, t)

# ---------------------------------------------------------------- Volume / Proxy
p = "doc/classes/RuntimeVirtualTextureVolume.xml"
t = rd(p)
t = t.replace(
    "<description>\n\t</description>",
    "<description>\n\t\tDefines the box covered by a [RuntimeVirtualTexture]. The node position and rotation together with [member size] define the covered box: the X and Z axes span the texture, the Y axis is the rendered height range, and the texture is rendered looking down the node's negative Y axis. The node scale is ignored.\n\t</description>",
    1,
)
wr(p, t)

p = "doc/classes/RuntimeVirtualTextureProxy.xml"
t = rd(p)
t = t.replace(
    "<description>\n\t</description>",
    "<description>\n\t\tReturned by [method RuntimeVirtualTexture.get_page_table_texture] and [method RuntimeVirtualTexture.get_physical_texture]. It cannot be created directly.\n\t</description>",
    1,
)
wr(p, t)

# ---------------------------------------------------------------- RenderingServer
p = "doc/classes/RenderingServer.xml"
t = rd(p)
rs_methods = {
    "runtime_virtual_texture_configure": "Configures a runtime virtual texture. See [RuntimeVirtualTexture] for the meaning of the parameters.",
    "runtime_virtual_texture_create": "Creates a runtime virtual texture. Use [method free_rid] to free it.",
    "runtime_virtual_texture_get_page_table_texture": "Returns the page table texture of the runtime virtual texture.",
    "runtime_virtual_texture_get_physical_texture": "Returns the physical page pool texture of the given layer.",
    "runtime_virtual_texture_get_page_info": "Returns the state of one page (resident, dirty, pool tile, locked).",
    "runtime_virtual_texture_get_stats": "Returns paging statistics of the runtime virtual texture.",
    "runtime_virtual_texture_invalidate": "Marks the pages overlapping [param world_aabb] as stale.",
    "runtime_virtual_texture_invalidate_all": "Marks all pages as stale.",
    "runtime_virtual_texture_lock_page": "Keeps a page produced and resident for [param seconds] and refreshes it every frame.",
    "runtime_virtual_texture_set_cull_mask": "Sets the instance layers rendered into the runtime virtual texture.",
    "runtime_virtual_texture_set_debug": "Selects the debug visualization and pins the sampled LOD ([code]-1[/code] keeps the computed one).",
    "runtime_virtual_texture_set_enabled": "If [code]false[/code], no new pages are produced.",
    "runtime_virtual_texture_set_lod_bias": "Sets the bias applied to the mip level selected for a viewer.",
    "runtime_virtual_texture_set_max_pages_per_frame": "Sets the maximum number of pages rendered or loaded per frame.",
    "runtime_virtual_texture_set_page_file": "Sets the page file streamed when the source is [constant RVT_SOURCE_STREAM]. The file layout overrides the configured page size.",
    "runtime_virtual_texture_set_scenario": "Sets the scenario whose instances are rendered into the runtime virtual texture.",
    "runtime_virtual_texture_set_source": "Selects whether pages are rendered from the scene ([constant RVT_SOURCE_RENDER]) or streamed from a page file ([constant RVT_SOURCE_STREAM]).",
    "runtime_virtual_texture_set_transform": "Sets the transform that maps the centered unit cube to the world area covered by the runtime virtual texture.",
    "runtime_virtual_texture_unlock_all_pages": "Releases every locked page.",
    "runtime_virtual_texture_unlock_page": "Releases one locked page.",
}
for k, v in rs_methods.items():
    t = fill(t, "method", k, v)
rs_constants = {
    "RVT_MATERIAL_BASE_COLOR": "Stores albedo.",
    "RVT_MATERIAL_BASE_COLOR_NORMAL_ROUGHNESS": "Stores albedo, normal, roughness and metallic.",
    "RVT_MATERIAL_WORLD_HEIGHT": "Stores the normalized height inside the volume.",
    "RVT_SOURCE_RENDER": "Pages are rendered from the scene every frame.",
    "RVT_SOURCE_STREAM": "Pages are streamed from a baked page file.",
    "RVT_DEBUG_OFF": "No debug visualization.",
    "RVT_DEBUG_PAGE_TABLE": "Page table visualization.",
    "RVT_DEBUG_PAGE_TABLE_MIP": "Residency per level visualization.",
    "RVT_DEBUG_PHYSICAL_POOL": "Physical pool tile visualization.",
    "RVT_DEBUG_LOD": "LOD heat map.",
    "RVT_DEBUG_BORDERS": "Page grid and tile border visualization.",
}
for k, v in rs_constants.items():
    t = fill(t, "constant", k, v)
wr(p, t)
print("docs filled")
print("now run: python doc/tools/make_rst.py doc/classes modules platform --dry-run")
