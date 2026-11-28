// Copyright © 2023-2026 Cory Petkovsek, Roope Palmroos, and Contributors.

#include "terrain_3d_material.h"
#include "core/io/marshalls.h"

#include "core/crypto/hashing_context.h"
#include "servers/rendering/rendering_server.h"
#include "core/variant/variant_utility.h"

#include "terrain_3d.h"
#include "terrain_3d_assets.h"
#include "terrain_3d_data.h"

void Terrain3DMaterial::SetMaterialStreamPath(int in_nIndex, const String &in_strPath)
{
	if (arrRvtStreamPaths[in_nIndex] == in_strPath && (in_strPath.is_empty() || !arrRvtWriters[in_nIndex].ridSurface.is_valid()))
	{
		return;
	}
	arrRvtStreamPaths[in_nIndex] = in_strPath;
	arrRvtStreamPending[in_nIndex] = true;
	nRvtStreamRetryTicks = 0;
	AttachMaterialStreams();
}

Error Terrain3DMaterial::MaterialSvtSignature(bool bFar, int64_t &out_nSignature)
{
	if (!bRvtStreamHashValid)
	{
		Terrain3DData *pData = _terrain->get_data();
		const Ref<Terrain3DAssets> refAssets = _terrain->get_assets();
		ERR_FAIL_NULL_V(pData, ERR_UNCONFIGURED);
		ERR_FAIL_COND_V(refAssets.is_null(), ERR_UNCONFIGURED);

		Ref<HashingContext> refHash;
		refHash.instantiate();
		const Error eErr = refHash->start(HashingContext::HASH_SHA256);
		if (eErr != OK)
		{
			return eErr;
		}
		auto fnHashValue = [&refHash](const Variant &varValue)
		{
			refHash->update(VariantUtilityFunctions::var_to_bytes(varValue));
		};
		auto fnHashImage = [&fnHashValue, &refHash](const Ref<Image> &refImage)
		{
			if (refImage.is_null())
			{
				fnHashValue(Variant());
				return;
			}
			fnHashValue(Array({ refImage->get_size(), int(refImage->get_format()), refImage->get_mipmap_count() }));
			refHash->update(refImage->get_data());
		};
		auto fnHashTexture = [&fnHashValue, &fnHashImage](const Ref<Texture2D> &refTexture)
		{
			if (refTexture.is_null())
			{
				fnHashValue(Variant());
				return true;
			}
			const Ref<Image> refImage = refTexture->get_image();
			if (refImage.is_null() || refImage->is_empty())
			{
				return false; // NoiseTexture2D may still be generating its first image.
			}
			fnHashImage(refImage);
			return true;
		};

		// Change the format revision when changing the engine-side physical layer packing.
		fnHashValue(Array({ "Terrain3D-PBR-2", rectRvtExtent, fRvtSpacing, int(_world_background), int(_terrain->get_region_size()), _generate_shader_code(true) }));
		// StringName::operator< orders interned pointers, which vary between processes.
		PackedStringArray arrParams;
		for (const StringName &snName : _active_params)
		{
			arrParams.push_back(String(snName));
		}
		arrParams.sort();
		for (const String &strParam : arrParams)
		{
			fnHashValue(strParam);
			const Variant varValue = get_shader_param(strParam);
			if (varValue.get_type() == Variant::OBJECT)
			{
				if (!fnHashTexture(Ref<Texture2D>(varValue)))
				{
					return ERR_BUSY;
				}
			}
			else
			{
				fnHashValue(varValue);
			}
		}

		fnHashValue(Array({ refAssets->get_texture_colors(), refAssets->get_texture_normal_depths(), refAssets->get_texture_ao_strengths(),
					refAssets->get_texture_ao_light_affects(), refAssets->get_texture_roughness_mods(), refAssets->get_texture_uv_scales(), refAssets->get_texture_detiles() }));
		// Hash precisely the inputs rendered on this platform, including synthesized
		// checker/normal layers. Their v2 records survive release of the source assets.
		for (int nLayer : refAssets->GetMaterialTextureLayers())
		{
			if (nLayer < 0)
			{
				fnHashValue(Variant());
				continue;
			}
			for (RID ridArray : { refAssets->get_albedo_array_rid(), refAssets->get_normal_array_rid() })
			{
				ERR_FAIL_COND_V(!ridArray.is_valid(), ERR_UNCONFIGURED);
				const Ref<Image> refImage = TERRAIN_RS->texture_2d_layer_get(ridArray, nLayer);
				ERR_FAIL_COND_V(refImage.is_null() || refImage->is_empty(), ERR_CANT_ACQUIRE_RESOURCE);
				fnHashImage(refImage);
			}
		}

		Array arrLocations = pData->get_region_locations().duplicate();
		arrLocations.sort();
		for (const Vector2i &vLocation : arrLocations)
		{
			Terrain3DRegion *pRegion = pData->get_region_ptr(vLocation);
			ERR_FAIL_NULL_V(pRegion, ERR_UNCONFIGURED);
			fnHashValue(vLocation);
			fnHashImage(pRegion->get_height_map());
			fnHashImage(pRegion->get_control_map());
			fnHashImage(pRegion->get_active_color_map());
		}
		nRvtStreamHash = int64_t(decode_uint64(refHash->finish().ptr()));
		bRvtStreamHashValid = true;
	}
	// Different endpoint inputs yield separate files even when paths or layouts coincide.
	out_nSignature = nRvtStreamHash ^ (bFar ? INT64_C(0x53a97cfe27610b8d) : 0);
	return OK;
}

void Terrain3DMaterial::AttachMaterialStreams()
{
	if (!arrRvtStreamPending[0] && !arrRvtStreamPending[1])
	{
		return;
	}
	if (nRvtStreamRetryTicks > 0)
	{
		--nRvtStreamRetryTicks;
		return;
	}
	for (int nI = 0; nI < 2; ++nI)
	{
		const RID ridSurface = arrRvtWriters[nI].ridSurface;
		if (!arrRvtStreamPending[nI] || !ridSurface.is_valid())
		{
			continue;
		}
		const String &strPath = arrRvtStreamPaths[nI];
		int64_t nSignature = 0;
		const Error eErr = strPath.is_empty() ? OK : MaterialSvtSignature(nI == 1, nSignature);
		if (eErr == ERR_BUSY)
		{
			nRvtStreamRetryTicks = 30;
			return;
		}
		arrRvtStreamPending[nI] = false;
		if (eErr == OK)
		{
			TERRAIN_RS->RuntimeVirtualTextureSetMaterialStream(ridSurface, strPath, nSignature);
		}
	}
}

Error Terrain3DMaterial::BakeMaterialSvt(const String &in_strPath, int nCoarseLevels, bool bFarVariant)
{
	const MaterialPageWriter &stWriter = arrRvtWriters[bFarVariant ? 1 : 0];
	if (!stWriter.ridSurface.is_valid() || !_terrain || !_terrain->get_data() || in_strPath.is_empty())
	{
		return ERR_UNCONFIGURED;
	}
	bRvtStreamHashValid = false;
	int64_t nSignature = 0;
	const Error eErr = MaterialSvtSignature(bFarVariant, nSignature);
	if (eErr != OK)
	{
		return eErr;
	}

	// Bakes include off-camera pages. Their source heights must be independent of
	// the current camera's VT residency. Restore both writer and native residency afterwards.
	Terrain3DData *pData = _terrain->get_data();
	const bool bHadNative = pData->GetResidentHeightMapsRid().is_valid();
	pData->SetNativeHeightRequired(true);
	TERRAIN_RS->material_set_param(stWriter.ridMaterial, "_height_maps", pData->GetResidentHeightMapsRid());
	TERRAIN_RS->material_set_param(stWriter.ridMaterial, "_t3d_mode", 0.0);
	const Error eResult = TERRAIN_RS->RuntimeVirtualTextureBakeMaterialStream(stWriter.ridSurface, in_strPath, nCoarseLevels, nSignature);
	BindWriterHeight(stWriter);
	if (!bHadNative && ridRvtHeightSource.is_valid())
	{
		pData->SetNativeHeightRequired(false);
	}
	const int nIndex = bFarVariant ? 1 : 0;
	if (eResult == OK && in_strPath == arrRvtStreamPaths[nIndex])
	{
		arrRvtStreamPending[nIndex] = true;
		AttachMaterialStreams();
	}
	return eResult;
}
