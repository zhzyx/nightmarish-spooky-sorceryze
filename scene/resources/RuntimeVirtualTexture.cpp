/**************************************************************************/
/*  RuntimeVirtualTexture.cpp                                            */
/**************************************************************************/
/*                         This file is part of:                          */
/*                             GODOT ENGINE                               */
/*                        https://godotengine.org                         */
/**************************************************************************/
/* Copyright (c) 2014-present Godot Engine contributors (see AUTHORS.md). */
/* Copyright (c) 2007-2014 Juan Linietsky, Ariel Manzur.                  */
/*                                                                        */
/* Permission is hereby granted, free of charge, to any person obtaining  */
/* a copy of this software and associated documentation files (the        */
/* "Software"), to deal in the Software without restriction, including    */
/* without limitation the rights to use, copy, modify, merge, publish,    */
/* distribute, sublicense, and/or sell copies of the Software, and to     */
/* permit persons to whom the Software is furnished to do so, subject to  */
/* the following conditions:                                              */
/*                                                                        */
/* The above copyright notice and this permission notice shall be         */
/* included in all copies or substantial portions of the Software.        */
/*                                                                        */
/* THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,        */
/* EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF     */
/* MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. */
/* IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY   */
/* CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT,   */
/* TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE      */
/* SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.                 */
/**************************************************************************/

#include "RuntimeVirtualTexture.h"

#pragma region Engine ZXB
// [ZXB] Runtime Virtual Texture resource implementation.
#pragma endregion

#include "core/object/class_db.h"
#include "core/object/object.h"
#include "scene/resources/material.h"
#include "servers/rendering/StreamingVirtualTextureFile.h"
#include "servers/rendering/rendering_server.h"

void RuntimeVirtualTextureProxy::SetProxy(RID in_ridTexture, const Size2i &in_vSize)
{
	ridTexture = in_ridTexture;
	vSize = in_vSize;
	emit_changed();
}

RuntimeVirtualTexture::RuntimeVirtualTexture()
{
	ridRvt = RS::get_singleton()->RuntimeVirtualTextureCreate();
	Configure();
}

RuntimeVirtualTexture::~RuntimeVirtualTexture()
{
	ERR_FAIL_NULL(RS::get_singleton());
	RS::get_singleton()->free_rid(ridRvt);
}

int RuntimeVirtualTexture::GetPhysicalSize() const
{
	return nPoolSize * (nTileSize + 2 * nTileBorder);
}

void RuntimeVirtualTexture::Configure()
{
	RS *pRs = RS::get_singleton();
	pRs->RuntimeVirtualTextureConfigure(ridRvt, (RSE::RuntimeVirtualTextureMaterialType)stMaterialType, nLog2TileCount, nTileSize, nTileBorder, nPoolSize);
	pRs->RuntimeVirtualTextureSetSource(ridRvt, eSource == SOURCE_STREAM ? RSE::RVT_SOURCE_STREAM : RSE::RVT_SOURCE_RENDER);
	pRs->RuntimeVirtualTextureSetPageFile(ridRvt, strPageFile);
	pRs->RuntimeVirtualTextureSetDebug(ridRvt, (RSE::RuntimeVirtualTextureDebugMode)eDebugMode, nDebugForceLod);
	pRs->RuntimeVirtualTextureSetCullMask(ridRvt, nCullMask);
	pRs->RuntimeVirtualTextureSetLodBias(ridRvt, fLodBias);
	pRs->RuntimeVirtualTextureSetMaxPagesPerFrame(ridRvt, nMaxPagesPerFrame);
	pRs->RuntimeVirtualTextureSetEnabled(ridRvt, bEnabled);

	if (refPageTableProxy.is_valid())
	{
		refPageTableProxy->SetProxy(pRs->RuntimeVirtualTextureGetPageTableTexture(ridRvt), Size2i(1 << nLog2TileCount, 1 << nLog2TileCount));
	}
	for (int nI = 0; nI < 2; nI++)
	{
		if (arrPhysicalProxy[nI].is_valid())
		{
			arrPhysicalProxy[nI]->SetProxy(pRs->RuntimeVirtualTextureGetPhysicalTexture(ridRvt, nI), Size2i(GetPhysicalSize(), GetPhysicalSize()));
		}
	}
	UpdateBoundMaterials();
}

void RuntimeVirtualTexture::SetMaterialType(MaterialType stType)
{
	stMaterialType = stType;
	Configure();
	emit_changed();
}

void RuntimeVirtualTexture::SetSource(Source in_eSource)
{
	if (eSource == in_eSource)
	{
		return;
	}
	eSource = in_eSource;
	Configure();
	emit_changed();
}

void RuntimeVirtualTexture::SetPageFile(const String &strPath)
{
	if (strPageFile == strPath)
	{
		return;
	}
	strPageFile = strPath;
	if (!strPageFile.is_empty())
	{
		StreamingVirtualTextureFile stFile;
		if (stFile.Open(strPageFile) == OK)
		{
			// The baked file owns the page layout.
			const StreamingVirtualTextureFile::Header &stH = stFile.GetHeader();
			nLog2TileCount = stH.nLog2TileCount;
			nTileSize = stH.nTileSize;
			nTileBorder = stH.nTileBorder;
			stMaterialType = stH.nFormat == StreamingVirtualTextureFile::FORMAT_R32F ? MATERIAL_WORLD_HEIGHT : MATERIAL_BASE_COLOR;
			eSource = SOURCE_STREAM;
		}
	}
	Configure();
	emit_changed();
}

static Error BakeHeightGridFile(const String &strPath, const Ref<Image> &refImage, int in_nLog2TileCount, int in_nTileSize, int in_nTileBorder)
{
	return StreamingVirtualTextureFile::BakeImage(strPath, refImage, in_nLog2TileCount, in_nTileSize, in_nTileBorder, StreamingVirtualTextureFile::FORMAT_R32F, false, true);
}

Error RuntimeVirtualTexture::BakePageFile(const String &strPath, const Ref<Image> &refImage, int in_nLog2TileCount, int in_nTileSize, int in_nTileBorder, FileFormat eFormat, bool bSrgb)
{
	return StreamingVirtualTextureFile::BakeImage(strPath, refImage, in_nLog2TileCount, in_nTileSize, in_nTileBorder, (StreamingVirtualTextureFile::Format)eFormat, bSrgb);
}

void RuntimeVirtualTexture::SetDebugMode(DebugMode eMode)
{
	if (eDebugMode == eMode)
	{
		return;
	}
	eDebugMode = eMode;
	RS::get_singleton()->RuntimeVirtualTextureSetDebug(ridRvt, (RSE::RuntimeVirtualTextureDebugMode)eDebugMode, nDebugForceLod);
	UpdateBoundMaterials();
	emit_changed();
}

void RuntimeVirtualTexture::SetDebugForceLod(int nLod)
{
	nLod = CLAMP(nLod, -1, nLog2TileCount);
	if (nDebugForceLod == nLod)
	{
		return;
	}
	nDebugForceLod = nLod;
	RS::get_singleton()->RuntimeVirtualTextureSetDebug(ridRvt, (RSE::RuntimeVirtualTextureDebugMode)eDebugMode, nDebugForceLod);
	UpdateBoundMaterials();
	emit_changed();
}

Vector3i RuntimeVirtualTexture::PickPage(const Vector3 &vWorldPosition, int in_nLevel) const
{
	const int nLevel = CLAMP(in_nLevel, 0, nLog2TileCount);
	const int nTiles = 1 << (nLog2TileCount - nLevel);
	const Transform3D xformToUnit = Transform3D(Basis(), Vector3(0.5, 0.5, 0.5)) * xformWorldTransform.affine_inverse();
	const Vector3 vUvh = xformToUnit.xform(vWorldPosition);
	const Vector2 vUv = Vector2(vUvh.x, vUvh.z);
	const int nX = CLAMP(int(Math::floor(vUv.x * nTiles)), 0, nTiles - 1);
	const int nY = CLAMP(int(Math::floor(vUv.y * nTiles)), 0, nTiles - 1);
	return Vector3i(nLevel, nX, nY);
}

Dictionary RuntimeVirtualTexture::GetPageInfo(int in_nLevel, int in_nX, int in_nY) const
{
	return RS::get_singleton()->RuntimeVirtualTextureGetPageInfo(ridRvt, in_nLevel, in_nX, in_nY);
}

void RuntimeVirtualTexture::LockPage(int in_nLevel, int in_nX, int in_nY, float fSeconds)
{
	RS::get_singleton()->RuntimeVirtualTextureLockPage(ridRvt, in_nLevel, in_nX, in_nY, fSeconds);
}

void RuntimeVirtualTexture::UnlockPage(int in_nLevel, int in_nX, int in_nY)
{
	RS::get_singleton()->RuntimeVirtualTextureUnlockPage(ridRvt, in_nLevel, in_nX, in_nY);
}

void RuntimeVirtualTexture::UnlockAllPages()
{
	RS::get_singleton()->RuntimeVirtualTextureUnlockAllPages(ridRvt);
}

void RuntimeVirtualTexture::SetLog2TileCount(int nLog2)
{
	nLog2TileCount = CLAMP(nLog2, 1, 10);
	Configure();
	emit_changed();
}

void RuntimeVirtualTexture::SetTileSize(int nSize)
{
	nTileSize = CLAMP(nSize, 16, 1024);
	Configure();
	emit_changed();
}

void RuntimeVirtualTexture::SetTileBorder(int nBorder)
{
	nTileBorder = CLAMP(nBorder, 0, 16);
	Configure();
	emit_changed();
}

void RuntimeVirtualTexture::SetPoolSize(int nSize)
{
	nPoolSize = CLAMP(nSize, 2, 255);
	Configure();
	emit_changed();
}

void RuntimeVirtualTexture::SetCullMask(uint32_t nMask)
{
	nCullMask = nMask;
	RS::get_singleton()->RuntimeVirtualTextureSetCullMask(ridRvt, nCullMask);
}

void RuntimeVirtualTexture::SetLodBias(float fBias)
{
	fLodBias = fBias;
	RS::get_singleton()->RuntimeVirtualTextureSetLodBias(ridRvt, fLodBias);
}

void RuntimeVirtualTexture::SetMaxPagesPerFrame(int nPages)
{
	nMaxPagesPerFrame = MAX(nPages, 1);
	RS::get_singleton()->RuntimeVirtualTextureSetMaxPagesPerFrame(ridRvt, nMaxPagesPerFrame);
}

void RuntimeVirtualTexture::SetEnabled(bool in_bEnabled)
{
	bEnabled = in_bEnabled;
	RS::get_singleton()->RuntimeVirtualTextureSetEnabled(ridRvt, bEnabled);
}

Ref<Texture2D> RuntimeVirtualTexture::GetPageTableTexture() const
{
	if (refPageTableProxy.is_null())
	{
		refPageTableProxy.instantiate();
		refPageTableProxy->SetProxy(RS::get_singleton()->RuntimeVirtualTextureGetPageTableTexture(ridRvt), Size2i(1 << nLog2TileCount, 1 << nLog2TileCount));
	}
	return refPageTableProxy;
}

Ref<Texture2D> RuntimeVirtualTexture::GetPhysicalTexture(int nLayer) const
{
	ERR_FAIL_INDEX_V(nLayer, 2, Ref<Texture2D>());
	if (arrPhysicalProxy[nLayer].is_null())
	{
		arrPhysicalProxy[nLayer].instantiate();
		arrPhysicalProxy[nLayer]->SetProxy(RS::get_singleton()->RuntimeVirtualTextureGetPhysicalTexture(ridRvt, nLayer), Size2i(GetPhysicalSize(), GetPhysicalSize()));
	}
	return arrPhysicalProxy[nLayer];
}

void RuntimeVirtualTexture::SetWorld(RID ridScenario, const Transform3D &xformTransform)
{
	xformWorldTransform = xformTransform;
	RS::get_singleton()->RuntimeVirtualTextureSetScenario(ridRvt, ridScenario);
	RS::get_singleton()->RuntimeVirtualTextureSetTransform(ridRvt, xformTransform);

	UpdateBoundMaterials();
}

void RuntimeVirtualTexture::UpdateBoundMaterials()
{
	// Keep already bound materials in sync with the volume and configuration.
	LocalVector<ObjectID> arrDead;
	for (const KeyValue<ObjectID, String> &stKv : mapBoundMaterials)
	{
		ShaderMaterial *pMaterial = ObjectDB::get_instance<ShaderMaterial>(stKv.key);
		if (pMaterial)
		{
			WriteMaterialUniforms(pMaterial, stKv.value);
		}
		else
		{
			arrDead.push_back(stKv.key);
		}
	}
	for (const ObjectID &idId : arrDead)
	{
		mapBoundMaterials.erase(idId);
	}
}

void RuntimeVirtualTexture::WriteMaterialUniforms(ShaderMaterial *in_pMaterial, const String &strPrefix) const
{
	const int nStride = nTileSize + 2 * nTileBorder;
	const int nPhysical = nPoolSize * nStride;
	const Transform3D xformToUnit = Transform3D(Basis(), Vector3(0.5, 0.5, 0.5)) * xformWorldTransform.affine_inverse();

	in_pMaterial->set_shader_parameter(strPrefix + "_page_table", GetPageTableTexture());
	in_pMaterial->set_shader_parameter(strPrefix + "_physical0", GetPhysicalTexture(0));
	in_pMaterial->set_shader_parameter(strPrefix + "_physical1", GetPhysicalTexture(GetLayerCount() > 1 ? 1 : 0));
	in_pMaterial->set_shader_parameter(strPrefix + "_params0", Vector4(1 << nLog2TileCount, nLog2TileCount, nTileSize, nTileBorder));
	in_pMaterial->set_shader_parameter(strPrefix + "_params1", Vector4(nPhysical, nPhysical, xformWorldTransform.basis.get_scale().abs().y, stMaterialType));
	in_pMaterial->set_shader_parameter(strPrefix + "_world_to_uv", Projection(xformToUnit));
	in_pMaterial->set_shader_parameter(strPrefix + "_normal_basis", Projection(Transform3D(xformWorldTransform.basis.orthonormalized(), Vector3())));
	in_pMaterial->set_shader_parameter(strPrefix + "_debug_mode", (int)eDebugMode);
	in_pMaterial->set_shader_parameter(strPrefix + "_debug_force_lod", nDebugForceLod);
}

void RuntimeVirtualTexture::ApplyToMaterial(const Ref<ShaderMaterial> &refMaterial, const String &strPrefix)
{
	ERR_FAIL_COND(refMaterial.is_null());
	WriteMaterialUniforms(refMaterial.ptr(), strPrefix);
	mapBoundMaterials[refMaterial->get_instance_id()] = strPrefix;
}

void RuntimeVirtualTexture::Invalidate(const AABB &aabbWorldAabb)
{
	RS::get_singleton()->RuntimeVirtualTextureInvalidate(ridRvt, aabbWorldAabb);
}

void RuntimeVirtualTexture::InvalidateAll()
{
	RS::get_singleton()->RuntimeVirtualTextureInvalidateAll(ridRvt);
}

Dictionary RuntimeVirtualTexture::GetStats() const
{
	return RS::get_singleton()->RuntimeVirtualTextureGetStats(ridRvt);
}

void RuntimeVirtualTexture::_bind_methods()
{
	ClassDB::bind_method(D_METHOD("set_material_type", "type"), &RuntimeVirtualTexture::SetMaterialType);
	ClassDB::bind_method(D_METHOD("get_material_type"), &RuntimeVirtualTexture::GetMaterialType);
	ClassDB::bind_method(D_METHOD("set_source", "source"), &RuntimeVirtualTexture::SetSource);
	ClassDB::bind_method(D_METHOD("get_source"), &RuntimeVirtualTexture::GetSource);
	ClassDB::bind_method(D_METHOD("set_page_file", "path"), &RuntimeVirtualTexture::SetPageFile);
	ClassDB::bind_method(D_METHOD("get_page_file"), &RuntimeVirtualTexture::GetPageFile);
	ClassDB::bind_method(D_METHOD("set_debug_mode", "mode"), &RuntimeVirtualTexture::SetDebugMode);
	ClassDB::bind_method(D_METHOD("get_debug_mode"), &RuntimeVirtualTexture::GetDebugMode);
	ClassDB::bind_method(D_METHOD("set_debug_force_lod", "lod"), &RuntimeVirtualTexture::SetDebugForceLod);
	ClassDB::bind_method(D_METHOD("get_debug_force_lod"), &RuntimeVirtualTexture::GetDebugForceLod);
	ClassDB::bind_method(D_METHOD("pick_page", "world_position", "level"), &RuntimeVirtualTexture::PickPage);
	ClassDB::bind_method(D_METHOD("get_page_info", "level", "x", "y"), &RuntimeVirtualTexture::GetPageInfo);
	ClassDB::bind_method(D_METHOD("lock_page", "level", "x", "y", "seconds"), &RuntimeVirtualTexture::LockPage, DEFVAL(5.0f));
	ClassDB::bind_method(D_METHOD("unlock_page", "level", "x", "y"), &RuntimeVirtualTexture::UnlockPage);
	ClassDB::bind_method(D_METHOD("unlock_all_pages"), &RuntimeVirtualTexture::UnlockAllPages);
	ClassDB::bind_static_method("RuntimeVirtualTexture", D_METHOD("bake_height_grid_file", "path", "image", "log2_tile_count", "tile_size", "tile_border"), &BakeHeightGridFile);
	ClassDB::bind_static_method("RuntimeVirtualTexture", D_METHOD("bake_page_file", "path", "image", "log2_tile_count", "tile_size", "tile_border", "format", "srgb"), &RuntimeVirtualTexture::BakePageFile);
	ClassDB::bind_method(D_METHOD("set_log2_tile_count", "log2_tile_count"), &RuntimeVirtualTexture::SetLog2TileCount);
	ClassDB::bind_method(D_METHOD("get_log2_tile_count"), &RuntimeVirtualTexture::GetLog2TileCount);
	ClassDB::bind_method(D_METHOD("set_tile_size", "tile_size"), &RuntimeVirtualTexture::SetTileSize);
	ClassDB::bind_method(D_METHOD("get_tile_size"), &RuntimeVirtualTexture::GetTileSize);
	ClassDB::bind_method(D_METHOD("set_tile_border", "tile_border"), &RuntimeVirtualTexture::SetTileBorder);
	ClassDB::bind_method(D_METHOD("get_tile_border"), &RuntimeVirtualTexture::GetTileBorder);
	ClassDB::bind_method(D_METHOD("set_pool_size", "pool_size"), &RuntimeVirtualTexture::SetPoolSize);
	ClassDB::bind_method(D_METHOD("get_pool_size"), &RuntimeVirtualTexture::GetPoolSize);
	ClassDB::bind_method(D_METHOD("set_cull_mask", "cull_mask"), &RuntimeVirtualTexture::SetCullMask);
	ClassDB::bind_method(D_METHOD("get_cull_mask"), &RuntimeVirtualTexture::GetCullMask);
	ClassDB::bind_method(D_METHOD("set_lod_bias", "lod_bias"), &RuntimeVirtualTexture::SetLodBias);
	ClassDB::bind_method(D_METHOD("get_lod_bias"), &RuntimeVirtualTexture::GetLodBias);
	ClassDB::bind_method(D_METHOD("set_max_pages_per_frame", "max_pages_per_frame"), &RuntimeVirtualTexture::SetMaxPagesPerFrame);
	ClassDB::bind_method(D_METHOD("get_max_pages_per_frame"), &RuntimeVirtualTexture::GetMaxPagesPerFrame);
	ClassDB::bind_method(D_METHOD("set_enabled", "enabled"), &RuntimeVirtualTexture::SetEnabled);
	ClassDB::bind_method(D_METHOD("is_enabled"), &RuntimeVirtualTexture::IsEnabled);

	ClassDB::bind_method(D_METHOD("get_layer_count"), &RuntimeVirtualTexture::GetLayerCount);
	ClassDB::bind_method(D_METHOD("get_page_table_texture"), &RuntimeVirtualTexture::GetPageTableTexture);
	ClassDB::bind_method(D_METHOD("get_physical_texture", "layer"), &RuntimeVirtualTexture::GetPhysicalTexture);
	ClassDB::bind_method(D_METHOD("apply_to_material", "material", "prefix"), &RuntimeVirtualTexture::ApplyToMaterial, DEFVAL("rvt"));
	ClassDB::bind_method(D_METHOD("invalidate", "world_aabb"), &RuntimeVirtualTexture::Invalidate);
	ClassDB::bind_method(D_METHOD("invalidate_all"), &RuntimeVirtualTexture::InvalidateAll);
	ClassDB::bind_method(D_METHOD("get_stats"), &RuntimeVirtualTexture::GetStats);

	ADD_PROPERTY(PropertyInfo(Variant::INT, "source", PROPERTY_HINT_ENUM, "Rendered,Streamed"), "set_source", "get_source");
	ADD_PROPERTY(PropertyInfo(Variant::STRING, "page_file", PROPERTY_HINT_FILE, "*.svt"), "set_page_file", "get_page_file");
	ADD_GROUP("Debug", "debug_");
	ADD_PROPERTY(PropertyInfo(Variant::INT, "debug_mode", PROPERTY_HINT_ENUM, "Off,Page Table,Page Table (Mip),Physical Pool,LOD,Borders"), "set_debug_mode", "get_debug_mode");
	ADD_PROPERTY(PropertyInfo(Variant::INT, "debug_force_lod", PROPERTY_HINT_RANGE, "-1,10,1"), "set_debug_force_lod", "get_debug_force_lod");
	ADD_PROPERTY(PropertyInfo(Variant::INT, "material_type", PROPERTY_HINT_ENUM, "Base Color,Base Color + Normal + Roughness,World Height"), "set_material_type", "get_material_type");
	ADD_PROPERTY(PropertyInfo(Variant::INT, "log2_tile_count", PROPERTY_HINT_RANGE, "1,10,1"), "set_log2_tile_count", "get_log2_tile_count");
	ADD_PROPERTY(PropertyInfo(Variant::INT, "tile_size", PROPERTY_HINT_RANGE, "16,1024,1,suffix:px"), "set_tile_size", "get_tile_size");
	ADD_PROPERTY(PropertyInfo(Variant::INT, "tile_border", PROPERTY_HINT_RANGE, "0,16,1,suffix:px"), "set_tile_border", "get_tile_border");
	ADD_PROPERTY(PropertyInfo(Variant::INT, "pool_size", PROPERTY_HINT_RANGE, "2,255,1"), "set_pool_size", "get_pool_size");
	ADD_PROPERTY(PropertyInfo(Variant::INT, "cull_mask", PROPERTY_HINT_LAYERS_3D_RENDER), "set_cull_mask", "get_cull_mask");
	ADD_PROPERTY(PropertyInfo(Variant::FLOAT, "lod_bias", PROPERTY_HINT_RANGE, "-4,4,0.1"), "set_lod_bias", "get_lod_bias");
	ADD_PROPERTY(PropertyInfo(Variant::INT, "max_pages_per_frame", PROPERTY_HINT_RANGE, "1,64,1"), "set_max_pages_per_frame", "get_max_pages_per_frame");
	ADD_PROPERTY(PropertyInfo(Variant::BOOL, "enabled"), "set_enabled", "is_enabled");

	BIND_ENUM_CONSTANT(MATERIAL_BASE_COLOR);
	BIND_ENUM_CONSTANT(MATERIAL_BASE_COLOR_NORMAL_ROUGHNESS);
	BIND_ENUM_CONSTANT(MATERIAL_WORLD_HEIGHT);
	BIND_ENUM_CONSTANT(SOURCE_RENDER);
	BIND_ENUM_CONSTANT(SOURCE_STREAM);
	BIND_ENUM_CONSTANT(FORMAT_RGBA8);
	BIND_ENUM_CONSTANT(FORMAT_BC1);
	BIND_ENUM_CONSTANT(FORMAT_BC7);
	BIND_ENUM_CONSTANT(FORMAT_R32F);
	BIND_ENUM_CONSTANT(DEBUG_OFF);
	BIND_ENUM_CONSTANT(DEBUG_PAGE_TABLE);
	BIND_ENUM_CONSTANT(DEBUG_PAGE_TABLE_MIP);
	BIND_ENUM_CONSTANT(DEBUG_PHYSICAL_POOL);
	BIND_ENUM_CONSTANT(DEBUG_LOD);
	BIND_ENUM_CONSTANT(DEBUG_BORDERS);
}
