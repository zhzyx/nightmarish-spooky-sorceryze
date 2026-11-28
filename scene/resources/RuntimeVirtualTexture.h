/**************************************************************************/
/*  RuntimeVirtualTexture.h                                              */
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

#pragma once

#pragma region Engine ZXB
// [ZXB] Runtime Virtual Texture resource. Owns the server-side RVT and exposes its page table / physical textures.
#pragma endregion

#include "core/math/aabb.h"
#include "core/math/transform_3d.h"
#include "core/templates/hash_map.h"
#include "core/templates/rid.h"
#include "core/variant/dictionary.h"
#include "scene/resources/texture.h"

class ShaderMaterial;

// Texture2D that forwards an RID owned by the rendering server (page table or physical page pool).
class RuntimeVirtualTextureProxy : public Texture2D
{
	GDCLASS(RuntimeVirtualTextureProxy, Texture2D);

	RID ridTexture;
	Size2i vSize = Size2i(1, 1);

public:
	void SetProxy(RID in_ridTexture, const Size2i &in_vSize);
	virtual int get_width() const override
	{
		return vSize.width;
	}
	virtual int get_height() const override
	{
		return vSize.height;
	}
	virtual RID get_rid() const override
	{
		return ridTexture;
	}
	virtual bool has_alpha() const override
	{
		return true;
	}
	virtual Ref<Image> get_image() const override
	{
		return Ref<Image>();
	}
};

class RuntimeVirtualTexture : public Resource
{
	GDCLASS(RuntimeVirtualTexture, Resource);

public:
	enum MaterialType
	{
		MATERIAL_BASE_COLOR,
		MATERIAL_BASE_COLOR_NORMAL_ROUGHNESS,
		MATERIAL_WORLD_HEIGHT,
	};

	enum Source
	{
		SOURCE_RENDER, // Pages are rendered from the scene every frame (RVT).
		SOURCE_STREAM, // Pages are streamed from a baked page file (SVT).
	};

	enum FileFormat
	{
		FORMAT_RGBA8,
		FORMAT_BC1,
		FORMAT_BC7,
		FORMAT_R32F,
	};

	// Mirrors RenderingServer.RuntimeVirtualTextureDebugMode.
	enum DebugMode
	{
		DEBUG_OFF,
		DEBUG_PAGE_TABLE,
		DEBUG_PAGE_TABLE_MIP,
		DEBUG_PHYSICAL_POOL,
		DEBUG_LOD,
		DEBUG_BORDERS,
	};

private:
	RID ridRvt;
	MaterialType stMaterialType = MATERIAL_BASE_COLOR_NORMAL_ROUGHNESS;
	Source eSource = SOURCE_RENDER;
	String strPageFile;
	DebugMode eDebugMode = DEBUG_OFF;
	int nDebugForceLod = -1;
	int nLog2TileCount = 6;
	int nTileSize = 128;
	int nTileBorder = 4;
	int nPoolSize = 16;
	uint32_t nCullMask = 0xFFFFF;
	float fLodBias = 0.0f;
	int nMaxPagesPerFrame = 4;
	bool bEnabled = true;

	Transform3D xformWorldTransform; // Unit cube centered at the origin to world.
	HashMap<ObjectID, String> mapBoundMaterials;

	mutable Ref<RuntimeVirtualTextureProxy> refPageTableProxy;
	mutable Ref<RuntimeVirtualTextureProxy> arrPhysicalProxy[2];

	void Configure();
	int GetPhysicalSize() const;
	void WriteMaterialUniforms(ShaderMaterial *in_pMaterial, const String &strPrefix) const;
	void UpdateBoundMaterials();

protected:
	static void _bind_methods();

public:
	void SetMaterialType(MaterialType stType);
	MaterialType GetMaterialType() const
	{
		return stMaterialType;
	}
	void SetSource(Source in_eSource);
	Source GetSource() const
	{
		return eSource;
	}
	void SetPageFile(const String &strPath);
	String GetPageFile() const
	{
		return strPageFile;
	}
	void SetDebugMode(DebugMode eMode);
	DebugMode GetDebugMode() const
	{
		return eDebugMode;
	}
	void SetDebugForceLod(int nLod);
	int GetDebugForceLod() const
	{
		return nDebugForceLod;
	}
	void SetLog2TileCount(int nLog2);
	int GetLog2TileCount() const
	{
		return nLog2TileCount;
	}
	void SetTileSize(int nSize);
	int GetTileSize() const
	{
		return nTileSize;
	}
	void SetTileBorder(int nBorder);
	int GetTileBorder() const
	{
		return nTileBorder;
	}
	void SetPoolSize(int nSize);
	int GetPoolSize() const
	{
		return nPoolSize;
	}
	void SetCullMask(uint32_t nMask);
	uint32_t GetCullMask() const
	{
		return nCullMask;
	}
	void SetLodBias(float fBias);
	float GetLodBias() const
	{
		return fLodBias;
	}
	void SetMaxPagesPerFrame(int nPages);
	int GetMaxPagesPerFrame() const
	{
		return nMaxPagesPerFrame;
	}
	void SetEnabled(bool in_bEnabled);
	bool IsEnabled() const
	{
		return bEnabled;
	}

	int GetLayerCount() const
	{
		return eSource == SOURCE_RENDER && stMaterialType == MATERIAL_BASE_COLOR_NORMAL_ROUGHNESS ? 2 : 1;
	}
	Ref<Texture2D> GetPageTableTexture() const;
	Ref<Texture2D> GetPhysicalTexture(int nLayer) const;

	// Called by RuntimeVirtualTextureVolume.
	void SetWorld(RID ridScenario, const Transform3D &xformTransform);
	Transform3D GetWorldTransform() const
	{
		return xformWorldTransform;
	}

	// Writes the uniforms read by the RVT shader include (<prefix>_page_table, _physical0/1, _params0/1, _world_to_uv).
	void ApplyToMaterial(const Ref<ShaderMaterial> &refMaterial, const String &strPrefix = "rvt");

	// Bakes `p_image` into a page file consumable by source = SOURCE_STREAM.
	static Error BakePageFile(const String &strPath, const Ref<Image> &refImage, int in_nLog2TileCount, int in_nTileSize, int in_nTileBorder, FileFormat eFormat, bool bSrgb = true);

	// Debug helpers. pick_page maps a world position to the page covering it at `level`.
	Vector3i PickPage(const Vector3 &vWorldPosition, int in_nLevel) const;
	Dictionary GetPageInfo(int in_nLevel, int in_nX, int in_nY) const;
	// Keeps a page produced and resident for `seconds` (max 6 locked pages, like r.VT.RVT.MaxLockedPages).
	void LockPage(int in_nLevel, int in_nX, int in_nY, float fSeconds = 5.0f);
	void UnlockPage(int in_nLevel, int in_nX, int in_nY);
	void UnlockAllPages();

	void Invalidate(const AABB &aabbWorldAabb);
	void InvalidateAll();
	Dictionary GetStats() const;

	virtual RID get_rid() const override
	{
		return ridRvt;
	}

	RuntimeVirtualTexture();
	~RuntimeVirtualTexture();
};

VARIANT_ENUM_CAST(RuntimeVirtualTexture::MaterialType);
VARIANT_ENUM_CAST(RuntimeVirtualTexture::Source);
VARIANT_ENUM_CAST(RuntimeVirtualTexture::FileFormat);
VARIANT_ENUM_CAST(RuntimeVirtualTexture::DebugMode);
