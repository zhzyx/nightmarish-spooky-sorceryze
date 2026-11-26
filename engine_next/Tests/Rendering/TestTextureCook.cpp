/**************************************************************************/
/*  TestTextureCook.cpp                                                   */
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

#include "engine_next/Tests/TestFramework.h"

#include "engine_next/Rendering/Cook/TextureCook.h"

#include <array>
#include <cmath>
#include <cstddef>
#include <cstdint>
#include <string>
#include <vector>

namespace
{

std::uint32_t Crc32(const std::uint8_t *pData, std::size_t nBytes)
{
	std::uint32_t nCrc = 0xFFFFFFFFU;
	for (std::size_t nIndex = 0; nIndex < nBytes; ++nIndex)
	{
		nCrc ^= pData[nIndex];
		for (std::uint32_t nBit = 0; nBit < 8; ++nBit)
		{
			nCrc = (nCrc >> 1U) ^ (0xEDB88320U & (0U - (nCrc & 1U)));
		}
	}
	return nCrc ^ 0xFFFFFFFFU;
}

void Append32(std::vector<std::uint8_t> &out_arrBytes, std::uint32_t nValue)
{
	for (std::uint32_t nShift : { 24U, 16U, 8U, 0U })
	{
		out_arrBytes.push_back(static_cast<std::uint8_t>(nValue >> nShift));
	}
}

void AppendChunk(std::vector<std::uint8_t> &out_arrBytes, const std::array<std::uint8_t, 4> &arrType, const std::vector<std::uint8_t> &arrPayload)
{
	Append32(out_arrBytes, static_cast<std::uint32_t>(arrPayload.size()));
	const std::size_t nStart = out_arrBytes.size();
	out_arrBytes.insert(out_arrBytes.end(), arrType.begin(), arrType.end());
	out_arrBytes.insert(out_arrBytes.end(), arrPayload.begin(), arrPayload.end());
	Append32(out_arrBytes, Crc32(out_arrBytes.data() + nStart, arrPayload.size() + 4));
}

std::vector<std::uint8_t> MakePng(bool bTruncated = false)
{
	// Transparent red and opaque blue make alpha-weighted and independent
	// channel filtering visibly different while preserving exact source bytes.
	const std::vector<std::uint8_t> arrRaw{ 0, 255, 0, 0, 0, 0, 0, 255, 255 };
	std::vector<std::uint8_t> arrZlib{ 0x78, 0x01, 0x01, 9, 0, 0xF6, 0xFF };
	arrZlib.insert(arrZlib.end(), arrRaw.begin(), arrRaw.end());
	std::uint32_t nSum = 1;
	std::uint32_t nSum2 = 0;
	for (std::uint8_t nValue : arrRaw)
	{
		nSum = (nSum + nValue) % 65521;
		nSum2 = (nSum2 + nSum) % 65521;
	}
	Append32(arrZlib, (nSum2 << 16U) | nSum);
	std::vector<std::uint8_t> arrPng{ 0x89, 'P', 'N', 'G', 13, 10, 26, 10 };
	AppendChunk(arrPng, { 'I', 'H', 'D', 'R' }, { 0, 0, 0, 2, 0, 0, 0, 1, 8, 6, 0, 0, 0 });
	if (bTruncated)
	{
		arrZlib.resize(arrZlib.size() - 5);
	}
	AppendChunk(arrPng, { 'I', 'D', 'A', 'T' }, arrZlib);
	AppendChunk(arrPng, { 'I', 'E', 'N', 'D' }, {});
	return arrPng;
}

EngineNext::Rendering::DecodedMesh MakeMesh()
{
	EngineNext::Rendering::DecodedMesh stMesh;
	stMesh.arrImages.push_back({ "image/png", MakePng() });
	stMesh.arrTextures.push_back({ 0, 9729, 9987, 10497, 10497 });
	stMesh.arrTextures.push_back({ 0, 9728, 9728, 33071, 33071 });
	EngineNext::Rendering::MaterialData stOpaque;
	stOpaque.nBaseColorTexture = 0;
	stOpaque.nMetallicRoughnessTexture = 0;
	stOpaque.nNormalTexture = 0;
	stOpaque.nOcclusionTexture = 1;
	stOpaque.nEmissiveTexture = 1;
	stMesh.arrMaterials.push_back(stOpaque);
	EngineNext::Rendering::MaterialData stMasked;
	stMasked.eAlphaMode = EngineNext::Rendering::AlphaMode::Mask;
	stMasked.nBaseColorTexture = 1;
	stMesh.arrMaterials.push_back(stMasked);
	return stMesh;
}

} // namespace

ENGINE_NEXT_TEST("Texture cook preserves untextured materials without platform dependencies")
{
	EngineNext::Rendering::DecodedMesh stMesh;
	stMesh.arrMaterials.resize(2);
	EngineNext::Rendering::MeshTextureCook stCook;
	EngineNext::Assets::Diagnostics arrDiagnostics;
	ENGINE_NEXT_CHECK(EngineNext::Rendering::CookMeshTextures(stMesh, stCook, arrDiagnostics, 0));
	ENGINE_NEXT_CHECK(stCook.arrVariants.empty());
	ENGINE_NEXT_CHECK_EQ(stCook.arrMaterials.size(), 2U);
	ENGINE_NEXT_CHECK_EQ(stCook.arrMaterials[0].arrVariants, (std::array<std::int32_t, 5>{ -1, -1, -1, -1, -1 }));
	ENGINE_NEXT_CHECK(EngineNext::Rendering::ValidateMeshTextureCook(stMesh, stCook, arrDiagnostics));
}

ENGINE_NEXT_TEST("Texture cook validates source references and preserves prior output on errors")
{
	EngineNext::Rendering::DecodedMesh stMesh = MakeMesh();
	EngineNext::Rendering::MeshTextureCook stCook;
	stCook.arrMaterials.resize(3);
	EngineNext::Assets::Diagnostics arrDiagnostics;
	stMesh.arrMaterials[0].nBaseColorTexture = -2;
	ENGINE_NEXT_CHECK(!EngineNext::Rendering::CookMeshTextures(stMesh, stCook, arrDiagnostics));
	ENGINE_NEXT_CHECK_EQ(stCook.arrMaterials.size(), 3U);
	stMesh.arrMaterials[0].nBaseColorTexture = 2;
	ENGINE_NEXT_CHECK(!EngineNext::Rendering::CookMeshTextures(stMesh, stCook, arrDiagnostics));
	stMesh = MakeMesh();
	stMesh.arrTextures[0].nImage = 2;
	ENGINE_NEXT_CHECK(!EngineNext::Rendering::CookMeshTextures(stMesh, stCook, arrDiagnostics));
	stMesh = MakeMesh();
	stMesh.arrImages[0].arrBytes.pop_back();
	ENGINE_NEXT_CHECK(!EngineNext::Rendering::CookMeshTextures(stMesh, stCook, arrDiagnostics));
	ENGINE_NEXT_CHECK_EQ(stCook.arrMaterials.size(), 3U);
	stMesh = MakeMesh();
	ENGINE_NEXT_CHECK(!EngineNext::Rendering::CookMeshTextures(stMesh, stCook, arrDiagnostics, 11));
	ENGINE_NEXT_CHECK_EQ(stCook.arrMaterials.size(), 3U);
	ENGINE_NEXT_CHECK(!EngineNext::Rendering::CookMeshTextures(stMesh, stCook, arrDiagnostics, 513ULL * 1024ULL * 1024ULL));
}

ENGINE_NEXT_TEST("Texture cook deduplicates semantic variants and applies alpha policies")
{
	const EngineNext::Rendering::DecodedMesh stMesh = MakeMesh();
	EngineNext::Rendering::MeshTextureCook stCook;
	EngineNext::Assets::Diagnostics arrDiagnostics;
	ENGINE_NEXT_CHECK(EngineNext::Rendering::CookMeshTextures(stMesh, stCook, arrDiagnostics, 48));
	ENGINE_NEXT_CHECK_EQ(stCook.arrVariants.size(), 4U);
	ENGINE_NEXT_CHECK_EQ(stCook.arrMaterials.size(), 2U);
	ENGINE_NEXT_CHECK_EQ(stCook.arrMaterials[0].arrVariants, (std::array<std::int32_t, 5>{ 0, 1, 2, 1, 0 }));
	ENGINE_NEXT_CHECK_EQ(stCook.arrMaterials[1].arrVariants, (std::array<std::int32_t, 5>{ 3, -1, -1, -1, -1 }));
	const EngineNext::Rendering::CookedTextureVariant &stOpaque = stCook.arrVariants[0];
	const EngineNext::Rendering::CookedTextureVariant &stLinear = stCook.arrVariants[1];
	const EngineNext::Rendering::CookedTextureVariant &stNormal = stCook.arrVariants[2];
	const EngineNext::Rendering::CookedTextureVariant &stMasked = stCook.arrVariants[3];
	ENGINE_NEXT_CHECK_EQ(stOpaque.arrMips.size(), 2U);
	ENGINE_NEXT_CHECK_EQ(stOpaque.arrMips[0].arrRgba8[3], 255);
	ENGINE_NEXT_CHECK_EQ(stOpaque.arrMips[1].arrRgba8, (std::vector<std::uint8_t>{ 188, 0, 188, 255 }));
	ENGINE_NEXT_CHECK_EQ(stLinear.arrMips[1].arrRgba8, (std::vector<std::uint8_t>{ 128, 0, 128, 128 }));
	ENGINE_NEXT_CHECK_EQ(stMasked.arrMips[0].arrRgba8[3], 0);
	ENGINE_NEXT_CHECK_EQ(stMasked.arrMips[1].arrRgba8, (std::vector<std::uint8_t>{ 0, 0, 255, 128 }));
	double dNormalLength = 0;
	for (std::size_t nChannel = 0; nChannel < 3; ++nChannel)
	{
		const double dValue = stNormal.arrMips[1].arrRgba8[nChannel] / 127.5 - 1.0;
		dNormalLength += dValue * dValue;
	}
	ENGINE_NEXT_CHECK(std::abs(std::sqrt(dNormalLength) - 1.0) < 0.01);
	ENGINE_NEXT_CHECK_EQ(stMesh.arrImages[0].arrBytes, MakePng());
	ENGINE_NEXT_CHECK(EngineNext::Rendering::ValidateMeshTextureCook(stMesh, stCook, arrDiagnostics));
	ENGINE_NEXT_CHECK(!EngineNext::Rendering::CookMeshTextures(stMesh, stCook, arrDiagnostics, 47));
	ENGINE_NEXT_CHECK_EQ(stCook.arrVariants.size(), 4U);
}

ENGINE_NEXT_TEST("Texture cook validation rejects modified mip bytes keys and bindings")
{
	const EngineNext::Rendering::DecodedMesh stMesh = MakeMesh();
	EngineNext::Rendering::MeshTextureCook stCook;
	EngineNext::Assets::Diagnostics arrDiagnostics;
	ENGINE_NEXT_CHECK(EngineNext::Rendering::CookMeshTextures(stMesh, stCook, arrDiagnostics));
	stCook.arrVariants[0].arrMips[1].arrRgba8[0] ^= 1;
	ENGINE_NEXT_CHECK(!EngineNext::Rendering::ValidateMeshTextureCook(stMesh, stCook, arrDiagnostics));
	ENGINE_NEXT_CHECK(EngineNext::Rendering::CookMeshTextures(stMesh, stCook, arrDiagnostics));
	stCook.arrVariants[0].eAlphaPolicy = EngineNext::Rendering::TextureAlphaPolicy::Preserve;
	ENGINE_NEXT_CHECK(!EngineNext::Rendering::ValidateMeshTextureCook(stMesh, stCook, arrDiagnostics));
	ENGINE_NEXT_CHECK(EngineNext::Rendering::CookMeshTextures(stMesh, stCook, arrDiagnostics));
	stCook.arrMaterials[0].arrVariants[0] = 1;
	ENGINE_NEXT_CHECK(!EngineNext::Rendering::ValidateMeshTextureCook(stMesh, stCook, arrDiagnostics));
}

ENGINE_NEXT_TEST("Texture cook rejects incomplete compressed image data before publication")
{
	EngineNext::Rendering::DecodedMesh stMesh = MakeMesh();
	stMesh.arrImages[0].arrBytes = MakePng(true);
	EngineNext::Rendering::MeshTextureCook stCook;
	stCook.arrMaterials.resize(3);
	EngineNext::Assets::Diagnostics arrDiagnostics;
	ENGINE_NEXT_CHECK(!EngineNext::Rendering::CookMeshTextures(stMesh, stCook, arrDiagnostics));
	ENGINE_NEXT_CHECK_EQ(stCook.arrMaterials.size(), 3U);
	ENGINE_NEXT_CHECK(!arrDiagnostics.empty());
}
