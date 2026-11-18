/**************************************************************************/
/*  GpuPackage.cpp                                                        */
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

#include "engine_next/Rendering/Cook/GpuPackage.h"
#include "engine_next/Rendering/Cook/GpuPackageCodec.h"

#include "engine_next/Assets/AssetValidation.h"
#include "engine_next/Rendering/Cook/MeshCluster.h"
#include "engine_next/Rendering/Cook/TextureCook.h"
#include "engine_next/include/EngineNext/Assets/BlobValidator.h"
#include "engine_next/include/EngineNext/Serialization/Json.h"
#include "engine_next/include/EngineNext/Serialization/Sha256.h"

#include <algorithm>
#include <array>
#include <atomic>
#include <chrono>
#include <cmath>
#include <cstddef>
#include <cstdint>
#include <cstring>
#include <cwchar>
#include <filesystem>
#include <fstream>
#include <limits>
#include <set>
#include <string>
#include <utility>
#include <vector>

#ifdef _WIN32
#ifndef NOMINMAX
#define NOMINMAX
#endif
#ifndef WIN32_LEAN_AND_MEAN
#define WIN32_LEAN_AND_MEAN
#endif
#include <windows.h>
#undef GetObject
#elif defined(__APPLE__)
#include <cstdio>
#elif defined(__linux__)
#include <fcntl.h>
#include <sys/syscall.h>
#include <unistd.h>
#endif

namespace EngineNext::Rendering
{
namespace
{

namespace fs = std::filesystem;
using Serialization::JsonValue;
constexpr std::size_t MAX_PAGE_BYTES = 512ULL * 1024ULL * 1024ULL;
constexpr std::size_t MAX_MANIFEST_BYTES = 65536;
constexpr std::uint32_t MAX_ITEMS = 65536;
constexpr std::array<std::uint8_t, 8> MAGIC{ 'E', 'N', 'G', 'P', 'U', '0', '1', 0 };
constexpr std::uint32_t LEGACY_FORMAT_VERSION = 1;
constexpr std::uint32_t PREPARED_FORMAT_VERSION = 2;

bool Fail(Assets::Diagnostics &out_arrDiagnostics, const char *pCode, const std::string &strPath, const char *pMessage)
{
	Assets::AddDiagnostic(out_arrDiagnostics, pCode, strPath, pMessage);
	return false;
}

class Writer final
{
public:
	void Uint32(std::uint32_t nValue)
	{
		Uint64(nValue, 4);
	}
	void Uint64(std::uint64_t nValue, std::size_t nBytes = 8)
	{
		std::array<std::uint8_t, 8> arrValue{};
		for (std::size_t nIndex = 0; nIndex < nBytes; ++nIndex)
		{
			arrValue[nIndex] = static_cast<std::uint8_t>(nValue >> (nIndex * 8U));
		}
		Bytes(arrValue.data(), nBytes);
	}
	void Float(float fValue)
	{
		std::uint32_t nBits = 0;
		std::memcpy(&nBits, &fValue, sizeof(nBits));
		Uint32(nBits);
	}
	void Double(double dValue)
	{
		std::uint64_t nBits = 0;
		std::memcpy(&nBits, &dValue, sizeof(nBits));
		Uint64(nBits);
	}
	void String(const std::string &strValue)
	{
		Uint32(static_cast<std::uint32_t>(strValue.size()));
		Bytes(reinterpret_cast<const std::uint8_t *>(strValue.data()), strValue.size());
	}
	void Bytes(const std::uint8_t *pBytes, std::size_t nBytes)
	{
		if (nBytes == 0)
		{
			return;
		}
		if (!bValid || nBytes > MAX_PAGE_BYTES - arrBytes.size())
		{
			bValid = false;
			return;
		}
		arrBytes.insert(arrBytes.end(), pBytes, pBytes + nBytes);
	}
	std::vector<std::uint8_t> arrBytes;
	bool bValid = true;
};

class Reader final
{
public:
	explicit Reader(const std::vector<std::uint8_t> &in_arrBytes) : arrBytes(in_arrBytes) {}
	bool Uint64(std::uint64_t &out_nValue, std::size_t nBytes = 8)
	{
		if (nBytes > arrBytes.size() - nPosition)
		{
			return false;
		}
		out_nValue = 0;
		for (std::size_t nIndex = 0; nIndex < nBytes; ++nIndex)
		{
			out_nValue |= static_cast<std::uint64_t>(arrBytes[nPosition++]) << (nIndex * 8U);
		}
		return true;
	}
	bool Uint32(std::uint32_t &out_nValue)
	{
		std::uint64_t nValue = 0;
		if (!Uint64(nValue, 4))
		{
			return false;
		}
		out_nValue = static_cast<std::uint32_t>(nValue);
		return true;
	}
	bool Count(std::uint32_t &out_nCount, std::size_t nItemBytes, std::uint32_t nLimit = MAX_ITEMS, std::size_t nAllocationBytes = 0)
	{
		const std::size_t nMemoryBytes = nAllocationBytes == 0 ? nItemBytes : nAllocationBytes;
		if (nItemBytes == 0 || !Uint32(out_nCount) || out_nCount > nLimit || out_nCount > (arrBytes.size() - nPosition) / nItemBytes || out_nCount > (MAX_PAGE_BYTES - nDecodedBytes) / nMemoryBytes)
		{
			return false;
		}
		nDecodedBytes += out_nCount * nMemoryBytes;
		return true;
	}
	bool Float(float &out_fValue)
	{
		std::uint32_t nBits = 0;
		if (!Uint32(nBits))
		{
			return false;
		}
		std::memcpy(&out_fValue, &nBits, sizeof(nBits));
		return std::isfinite(out_fValue);
	}
	bool Double(double &out_dValue)
	{
		std::uint64_t nBits = 0;
		if (!Uint64(nBits))
		{
			return false;
		}
		std::memcpy(&out_dValue, &nBits, sizeof(nBits));
		return std::isfinite(out_dValue) && std::abs(out_dValue) <= std::numeric_limits<float>::max();
	}
	bool String(std::string &out_strValue)
	{
		std::uint32_t nBytes = 0;
		if (!Count(nBytes, 1, 256))
		{
			return false;
		}
		out_strValue.assign(reinterpret_cast<const char *>(arrBytes.data() + nPosition), nBytes);
		nPosition += nBytes;
		return out_strValue.find('\0') == std::string::npos;
	}
	bool Bytes(std::vector<std::uint8_t> &out_arrBytes, std::uint32_t nLimit = 16 * 1024 * 1024)
	{
		std::uint32_t nBytes = 0;
		if (!Count(nBytes, 1, nLimit))
		{
			return false;
		}
		out_arrBytes.assign(arrBytes.begin() + static_cast<std::ptrdiff_t>(nPosition), arrBytes.begin() + static_cast<std::ptrdiff_t>(nPosition + nBytes));
		nPosition += nBytes;
		return true;
	}
	bool IsComplete() const
	{
		return nPosition == arrBytes.size();
	}

private:
	const std::vector<std::uint8_t> &arrBytes;
	std::size_t nPosition = 0;
	std::size_t nDecodedBytes = 0;
};

void WriteMaterial(Writer &stWriter, const MaterialData &stMaterial)
{
	for (float fValue : stMaterial.arrBaseColor)
	{
		stWriter.Float(fValue);
	}
	stWriter.Float(stMaterial.fMetallic);
	stWriter.Float(stMaterial.fRoughness);
	for (float fValue : stMaterial.arrEmissive)
	{
		stWriter.Float(fValue);
	}
	stWriter.Float(stMaterial.fNormalScale);
	stWriter.Float(stMaterial.fOcclusionStrength);
	stWriter.Float(stMaterial.fAlphaCutoff);
	stWriter.Uint32(stMaterial.bDoubleSided ? 1 : 0);
	stWriter.Uint32(static_cast<std::uint32_t>(stMaterial.eAlphaMode));
	for (std::int32_t nTexture : { stMaterial.nBaseColorTexture, stMaterial.nMetallicRoughnessTexture, stMaterial.nNormalTexture, stMaterial.nOcclusionTexture, stMaterial.nEmissiveTexture })
	{
		stWriter.Uint32(nTexture < 0 ? UINT32_MAX : static_cast<std::uint32_t>(nTexture));
	}
}

bool ReadTextureIndex(Reader &stReader, std::int32_t &out_nIndex, std::size_t nTextures)
{
	std::uint32_t nValue = 0;
	if (!stReader.Uint32(nValue) || (nValue != UINT32_MAX && nValue >= nTextures))
	{
		return false;
	}
	out_nIndex = nValue == UINT32_MAX ? -1 : static_cast<std::int32_t>(nValue);
	return true;
}

bool ReadMaterial(Reader &stReader, MaterialData &out_stMaterial, std::size_t nTextures)
{
	for (float &fValue : out_stMaterial.arrBaseColor)
	{
		if (!stReader.Float(fValue) || fValue < 0 || fValue > 1)
		{
			return false;
		}
	}
	if (!stReader.Float(out_stMaterial.fMetallic) || !stReader.Float(out_stMaterial.fRoughness) || out_stMaterial.fMetallic < 0 || out_stMaterial.fMetallic > 1 || out_stMaterial.fRoughness < 0 || out_stMaterial.fRoughness > 1)
	{
		return false;
	}
	for (float &fValue : out_stMaterial.arrEmissive)
	{
		if (!stReader.Float(fValue) || fValue < 0 || fValue > 1)
		{
			return false;
		}
	}
	std::uint32_t nDoubleSided = 0;
	std::uint32_t nAlpha = 0;
	if (!stReader.Float(out_stMaterial.fNormalScale) || !stReader.Float(out_stMaterial.fOcclusionStrength) || !stReader.Float(out_stMaterial.fAlphaCutoff) ||
		out_stMaterial.fOcclusionStrength < 0 || out_stMaterial.fOcclusionStrength > 1 || out_stMaterial.fAlphaCutoff < 0 || !stReader.Uint32(nDoubleSided) || nDoubleSided > 1 || !stReader.Uint32(nAlpha) || nAlpha > 2)
	{
		return false;
	}
	out_stMaterial.bDoubleSided = nDoubleSided == 1;
	out_stMaterial.eAlphaMode = static_cast<AlphaMode>(nAlpha);
	return ReadTextureIndex(stReader, out_stMaterial.nBaseColorTexture, nTextures) && ReadTextureIndex(stReader, out_stMaterial.nMetallicRoughnessTexture, nTextures) &&
			ReadTextureIndex(stReader, out_stMaterial.nNormalTexture, nTextures) && ReadTextureIndex(stReader, out_stMaterial.nOcclusionTexture, nTextures) && ReadTextureIndex(stReader, out_stMaterial.nEmissiveTexture, nTextures);
}

bool IsBasisValid(const MeshVertex &stVertex)
{
	double dNormalLength = 0;
	double dTangentLength = 0;
	double dDot = 0;
	for (std::size_t nAxis = 0; nAxis < 3; ++nAxis)
	{
		dNormalLength += static_cast<double>(stVertex.arrNormal[nAxis]) * stVertex.arrNormal[nAxis];
		dTangentLength += static_cast<double>(stVertex.arrTangent[nAxis]) * stVertex.arrTangent[nAxis];
		dDot += static_cast<double>(stVertex.arrNormal[nAxis]) * stVertex.arrTangent[nAxis];
	}
	return std::abs(dNormalLength - 1) <= 0.001 && std::abs(dTangentLength - 1) <= 0.001 && std::abs(dDot) <= 0.001 && (stVertex.arrTangent[3] == -1 || stVertex.arrTangent[3] == 1);
}

void WriteTransform(Writer &stWriter, const std::array<double, 16> &arrTransform)
{
	for (double dValue : arrTransform)
	{
		stWriter.Double(dValue);
	}
}

bool ReadTransform(Reader &stReader, std::array<double, 16> &out_arrTransform)
{
	for (double &dValue : out_arrTransform)
	{
		if (!stReader.Double(dValue))
		{
			return false;
		}
	}
	const std::array<double, 16> &arrM = out_arrTransform;
	const double dDeterminant = arrM[0] * (arrM[5] * arrM[10] - arrM[9] * arrM[6]) - arrM[4] * (arrM[1] * arrM[10] - arrM[9] * arrM[2]) + arrM[8] * (arrM[1] * arrM[6] - arrM[5] * arrM[2]);
	return arrM[3] == 0 && arrM[7] == 0 && arrM[11] == 0 && arrM[15] == 1 && std::isfinite(dDeterminant) && dDeterminant != 0;
}

void WriteMesh(Writer &stWriter, const DecodedMesh &stMesh)
{
	stWriter.Uint32(static_cast<std::uint32_t>(stMesh.arrImages.size()));
	for (const EncodedImage &stImage : stMesh.arrImages)
	{
		stWriter.String(stImage.strMimeType);
		stWriter.Uint32(static_cast<std::uint32_t>(stImage.arrBytes.size()));
		stWriter.Bytes(stImage.arrBytes.data(), stImage.arrBytes.size());
	}
	stWriter.Uint32(static_cast<std::uint32_t>(stMesh.arrTextures.size()));
	for (const TextureData &stTexture : stMesh.arrTextures)
	{
		stWriter.Uint32(stTexture.nImage);
		stWriter.Uint32(static_cast<std::uint32_t>(stTexture.nMagFilter));
		stWriter.Uint32(static_cast<std::uint32_t>(stTexture.nMinFilter));
		stWriter.Uint32(static_cast<std::uint32_t>(stTexture.nWrapS));
		stWriter.Uint32(static_cast<std::uint32_t>(stTexture.nWrapT));
	}
	stWriter.Uint32(static_cast<std::uint32_t>(stMesh.arrMaterials.size()));
	for (const MaterialData &stMaterial : stMesh.arrMaterials)
	{
		WriteMaterial(stWriter, stMaterial);
	}
	stWriter.Uint32(static_cast<std::uint32_t>(stMesh.arrPrimitives.size()));
	for (const MeshPrimitive &stPrimitive : stMesh.arrPrimitives)
	{
		stWriter.Uint32(static_cast<std::uint32_t>(stPrimitive.nMaterial));
		stWriter.Uint32(static_cast<std::uint32_t>(stPrimitive.arrVertices.size()));
		for (const MeshVertex &stVertex : stPrimitive.arrVertices)
		{
			for (float fValue : stVertex.arrPosition)
			{
				stWriter.Float(fValue);
			}
			for (float fValue : stVertex.arrNormal)
			{
				stWriter.Float(fValue);
			}
			for (float fValue : stVertex.arrTangent)
			{
				stWriter.Float(fValue);
			}
			for (float fValue : stVertex.arrTexcoord)
			{
				stWriter.Float(fValue);
			}
		}
		stWriter.Uint32(static_cast<std::uint32_t>(stPrimitive.arrIndices.size()));
		for (std::uint32_t nIndex : stPrimitive.arrIndices)
		{
			stWriter.Uint32(nIndex);
		}
	}
	stWriter.Uint32(static_cast<std::uint32_t>(stMesh.arrInstances.size()));
	for (const MeshInstance &stInstance : stMesh.arrInstances)
	{
		stWriter.Uint32(stInstance.nPrimitive);
		stWriter.Uint32(stInstance.nNode);
		WriteTransform(stWriter, stInstance.arrTransform);
	}
}

bool ReadMesh(Reader &stReader, DecodedMesh &out_stMesh, bool bMetadata = false)
{
	std::uint32_t nCount = 0;
	if (!stReader.Count(nCount, 8))
	{
		return false;
	}
	for (std::uint32_t nIndex = 0; nIndex < nCount; ++nIndex)
	{
		EncodedImage stImage;
		Assets::BlobInfo stInfo;
		Assets::Diagnostics arrDiagnostics;
		if (!stReader.String(stImage.strMimeType) || !stReader.Bytes(stImage.arrBytes) || (stImage.strMimeType != "image/png" && stImage.strMimeType != "image/jpeg") || (bMetadata ? !stImage.arrBytes.empty() : !Assets::ValidateBlob(stImage.strMimeType, stImage.arrBytes, stInfo, arrDiagnostics)))
		{
			return false;
		}
		out_stMesh.arrImages.push_back(std::move(stImage));
	}
	if (!stReader.Count(nCount, 20))
	{
		return false;
	}
	for (std::uint32_t nIndex = 0; nIndex < nCount; ++nIndex)
	{
		TextureData stTexture;
		std::uint32_t nMag = 0;
		std::uint32_t nMin = 0;
		std::uint32_t nS = 0;
		std::uint32_t nT = 0;
		if (!stReader.Uint32(stTexture.nImage) || stTexture.nImage >= out_stMesh.arrImages.size() || !stReader.Uint32(nMag) || !stReader.Uint32(nMin) || !stReader.Uint32(nS) || !stReader.Uint32(nT) ||
			(nMag != 0 && nMag != 9728 && nMag != 9729) || (nMin != 0 && nMin != 9728 && nMin != 9729 && (nMin < 9984 || nMin > 9987)) ||
			(nS != 33071 && nS != 33648 && nS != 10497) || (nT != 33071 && nT != 33648 && nT != 10497))
		{
			return false;
		}
		stTexture.nMagFilter = static_cast<std::int32_t>(nMag);
		stTexture.nMinFilter = static_cast<std::int32_t>(nMin);
		stTexture.nWrapS = static_cast<std::int32_t>(nS);
		stTexture.nWrapT = static_cast<std::int32_t>(nT);
		out_stMesh.arrTextures.push_back(stTexture);
	}
	if (!stReader.Count(nCount, 76) || nCount == 0)
	{
		return false;
	}
	for (std::uint32_t nIndex = 0; nIndex < nCount; ++nIndex)
	{
		MaterialData stMaterial;
		if (!ReadMaterial(stReader, stMaterial, out_stMesh.arrTextures.size()))
		{
			return false;
		}
		out_stMesh.arrMaterials.push_back(stMaterial);
	}
	if (!stReader.Count(nCount, 12) || nCount == 0)
	{
		return false;
	}
	for (std::uint32_t nIndex = 0; nIndex < nCount; ++nIndex)
	{
		MeshPrimitive stPrimitive;
		std::uint32_t nMaterial = 0;
		std::uint32_t nVertices = 0;
		if (!stReader.Uint32(nMaterial) || nMaterial >= out_stMesh.arrMaterials.size() || !stReader.Count(nVertices, 48, 6000000) || (bMetadata ? nVertices != 0 : nVertices == 0))
		{
			return false;
		}
		stPrimitive.nMaterial = static_cast<std::int32_t>(nMaterial);
		stPrimitive.arrVertices.resize(nVertices);
		for (MeshVertex &stVertex : stPrimitive.arrVertices)
		{
			for (float &fValue : stVertex.arrPosition)
			{
				if (!stReader.Float(fValue))
				{
					return false;
				}
			}
			for (float &fValue : stVertex.arrNormal)
			{
				if (!stReader.Float(fValue))
				{
					return false;
				}
			}
			for (float &fValue : stVertex.arrTangent)
			{
				if (!stReader.Float(fValue))
				{
					return false;
				}
			}
			for (float &fValue : stVertex.arrTexcoord)
			{
				if (!stReader.Float(fValue))
				{
					return false;
				}
			}
			if (!IsBasisValid(stVertex))
			{
				return false;
			}
		}
		std::uint32_t nIndices = 0;
		if (!stReader.Count(nIndices, 4, 6000000) || (bMetadata ? nIndices != 0 : nIndices == 0) || nIndices % 3 != 0)
		{
			return false;
		}
		stPrimitive.arrIndices.resize(nIndices);
		for (std::uint32_t &nValue : stPrimitive.arrIndices)
		{
			if (!stReader.Uint32(nValue) || nValue >= nVertices)
			{
				return false;
			}
		}
		out_stMesh.arrPrimitives.push_back(std::move(stPrimitive));
	}
	if (!stReader.Count(nCount, 136) || nCount == 0)
	{
		return false;
	}
	for (std::uint32_t nIndex = 0; nIndex < nCount; ++nIndex)
	{
		MeshInstance stInstance;
		if (!stReader.Uint32(stInstance.nPrimitive) || stInstance.nPrimitive >= out_stMesh.arrPrimitives.size() || !stReader.Uint32(stInstance.nNode) || stInstance.nNode >= MAX_ITEMS || !ReadTransform(stReader, stInstance.arrTransform))
		{
			return false;
		}
		out_stMesh.arrInstances.push_back(stInstance);
	}
	return true;
}

std::array<std::int32_t, 5> MaterialTextureIndices(const MaterialData &stMaterial)
{
	return { stMaterial.nBaseColorTexture, stMaterial.nMetallicRoughnessTexture, stMaterial.nNormalTexture, stMaterial.nOcclusionTexture, stMaterial.nEmissiveTexture };
}

void WritePreparedData(Writer &stWriter, const RenderScene &stScene)
{
	stWriter.Uint32(static_cast<std::uint32_t>(stScene.arrAssets.size()));
	for (const RenderAsset &stAsset : stScene.arrAssets)
	{
		stWriter.Uint32(static_cast<std::uint32_t>(stAsset.stTextureCook.arrVariants.size()));
		for (const CookedTextureVariant &stVariant : stAsset.stTextureCook.arrVariants)
		{
			stWriter.Uint32(stVariant.nImage);
			stWriter.Uint32(static_cast<std::uint32_t>(stVariant.eSemantic));
			stWriter.Uint32(static_cast<std::uint32_t>(stVariant.eAlphaPolicy));
			stWriter.Uint32(static_cast<std::uint32_t>(stVariant.arrMips.size()));
			for (const MipLevel &stMip : stVariant.arrMips)
			{
				stWriter.Uint32(stMip.nWidth);
				stWriter.Uint32(stMip.nHeight);
				stWriter.Uint32(static_cast<std::uint32_t>(stMip.arrRgba8.size()));
				stWriter.Bytes(stMip.arrRgba8.data(), stMip.arrRgba8.size());
			}
		}
		stWriter.Uint32(static_cast<std::uint32_t>(stAsset.stTextureCook.arrMaterials.size()));
		for (const CookedMaterialTextures &stMaterial : stAsset.stTextureCook.arrMaterials)
		{
			for (std::int32_t nVariant : stMaterial.arrVariants)
			{
				stWriter.Uint32(nVariant < 0 ? UINT32_MAX : static_cast<std::uint32_t>(nVariant));
			}
		}
		stWriter.Uint32(static_cast<std::uint32_t>(stAsset.stMesh.arrPrimitives.size()));
		for (const MeshPrimitive &stPrimitive : stAsset.stMesh.arrPrimitives)
		{
			stWriter.Uint32(static_cast<std::uint32_t>(stPrimitive.arrClusters.size()));
			for (const MeshCluster &stCluster : stPrimitive.arrClusters)
			{
				stWriter.Uint32(static_cast<std::uint32_t>(stCluster.arrVertexIndices.size()));
				for (std::uint32_t nIndex : stCluster.arrVertexIndices)
				{
					stWriter.Uint32(nIndex);
				}
				stWriter.Uint32(static_cast<std::uint32_t>(stCluster.arrTriangleIndices.size()));
				stWriter.Bytes(stCluster.arrTriangleIndices.data(), stCluster.arrTriangleIndices.size());
				for (const std::array<float, 3> &arrBounds : { stCluster.arrBoundsMinimum, stCluster.arrBoundsMaximum, stCluster.arrSphereCenter })
				{
					for (float fValue : arrBounds)
					{
						stWriter.Float(fValue);
					}
				}
				stWriter.Float(stCluster.fSphereRadius);
				stWriter.Uint32(stCluster.nDegenerateTriangleCount);
			}
		}
	}
}

bool ReadTextureData(Reader &stReader, RenderAsset &out_stAsset, bool bMetadata = false)
{
	std::uint32_t nVariants = 0;
	if (!stReader.Count(nVariants, 16, MAX_ITEMS, sizeof(CookedTextureVariant)))
	{
		return false;
	}
	std::set<std::array<std::uint32_t, 3>> setKeys;
	for (std::uint32_t nVariant = 0; nVariant < nVariants; ++nVariant)
	{
		CookedTextureVariant stVariant;
		std::uint32_t nSemantic = 0;
		std::uint32_t nAlpha = 0;
		std::uint32_t nMips = 0;
		if (!stReader.Uint32(stVariant.nImage) || stVariant.nImage >= out_stAsset.stMesh.arrImages.size() ||
			!stReader.Uint32(nSemantic) || nSemantic > static_cast<std::uint32_t>(ImageSemantic::Normal) ||
			!stReader.Uint32(nAlpha) || nAlpha > static_cast<std::uint32_t>(TextureAlphaPolicy::Ignore) ||
			!setKeys.insert({ stVariant.nImage, nSemantic, nAlpha }).second || !stReader.Count(nMips, bMetadata ? 12 : 16, 14, sizeof(MipLevel)) || nMips == 0)
		{
			return false;
		}
		stVariant.eSemantic = static_cast<ImageSemantic>(nSemantic);
		stVariant.eAlphaPolicy = static_cast<TextureAlphaPolicy>(nAlpha);
		Assets::BlobInfo stImageInfo;
		Assets::Diagnostics arrImageDiagnostics;
		const EncodedImage &stImage = out_stAsset.stMesh.arrImages[stVariant.nImage];
		if (!bMetadata && !Assets::ValidateBlob(stImage.strMimeType, stImage.arrBytes, stImageInfo, arrImageDiagnostics))
		{
			return false;
		}
		std::uint32_t nWidth = 0;
		std::uint32_t nHeight = 0;
		for (std::uint32_t nMip = 0; nMip < nMips; ++nMip)
		{
			MipLevel stLevel;
			if (!stReader.Uint32(stLevel.nWidth) || !stReader.Uint32(stLevel.nHeight) || stLevel.nWidth == 0 || stLevel.nHeight == 0 ||
				stLevel.nWidth > 8192 || stLevel.nHeight > 8192 ||
				(!bMetadata && nMip == 0 && (stLevel.nWidth != stImageInfo.nWidth || stLevel.nHeight != stImageInfo.nHeight)) ||
				(nMip != 0 && (stLevel.nWidth != (std::max)(1U, nWidth / 2) || stLevel.nHeight != (std::max)(1U, nHeight / 2) || (nWidth == 1 && nHeight == 1))) ||
				!stReader.Bytes(stLevel.arrRgba8, static_cast<std::uint32_t>(MAX_PAGE_BYTES)) ||
				(bMetadata ? !stLevel.arrRgba8.empty() : stLevel.arrRgba8.size() != static_cast<std::size_t>(stLevel.nWidth) * stLevel.nHeight * 4))
			{
				return false;
			}
			nWidth = stLevel.nWidth;
			nHeight = stLevel.nHeight;
			stVariant.arrMips.push_back(std::move(stLevel));
		}
		if (nWidth != 1 || nHeight != 1)
		{
			return false;
		}
		out_stAsset.stTextureCook.arrVariants.push_back(std::move(stVariant));
	}
	std::uint32_t nMaterials = 0;
	if (!stReader.Count(nMaterials, sizeof(CookedMaterialTextures)) || nMaterials != out_stAsset.stMesh.arrMaterials.size())
	{
		return false;
	}
	std::set<std::uint32_t> setReferenced;
	for (std::uint32_t nMaterial = 0; nMaterial < nMaterials; ++nMaterial)
	{
		CookedMaterialTextures stBindings;
		const MaterialData &stMaterial = out_stAsset.stMesh.arrMaterials[nMaterial];
		const std::array<std::int32_t, 5> arrSourceTextures = MaterialTextureIndices(stMaterial);
		for (std::size_t nSlot = 0; nSlot < stBindings.arrVariants.size(); ++nSlot)
		{
			std::uint32_t nVariant = 0;
			if (!stReader.Uint32(nVariant) || (nVariant != UINT32_MAX && nVariant >= nVariants) ||
				((nVariant == UINT32_MAX) != (arrSourceTextures[nSlot] < 0)))
			{
				return false;
			}
			if (nVariant != UINT32_MAX)
			{
				const CookedTextureVariant &stVariant = out_stAsset.stTextureCook.arrVariants[nVariant];
				const ImageSemantic eExpected = nSlot == 2 ? ImageSemantic::Normal : (nSlot == 0 || nSlot == 4 ? ImageSemantic::Srgb : ImageSemantic::Linear);
				const TextureAlphaPolicy eExpectedAlpha = nSlot == 4 || (nSlot == 0 && stMaterial.eAlphaMode == AlphaMode::Opaque) ? TextureAlphaPolicy::Ignore : TextureAlphaPolicy::Preserve;
				const TextureData &stSourceTexture = out_stAsset.stMesh.arrTextures[static_cast<std::size_t>(arrSourceTextures[nSlot])];
				if (stVariant.nImage != stSourceTexture.nImage || stVariant.eSemantic != eExpected || stVariant.eAlphaPolicy != eExpectedAlpha)
				{
					return false;
				}
				setReferenced.insert(nVariant);
			}
			stBindings.arrVariants[nSlot] = nVariant == UINT32_MAX ? -1 : static_cast<std::int32_t>(nVariant);
		}
		out_stAsset.stTextureCook.arrMaterials.push_back(stBindings);
	}
	return setReferenced.size() == nVariants;
}

bool ReadClusterData(Reader &stReader, MeshPrimitive &out_stPrimitive)
{
	std::uint32_t nClusters = 0;
	if (!stReader.Count(nClusters, 59, MAX_ITEMS, sizeof(MeshCluster)) || nClusters == 0)
	{
		return false;
	}
	for (std::uint32_t nCluster = 0; nCluster < nClusters; ++nCluster)
	{
		MeshCluster stCluster;
		std::uint32_t nVertices = 0;
		if (!stReader.Count(nVertices, sizeof(std::uint32_t), MAX_MESH_CLUSTER_VERTICES) || nVertices == 0)
		{
			return false;
		}
		std::set<std::uint32_t> setVertices;
		for (std::uint32_t nVertex = 0; nVertex < nVertices; ++nVertex)
		{
			std::uint32_t nIndex = 0;
			if (!stReader.Uint32(nIndex) || nIndex >= out_stPrimitive.arrVertices.size() || !setVertices.insert(nIndex).second)
			{
				return false;
			}
			stCluster.arrVertexIndices.push_back(nIndex);
		}
		if (!stReader.Bytes(stCluster.arrTriangleIndices, MAX_MESH_CLUSTER_TRIANGLES * 3) || stCluster.arrTriangleIndices.empty() || stCluster.arrTriangleIndices.size() % 3 != 0)
		{
			return false;
		}
		for (std::uint8_t nIndex : stCluster.arrTriangleIndices)
		{
			if (nIndex >= nVertices)
			{
				return false;
			}
		}
		for (std::array<float, 3> *pBounds : { &stCluster.arrBoundsMinimum, &stCluster.arrBoundsMaximum, &stCluster.arrSphereCenter })
		{
			for (float &fValue : *pBounds)
			{
				if (!stReader.Float(fValue))
				{
					return false;
				}
			}
		}
		if (!stReader.Float(stCluster.fSphereRadius) || stCluster.fSphereRadius < 0 || !stReader.Uint32(stCluster.nDegenerateTriangleCount) ||
			stCluster.nDegenerateTriangleCount > stCluster.arrTriangleIndices.size() / 3)
		{
			return false;
		}
		out_stPrimitive.arrClusters.push_back(std::move(stCluster));
	}
	std::vector<MeshCluster> arrExpected;
	Assets::Diagnostics arrDiagnostics;
	if (!CookMeshClusters(out_stPrimitive, arrExpected, arrDiagnostics) || arrExpected.size() != out_stPrimitive.arrClusters.size())
	{
		return false;
	}
	for (std::size_t nIndex = 0; nIndex < arrExpected.size(); ++nIndex)
	{
		const MeshCluster &stExpected = arrExpected[nIndex];
		const MeshCluster &stActual = out_stPrimitive.arrClusters[nIndex];
		if (stExpected.arrVertexIndices != stActual.arrVertexIndices || stExpected.arrTriangleIndices != stActual.arrTriangleIndices ||
			stExpected.arrBoundsMinimum != stActual.arrBoundsMinimum || stExpected.arrBoundsMaximum != stActual.arrBoundsMaximum ||
			stExpected.arrSphereCenter != stActual.arrSphereCenter || stExpected.fSphereRadius != stActual.fSphereRadius ||
			stExpected.nDegenerateTriangleCount != stActual.nDegenerateTriangleCount)
		{
			return false;
		}
	}
	return true;
}

bool ReadPreparedData(Reader &stReader, RenderScene &out_stScene, bool bMetadata = false)
{
	std::uint32_t nAssets = 0;
	if (!stReader.Count(nAssets, 4, 1024) || nAssets != out_stScene.arrAssets.size())
	{
		return false;
	}
	for (RenderAsset &stAsset : out_stScene.arrAssets)
	{
		if (!ReadTextureData(stReader, stAsset, bMetadata))
		{
			return false;
		}
		std::uint32_t nPrimitives = 0;
		if (!stReader.Count(nPrimitives, 4) || nPrimitives != stAsset.stMesh.arrPrimitives.size())
		{
			return false;
		}
		for (MeshPrimitive &stPrimitive : stAsset.stMesh.arrPrimitives)
		{
			std::uint32_t nEmptyClusters = 0;
			if (bMetadata ? (!stReader.Uint32(nEmptyClusters) || nEmptyClusters != 0) : !ReadClusterData(stReader, stPrimitive))
			{
				return false;
			}
		}
	}
	return true;
}

bool PrepareScene(RenderScene &out_stScene, Assets::Diagnostics &out_arrDiagnostics)
{
	std::size_t nRemainingBytes = MAX_PAGE_BYTES;
	for (RenderAsset &stAsset : out_stScene.arrAssets)
	{
		if (!CookMeshTextures(stAsset.stMesh, stAsset.stTextureCook, out_arrDiagnostics, nRemainingBytes))
		{
			return false;
		}
		for (const CookedTextureVariant &stVariant : stAsset.stTextureCook.arrVariants)
		{
			for (const MipLevel &stMip : stVariant.arrMips)
			{
				nRemainingBytes -= stMip.arrRgba8.size();
			}
		}
		for (MeshPrimitive &stPrimitive : stAsset.stMesh.arrPrimitives)
		{
			const std::size_t nTriangles = stPrimitive.arrIndices.size() / 3;
			// At least 21 complete triangles fit the 64-vertex limit, including
			// disjoint input triangles. Bound all temporary cluster allocations.
			const std::size_t nMaximumClusters = (nTriangles + 20) / 21;
			const std::size_t nMaximumBytes = nMaximumClusters * sizeof(MeshCluster) + stPrimitive.arrIndices.size() * 5;
			if (nMaximumBytes > nRemainingBytes)
			{
				return Fail(out_arrDiagnostics, "gpu_cook_budget", "$", "Cluster data exceeds the remaining prepared-data budget.");
			}
			if (!CookMeshClusters(stPrimitive, stPrimitive.arrClusters, out_arrDiagnostics))
			{
				return false;
			}
			for (const MeshCluster &stCluster : stPrimitive.arrClusters)
			{
				nRemainingBytes -= sizeof(MeshCluster) + stCluster.arrVertexIndices.size() * sizeof(std::uint32_t) + stCluster.arrTriangleIndices.size();
			}
		}
	}
	out_stScene.nGpuFormatVersion = PREPARED_FORMAT_VERSION;
	return true;
}

bool Encode(const RenderScene &stScene, std::vector<std::uint8_t> &out_arrPage, std::uint32_t nVersion = LEGACY_FORMAT_VERSION)
{
	Writer stWriter;
	stWriter.Bytes(MAGIC.data(), MAGIC.size());
	stWriter.Uint32(nVersion);
	stWriter.String(stScene.strSceneId);
	stWriter.String(stScene.strSceneRevision);
	stWriter.String(stScene.strSceneDigest);
	stWriter.String(stScene.strPackageDigest);
	stWriter.Uint32(static_cast<std::uint32_t>(stScene.arrAssets.size()));
	for (const RenderAsset &stAsset : stScene.arrAssets)
	{
		stWriter.String(stAsset.stIdentity.strAssetId);
		stWriter.String(stAsset.stIdentity.strRevision);
		stWriter.String(stAsset.stIdentity.strContentSha256);
		WriteMesh(stWriter, stAsset.stMesh);
	}
	stWriter.Uint32(static_cast<std::uint32_t>(stScene.arrInstances.size()));
	for (const RenderInstance &stInstance : stScene.arrInstances)
	{
		stWriter.Uint64(stInstance.nEntityId);
		stWriter.Uint32(stInstance.nAsset);
		stWriter.Uint32(stInstance.nPrimitive);
		stWriter.Uint32(stInstance.nNode);
		WriteTransform(stWriter, stInstance.arrTransform);
		for (double dValue : stInstance.arrEntityOrigin)
		{
			stWriter.Double(dValue);
		}
	}
	if (nVersion >= PREPARED_FORMAT_VERSION)
	{
		WritePreparedData(stWriter, stScene);
	}
	out_arrPage = std::move(stWriter.arrBytes);
	return stWriter.bValid;
}

bool Decode(const std::vector<std::uint8_t> &arrPage, RenderScene &out_stScene)
{
	if (arrPage.size() < 16 || !std::equal(MAGIC.begin(), MAGIC.end(), arrPage.begin()))
	{
		return false;
	}
	Reader stReader(arrPage);
	std::uint64_t nMagic = 0;
	std::uint32_t nVersion = 0;
	std::uint32_t nAssets = 0;
	std::string strSceneId;
	std::string strSceneRevision;
	std::string strSceneDigest;
	std::string strPackageDigest;
	if (!stReader.Uint64(nMagic) || !stReader.Uint32(nVersion) || nVersion != out_stScene.nGpuFormatVersion ||
		!stReader.String(strSceneId) || strSceneId != out_stScene.strSceneId || !stReader.String(strSceneRevision) || strSceneRevision != out_stScene.strSceneRevision ||
		!stReader.String(strSceneDigest) || strSceneDigest != out_stScene.strSceneDigest || !stReader.String(strPackageDigest) || strPackageDigest != out_stScene.strPackageDigest ||
		!stReader.Count(nAssets, 32, 1024) || nAssets == 0)
	{
		return false;
	}
	std::set<std::string> setAssets;
	for (std::uint32_t nIndex = 0; nIndex < nAssets; ++nIndex)
	{
		RenderAsset stAsset;
		if (!stReader.String(stAsset.stIdentity.strAssetId) || !stReader.String(stAsset.stIdentity.strRevision) || !stReader.String(stAsset.stIdentity.strContentSha256) ||
			!Assets::IsIdentity(stAsset.stIdentity.strAssetId) || !Assets::IsRevision(stAsset.stIdentity.strRevision) || !Assets::IsSha256(stAsset.stIdentity.strContentSha256) || !setAssets.insert(stAsset.stIdentity.strAssetId).second || !ReadMesh(stReader, stAsset.stMesh, nVersion == 3))
		{
			return false;
		}
		out_stScene.arrAssets.push_back(std::move(stAsset));
	}
	std::uint32_t nInstances = 0;
	if (!stReader.Count(nInstances, 172) || nInstances == 0)
	{
		return false;
	}
	std::set<std::array<std::uint64_t, 4>> setInstances;
	for (std::uint32_t nIndex = 0; nIndex < nInstances; ++nIndex)
	{
		RenderInstance stInstance;
		if (!stReader.Uint64(stInstance.nEntityId) || stInstance.nEntityId == 0 || stInstance.nEntityId > static_cast<std::uint64_t>(INT64_MAX) ||
			!stReader.Uint32(stInstance.nAsset) || stInstance.nAsset >= out_stScene.arrAssets.size() || !stReader.Uint32(stInstance.nPrimitive) || !stReader.Uint32(stInstance.nNode) || stInstance.nNode >= MAX_ITEMS ||
			stInstance.nPrimitive >= out_stScene.arrAssets[stInstance.nAsset].stMesh.arrPrimitives.size() || !ReadTransform(stReader, stInstance.arrTransform))
		{
			return false;
		}
		if (!setInstances.insert({ stInstance.nEntityId, stInstance.nAsset, stInstance.nNode, stInstance.nPrimitive }).second)
		{
			return false;
		}
		for (double &dValue : stInstance.arrEntityOrigin)
		{
			if (!stReader.Double(dValue))
			{
				return false;
			}
		}
		out_stScene.arrInstances.push_back(stInstance);
	}
	if (nVersion >= PREPARED_FORMAT_VERSION && !ReadPreparedData(stReader, out_stScene, nVersion == 3))
	{
		return false;
	}
	return stReader.IsComplete();
}

bool ReadFile(const fs::path &stPath, std::size_t nLimit, std::vector<std::uint8_t> &out_arrBytes)
{
	std::error_code stError;
	if (!Assets::NoLinkedComponents(stPath) || !fs::is_regular_file(stPath, stError) || stError)
	{
		return false;
	}
	const std::uintmax_t nBytes = fs::file_size(stPath, stError);
	if (stError || nBytes == 0 || nBytes > nLimit)
	{
		return false;
	}
	std::ifstream stFile(stPath, std::ios::binary);
	out_arrBytes.resize(static_cast<std::size_t>(nBytes));
	stFile.read(reinterpret_cast<char *>(out_arrBytes.data()), static_cast<std::streamsize>(nBytes));
	return stFile.good() && stFile.peek() == std::char_traits<char>::eof();
}

bool WriteFile(const fs::path &stPath, const std::uint8_t *pBytes, std::size_t nBytes)
{
	std::ofstream stFile(stPath, std::ios::binary);
	stFile.write(reinterpret_cast<const char *>(pBytes), static_cast<std::streamsize>(nBytes));
	stFile.flush();
	stFile.close();
	return stFile.good();
}

bool RenameNoReplace(const fs::path &stSource, const fs::path &stTarget)
{
#ifdef _WIN32
	return MoveFileExW(stSource.wstring().c_str(), stTarget.wstring().c_str(), 0) != 0;
#elif defined(__APPLE__)
	return renamex_np(stSource.c_str(), stTarget.c_str(), RENAME_EXCL) == 0;
#elif defined(__linux__)
	return syscall(SYS_renameat2, AT_FDCWD, stSource.c_str(), AT_FDCWD, stTarget.c_str(), 1U) == 0;
#else
	return false;
#endif
}

bool IsInside(const fs::path &stPath, const fs::path &stParent)
{
	fs::path::const_iterator itPath = stPath.begin();
	for (const fs::path &stPart : stParent)
	{
		if (itPath == stPath.end())
		{
			return false;
		}
#ifdef _WIN32
		if (_wcsicmp(itPath->c_str(), stPart.c_str()) != 0)
#else
		if (*itPath != stPart)
#endif
		{
			return false;
		}
		++itPath;
	}
	return true;
}

JsonValue Manifest(const RenderScene &stScene, const std::vector<std::uint8_t> &arrPage, std::uint32_t nVersion)
{
	JsonValue::Object mapManifest{
		{ "schema_version", static_cast<std::int64_t>(nVersion) },
		{ "cook_version", nVersion == PREPARED_FORMAT_VERSION ? "engine-next-gpu-data-v2" : "engine-next-cpu-layout-v1" },
		{ "source_package_sha256", stScene.strPackageDigest },
		{ "scene_id", stScene.strSceneId },
		{ "scene_revision", stScene.strSceneRevision },
		{ "scene_sha256", stScene.strSceneDigest },
		{ "page_sha256", Serialization::Sha256Hex(arrPage.data(), arrPage.size()) },
		{ "page_bytes", static_cast<std::int64_t>(arrPage.size()) },
		{ "vertex_layout", "position3f-normal3f-tangent4f-texcoord2f-le" },
		{ "image_encoding", "source-png-jpeg" },
	};
	if (nVersion == PREPARED_FORMAT_VERSION)
	{
		mapManifest.emplace("texture_format", "rgba8-uncompressed");
		mapManifest.emplace("texture_cook_version", "srgb-linear-normal-v1");
		mapManifest.emplace("cluster_version", "sequential-64v-126t-v1");
	}
	return mapManifest;
}

bool ParseManifest(const std::vector<std::uint8_t> &arrManifest, const std::string &strExpectedSourceDigest, RenderScene &out_stScene, std::string &out_strPageDigest, std::size_t &out_nPageBytes, Assets::Diagnostics &out_arrDiagnostics)
{
	const std::string strText(arrManifest.begin(), arrManifest.end());
	JsonValue stValue;
	std::string strError;
	std::string strCanonical;
	if (!Serialization::ParseJson(strText, stValue, strError) || !Serialization::CanonicalJson(stValue, strCanonical) || strText != strCanonical)
	{
		return false;
	}
	const JsonValue::Object *pObject = stValue.GetObject();
	std::int64_t nVersion = 0;
	if (pObject == nullptr || !Assets::Integer(*pObject, "schema_version", "$", nVersion, out_arrDiagnostics) ||
		(nVersion != LEGACY_FORMAT_VERSION && nVersion != PREPARED_FORMAT_VERSION))
	{
		return false;
	}
	const bool bPrepared = nVersion == PREPARED_FORMAT_VERSION;
	if ((!bPrepared && !Assets::Fields(*pObject, { "schema_version", "cook_version", "source_package_sha256", "scene_id", "scene_revision", "scene_sha256", "page_sha256", "page_bytes", "vertex_layout", "image_encoding" }, "$", out_arrDiagnostics)) ||
		(bPrepared && !Assets::Fields(*pObject, { "schema_version", "cook_version", "source_package_sha256", "scene_id", "scene_revision", "scene_sha256", "page_sha256", "page_bytes", "vertex_layout", "image_encoding", "texture_format", "texture_cook_version", "cluster_version" }, "$", out_arrDiagnostics)))
	{
		return false;
	}
	std::string strTextureFormat;
	std::string strTextureVersion;
	std::string strClusterVersion;
	if (bPrepared && (!Assets::String(*pObject, "texture_format", "$", strTextureFormat, out_arrDiagnostics) || strTextureFormat != "rgba8-uncompressed" || !Assets::String(*pObject, "texture_cook_version", "$", strTextureVersion, out_arrDiagnostics) || strTextureVersion != "srgb-linear-normal-v1" || !Assets::String(*pObject, "cluster_version", "$", strClusterVersion, out_arrDiagnostics) || strClusterVersion != "sequential-64v-126t-v1"))
	{
		return false;
	}
	out_stScene.nGpuFormatVersion = static_cast<std::uint32_t>(nVersion);
	std::int64_t nBytes = 0;
	std::string strCook;
	std::string strLayout;
	std::string strEncoding;
	if (
			!Assets::Integer(*pObject, "page_bytes", "$", nBytes, out_arrDiagnostics) || nBytes <= 0 || static_cast<std::uint64_t>(nBytes) > MAX_PAGE_BYTES ||
			!Assets::String(*pObject, "cook_version", "$", strCook, out_arrDiagnostics) || strCook != (bPrepared ? "engine-next-gpu-data-v2" : "engine-next-cpu-layout-v1") ||
			!Assets::String(*pObject, "vertex_layout", "$", strLayout, out_arrDiagnostics) || strLayout != "position3f-normal3f-tangent4f-texcoord2f-le" ||
			!Assets::String(*pObject, "image_encoding", "$", strEncoding, out_arrDiagnostics) || strEncoding != "source-png-jpeg" ||
			!Assets::String(*pObject, "source_package_sha256", "$", out_stScene.strPackageDigest, out_arrDiagnostics) || out_stScene.strPackageDigest != strExpectedSourceDigest ||
			!Assets::String(*pObject, "scene_id", "$", out_stScene.strSceneId, out_arrDiagnostics) || !Assets::IsIdentity(out_stScene.strSceneId) ||
			!Assets::String(*pObject, "scene_revision", "$", out_stScene.strSceneRevision, out_arrDiagnostics) || !Assets::IsRevision(out_stScene.strSceneRevision) ||
			!Assets::String(*pObject, "scene_sha256", "$", out_stScene.strSceneDigest, out_arrDiagnostics) || !Assets::IsSha256(out_stScene.strSceneDigest) ||
			!Assets::String(*pObject, "page_sha256", "$", out_strPageDigest, out_arrDiagnostics) || !Assets::IsSha256(out_strPageDigest))
	{
		return false;
	}
	out_nPageBytes = static_cast<std::size_t>(nBytes);
	return true;
}

} // namespace

bool VerifyCookedScene(const RenderScene &stSource, const RenderScene &stCooked, Assets::Diagnostics &out_arrDiagnostics)
{
	std::vector<std::uint8_t> arrSource;
	std::vector<std::uint8_t> arrCooked;
	if (!Encode(stSource, arrSource) || !Encode(stCooked, arrCooked))
	{
		return Fail(out_arrDiagnostics, "gpu_source_budget", "$", "Source comparison exceeds the canonical GPU page budget.");
	}
	if (arrSource != arrCooked)
	{
		return Fail(out_arrDiagnostics, "gpu_source_mismatch", "$", "Cooked scene does not match the validated source scene.");
	}
	if (stCooked.nGpuFormatVersion == PREPARED_FORMAT_VERSION)
	{
		RenderScene stExpected = stSource;
		if (!PrepareScene(stExpected, out_arrDiagnostics) || !Encode(stExpected, arrSource, PREPARED_FORMAT_VERSION) ||
			!Encode(stCooked, arrCooked, PREPARED_FORMAT_VERSION))
		{
			return Fail(out_arrDiagnostics, "gpu_source_derived", "$", "Unable to verify prepared data against its source.");
		}
		if (arrSource != arrCooked)
		{
			return Fail(out_arrDiagnostics, "gpu_source_mismatch", "$", "Prepared mip or cluster data does not match the validated source scene.");
		}
	}
	return true;
}

bool PrepareGpuSceneForPaging(const RenderScene &stSource, RenderScene &out_stPrepared, Assets::Diagnostics &out_arrDiagnostics)
{
	RenderScene stCandidate = stSource;
	if (!PrepareScene(stCandidate, out_arrDiagnostics))
	{
		return false;
	}
	out_stPrepared = std::move(stCandidate);
	return true;
}

bool EncodeGpuSceneMetadata(const RenderScene &stPrepared, std::vector<std::uint8_t> &out_arrBytes, Assets::Diagnostics &out_arrDiagnostics)
{
	RenderScene stMetadata;
	stMetadata.nGpuFormatVersion = 3;
	stMetadata.strSceneId = stPrepared.strSceneId;
	stMetadata.strSceneRevision = stPrepared.strSceneRevision;
	stMetadata.strSceneDigest = stPrepared.strSceneDigest;
	stMetadata.strPackageDigest = stPrepared.strPackageDigest;
	stMetadata.arrInstances = stPrepared.arrInstances;
	stMetadata.arrAssets.reserve(stPrepared.arrAssets.size());
	for (const RenderAsset &stAsset : stPrepared.arrAssets)
	{
		RenderAsset stCopy;
		stCopy.stIdentity = stAsset.stIdentity;
		stCopy.stMesh.arrMaterials = stAsset.stMesh.arrMaterials;
		stCopy.stMesh.arrTextures = stAsset.stMesh.arrTextures;
		stCopy.stMesh.arrInstances = stAsset.stMesh.arrInstances;
		stCopy.stMesh.arrImages.resize(stAsset.stMesh.arrImages.size());
		for (std::size_t nImage = 0; nImage < stCopy.stMesh.arrImages.size(); ++nImage)
		{
			stCopy.stMesh.arrImages[nImage].strMimeType = stAsset.stMesh.arrImages[nImage].strMimeType;
		}
		stCopy.stMesh.arrPrimitives.resize(stAsset.stMesh.arrPrimitives.size());
		for (std::size_t nPrimitive = 0; nPrimitive < stCopy.stMesh.arrPrimitives.size(); ++nPrimitive)
		{
			stCopy.stMesh.arrPrimitives[nPrimitive].nMaterial = stAsset.stMesh.arrPrimitives[nPrimitive].nMaterial;
		}
		stCopy.stTextureCook.arrMaterials = stAsset.stTextureCook.arrMaterials;
		stCopy.stTextureCook.arrVariants.reserve(stAsset.stTextureCook.arrVariants.size());
		for (const CookedTextureVariant &stVariant : stAsset.stTextureCook.arrVariants)
		{
			CookedTextureVariant stVariantCopy;
			stVariantCopy.nImage = stVariant.nImage;
			stVariantCopy.eSemantic = stVariant.eSemantic;
			stVariantCopy.eAlphaPolicy = stVariant.eAlphaPolicy;
			stVariantCopy.arrMips.reserve(stVariant.arrMips.size());
			for (const MipLevel &stMip : stVariant.arrMips)
			{
				MipLevel stMipCopy;
				stMipCopy.nWidth = stMip.nWidth;
				stMipCopy.nHeight = stMip.nHeight;
				stVariantCopy.arrMips.push_back(std::move(stMipCopy));
			}
			stCopy.stTextureCook.arrVariants.push_back(std::move(stVariantCopy));
		}
		stMetadata.arrAssets.push_back(std::move(stCopy));
	}
	std::vector<std::uint8_t> arrBytes;
	if (!Encode(stMetadata, arrBytes, 3))
	{
		return Fail(out_arrDiagnostics, "gpu_metadata", "$", "Metadata exceeds the codec budget.");
	}
	RenderScene stVerified;
	if (!DecodeGpuSceneMetadata(arrBytes, stPrepared.strPackageDigest, stVerified, out_arrDiagnostics))
	{
		return false;
	}
	out_arrBytes = std::move(arrBytes);
	return true;
}

bool DecodeGpuSceneMetadata(const std::vector<std::uint8_t> &arrBytes, const std::string &strSourceDigest,
							RenderScene &out_stMetadata, Assets::Diagnostics &out_arrDiagnostics)
{
	if (arrBytes.size() > MAX_PAGE_BYTES || !Assets::IsSha256(strSourceDigest))
	{
		return Fail(out_arrDiagnostics, "gpu_metadata", "$", "Invalid metadata size or source digest.");
	}
	Reader stReader(arrBytes);
	std::uint64_t nMagic = 0;
	RenderScene stCandidate;
	if (!stReader.Uint64(nMagic) || !stReader.Uint32(stCandidate.nGpuFormatVersion) || stCandidate.nGpuFormatVersion != 3 ||
		!stReader.String(stCandidate.strSceneId) || !Assets::IsIdentity(stCandidate.strSceneId) ||
		!stReader.String(stCandidate.strSceneRevision) || !Assets::IsRevision(stCandidate.strSceneRevision) ||
		!stReader.String(stCandidate.strSceneDigest) || !Assets::IsSha256(stCandidate.strSceneDigest) ||
		!stReader.String(stCandidate.strPackageDigest) || stCandidate.strPackageDigest != strSourceDigest ||
		!Decode(arrBytes, stCandidate))
	{
		return Fail(out_arrDiagnostics, "gpu_metadata", "$", "Invalid or mismatched metadata payload.");
	}
	out_stMetadata = std::move(stCandidate);
	return true;
}

bool PublishGpuDirectoryNoReplace(const std::filesystem::path &stSource, const std::filesystem::path &stTarget)
{
	return RenameNoReplace(stSource, stTarget);
}

bool LoadGpuPackage(const std::string &strPackage, const std::string &strExpectedSourceDigest, RenderScene &out_stScene, Assets::Diagnostics &out_arrDiagnostics)
{
	out_arrDiagnostics.clear();
	std::error_code stError;
	const fs::path stRoot = fs::absolute(strPackage, stError).lexically_normal();
	if (stError || !Assets::IsSha256(strExpectedSourceDigest) || !Assets::NoLinkedComponents(stRoot) || !fs::is_directory(stRoot, stError) || stError)
	{
		return Fail(out_arrDiagnostics, "gpu_package_path", "$", "GPU package root or expected source digest is invalid.");
	}
	std::vector<std::uint8_t> arrManifest;
	RenderScene stScene;
	std::string strPageDigest;
	std::size_t nPageBytes = 0;
	if (!ReadFile(stRoot / "GpuManifest.json", MAX_MANIFEST_BYTES, arrManifest) || !ParseManifest(arrManifest, strExpectedSourceDigest, stScene, strPageDigest, nPageBytes, out_arrDiagnostics))
	{
		return Fail(out_arrDiagnostics, "gpu_manifest", "$", "GPU manifest is invalid, noncanonical, or bound to another source package.");
	}
	const std::set<std::string> setExpected{ "GpuManifest.json", "blobs/" + strPageDigest };
	std::set<std::string> setFound;
	std::uint32_t nEntryCount = 0;
	for (fs::recursive_directory_iterator itEntry(stRoot, stError); !stError && itEntry != fs::recursive_directory_iterator(); itEntry.increment(stError))
	{
		if (++nEntryCount > 3)
		{
			return Fail(out_arrDiagnostics, "gpu_package_files", "$", "GPU package contains too many entries.");
		}
		if (itEntry->is_symlink(stError) || stError)
		{
			return Fail(out_arrDiagnostics, "gpu_package_path", "$", "Linked package entries are forbidden.");
		}
		if (itEntry->is_regular_file(stError))
		{
			const std::string strRelative = itEntry->path().lexically_relative(stRoot).generic_string();
			if (setExpected.find(strRelative) == setExpected.end())
			{
				return Fail(out_arrDiagnostics, "gpu_package_files", "$", "GPU package has an undeclared file.");
			}
			setFound.insert(strRelative);
		}
		else if (!itEntry->is_directory(stError) || itEntry->path().lexically_relative(stRoot).generic_string() != "blobs")
		{
			return Fail(out_arrDiagnostics, "gpu_package_files", "$", "Unexpected directory or non-regular package entry.");
		}
	}
	if (stError || setFound != setExpected)
	{
		return Fail(out_arrDiagnostics, "gpu_package_files", "$", "GPU package must contain exactly its manifest and declared page.");
	}
	std::vector<std::uint8_t> arrPage;
	if (!ReadFile(stRoot / "blobs" / strPageDigest, MAX_PAGE_BYTES, arrPage) || arrPage.size() != nPageBytes || Serialization::Sha256Hex(arrPage.data(), arrPage.size()) != strPageDigest || !Decode(arrPage, stScene))
	{
		return Fail(out_arrDiagnostics, "gpu_page", "$", "GPU page digest, bounds, layout or references are invalid.");
	}
	out_stScene = std::move(stScene);
	return true;
}

bool CookGpuPackage(const std::string &strSourcePackage, const std::string &strTargetPackage, Assets::Diagnostics &out_arrDiagnostics)
{
	GpuCookConfig stConfig;
	stConfig.bPrepareGpuData = false;
	return CookGpuPackage(strSourcePackage, strTargetPackage, stConfig, out_arrDiagnostics);
}

bool CookGpuPackage(const std::string &strSourcePackage, const std::string &strTargetPackage, const GpuCookConfig &stConfig, Assets::Diagnostics &out_arrDiagnostics)
{
	out_arrDiagnostics.clear();
	std::error_code stError;
	const fs::path stSource = fs::absolute(strSourcePackage, stError).lexically_normal();
	if (stError)
	{
		return Fail(out_arrDiagnostics, "gpu_cook_path", "$", "Unable to resolve source package.");
	}
	const fs::path stTarget = fs::absolute(strTargetPackage, stError).lexically_normal();
	if (stError || strTargetPackage.empty() || IsInside(stTarget, stSource) || !Assets::NoLinkedComponents(stTarget.parent_path()))
	{
		return Fail(out_arrDiagnostics, "gpu_cook_path", "$", "Target must have an existing safe parent outside the source package.");
	}
	RenderScene stScene;
	if (!LoadRenderScene(stSource.string(), stScene, out_arrDiagnostics))
	{
		return false;
	}
	const std::uint32_t nVersion = stConfig.bPrepareGpuData ? PREPARED_FORMAT_VERSION : LEGACY_FORMAT_VERSION;
	if (stConfig.bPrepareGpuData && !PrepareScene(stScene, out_arrDiagnostics))
	{
		return false;
	}
	std::vector<std::uint8_t> arrPage;
	std::string strManifest;
	if (!Encode(stScene, arrPage, nVersion) || !Serialization::CanonicalJson(Manifest(stScene, arrPage, nVersion), strManifest))
	{
		return Fail(out_arrDiagnostics, "gpu_cook_budget", "$", "GPU package exceeds its serialization budget.");
	}
	if (fs::exists(stTarget, stError))
	{
		RenderScene stExisting;
		std::vector<std::uint8_t> arrExistingManifest;
		return (LoadGpuPackage(stTarget.string(), stScene.strPackageDigest, stExisting, out_arrDiagnostics) && ReadFile(stTarget / "GpuManifest.json", MAX_MANIFEST_BYTES, arrExistingManifest) && std::string(arrExistingManifest.begin(), arrExistingManifest.end()) == strManifest) ||
				Fail(out_arrDiagnostics, "gpu_cook_conflict", "$", "Existing target differs from this deterministic cook.");
	}
	if (stError)
	{
		return Fail(out_arrDiagnostics, "gpu_cook_path", "$", "Unable to inspect output path.");
	}
	static std::atomic<std::uint64_t> nSequence{ 0 };
	fs::path stStaging;
	for (std::uint32_t nAttempt = 0; nAttempt < 32; ++nAttempt)
	{
		const std::uint64_t nStamp = static_cast<std::uint64_t>(std::chrono::steady_clock::now().time_since_epoch().count());
		stStaging = stTarget.parent_path() / (".engpu-stage-" + std::to_string(nStamp) + "-" + std::to_string(nSequence.fetch_add(1)));
		if (fs::create_directory(stStaging, stError))
		{
			break;
		}
		stStaging.clear();
		stError.clear();
	}
	if (stStaging.empty())
	{
		return Fail(out_arrDiagnostics, "gpu_cook_staging", "$", "Unable to create exclusive staging directory.");
	}
	bool bSucceeded = fs::create_directory(stStaging / "blobs", stError) && !stError;
	const std::string strPageDigest = Serialization::Sha256Hex(arrPage.data(), arrPage.size());
	bSucceeded = bSucceeded && WriteFile(stStaging / "blobs" / strPageDigest, arrPage.data(), arrPage.size()) &&
			WriteFile(stStaging / "GpuManifest.json", reinterpret_cast<const std::uint8_t *>(strManifest.data()), strManifest.size());
	RenderScene stVerified;
	bSucceeded = bSucceeded && LoadGpuPackage(stStaging.string(), stScene.strPackageDigest, stVerified, out_arrDiagnostics);
	if (bSucceeded && RenameNoReplace(stStaging, stTarget))
	{
		return true;
	}
	fs::remove_all(stStaging, stError);
	if (bSucceeded)
	{
		RenderScene stExisting;
		std::vector<std::uint8_t> arrExistingManifest;
		if (LoadGpuPackage(stTarget.string(), stScene.strPackageDigest, stExisting, out_arrDiagnostics) && ReadFile(stTarget / "GpuManifest.json", MAX_MANIFEST_BYTES, arrExistingManifest) && std::string(arrExistingManifest.begin(), arrExistingManifest.end()) == strManifest)
		{
			return true;
		}
	}
	return Fail(out_arrDiagnostics, "gpu_cook_publish", "$", "GPU cook publication failed; existing output was preserved.");
}

} // namespace EngineNext::Rendering
