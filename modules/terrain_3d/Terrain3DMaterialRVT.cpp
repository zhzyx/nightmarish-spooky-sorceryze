// Copyright © 2023-2026 Cory Petkovsek, Roope Palmroos, and Contributors.

#include "terrain_3d_material.h"

#include "servers/rendering/rendering_server.h"
#include "scene/resources/3d/world_3d.h"

#include "terrain_3d.h"
#include "terrain_3d_data.h"
#include "Terrain3DQuadtree.h"

namespace
{
constexpr int MATERIAL_TILE = 256;
constexpr int MATERIAL_BORDER = 4;
constexpr int MATERIAL_TEXELS_PER_CELL = 64;
constexpr int MATERIAL_MAX_LEVEL = 10;
constexpr int DETAIL_SIDE = 512; // Native grid cells.
constexpr int DETAIL_TILE = 128;
const char *const arrMATERIALPREFIX[] = { "_t3d_material_rvt_", "_t3d_material_rvt_far_", "_t3d_material_rvt_detail_", "_t3d_material_rvt_detail_far_" };

int MaterialLevels(int nSide, int in_nTile = MATERIAL_TILE)
{
	int nLevels = 1;
	while (nLevels < MATERIAL_MAX_LEVEL && (in_nTile << nLevels) < int64_t(nSide) * MATERIAL_TEXELS_PER_CELL)
	{
		++nLevels;
	}
	return nLevels;
}
} // namespace

void Terrain3DMaterial::SetMaterialRvtEnabled(bool bEnabled)
{
	if (bMaterialRvtEnabled == bEnabled)
	{
		return;
	}
	bMaterialRvtEnabled = bEnabled;
	if (_terrain && _material.is_valid())
	{
		if (!bEnabled)
		{
			ReleaseMaterialRvt();
		}
		update(FULL_REBUILD);
		UpdateRuntimeVirtualTexture();
	}
}

void Terrain3DMaterial::SetMaterialRvtFarMipBias(real_t fBias)
{
	fMaterialRvtFarMipBias = CLAMP(fBias, real_t(0), real_t(6));
	if (arrRvtWriters[1].ridSurface.is_valid())
	{
		TERRAIN_RS->RuntimeVirtualTextureSetLodBias(arrRvtWriters[1].ridSurface, fMaterialRvtFarMipBias);
		TERRAIN_RS->material_set_param(_material, "_t3d_material_rvt_far_bias", fMaterialRvtFarMipBias);
	}
}

void Terrain3DMaterial::ReleaseMaterialRvt()
{
	for (MaterialPageWriter &stWriter : arrRvtWriters)
	{
		// Release the page surface before the render instance it references.
		for (RID *pRid : { &stWriter.ridSurface, &stWriter.ridInstance, &stWriter.ridMaterial })
		{
			if (pRid->is_valid())
			{
				TERRAIN_RS->free_rid(*pRid);
				*pRid = RID();
			}
		}
	}
	refRvtPlane.unref();
	refRvtWriterShader.unref();
	bRvtStreamHashValid = false;
	nRvtStreamRetryTicks = 0;
	rectRvtExtent = Rect2i();
	rectRvtDetailExtent = Rect2i();
	ridRvtScenario = RID();
	if (_material.is_valid())
	{
		TERRAIN_RS->material_set_param(_material, "_t3d_material_rvt_grid", Vector4(0, 0, 1, 0));
		TERRAIN_RS->material_set_param(_material, "_t3d_material_rvt_detail_grid", Vector4(0, 0, 1, 0));
	}
}

void Terrain3DMaterial::InvalidateMaterialRvt(const AABB &aabbBounds)
{
	bRvtStreamHashValid = false;
	for (const MaterialPageWriter &stWriter : arrRvtWriters)
	{
		if (!stWriter.ridSurface.is_valid())
		{
			continue;
		}
		if (aabbBounds.size.x > 0.0 && aabbBounds.size.z > 0.0)
		{
			// Terrain normals look two samples beyond the shaded cell. The page manager
			// also expands this rectangle by each mip's texture gutter.
			const AABB aabbExpanded = aabbBounds.grow(2.0 * fRvtSpacing);
			TERRAIN_RS->RuntimeVirtualTextureInvalidate(stWriter.ridSurface, aabbExpanded);
		}
		else
		{
			TERRAIN_RS->RuntimeVirtualTextureInvalidateAll(stWriter.ridSurface);
		}
	}
}

void Terrain3DMaterial::BindWriterHeight(const MaterialPageWriter &in_stWriter)
{
	const bool bVt = ridRvtHeightSource.is_valid();
	TERRAIN_RS->material_set_param(in_stWriter.ridMaterial, "_t3d_mode", bVt ? 1.0f : 0.0f);
	TERRAIN_RS->material_set_param(in_stWriter.ridMaterial, "_t3d_vt_grid", vRvtHeightGrid);
	TERRAIN_RS->material_set_param(in_stWriter.ridMaterial, "_t3d_vt_layout", vRvtHeightLayout);
	TERRAIN_RS->material_set_param(in_stWriter.ridMaterial, "_t3d_vt_page_table", ridRvtHeightTable);
	TERRAIN_RS->material_set_param(in_stWriter.ridMaterial, "_t3d_vt_physical0", ridRvtHeightPhysical);
	const RID ridNative = !bVt && _terrain && _terrain->get_data() ? _terrain->get_data()->GetResidentHeightMapsRid() : RID();
	TERRAIN_RS->material_set_param(in_stWriter.ridMaterial, "_height_maps", ridNative.is_valid() ? ridNative : _generated_dummy.get_rid());
}

void Terrain3DMaterial::SetHeightVtSource(RID ridHeightRvt, RID ridPageTable, RID ridPhysical, Vector4 vGrid, Vector4 vLayout)
{
	const RID ridSource = vGrid.w > 0.5 && ridPageTable.is_valid() && ridPhysical.is_valid() ? ridHeightRvt : RID();
	if (ridRvtHeightSource == ridSource && ridRvtHeightTable == ridPageTable && ridRvtHeightPhysical == ridPhysical &&
		vRvtHeightGrid == vGrid && vRvtHeightLayout == vLayout)
	{
		return;
	}
	ridRvtHeightSource = ridSource;
	ridRvtHeightTable = ridPageTable;
	ridRvtHeightPhysical = ridPhysical;
	vRvtHeightGrid = vGrid;
	vRvtHeightLayout = vLayout;
	if (_buffer_material.is_valid())
	{
		TERRAIN_RS->material_set_param(_buffer_material, "_t3d_mode", ridSource.is_valid() ? 1.0f : 0.0f);
		TERRAIN_RS->material_set_param(_buffer_material, "_t3d_vt_grid", vGrid);
		TERRAIN_RS->material_set_param(_buffer_material, "_t3d_vt_layout", vLayout);
		TERRAIN_RS->material_set_param(_buffer_material, "_t3d_vt_page_table", ridPageTable);
		TERRAIN_RS->material_set_param(_buffer_material, "_t3d_vt_physical0", ridPhysical);
	}
	if (!GetMaterialRvtRid().is_valid())
	{
		return;
	}
	if (UsesNativeHeightForMaterialRvt() && _terrain && _terrain->get_data())
	{
		_terrain->get_data()->SetNativeHeightRequired(true);
	}
	for (const MaterialPageWriter &stWriter : arrRvtWriters)
	{
		if (stWriter.ridSurface.is_valid())
		{
			BindWriterHeight(stWriter);
			TERRAIN_RS->RuntimeVirtualTextureSetMaterialHeightSource(stWriter.ridSurface, ridSource);
		}
	}
}

void Terrain3DMaterial::SyncRvtWriters(uint32_t nFlags)
{
	for (int nI = 0; nI < MATERIAL_VOLUME_COUNT; ++nI)
	{
		const RID ridWriter = arrRvtWriters[nI].ridMaterial;
		if (!ridWriter.is_valid())
		{
			continue;
		}
		_update_uniforms(ridWriter, nFlags);
		BindWriterHeight(arrRvtWriters[nI]);
		for (const StringName &snParam : _active_params)
		{
			TERRAIN_RS->material_set_param(ridWriter, snParam, TERRAIN_RS->material_get_param(_material, snParam));
		}
		TERRAIN_RS->material_set_param(ridWriter, "_background_mode", _world_background);
		TERRAIN_RS->material_set_param(ridWriter, "_t3d_material_rvt_writer_far", float(nI == WORLD_VOLUME || nI == DETAIL_FAR_VOLUME));
	}
	UpdateDetailFeedbackLimits();
}

void Terrain3DMaterial::PlaceMaterialVolume(MaterialVolume stVolume, const Rect2i &in_rectExtent)
{
	const MaterialPageWriter &stWriter = arrRvtWriters[stVolume];
	const real_t fSide = in_rectExtent.size.x * fRvtSpacing;
	const Vector2 vOrigin = Vector2(in_rectExtent.position) * fRvtSpacing;
	Transform3D xformVolume;
	xformVolume.basis.scale(Vector3(fSide, vRvtVolumeHeights.y - vRvtVolumeHeights.x, fSide));
	xformVolume.origin = Vector3(vOrigin.x + fSide * 0.5, (vRvtVolumeHeights.x + vRvtVolumeHeights.y) * 0.5, vOrigin.y + fSide * 0.5);
	// Rolling edge pages can become interior pages on the next step. Render the
	// full border even for the single coarsest tile, keeping UVs in world metres.
	const real_t fPlaneSide = stVolume >= DETAIL_NEAR_VOLUME ? fSide * (1.0 + 2.0 * MATERIAL_BORDER / DETAIL_TILE) : fSide;
	TERRAIN_RS->instance_set_transform(stWriter.ridInstance, Transform3D(Basis().scaled(Vector3(fPlaneSide, 1, fPlaneSide)), xformVolume.origin));
	TERRAIN_RS->RuntimeVirtualTextureSetTransform(stWriter.ridSurface, xformVolume);
	if (stVolume != DETAIL_FAR_VOLUME)
	{
		TERRAIN_RS->material_set_param(_material, String(arrMATERIALPREFIX[stVolume]) + "grid", Vector4(vOrigin.x, vOrigin.y, fSide, 1));
	}
}

void Terrain3DMaterial::UpdateDetailFeedbackLimits()
{
	if (!arrRvtWriters[DETAIL_NEAR_VOLUME].ridSurface.is_valid())
	{
		return;
	}
	const real_t fOuterTexel = rectRvtOuterExtent.size.x * fRvtSpacing / (MATERIAL_TILE << MaterialLevels(rectRvtOuterExtent.size.x));
	const real_t fRadius = DETAIL_SIDE * fRvtSpacing * 0.375;
	const real_t fFootprint = 4 * fOuterTexel;
	TERRAIN_RS->material_set_param(_material, "_t3d_material_rvt_detail_limits", Vector2(fRadius, fFootprint));
	const bool bDual = arrRvtWriters[DETAIL_FAR_VOLUME].ridSurface.is_valid();
	const real_t fNearDistance = bDual ? real_t(get_shader_param("dual_scale_near")) : 0;
	const real_t fFarDistance = bDual ? MAX(real_t(get_shader_param("dual_scale_far")), fNearDistance + real_t(0.0001)) : 0;
	TERRAIN_RS->RuntimeVirtualTextureSetMaterialFeedbackLimits(arrRvtWriters[DETAIL_NEAR_VOLUME].ridSurface, Vector4(0, fFarDistance, fRadius, fFootprint));
	if (bDual)
	{
		TERRAIN_RS->RuntimeVirtualTextureSetMaterialFeedbackLimits(arrRvtWriters[DETAIL_FAR_VOLUME].ridSurface, Vector4(fNearDistance, 0, fRadius, fFootprint));
	}
}

void Terrain3DMaterial::UpdateRuntimeVirtualTexture()
{
	if (!_terrain || !bMaterialRvtEnabled || _shader_override_enabled || !_terrain->is_inside_tree() ||
		!_terrain->GetQuadTree() || !TERRAIN_RS->get_rendering_device())
	{
		if (GetMaterialRvtRid().is_valid())
		{
			ReleaseMaterialRvt();
		}
		return;
	}
	const Ref<World3D> refWorld = _terrain->get_world_3d();
	const Rect2i rectOuterExtent = _terrain->GetQuadTree()->GetMaterialExtent();
	const Rect2i rectAuthored = _terrain->GetQuadTree()->GetExtent();
	const Rect2i rectExtent = rectAuthored.has_area() ? rectAuthored : rectOuterExtent;
	const bool bFarWriter = _dual_scaling_enabled || rectExtent != rectOuterExtent;
	const real_t fSpacing = _terrain->get_vertex_spacing();
	if (refWorld.is_null() || !rectExtent.has_area())
	{
		if (GetMaterialRvtRid().is_valid())
		{
			ReleaseMaterialRvt();
		}
		return;
	}
	const RID ridScenario = refWorld->get_scenario();
	Vector2 vHeights = _terrain->get_data()->get_height_range();
	if (_world_background != NONE && _terrain->GetGpuDriven())
	{
		const Vector2 vBackground = _terrain->GetGpuDriven()->GetBackgroundHeightRange();
		vHeights.x = MIN(vHeights.x, real_t(0)) + vBackground.x;
		vHeights.y = MAX(vHeights.y, real_t(0)) + vBackground.y;
	}
	const bool bDetail = _world_background != NONE || rectExtent.size.x > (MATERIAL_TILE << MATERIAL_MAX_LEVEL) / MATERIAL_TEXELS_PER_CELL;
	Rect2i rectDetailExtent;
	if (bDetail)
	{
		const Camera3D *pCamera = _terrain->get_camera();
		const Vector3 vEye = pCamera ? pCamera->get_global_position() : _terrain->get_clipmap_target_position();
		const int nStep = DETAIL_SIDE / 4;
		const Vector2 vCenter = (Vector2(vEye.x, vEye.z) / (fSpacing * nStep)).round() * nStep;
		rectDetailExtent = Rect2i(Vector2i(vCenter) - V2I(DETAIL_SIDE / 2), V2I(DETAIL_SIDE));
	}
	const bool bSameGrid = GetMaterialRvtRid().is_valid() && rectExtent == rectRvtExtent && rectOuterExtent == rectRvtOuterExtent &&
						   fSpacing == fRvtSpacing && ridScenario == ridRvtScenario && arrRvtWriters[WORLD_VOLUME].ridSurface.is_valid() == bFarWriter &&
						   arrRvtWriters[DETAIL_NEAR_VOLUME].ridSurface.is_valid() == bDetail && arrRvtWriters[DETAIL_FAR_VOLUME].ridSurface.is_valid() == (bDetail && _dual_scaling_enabled);
	const bool bHeightChanged = vHeights.x < vRvtVolumeHeights.x || vHeights.y > vRvtVolumeHeights.y;
	if (bSameGrid)
	{
		if (bHeightChanged)
		{
			vRvtVolumeHeights.x = MIN(vHeights.x - real_t(8), vRvtVolumeHeights.x);
			vRvtVolumeHeights.y = MAX(vHeights.y + real_t(8), vRvtVolumeHeights.y);
			PlaceMaterialVolume(AUTHORED_VOLUME, rectExtent);
			if (bFarWriter)
			{
				PlaceMaterialVolume(WORLD_VOLUME, rectOuterExtent);
			}
		}
		if (bDetail && (rectDetailExtent != rectRvtDetailExtent || bHeightChanged))
		{
			rectRvtDetailExtent = rectDetailExtent;
			PlaceMaterialVolume(DETAIL_NEAR_VOLUME, rectDetailExtent);
			if (_dual_scaling_enabled)
			{
				PlaceMaterialVolume(DETAIL_FAR_VOLUME, rectDetailExtent);
			}
		}
		AttachMaterialStreams();
		return;
	}

	ReleaseMaterialRvt();
	rectRvtExtent = rectExtent;
	rectRvtOuterExtent = rectOuterExtent;
	rectRvtDetailExtent = rectDetailExtent;
	vRvtVolumeHeights = Vector2(vHeights.x - 8, vHeights.y + 8);
	fRvtSpacing = fSpacing;
	_terrain->get_data()->PrimeMaterialEditTracking();
	ridRvtScenario = ridScenario;

	if (UsesNativeHeightForMaterialRvt())
	{
		_terrain->get_data()->SetNativeHeightRequired(true);
	}
	refRvtPlane.instantiate();
	// Geometry is in world metres. The page camera clips this flat plane to each tile,
	// and the writer reconstructs the terrain height at every fragment for projection.
	refRvtPlane->set_size(Vector2(1, 1));
	refRvtWriterShader.instantiate();
	refRvtWriterShader->set_code(_generate_shader_code(true).replace("shader_type spatial;", "shader_type spatial;\n#define T3D_MATERIAL_RVT_WRITER"));
	for (int nI = 0; nI < MATERIAL_VOLUME_COUNT; ++nI)
	{
		const bool bLocal = nI >= DETAIL_NEAR_VOLUME;
		if ((nI == WORLD_VOLUME && !bFarWriter) || (bLocal && !bDetail) || (nI == DETAIL_FAR_VOLUME && !_dual_scaling_enabled))
		{
			continue;
		}
		const Rect2i &rectRect = bLocal ? rectDetailExtent : (nI == WORLD_VOLUME ? rectOuterExtent : rectExtent);
		const int nTile = bLocal ? DETAIL_TILE : MATERIAL_TILE;
		const int nLevels = MaterialLevels(rectRect.size.x, nTile);
		MaterialPageWriter &stWriter = arrRvtWriters[nI];
		if (!bLocal)
		{
			arrRvtStreamPending[nI] = !arrRvtStreamPaths[nI].is_empty();
		}
		stWriter.ridMaterial = TERRAIN_RS->material_create();
		TERRAIN_RS->material_set_shader(stWriter.ridMaterial, refRvtWriterShader->get_rid());
		stWriter.ridInstance = TERRAIN_RS->instance_create2(refRvtPlane->get_rid(), ridScenario);
		TERRAIN_RS->instance_set_layer_mask(stWriter.ridInstance, 0);
		TERRAIN_RS->instance_geometry_set_cast_shadows_setting(stWriter.ridInstance, RSE::SHADOW_CASTING_SETTING_OFF);
		TERRAIN_RS->instance_geometry_set_material_override(stWriter.ridInstance, stWriter.ridMaterial);
		stWriter.ridSurface = TERRAIN_RS->RuntimeVirtualTextureCreate();
		// Smaller detail tiles waste fewer texels along sloping silhouettes and mip boundaries.
		// The detail pool holds the current footprint, its trilinear parents and the
		// leading strip during the eight-frame arrival fade.
		TERRAIN_RS->RuntimeVirtualTextureConfigure(stWriter.ridSurface, RSE::RVT_MATERIAL_TERRAIN_PBR, nLevels, nTile, MATERIAL_BORDER, bLocal ? 24 : 10);
		TERRAIN_RS->RuntimeVirtualTextureSetCullMask(stWriter.ridSurface, 0);
		const bool bAnisotropic = _texture_filtering == LINEAR_ANISOTROPIC || _texture_filtering == NEAREST_ANISOTROPIC;
		TERRAIN_RS->RuntimeVirtualTextureSetMaterialWriter(stWriter.ridSurface, stWriter.ridInstance, bAnisotropic ? 4 : 1);
		TERRAIN_RS->RuntimeVirtualTextureSetMaterialHeightSource(stWriter.ridSurface, ridRvtHeightSource);
		TERRAIN_RS->RuntimeVirtualTextureSetMaxPagesPerFrame(stWriter.ridSurface, bLocal ? 64 : 8);
		TERRAIN_RS->RuntimeVirtualTextureSetScenario(stWriter.ridSurface, ridScenario);
		PlaceMaterialVolume(MaterialVolume(nI), rectRect);
		const String strPrefix = arrMATERIALPREFIX[nI];
		if (nI != DETAIL_FAR_VOLUME)
		{
			TERRAIN_RS->material_set_param(_material, strPrefix + String("layout"), Vector4(1 << nLevels, nLevels, nTile, MATERIAL_BORDER));
		}
		TERRAIN_RS->material_set_param(_material, strPrefix + String("table"), TERRAIN_RS->RuntimeVirtualTextureGetPageTableTexture(stWriter.ridSurface));
		TERRAIN_RS->material_set_param(_material, strPrefix + String("color"), TERRAIN_RS->RuntimeVirtualTextureGetPhysicalTexture(stWriter.ridSurface, 0));
		TERRAIN_RS->material_set_param(_material, strPrefix + String("surface"), TERRAIN_RS->RuntimeVirtualTextureGetPhysicalTexture(stWriter.ridSurface, 1));
	}
	SyncRvtWriters(UPDATE_ARRAYS);
	if (bFarWriter)
	{
		SetMaterialRvtFarMipBias(fMaterialRvtFarMipBias);
	}
	else
	{
		TERRAIN_RS->material_set_param(_material, "_t3d_material_rvt_far_grid", Vector4(0, 0, 1, 0));
	}
	AttachMaterialStreams();
}
