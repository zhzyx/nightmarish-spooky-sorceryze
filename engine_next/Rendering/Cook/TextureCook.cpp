/**************************************************************************/
/*  TextureCook.cpp                                                       */
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

#include "engine_next/Rendering/Cook/TextureCook.h"

#include "engine_next/Rendering/Cook/ImageDecoder.h"
#include "engine_next/include/EngineNext/Assets/BlobValidator.h"

#include <algorithm>
#include <array>
#include <cstddef>
#include <cstdint>
#include <map>
#include <string>
#include <tuple>
#include <utility>

namespace EngineNext::Rendering
{
namespace
{

constexpr std::size_t MAX_MATERIALS = 65536;
constexpr std::size_t MAX_VARIANTS = 65536;
constexpr std::size_t MAX_MIP_BYTES = 512ULL * 1024ULL * 1024ULL;
using VariantKey = std::tuple<std::uint32_t, ImageSemantic, TextureAlphaPolicy>;

bool Fail(Assets::Diagnostics &out_arrDiagnostics, const std::string &strPath, const char *pMessage)
{
	Assets::AddDiagnostic(out_arrDiagnostics, "texture_cook", strPath, pMessage);
	return false;
}

std::array<std::int32_t, 5> TextureSlots(const MaterialData &stMaterial)
{
	return { stMaterial.nBaseColorTexture, stMaterial.nMetallicRoughnessTexture, stMaterial.nNormalTexture,
			 stMaterial.nOcclusionTexture, stMaterial.nEmissiveTexture };
}

ImageSemantic SlotSemantic(std::size_t nSlot)
{
	if (nSlot == 0 || nSlot == 4)
	{
		return ImageSemantic::Srgb;
	}
	return nSlot == 2 ? ImageSemantic::Normal : ImageSemantic::Linear;
}

TextureAlphaPolicy SlotAlphaPolicy(std::size_t nSlot, AlphaMode eAlpha)
{
	return nSlot == 4 || (nSlot == 0 && eAlpha == AlphaMode::Opaque) ? TextureAlphaPolicy::Ignore : TextureAlphaPolicy::Preserve;
}

bool CountMipBytes(const EncodedImage &stImage, std::size_t nRemainingBytes, std::size_t &out_nBytes, Assets::Diagnostics &out_arrDiagnostics)
{
	Assets::BlobInfo stInfo;
	if (!Assets::ValidateBlob(stImage.strMimeType, stImage.arrBytes, stInfo, out_arrDiagnostics))
	{
		return false;
	}
	if (stInfo.nWidth == 0 || stInfo.nHeight == 0 || stInfo.nWidth > 8192 || stInfo.nHeight > 8192)
	{
		return Fail(out_arrDiagnostics, "$", "Texture dimensions exceed the image decoder bounds.");
	}
	std::size_t nWidth = stInfo.nWidth;
	std::size_t nHeight = stInfo.nHeight;
	out_nBytes = 0;
	for (;;)
	{
		const std::size_t nLevelBytes = nWidth * nHeight * 4;
		if (nLevelBytes > nRemainingBytes - out_nBytes)
		{
			return Fail(out_arrDiagnostics, "$", "Texture mip bytes exceed the remaining cook budget.");
		}
		out_nBytes += nLevelBytes;
		if (nWidth == 1 && nHeight == 1)
		{
			return true;
		}
		nWidth = (std::max)(nWidth / 2, std::size_t{ 1 });
		nHeight = (std::max)(nHeight / 2, std::size_t{ 1 });
	}
}

bool SameVariant(const CookedTextureVariant &stExpected, const CookedTextureVariant &stActual)
{
	if (stExpected.nImage != stActual.nImage || stExpected.eSemantic != stActual.eSemantic || stExpected.eAlphaPolicy != stActual.eAlphaPolicy || stExpected.arrMips.size() != stActual.arrMips.size())
	{
		return false;
	}
	for (std::size_t nMip = 0; nMip < stExpected.arrMips.size(); ++nMip)
	{
		const MipLevel &stLeft = stExpected.arrMips[nMip];
		const MipLevel &stRight = stActual.arrMips[nMip];
		if (stLeft.nWidth != stRight.nWidth || stLeft.nHeight != stRight.nHeight || stLeft.arrRgba8 != stRight.arrRgba8)
		{
			return false;
		}
	}
	return true;
}

} // namespace

bool CookMeshTextures(const DecodedMesh &stMesh, MeshTextureCook &out_stCook, Assets::Diagnostics &out_arrDiagnostics, std::size_t nByteBudget)
{
	if (stMesh.arrMaterials.size() > MAX_MATERIALS || nByteBudget > MAX_MIP_BYTES)
	{
		return Fail(out_arrDiagnostics, "$", "Material count or mip-byte budget exceeds the cook limits.");
	}
	MeshTextureCook stCook;
	std::map<VariantKey, std::int32_t> mapVariants;
	std::size_t nCookedBytes = 0;
	for (std::size_t nMaterial = 0; nMaterial < stMesh.arrMaterials.size(); ++nMaterial)
	{
		const MaterialData &stMaterial = stMesh.arrMaterials[nMaterial];
		const std::string strPath = "$.materials[" + std::to_string(nMaterial) + "]";
		if (stMaterial.eAlphaMode != AlphaMode::Opaque && stMaterial.eAlphaMode != AlphaMode::Mask && stMaterial.eAlphaMode != AlphaMode::Blend)
		{
			return Fail(out_arrDiagnostics, strPath, "Material alpha mode is invalid.");
		}
		CookedMaterialTextures stBindings;
		const std::array<std::int32_t, 5> arrTextures = TextureSlots(stMaterial);
		for (std::size_t nSlot = 0; nSlot < arrTextures.size(); ++nSlot)
		{
			const std::int32_t nTexture = arrTextures[nSlot];
			if (nTexture == -1)
			{
				continue;
			}
			if (nTexture < 0 || static_cast<std::size_t>(nTexture) >= stMesh.arrTextures.size())
			{
				return Fail(out_arrDiagnostics, strPath, "Material texture reference is outside the source table.");
			}
			const TextureData &stTexture = stMesh.arrTextures[static_cast<std::size_t>(nTexture)];
			if (stTexture.nImage >= stMesh.arrImages.size())
			{
				return Fail(out_arrDiagnostics, strPath, "Texture image reference is outside the source table.");
			}
			const ImageSemantic eSemantic = SlotSemantic(nSlot);
			const TextureAlphaPolicy eAlphaPolicy = SlotAlphaPolicy(nSlot, stMaterial.eAlphaMode);
			const VariantKey stKey{ stTexture.nImage, eSemantic, eAlphaPolicy };
			const std::map<VariantKey, std::int32_t>::const_iterator itFound = mapVariants.find(stKey);
			if (itFound != mapVariants.end())
			{
				stBindings.arrVariants[nSlot] = itFound->second;
				continue;
			}
			if (stCook.arrVariants.size() >= MAX_VARIANTS)
			{
				return Fail(out_arrDiagnostics, strPath, "Texture variant count exceeds the cook limit.");
			}
			const EncodedImage &stImage = stMesh.arrImages[stTexture.nImage];
			std::size_t nMipBytes = 0;
			if (!CountMipBytes(stImage, nByteBudget - nCookedBytes, nMipBytes, out_arrDiagnostics))
			{
				return false;
			}
			DecodedImage stDecoded;
			if (!DecodeImage(stImage.arrBytes, stImage.strMimeType, stDecoded, out_arrDiagnostics))
			{
				return false;
			}
			if (eAlphaPolicy == TextureAlphaPolicy::Ignore)
			{
				for (std::size_t nAlpha = 3; nAlpha < stDecoded.arrRgba8.size(); nAlpha += 4)
				{
					stDecoded.arrRgba8[nAlpha] = 255;
				}
			}
			CookedTextureVariant stVariant;
			stVariant.nImage = stTexture.nImage;
			stVariant.eSemantic = eSemantic;
			stVariant.eAlphaPolicy = eAlphaPolicy;
			if (!BuildMipChain(stDecoded, eSemantic, stVariant.arrMips, out_arrDiagnostics))
			{
				return false;
			}
			const std::int32_t nVariant = static_cast<std::int32_t>(stCook.arrVariants.size());
			stBindings.arrVariants[nSlot] = nVariant;
			mapVariants.emplace(stKey, nVariant);
			stCook.arrVariants.push_back(std::move(stVariant));
			nCookedBytes += nMipBytes;
		}
		stCook.arrMaterials.push_back(stBindings);
	}
	out_stCook = std::move(stCook);
	return true;
}

bool ValidateMeshTextureCook(const DecodedMesh &stMesh, const MeshTextureCook &stCook, Assets::Diagnostics &out_arrDiagnostics)
{
	MeshTextureCook stExpected;
	if (!CookMeshTextures(stMesh, stExpected, out_arrDiagnostics))
	{
		return false;
	}
	if (stExpected.arrMaterials.size() != stCook.arrMaterials.size() || stExpected.arrVariants.size() != stCook.arrVariants.size())
	{
		return Fail(out_arrDiagnostics, "$", "Cooked texture tables differ from the source material bindings.");
	}
	for (std::size_t nMaterial = 0; nMaterial < stExpected.arrMaterials.size(); ++nMaterial)
	{
		if (stExpected.arrMaterials[nMaterial].arrVariants != stCook.arrMaterials[nMaterial].arrVariants)
		{
			return Fail(out_arrDiagnostics, "$", "Cooked material references differ from the deterministic source cook.");
		}
	}
	for (std::size_t nVariant = 0; nVariant < stExpected.arrVariants.size(); ++nVariant)
	{
		if (!SameVariant(stExpected.arrVariants[nVariant], stCook.arrVariants[nVariant]))
		{
			return Fail(out_arrDiagnostics, "$", "Cooked texture pixels or keys differ from the deterministic source cook.");
		}
	}
	return true;
}

} // namespace EngineNext::Rendering
