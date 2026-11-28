// Copyright 漏 2023-2026 Cory Petkovsek, Roope Palmroos, and Contributors.

#include "Terrain3DGPUDriven.h"

#include "core/config/engine.h"
#include "core/io/image.h"
#include "servers/rendering/rendering_server.h"
#include "scene/resources/3d/world_3d.h"
#include "core/variant/variant.h"
#include "core/variant/typed_array.h"

#include "logger.h"
#include "terrain_3d.h"
#include "terrain_3d_material.h"
#include "terrain_3d_mesher.h"
#include "Terrain3DQuadtree.h"

void Terrain3DGPUDriven::ReleaseGeometry()
{
	for (RID *pResource : { &ridHookRid, &ridInstance, &ridMultimesh, &ridMesh, &ridNodeTexture })
	{
		if (pResource->is_valid())
		{
			TERRAIN_RS->free_rid(*pResource);
			*pResource = RID();
		}
	}
}

Rect2i Terrain3DGPUDriven::GetDrawExtent() const
{
	const Terrain3DQuadTree *pTree = pTerrain->GetQuadTree();
	if (nBackground == Terrain3DMaterial::NONE)
	{
		return pTree->GetExtent();
	}
	// Keep candidate cells on the world tile lattice as the procedural footprint moves.
	// The padded power-of-two root contains the clipmap square at every snap position.
	const int nRes = pTree->GetTileRes();
	const int nAlignment = MIN(int(VariantUtilityFunctions::nearest_po2(MAX(nRes, rectClipmapBounds.size.x))), nRes << CLAMP(nCullMaxLod, 0, 15));
	const int nSide = VariantUtilityFunctions::nearest_po2(rectClipmapBounds.size.x + nAlignment);
	const Vector2i vOrigin = V2I_DIVIDE_FLOOR(rectClipmapBounds.position, nAlignment) * nAlignment;
	return Rect2i(vOrigin, V2I(nSide));
}

void Terrain3DGPUDriven::UpdateDrawBounds()
{
	const RID ridMat = pTerrain->get_material()->get_material_rid();
	if (ridMat.is_valid())
	{
		const Vector2i vEnd = rectClipmapBounds.get_end();
		TERRAIN_RS->material_set_param(ridMat, "_t3d_draw_bounds", Vector4(rectClipmapBounds.position.x, rectClipmapBounds.position.y, vEnd.x, vEnd.y));
	}
}

void Terrain3DGPUDriven::RebuildGeometry()
{
	ReleaseGeometry();
	const Terrain3DQuadTree *pTree = pTerrain->GetQuadTree();
	const Terrain3DMaterial::WorldBackground eWorldBackground = pTerrain->get_material()->get_world_background();
	bVtDirty |= eWorldBackground != nBackground;
	nBackground = eWorldBackground;
	rectDrawExtent = GetDrawExtent();
	if (!rectDrawExtent.has_area() || pTerrain->get_world_3d().is_null())
	{
		return;
	}
	const real_t fSpacing = pTerrain->get_vertex_spacing();
	const int nRes = pTree->GetTileRes();
	const int nBaseTiles = MAX(1, rectDrawExtent.size.x / nRes);
	int nRootLevel = 0;
	for (int nWidth = nBaseTiles; nWidth > 1; nWidth >>= 1)
	{
		++nRootLevel;
	}
	const int nLastLevel = CLAMP(nCullMaxLod, 0, nRootLevel);
	const float fRadius = MAX(fCullLod0Dist, 4.f * nRes * float(fSpacing));
	// The final texel describes the root. Each preceding texel describes a square of
	// candidate nodes at one level. Below the coarsest level only the children of a
	// split parent can be visible, so its split radius bounds the work around the camera.
	nTexWidth = nLastLevel + 2;
	arrDescriptors.resize(nTexWidth * 4);
	float *pDst = arrDescriptors.ptrw();
	nNodeCount = 0;
	for (int nLevel = 0; nLevel <= nLastLevel; ++nLevel)
	{
		const float fSide = (nRes << nLevel) * fSpacing;
		const int nTiles = nBaseTiles >> nLevel;
		const float fLimit = fCullMaxDistance > 0.f ? fCullMaxDistance : float(rectDrawExtent.size.x * fSpacing);
		const float fReach = nLevel == nLastLevel ? fLimit : MIN(fLimit, 2.f * fRadius * (1 << nLevel) + fSide);
		const int nHalf = MIN(nTiles, int(Math::ceil(MAX(fReach, 0.f) / fSide)) + 1);
		const int nWidth = MIN(nTiles, 2 * nHalf + 1);
		// A negative width means all tiles at this level fit, with fixed origins.
		*pDst++ = nWidth == nTiles ? -float(nWidth) : float(nWidth);
		*pDst++ = float(nNodeCount);
		*pDst++ = fSide;
		*pDst++ = float(nLevel);
		// Levels and dispatch bounds use exactly representable float indices.
		const int64_t nNextCount = int64_t(nNodeCount) + int64_t(nWidth) * nWidth;
		ERR_FAIL_COND_MSG(nNextCount > (1 << 24), "Terrain quadtree exceeds the GPU candidate index range. Increase TileRes or reduce MaxDistance.");
		nNodeCount = int(nNextCount);
	}
	*pDst++ = rectDrawExtent.position.x * fSpacing;
	*pDst++ = rectDrawExtent.position.y * fSpacing;
	*pDst++ = rectDrawExtent.size.x * fSpacing;
	*pDst++ = float(nRootLevel);
	nCapacity = int(MIN(int64_t(nNodeCount), int64_t(nBaseTiles) * nBaseTiles));
	ridNodeTexture = TERRAIN_RS->texture_2d_create(Image::create_from_data(nTexWidth, 1, false, Image::FORMAT_RGBAF, arrDescriptors.to_byte_array()));
	ridMesh = pTerrain->get_mesher()->CreateTileMesh(nRes);
	ridMultimesh = TERRAIN_RS->multimesh_create();
	TERRAIN_RS->multimesh_set_mesh(ridMultimesh, ridMesh);
	TERRAIN_RS->multimesh_allocate_data(ridMultimesh, nCapacity, RSE::MULTIMESH_TRANSFORM_3D, false, true, true);
	ridInstance = TERRAIN_RS->instance_create2(ridMultimesh, pTerrain->get_world_3d()->get_scenario());
	ridHookRid = TERRAIN_RS->GpuDrivenTerrainCreate();
	UpdateInstance();
	ApplyCullConfig();
}

void Terrain3DGPUDriven::UpdateInstance()
{
	if (!ridInstance.is_valid())
	{
		return;
	}
	const uint32_t nLayers = pTerrain->get_render_layers() & ~(1u << (pTerrain->get_mouse_layer() - 1));
	const bool bVisible = pTerrain->is_inside_world() && pTerrain->is_visible_in_tree();
	TERRAIN_RS->instance_set_visible(ridInstance, bVisible);
	TERRAIN_RS->instance_set_layer_mask(ridInstance, nLayers);
	TERRAIN_RS->instance_geometry_set_cast_shadows_setting(ridInstance, pTerrain->get_cast_shadows());
	const GeometryInstance3D::GIMode eGiMode = pTerrain->get_gi_mode();
	TERRAIN_RS->instance_geometry_set_flag(ridInstance, RSE::INSTANCE_FLAG_USE_BAKED_LIGHT, eGiMode == GeometryInstance3D::GI_MODE_STATIC);
	TERRAIN_RS->instance_geometry_set_flag(ridInstance, RSE::INSTANCE_FLAG_USE_DYNAMIC_GI, eGiMode == GeometryInstance3D::GI_MODE_DYNAMIC);
	const Ref<Terrain3DMaterial> refMat = pTerrain->get_material();
	float fGround = 0.f;
	Vector2 vNoise;
	if (nBackground != Terrain3DMaterial::NONE)
	{
		fGround = refMat->get_shader_param("ground_level");
		if (nBackground == Terrain3DMaterial::NOISE)
		{
			// world_noise sums positive octaves weighted by 1, 1/2, 1/4, ...
			const float fAmplitude = float(refMat->get_shader_param("world_noise_height")) * 20.f;
			const Vector3 vOffset = refMat->get_shader_param("world_noise_offset");
			vNoise = Vector2(MIN(0.f, float(vOffset.y) * 100.f + MIN(0.f, fAmplitude)),
							 MAX(0.f, float(vOffset.y) * 100.f + MAX(0.f, fAmplitude)));
		}
	}
	vBackgroundHeights = Vector2(MIN(0.f, fGround), MAX(0.f, fGround)) + vNoise;
	bVtDirty |= fGroundHeight != fGround || vNoiseRange != vNoise;
	fGroundHeight = fGround;
	vNoiseRange = vNoise;
	UpdateMeshBounds();
	const real_t fSpacing = pTerrain->get_vertex_spacing();
	const RID ridMaterial = refMat->get_material_rid();
	TERRAIN_RS->mesh_surface_set_material(ridMesh, 0, ridMaterial);
	UpdateDrawBounds();
	const int nRes = pTerrain->GetQuadTree()->GetTileRes();
	TERRAIN_RS->material_set_param(ridMaterial, "_t3d_tile_res", float(nRes));
	TERRAIN_RS->material_set_param(ridMaterial, "_t3d_lod0_distance", MAX(fCullLod0Dist, 4.f * nRes * float(fSpacing)));
	TERRAIN_RS->material_set_param(ridMaterial, "_t3d_last_lod", nTexWidth - 2);
	// Empty vertex array: this registration schedules compute only; MultiMesh submits the draw.
	TERRAIN_RS->GpuDrivenTerrainConfigure(ridHookRid, ridMaterial, RID(), RID(), nRes * nRes * 6, 0, nLayers, false);
	TERRAIN_RS->GpuDrivenTerrainSetEnabled(ridHookRid, bVisible);
	BindHeightfield();
}

void Terrain3DGPUDriven::UpdateMeshBounds()
{
	if (!ridMultimesh.is_valid())
	{
		return;
	}
	Vector2 vHeights = pTerrain->get_data()->get_height_range();
	if (nBackground != Terrain3DMaterial::NONE)
	{
		vHeights.x = MIN(vHeights.x, fGroundHeight) + vNoiseRange.x;
		vHeights.y = MAX(vHeights.y, fGroundHeight) + vNoiseRange.y;
	}
	// Direct Image edits can precede a Terrain3DRegion height-range refresh.
	// Include the exact published root range in the scene's broad-phase AABB.
	const Vector2 vVtBounds = stHeightBounds.GetGlobalRange();
	vHeights.x = MIN(vHeights.x, vVtBounds.x);
	vHeights.y = MAX(vHeights.y, vVtBounds.y);
	const real_t fSpacing = pTerrain->get_vertex_spacing();
	const AABB aabbBounds(Vector3(rectDrawExtent.position.x * fSpacing, vHeights.x, rectDrawExtent.position.y * fSpacing),
						  Vector3(rectDrawExtent.size.x * fSpacing, MAX(vHeights.y - vHeights.x, 0.01f), rectDrawExtent.size.y * fSpacing));
	TERRAIN_RS->multimesh_set_custom_aabb(ridMultimesh, aabbBounds.grow(pTerrain->get_cull_margin()));
}

void Terrain3DGPUDriven::ApplyCullConfig()
{
	if (!ridHookRid.is_valid())
	{
		return;
	}
	const RID ridNodes = TERRAIN_RS->texture_get_rd_texture(ridNodeTexture);
	const RID ridInstances = TERRAIN_RS->multimesh_get_buffer_rd_rid(ridMultimesh);
	const RID ridArgs = TERRAIN_RS->multimesh_get_command_buffer_rd_rid(ridMultimesh);
	// With automatic coverage the finite draw footprint and view frustum bound the cut, including high-altitude views.
	const float fDistance = fCullMaxDistance > 0.f ? fCullMaxDistance : FLT_MAX;
	// No secondary command buffer: the renderer writes native MultiMesh transforms and
	// shares its one instance count between all passes of this view.
	TERRAIN_RS->GpuDrivenTerrainSetCull(ridHookRid, (int64_t)ridNodes.get_id(), (int64_t)ridInstances.get_id(), 0,
										(int64_t)ridArgs.get_id(), 0, nNodeCount, float(nTexWidth), float(nCapacity),
										fCullLod0Dist, nCullMaxLod, fDistance, float(pTerrain->get_vertex_spacing()));
	if (ridHeightRvt.is_valid())
	{
		const float fSpacing = pTerrain->get_vertex_spacing();
		const float fRadius = MAX(fCullLod0Dist, 4.f * pTerrain->GetQuadTree()->GetTileRes() * fSpacing);
		TERRAIN_RS->RuntimeVirtualTextureSetHeightLod(ridHeightRvt, fRadius, fSpacing, nTexWidth - 2, fDistance);
	}
}

void Terrain3DGPUDriven::SetCullParams(float fLod0Dist, int nMaxLod, float fMaxDistance)
{
	if (fCullLod0Dist == fLod0Dist && nCullMaxLod == nMaxLod && fCullMaxDistance == fMaxDistance)
	{
		return;
	}
	fCullLod0Dist = fLod0Dist;
	nCullMaxLod = nMaxLod;
	fCullMaxDistance = fMaxDistance;
	Rebuild();
}

void Terrain3DGPUDriven::Initialize(Terrain3D *in_pTerrain)
{
	pTerrain = in_pTerrain;
	bDirty = true;
	bVtDirty = true;
}

void Terrain3DGPUDriven::Destroy()
{
	if (!pTerrain)
	{
		return;
	}
	ReleaseGeometry();
	ReleaseVt();
	stHeightBounds.Clear();
	bVtDirty = true;
	pTerrain = nullptr;
}

void Terrain3DGPUDriven::Update()
{
	if (!pTerrain)
	{
		LOG(ERROR, "Terrain not initialized");
		return;
	}
	const Rect2i rectFootprint = pTerrain->get_mesher()->GetClipmapBounds();
	const bool bMoved = rectFootprint != rectClipmapBounds;
	bDirty |= rectFootprint.size != rectClipmapBounds.size;
	rectClipmapBounds = rectFootprint;
	if (bDirty || nBackground != pTerrain->get_material()->get_world_background())
	{
		RebuildGeometry();
		bDirty = false;
	}
	else if (bMoved && ridNodeTexture.is_valid())
	{
		const Rect2i rectExtent = GetDrawExtent();
		if (rectExtent.position != rectDrawExtent.position)
		{
			rectDrawExtent = rectExtent;
			const int nRoot = arrDescriptors.size() - 4;
			arrDescriptors.set(nRoot, rectExtent.position.x * pTerrain->get_vertex_spacing());
			arrDescriptors.set(nRoot + 1, rectExtent.position.y * pTerrain->get_vertex_spacing());
			TERRAIN_RS->texture_2d_update(ridNodeTexture, Image::create_from_data(nTexWidth, 1, false, Image::FORMAT_RGBAF, arrDescriptors.to_byte_array()), 0);
			UpdateMeshBounds();
		}
		UpdateDrawBounds();
	}
	if (bVtDirty || bStreamDirty || fVtSpacing != pTerrain->get_vertex_spacing())
	{
		UpdateHeightResources();
	}
	if (ridHeightRvt.is_valid() && !bVtReady && Engine::get_singleton()->get_frames_drawn() != nVtConfigFrame)
	{
		const Dictionary dictStats = TERRAIN_RS->RuntimeVirtualTextureGetStats(ridHeightRvt);
		const PackedInt32Array arrLevels = dictStats.get("levels", PackedInt32Array());
		if (arrLevels.size() > nVtLog2 && arrLevels[nVtLog2] != 0)
		{
			bVtReady = true;
			ApplyVtUniforms();
		}
	}
	const Ref<Terrain3DMaterial> refMaterial = pTerrain->get_material();
	const bool bCustomDisplacement = pTerrain->get_tessellation_level() > 0 && refMaterial->is_buffer_shader_override_enabled();
	const bool bUsesNative = !bVtReady || IS_EDITOR || bCustomDisplacement || refMaterial->UsesNativeHeightForMaterialRvt() ||
							 refMaterial->is_shader_override_enabled() || pTerrain->get_show_jaggedness();
	pTerrain->get_data()->SetNativeHeightRequired(bUsesNative);
}

void Terrain3DGPUDriven::SetVtConfig(bool bEnabled, int nLog2, int nTile, int nBorder, int nPool)
{
	nLog2 = CLAMP(nLog2, 1, 10);
	nTile = CLAMP(nTile, 16, 1024);
	// Bilinear sampling at page boundaries needs at least one neighboring texel.
	nBorder = CLAMP(nBorder, 1, 16);
	nPool = CLAMP(nPool, 2, MIN(255, 16384 / (nTile + 2 * nBorder)));
	if (bVtEnabled != bEnabled || nVtLog2 != nLog2 || nVtTile != nTile || nVtBorder != nBorder || nVtPool != nPool)
	{
		ReleaseVt();
		bVtDirty = true;
	}
	bVtEnabled = bEnabled;
	nVtLog2 = nLog2;
	nVtTile = nTile;
	nVtBorder = nBorder;
	nVtPool = nPool;
	ApplyVtUniforms();
}

void Terrain3DGPUDriven::ReleaseVt()
{
	const RID ridOld = ridHeightRvt;
	ridHeightRvt = RID();
	bVtReady = false;
	if (ridOld.is_valid())
	{
		// Release material-writer dependencies before destroying the old pool.
		ApplyVtUniforms();
		TERRAIN_RS->free_rid(ridOld);
	}
}

void Terrain3DGPUDriven::BindHeightfield()
{
	if (!ridHookRid.is_valid())
	{
		return;
	}
	const float fSpacing = pTerrain->get_vertex_spacing();
	const Rect2 rectDomain(Vector2(rectVtExtent.position) * fSpacing, Vector2(rectVtExtent.size) * fSpacing);
	const float fMargin = pTerrain->get_tessellation_level() > 0 ? Math::abs(pTerrain->get_material()->get_displacement_scale()) : 0.f;
	TERRAIN_RS->GpuDrivenTerrainSetHeightfield(ridHookRid, ridHeightRvt, stHeightBounds.GetTexture(), rectDomain,
											   vBackgroundHeights, fMargin, nVtLog2, nVtTile);
}

void Terrain3DGPUDriven::UpdateHeightResources()
{
	Terrain3DData *pData = pTerrain->get_data();
	const Rect2i rectExtent = pTerrain->GetQuadTree()->GetExtent();
	const int nRegionSize = pTerrain->get_region_size();
	const float fSpacing = pTerrain->get_vertex_spacing();
	const bool bMappingChanged = rectExtent != rectVtExtent || fVtSpacing != fSpacing || nVtRegionSize != nRegionSize;
	bVtDirty = false;
	fVtSpacing = fSpacing;
	nVtRegionSize = nRegionSize;
	rectVtExtent = rectExtent;
	if (!rectExtent.has_area())
	{
		ReleaseVt();
		stHeightBounds.Clear();
		BindHeightfield();
		ApplyVtUniforms();
		bStreamDirty = false;
		return;
	}

	Vector<Rect2i> arrChanged;
	stHeightBounds.Update(pData, rectExtent, nRegionSize, 1 << nVtLog2, nVtTile, nBackground != Terrain3DMaterial::NONE, fGroundHeight, vNoiseRange, arrChanged);
	UpdateMeshBounds();
	if (bVtEnabled)
	{
		if (bMappingChanged && ridHeightRvt.is_valid())
		{
			ReleaseVt();
		}
		const bool bCreate = !ridHeightRvt.is_valid();
		if (bCreate)
		{
			ridHeightRvt = TERRAIN_RS->RuntimeVirtualTextureCreate();
			ERR_FAIL_COND(!ridHeightRvt.is_valid());
			TERRAIN_RS->RuntimeVirtualTextureConfigure(ridHeightRvt, RSE::RVT_MATERIAL_WORLD_HEIGHT, nVtLog2, nVtTile, nVtBorder, nVtPool);
			TERRAIN_RS->RuntimeVirtualTextureSetMaxPagesPerFrame(ridHeightRvt, 64);
			TERRAIN_RS->RuntimeVirtualTextureSetScenario(ridHeightRvt, pTerrain->get_world_3d()->get_scenario());
		}
		// Region snapshots are copy-on-write. The producer needs only CPU inputs and
		// writes the requested R32F tiles, without retaining a full source GPU array.
		TERRAIN_RS->RuntimeVirtualTextureSetHeightSource(ridHeightRvt, RID(), pData->get_region_map(),
														 nRegionSize, rectExtent.position, rectExtent.size.x);
		if (bCreate)
		{
			for (const Vector2i &vLocation : pData->get_region_locations())
			{
				const Terrain3DRegion *pRegion = pData->get_region_ptr(vLocation);
				if (pRegion)
				{
					TERRAIN_RS->RuntimeVirtualTextureSetHeightRegion(ridHeightRvt, vLocation, pRegion->get_height_map());
				}
			}
		}
		else
		{
			for (const Rect2i &rectRect : arrChanged)
			{
				// Changed rectangles are already intersected with one region by the bounds builder.
				const Vector2i vLocation = V2I_DIVIDE_FLOOR(rectRect.position, nRegionSize);
				const Terrain3DRegion *pRegion = pData->get_region_ptr(vLocation);
				TERRAIN_RS->RuntimeVirtualTextureSetHeightRegion(ridHeightRvt, vLocation,
																 pRegion && !pRegion->is_deleted() ? pRegion->get_height_map() : Ref<Image>());
			}
		}
		if (bCreate || bMappingChanged)
		{
			const float fSide = float(rectExtent.size.x) * fSpacing;
			Transform3D xformVolume;
			xformVolume.basis.scale(Vector3(fSide, 1.f, fSide));
			xformVolume.origin = Vector3(rectExtent.position.x * fSpacing + 0.5f * fSide, 0.f, rectExtent.position.y * fSpacing + 0.5f * fSide);
			TERRAIN_RS->RuntimeVirtualTextureSetTransform(ridHeightRvt, xformVolume);
			ApplyCullConfig();
			bVtReady = false;
		}
		if (bCreate || bStreamDirty)
		{
			// Stream configuration replaces the physical pool on the next render frame.
			// A stats poll here could still observe the previous pool's root.
			bVtReady = false;
			nVtConfigFrame = Engine::get_singleton()->get_frames_drawn();
			TERRAIN_RS->RuntimeVirtualTextureSetHeightStream(ridHeightRvt, pTerrain->GetHeightVtStreamFile(), pTerrain->GetHeightVtStreamLevels());
		}
		if (!bCreate && !bMappingChanged)
		{
			for (const Rect2i &rectR : arrChanged)
			{
				TERRAIN_RS->RuntimeVirtualTextureInvalidate(ridHeightRvt,
															AABB(Vector3(rectR.position.x * fSpacing, -1.f, rectR.position.y * fSpacing), Vector3(rectR.size.x * fSpacing, 2.f, rectR.size.y * fSpacing)));
			}
		}
	}
	BindHeightfield();
	ApplyVtUniforms();
	bStreamDirty = false;
}

void Terrain3DGPUDriven::ApplyVtUniforms()
{
	if (!pTerrain || pTerrain->get_material().is_null())
	{
		return;
	}
	const Ref<Terrain3DMaterial> refMaterial = pTerrain->get_material();
	RID ridTable, stPhysical;
	if (ridHeightRvt.is_valid())
	{
		ridTable = TERRAIN_RS->RuntimeVirtualTextureGetPageTableTexture(ridHeightRvt);
		stPhysical = TERRAIN_RS->RuntimeVirtualTextureGetPhysicalTexture(ridHeightRvt, 0);
	}
	const Vector4 vGrid(rectVtExtent.position.x, rectVtExtent.position.y, rectVtExtent.size.x, bVtReady ? 1.f : 0.f);
	const Vector4 vLayout(1 << nVtLog2, nVtLog2, nVtTile, nVtBorder);
	const RID ridMat = refMaterial->get_material_rid();
	if (ridMat.is_valid())
	{
		TERRAIN_RS->material_set_param(ridMat, "_t3d_vt_page_table", ridTable);
		TERRAIN_RS->material_set_param(ridMat, "_t3d_vt_physical0", stPhysical);
		TERRAIN_RS->material_set_param(ridMat, "_t3d_vt_grid", vGrid);
		TERRAIN_RS->material_set_param(ridMat, "_t3d_vt_layout", vLayout);
	}
	refMaterial->SetHeightVtSource(ridHeightRvt, ridTable, stPhysical, vGrid, vLayout);
}
